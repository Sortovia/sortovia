"""When a device gives the library drive a new letter, point Kodi's library at the new one.

Xbox drive letters depend on what else is plugged in: adding or removing a USB stick can turn
E: into D:. The files are fine, but Kodi's library, sources and Sortovia's saved folders still
name the old letter. Nothing here moves or deletes a video.
"""
import re

# Plain addresses (win-lib://removable/E:\TV) and the encoded form inside artwork addresses.
_ADDRESS = re.compile(r"(win-lib(?:://|%3a%2f%2f)removable(?:/|%2f))([A-Za-z])(:|%3a)", re.I)
_FILE = re.compile(r"^(.*[\\/])([^\\/]+)$")
LIBRARY_COLUMNS = (("episode", "c18"), ("movie", "c22"), ("musicvideo", "c13"))
CANDIDATES = "DEFGHIJK"
SAMPLE = 12
ENOUGH = 0.8  # a few files can be missing, for example after a bad download


class DriveLetterError(Exception):
    """A plain sentence for the screen. Nothing was changed."""


def swap_text(text, old, new):
    """text with every drive address on old changed to new. Other drives are left alone."""
    def change(m):
        return m.group(1) + new + m.group(3) if m.group(2).upper() == old else m.group(0)
    return _ADDRESS.sub(change, text)


def letter_of(path):
    m = _ADDRESS.search(path or "")
    return m.group(2).upper() if m else ""


def _sqlite():
    try:
        import sqlite3
    except ImportError:
        raise DriveLetterError("This copy of Kodi can't edit its library database directly.")
    return sqlite3


def library_files(db_path):
    """The address of every library video that's on a removable drive."""
    sqlite3 = _sqlite()
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        out = []
        for table, column in LIBRARY_COLUMNS:
            out += [r[0] for r in conn.execute('SELECT "%s" FROM "%s"' % (column, table)) if letter_of(r[0])]
        return out
    finally:
        conn.close()


def _sample(paths):
    step = max(1, len(paths) // SAMPLE)
    return paths[::step][:SAMPLE]


def share_found(paths, letter, listdir):
    """How many of paths (0 to 1) are really there when read on letter. Folders are listed rather
    than files measured, because the Xbox reports a missing file as an empty one."""
    if not paths:
        return 0.0
    found = 0
    listed = {}
    for path in paths:
        m = _FILE.match(swap_text(path, letter_of(path), letter))
        if not m:
            continue
        if m.group(1) not in listed:
            listed[m.group(1)] = set(listdir(m.group(1))[1])
        found += m.group(2) in listed[m.group(1)]
    return float(found) / len(paths)


def diagnose(files, listdir, candidates=CANDIDATES):
    """{"ok": letters that still work, "moved": [(old letter, [letters holding its files])], "lost": letters}"""
    groups = {}
    for path in files:
        groups.setdefault(letter_of(path), []).append(path)
    out = {"ok": [], "moved": [], "lost": []}
    for old in sorted(groups, key=lambda k: -len(groups[k])):
        paths = _sample(groups[old])
        if share_found(paths, old, listdir) >= ENOUGH:
            out["ok"].append(old)
            continue
        hits = []
        for new in candidates:
            root = "win-lib://removable/%s:\\" % new
            if new != old and any(listdir(root)) and share_found(paths, new, listdir) >= ENOUGH:
                hits.append(new)
        if hits:
            out["moved"].append((old, hits))
        else:
            out["lost"].append(old)
    return out


def rewrite_db(db_path, old, new):
    """Change old to new everywhere in Kodi's video database, as one transaction: if anything
    goes wrong the database stays exactly as it was. Returns how many values changed."""
    sqlite3 = _sqlite()
    changed = [0]

    def swap(value):
        if not isinstance(value, str):
            return value
        result = swap_text(value, old, new)
        changed[0] += result != value
        return result

    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    try:
        conn.create_function("sortovia_swap", 1, swap)
        conn.execute("BEGIN IMMEDIATE")
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
        for table in tables:
            for column in [r[1] for r in conn.execute('PRAGMA table_info("%s")' % table).fetchall()]:
                conn.execute('UPDATE "%s" SET "%s" = sortovia_swap("%s") WHERE "%s" LIKE \'%%removable%%\''
                             % (table, column, column, column))
        for table, column in LIBRARY_COLUMNS:
            for r in conn.execute('SELECT "%s" FROM "%s"' % (column, table)).fetchall():
                if letter_of(r[0]) == old:
                    raise DriveLetterError("Some library entries didn't change. Nothing was changed.")
        conn.execute("COMMIT")
    except sqlite3.IntegrityError:
        raise DriveLetterError("Kodi's library already has entries on %s:. Nothing was changed." % new)
    except sqlite3.OperationalError as e:
        raise DriveLetterError("Kodi's library is busy (%s). Nothing was changed. Try again when "
                               "a library scan has finished." % e)
    finally:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.close()
    return changed[0]

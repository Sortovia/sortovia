# Kodi Sorter - sorts downloads into Kodi-friendly folders from inside Kodi.
#   TV:     <dest>/TV/Show Name (Year)/Season 01/Show Name (Year) S01E02.mkv
#   Movies: <dest>/Movies/Movie Name (Year)/Movie Name (Year).mkv
#   Comics: <dest>/Comics/<original name>
# Duplicates: keeps the better copy (higher resolution, else bigger file).
# Can check audio tracks and keep only files with English audio.
# Nothing is overwritten without your OK; replaced copies go to <dest>/_Replaced
# unless you choose to delete them.
import hashlib
import io
import json
import os
import re
import time
import zipfile
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

# File naming rules (shared with the command-line kodi_sort.py and its tests)
from sortlib import VIDEO, MIN_VIDEO_BYTES, plan_name

try:
    ADDON = "Kodi Sorter " + xbmcaddon.Addon().getAddonInfo("version")
except Exception:
    ADDON = "Kodi Sorter"
RES_RE = re.compile(r"(?<![0-9])(2160|1440|1080|720|576|480|360)[pi](?![a-z0-9])", re.I)

ASK, ALWAYS, NEVER = 0, 1, 2


# ---------- path helpers ----------
def log(msg):
    xbmc.log("[%s] %s" % (ADDON, msg), xbmc.LOGINFO)


def sep_of(path):
    # Xbox/Windows local paths use "\", Kodi URLs (smb://, special://) use "/"
    return "\\" if ("\\" in path and "://" not in path) else "/"


def ensure_slash(path):
    return path if path.endswith(("/", "\\")) else path + sep_of(path)


def join(base, *parts):
    return ensure_slash(base) + sep_of(base).join(parts)


def parent_of(path):
    return path[: path.rstrip("/\\").rfind(sep_of(path)) + 1]


def base_of(path):
    return path.rstrip("/\\")[path.rstrip("/\\").rfind(sep_of(path)) + 1:]


def split_name(filename):
    if "." in filename:
        stem, ext = filename.rsplit(".", 1)
        return stem, "." + ext.lower()
    return filename, ""


def size_of(path):
    try:
        return xbmcvfs.Stat(path).st_size()
    except Exception:
        return -1


def walk(folder):
    folder = ensure_slash(folder)
    dirs, files = xbmcvfs.listdir(folder)
    for f in files:
        yield folder + f, f
    for d in dirs:
        if d.lower() in ("_replaced", "_no english"):
            continue
        for item in walk(folder + d):
            yield item


# ---------- audio language detection (reads file headers, no playback) ----------
# Only an explicit English mention counts. "Dual audio"/"multi" could be French + Japanese.
ENG_HINT_RE = re.compile(r"(?<![a-z])(eng|english)(?![a-z])", re.I)


def _read_vint(f, keep_marker=False):
    b = f.readBytes(1)
    if not b:
        return None, 0
    first = b[0]
    length, mask = 1, 0x80
    while length <= 8 and not (first & mask):
        length += 1
        mask >>= 1
    if length > 8:
        return None, 0
    value = first if keep_marker else first & (mask - 1)
    rest = f.readBytes(length - 1) if length > 1 else b""
    if len(rest) != length - 1:
        return None, 0
    unknown = (not keep_marker) and value == (mask - 1) and all(x == 0xFF for x in rest)
    for x in rest:
        value = (value << 8) | x
    return (-1 if unknown else value), length


def _mkv_langs(f, file_size):
    """Return list of audio track languages from a Matroska/WebM file."""
    langs = []

    def walk_children(start, end, depth):
        pos = start
        while pos < end:
            f.seek(pos, 0)
            eid, l1 = _read_vint(f, keep_marker=True)
            size, l2 = _read_vint(f)
            if eid is None or size is None:
                return False
            data = pos + l1 + l2
            stop = end if size < 0 else min(end, data + size)
            if eid == 0x18538067:            # Segment
                return walk_children(data, stop, depth + 1)
            if eid == 0x1654AE6B:            # Tracks
                walk_children(data, stop, depth + 1)
                return True
            if eid == 0xAE:                  # TrackEntry
                ttype, lang, ietf, name = None, None, None, ""
                q = data
                while q < stop:
                    f.seek(q, 0)
                    cid, c1 = _read_vint(f, keep_marker=True)
                    csz, c2 = _read_vint(f)
                    if cid is None or csz is None or csz < 0:
                        break
                    if csz <= 256:
                        raw = bytes(f.readBytes(csz))
                        if cid == 0x83:
                            ttype = int.from_bytes(raw, "big") if raw else None
                        elif cid == 0x22B59C:
                            lang = raw.split(b"\0")[0].decode("ascii", "ignore").lower()
                        elif cid == 0x22B59D:
                            ietf = raw.split(b"\0")[0].decode("ascii", "ignore").lower()
                        elif cid == 0x536E:
                            name = raw.decode("utf-8", "ignore").lower()
                    q += c1 + c2 + csz
                if ttype == 2:
                    if ietf:
                        langs.append(ietf.split("-")[0])
                    elif lang:
                        langs.append(lang)
                    elif "english" in name:
                        langs.append("eng")
                    else:
                        langs.append("eng")  # Matroska default language is English
            elif eid == 0x1F43B675:          # Cluster: tracks should have come before this
                return False
            if size < 0:
                return False
            pos = data + size
        return False

    walk_children(0, file_size, 0)
    return langs


def _mp4_langs(f, file_size):
    """Return list of audio track languages from an MP4/M4V/MOV file."""
    langs = []

    def boxes(start, end):
        pos = start
        while pos + 8 <= end:
            f.seek(pos, 0)
            hdr = bytes(f.readBytes(8))
            if len(hdr) < 8:
                return
            size = int.from_bytes(hdr[:4], "big")
            btype = hdr[4:8]
            head = 8
            if size == 1:
                size = int.from_bytes(bytes(f.readBytes(8)), "big")
                head = 16
            elif size == 0:
                size = end - pos
            if size < head:
                return
            yield btype, pos + head, pos + size
            pos += size

    def read_at(off, n):
        f.seek(off, 0)
        return bytes(f.readBytes(n))

    for btype, s, e in boxes(0, file_size):
        if btype != b"moov":
            continue
        for t, ts, te in boxes(s, e):
            if t != b"trak":
                continue
            for m, ms, me in boxes(ts, te):
                if m != b"mdia":
                    continue
                handler, lang, elng = None, None, None
                for c, cs, ce in boxes(ms, me):
                    if c == b"hdlr":
                        handler = read_at(cs + 8, 4)
                    elif c == b"mdhd":
                        ver = read_at(cs, 1)
                        off = cs + (32 if ver and ver[0] == 1 else 20)
                        raw = read_at(off, 2)
                        if len(raw) == 2:
                            v = int.from_bytes(raw, "big")
                            lang = "".join(chr(((v >> sh) & 0x1F) + 0x60) for sh in (10, 5, 0))
                    elif c == b"elng":
                        elng = read_at(cs + 4, ce - cs - 4).split(b"\0")[0].decode("ascii", "ignore").lower()
                if handler == b"soun":
                    langs.append((elng.split("-")[0] if elng else lang) or "und")
        break
    return langs


def audio_languages(path):
    """List of audio languages, or None if the file type can't be read."""
    ext = split_name(path)[1]
    try:
        f = xbmcvfs.File(path)
        try:
            size = f.size()
            if ext in (".mkv", ".webm"):
                return _mkv_langs(f, size)
            if ext in (".mp4", ".m4v", ".mov"):
                return _mp4_langs(f, size)
        finally:
            f.close()
    except Exception as e:
        log("audio check failed for %s: %s" % (path, e))
    return None


def english_status(path, name):
    """True = has English audio, False = audio found but none English, None = unknown."""
    langs = audio_languages(path)
    if langs:
        if any(l in ("eng", "en") for l in langs):
            return True, langs
        if all(l not in ("und", "") for l in langs):
            return False, langs
    if ENG_HINT_RE.search(name):
        return True, langs or ["filename says English"]
    return None, langs or []


def lang_note(eng, langs):
    if eng is True:
        return "English audio"
    if eng is False:
        return "no English audio: " + ", ".join(langs)
    return "audio language unknown"


# ---------- quality ----------
def resolution(name):
    m = RES_RE.search(name)
    if m:
        return int(m.group(1))
    if re.search(r"(?<![a-z0-9])(4k|uhd)(?![a-z0-9])", name, re.I):
        return 2160
    return 0  # unknown (e.g. a file already renamed for Kodi)


def describe(res, size):
    r = ("%dp" % res) if res else "res unknown"
    gb = size / 1024.0 ** 3 if size and size > 0 else 0
    return "%s, %.2f GB" % (r, gb)


ENG_RANK = {True: 2, None: 1, False: 0}


def is_better(new_res, new_size, old_res, old_size, new_eng=None, old_eng=None):
    """English audio wins first, then higher resolution (when both known), then bigger file."""
    if ENG_RANK[new_eng] != ENG_RANK[old_eng]:
        return ENG_RANK[new_eng] > ENG_RANK[old_eng]
    if new_res and old_res and new_res != old_res:
        return new_res > old_res
    return new_size > old_size


# ---------- naming ----------
def plan_for(path, filename, dest):
    """Returns (target or None, kind or skip reason, note)."""
    if split_name(filename)[1] in VIDEO and 0 <= size_of(path) < MIN_VIDEO_BYTES:
        return None, "sample/too small", ""
    parts, kind, note = plan_name(filename)
    if parts is None:
        return None, kind, ""
    return join(dest, *parts), kind.upper(), note


def dup_key(target):
    """Same episode/movie regardless of .mkv/.mp4; subs and comics keep their extension."""
    stem, ext = split_name(target)
    return (stem if ext in VIDEO else target).lower()


def find_existing(target):
    """Existing file at destination for the same episode/movie (any video extension)."""
    if xbmcvfs.exists(target):
        return target
    stem, ext = split_name(base_of(target))
    if ext not in VIDEO:
        return None
    folder = parent_of(target)
    if not xbmcvfs.exists(folder):
        return None
    _, files = xbmcvfs.listdir(folder)
    for f in files:
        fs, fe = split_name(f)
        if fe in VIDEO and fs.lower() == stem.lower():
            return folder + f
    return None


# ---------- file operations ----------
def move_file(src, dst):
    """Rename if possible (same drive, instant); else copy, check size, delete."""
    if xbmcvfs.exists(dst):
        return False, "destination already exists - nothing overwritten"
    xbmcvfs.mkdirs(parent_of(dst))
    if xbmcvfs.rename(src, dst) and xbmcvfs.exists(dst):
        return True, "moved"
    src_size = size_of(src)
    if not xbmcvfs.copy(src, dst):
        return False, "copy failed - original kept"
    dst_size = size_of(dst)
    if src_size < 0 or src_size != dst_size:
        xbmcvfs.delete(dst)
        return False, "size mismatch (%s vs %s) - copy removed, original kept" % (src_size, dst_size)
    xbmcvfs.delete(src)
    return True, "copied + size verified"


def replaced_path(old, dest):
    rel = old[len(ensure_slash(dest)):] if old.startswith(ensure_slash(dest)) else base_of(old)
    out = join(dest, "_Replaced", *re.split(r"[\\/]", rel))
    n = 2
    while xbmcvfs.exists(out):
        stem, ext = split_name(out)
        out = "%s (%d)%s" % (stem, n, ext)
        n += 1
    return out


def replace_file(src, dst, old, dest, delete_old):
    """Move the old copy aside (or delete it), then move the new one in. Restores on failure."""
    if delete_old:
        parked = None
    else:
        parked = replaced_path(old, dest)
        ok, how = move_file(old, parked)
        if not ok:
            return False, "couldn't move old copy aside (%s) - nothing changed" % how
    if delete_old:
        # Copy new file in under a temp name first so the old one is only deleted after success.
        tmp = dst + ".kodisorter.tmp"
        ok, how = move_file(src, tmp)
        if not ok:
            return False, "new copy failed (%s) - old copy kept" % how
        xbmcvfs.delete(old)
        if xbmcvfs.rename(tmp, dst):
            return True, "replaced (old deleted)"
        return False, "new file left as %s - rename it by hand" % base_of(tmp)
    ok, how = move_file(src, dst)
    if ok:
        return True, "replaced (old copy in _Replaced)"
    move_file(parked, old)  # put the old one back
    return False, "new copy failed (%s) - old copy restored" % how


# ---------- scan cache ----------
# Reading audio tracks is the slow part of a scan (it opens every video).
# Results are saved as the scan goes, so a scan that was stopped or crashed
# picks up where it left off, and files already checked are not re-read.
CACHE_SAVE_EVERY = 20


def cache_file():
    try:
        folder = xbmcvfs.translatePath("special://profile/addon_data/script.kodisorter/")
        xbmcvfs.mkdirs(folder)
        return folder + "scan_cache.json"
    except Exception as e:
        log("no cache folder: %s" % e)
        return None


def load_cache(path):
    if not path or not xbmcvfs.exists(path):
        return {}
    try:
        f = xbmcvfs.File(path)
        try:
            return json.loads(f.read() or "{}")
        finally:
            f.close()
    except Exception as e:
        log("cache unreadable, starting fresh: %s" % e)
        return {}


def save_cache(path, cache):
    if not path:
        return
    try:
        f = xbmcvfs.File(path, "w")
        try:
            f.write(json.dumps(cache))
        finally:
            f.close()
    except Exception as e:
        log("could not save cache: %s" % e)


def cache_key(path, size):
    return "%s|%d" % (path, size)


# ---------- self-update ----------
# The "repository" add-on can't connect on this Xbox, but Kodi can read the
# same web page fine, so the add-on checks it directly on every run.
UPDATE_BASE = "https://akaguyver.github.io/kodi-repo/"
ADDON_ID = "script.kodisorter"


def _vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def _fetch(url):
    f = xbmcvfs.File(url)
    try:
        return bytes(f.readBytes())
    finally:
        f.close()


def latest_version():
    """Newest version on the web page, or None if it can't be checked."""
    xml = _fetch(UPDATE_BASE + "addons.xml").decode("utf-8", "ignore")
    m = re.search(r'<addon[^>]*id="%s"[^>]*version="([^"]+)"' % re.escape(ADDON_ID), xml)
    return m.group(1) if m else None


def install_update(version, folder):
    """Download, verify and unpack the new version over this add-on's folder."""
    url = "%s%s/%s-%s.zip" % (UPDATE_BASE, ADDON_ID, ADDON_ID, version)
    data = _fetch(url)
    want = _fetch(url + ".md5").decode("ascii", "ignore").strip().split(" ")[0]
    if not data or hashlib.md5(data).hexdigest() != want:
        raise ValueError("download damaged (checksum mismatch)")
    prefix = ADDON_ID + "/"
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        members = [n for n in z.namelist() if n.startswith(prefix) and not n.endswith("/")]
        if not any(n == prefix + "addon.xml" for n in members):
            raise ValueError("download is not a Kodi Sorter add-on")
        for n in members:
            rel = n[len(prefix):]
            if rel.startswith(("/", "\\")) or ".." in rel.replace("\\", "/").split("/"):
                raise ValueError("bad path in download: %s" % n)
        for n in members:
            out = os.path.join(folder, *n[len(prefix):].split("/"))
            if not os.path.isdir(os.path.dirname(out)):
                os.makedirs(os.path.dirname(out))
            with open(out + ".new", "wb") as fh:
                fh.write(z.read(n))
            os.replace(out + ".new", out)
    xbmc.executebuiltin("UpdateLocalAddons")


def check_for_update(dlg):
    """Returns True if an update was installed (caller should stop)."""
    try:
        me = xbmcaddon.Addon()
        current = me.getAddonInfo("version")
        folder = xbmcvfs.translatePath(me.getAddonInfo("path"))
        newest = latest_version()
    except Exception as e:
        log("update check skipped: %s" % e)
        return False
    if not newest or _vtuple(newest) <= _vtuple(current):
        return False
    if not dlg.yesno(ADDON, "Kodi Sorter %s is available (you have %s).\nUpdate now?" % (newest, current),
                     nolabel="Not now", yeslabel="Update"):
        return False
    try:
        install_update(newest, folder)
    except Exception as e:
        log("update failed: %s" % e)
        dlg.ok(ADDON, "Update failed: %s\nNothing was changed. Carrying on with %s." % (e, current))
        return False
    dlg.ok(ADDON, "Updated to %s.\nOpen Kodi Sorter again to use the new version." % newest)
    return True


# ---------- main ----------
def main():
    dlg = xbmcgui.Dialog()
    if check_for_update(dlg):
        return
    src = dlg.browse(0, "Kodi Sorter: pick SOURCE folder (downloads)", "files")
    if not src:
        return
    dest = dlg.browse(0, "Pick DESTINATION drive/folder (holds TV, Movies, Comics)", "files")
    if not dest:
        return

    mode = dlg.select("If a better copy of something you already have is found:",
                      ["Ask me each time",
                       "Always keep the better copy (higher res, else bigger file)",
                       "Never replace existing files"])
    if mode < 0:
        return
    delete_old = False
    if mode != NEVER:
        delete_old = dlg.select("What to do with the copy being replaced?",
                                ["Move it to a _Replaced folder (safe - delete later)",
                                 "Delete it"]) == 1

    lang_mode = dlg.select("Video files with NO English audio track:",
                           ["Leave them on the source drive (skip)",
                            "Move them to a _No English folder",
                            "Delete them",
                            "Don't check audio languages"])
    if lang_mode < 0:
        return
    check_lang = lang_mode != 3

    busy = xbmcgui.DialogProgress()
    busy.create(ADDON, "Listing files...")
    files = list(walk(src))
    cpath = cache_file()
    cache = load_cache(cpath) if check_lang else {}
    seen, fresh, reused = set(), 0, 0
    groups, skipped, no_eng = {}, [], []
    for i, (path, name) in enumerate(files):
        if busy.iscanceled():
            save_cache(cpath, cache)
            busy.close()
            xbmcgui.Dialog().ok(ADDON, "Scan stopped after %d of %d files.\nNothing was moved. "
                                "Files already checked are remembered, so the next scan "
                                "goes straight past them." % (i, len(files)))
            return
        busy.update(int(i * 100 / max(len(files), 1)),
                    "Scanning %d of %d (%d remembered from last time)\n%s" % (i + 1, len(files), reused, name))
        target, kind, note = plan_for(path, name, dest)
        if target is None:
            skipped.append("SKIP  %s  (%s)" % (name, kind))
            continue
        item = {"src": path, "name": name, "target": target, "kind": kind, "note": note,
                "res": resolution(name), "size": size_of(path), "eng": None, "langs": []}
        if check_lang and kind in ("TV", "MOVIE") and split_name(name)[1] in VIDEO:
            key = cache_key(path, item["size"])
            seen.add(key)
            if key in cache:
                item["eng"], item["langs"] = cache[key]
                reused += 1
            else:
                item["eng"], item["langs"] = english_status(path, name)
                cache[key] = [item["eng"], item["langs"]]
                fresh += 1
                if fresh % CACHE_SAVE_EVERY == 0:
                    save_cache(cpath, cache)
            if item["eng"] is False:
                if lang_mode == 0:
                    skipped.append("NO ENGLISH  %s  (%s)" % (name, lang_note(False, item["langs"])))
                else:
                    no_eng.append(item)
                continue
        groups.setdefault(dup_key(target), []).append(item)

    if check_lang:
        # Scan finished: forget files that are gone from this source folder.
        cache = dict((k, v) for k, v in cache.items() if k in seen or not k.startswith(src))
        save_cache(cpath, cache)

    plan, replaces = [], 0
    for key, items in groups.items():
        # Within this run: keep the best copy, skip the rest.
        best = items[0]
        for it in items[1:]:
            if is_better(it["res"], it["size"], best["res"], best["size"], it["eng"], best["eng"]):
                best = it
        for it in items:
            if it is not best:
                skipped.append("DUPLICATE  %s  (%s) - keeping %s (%s)" % (
                    it["name"], describe(it["res"], it["size"]),
                    best["name"], describe(best["res"], best["size"])))
        # Against what's already at the destination.
        old = find_existing(best["target"])
        if old:
            best["old"] = old
            best["old_res"] = resolution(base_of(old))
            best["old_size"] = size_of(old)
            best["old_eng"] = english_status(old, base_of(old))[0] if check_lang else None
            better = best["kind"] in ("TV", "MOVIE") and is_better(
                best["res"], best["size"], best["old_res"], best["old_size"],
                best["eng"], best["old_eng"])
            if not better or mode == NEVER:
                skipped.append("EXISTS  %s  (%s) - keeping existing %s (%s)" % (
                    best["name"], describe(best["res"], best["size"]),
                    base_of(old), describe(best["old_res"], best["old_size"])))
                continue
            replaces += 1
        plan.append(best)
    busy.close()

    lines = ["%d file(s) to move (%d would replace a lower-quality copy), %d with no English audio, %d skipped.\n"
             % (len(plan), replaces, len(no_eng), len(skipped))]
    for it in plan:
        tag = "REPLACE" if it.get("old") else it["kind"]
        lines.append("[%s] %s\n    -> %s" % (tag, it["src"].replace(src, ""), it["target"].replace(dest, "")))
        if it.get("old"):
            lines.append("    new: %s   vs   existing: %s" % (
                describe(it["res"], it["size"]), describe(it["old_res"], it["old_size"])))
        if it["note"]:
            lines.append("    (%s)" % it["note"])
        if check_lang and it["kind"] in ("TV", "MOVIE") and it["eng"] is not True:
            lines.append("    (%s - kept to be safe)" % lang_note(it["eng"], it["langs"]))
    if no_eng:
        verb = "MOVE to _No English" if lang_mode == 1 else "DELETE"
        lines.append("\n--- No English audio: will %s ---" % verb)
        for it in no_eng:
            lines.append("%s  (%s)" % (it["name"], lang_note(False, it["langs"])))
    if skipped:
        lines.append("\n--- Skipped (left where they are) ---")
        lines.extend(sorted(skipped))
    preview = "\n".join(lines)
    title = "%s - scan finished (%d files checked)" % (ADDON, len(files))
    if not plan and not no_eng:
        while dlg.select(title + " - nothing to move",
                         ["View the full list", "Done"]) == 0:
            dlg.textviewer("%s - preview (nothing moved)" % ADDON, preview)
        return
    action = "Move %d file(s) now" % len(plan)
    if no_eng:
        action += " + %s %d with no English audio" % (
            "move" if lang_mode == 1 else "DELETE", len(no_eng))
    while True:
        choice = dlg.select(title, [action,
                                    "View the full list first (%d to move, %d skipped)" % (len(plan), len(skipped)),
                                    "Cancel - move nothing"])
        if choice == 1:
            dlg.textviewer("%s - preview (nothing moved yet)" % ADDON, preview)
            continue
        if choice != 0:
            return
        break

    prog = xbmcgui.DialogProgress()
    prog.create(ADDON, "Moving files...")
    report, ok_count = [], 0
    for i, it in enumerate(plan):
        if prog.iscanceled():
            report.append("CANCELLED - remaining files untouched. Run again to continue.")
            break
        short = it["target"].replace(dest, "")
        prog.update(int(i * 100 / len(plan)), "%d of %d\n%s" % (i + 1, len(plan), short))
        if it.get("old"):
            if mode == ASK and not dlg.yesno(
                    ADDON, "Replace existing copy?\n%s\nNew: %s\nExisting: %s" % (
                        short, describe(it["res"], it["size"]), describe(it["old_res"], it["old_size"])),
                    nolabel="Keep existing", yeslabel="Replace"):
                report.append("KEPT  %s  (you chose to keep the existing copy)" % short)
                continue
            ok, how = replace_file(it["src"], it["target"], it["old"], dest, delete_old)
        else:
            ok, how = move_file(it["src"], it["target"])
        ok_count += ok
        report.append("%s  %s -> %s  (%s)" % ("OK " if ok else "ERR", it["src"].replace(src, ""), short, how))
        log(report[-1])
    for it in no_eng:
        if prog.iscanceled():
            break
        if lang_mode == 1:
            rel = it["target"][len(ensure_slash(dest)):]
            nt = join(dest, "_No English", *re.split(r"[\\/]", rel))
            ok, how = move_file(it["src"], nt)
            how = "moved to _No English" if ok else how
        else:
            ok = xbmcvfs.delete(it["src"])
            how = "deleted" if ok else "delete failed"
        ok_count += bool(ok)
        report.append("%s  %s  (%s; %s)" % ("OK " if ok else "ERR", it["name"], lang_note(False, it["langs"]), how))
        log(report[-1])
    prog.close()

    stamp = time.strftime("%Y-%m-%d %H:%M")
    text = "Kodi Sorter run %s\n%d of %d actions done OK\n\n%s\n" % (stamp, ok_count, len(plan) + len(no_eng), "\n".join(report))
    try:
        f = xbmcvfs.File(join(dest, "kodi_sorter_log.txt"), "w")
        f.write(text)
        f.close()
    except Exception as e:
        log("could not write log: %s" % e)
    if dlg.yesno(ADDON, "Finished: %d of %d done OK.\nA log was saved as kodi_sorter_log.txt "
                 "on the destination drive." % (ok_count, len(plan) + len(no_eng)),
                 nolabel="Close", yeslabel="View report"):
        dlg.textviewer("%s - done" % ADDON, text)
    if ok_count:
        xbmc.executebuiltin("UpdateLibrary(video)")


main()

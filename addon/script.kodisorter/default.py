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
try:
    from urllib.parse import quote
except ImportError:  # very old Kodi
    from urllib import quote
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

# File naming rules (shared with the command-line kodi_sort.py and its tests)
from sortlib import VIDEO, MIN_VIDEO_BYTES, SPECIAL_GUESS_NOTE, plan_name

try:
    ADDON = "Kodi Sorter " + xbmcaddon.Addon().getAddonInfo("version")
except Exception:
    ADDON = "Kodi Sorter"
RES_RE = re.compile(r"(?<![0-9])(2160|1440|1080|720|576|480|360)[pi](?![a-z0-9])", re.I)

ASK, ALWAYS, NEVER = 0, 1, 2

# Background moves: Kodi's home window holds two flags so that opening Kodi Sorter
# again while a move is running offers to stop it instead of starting a second run.
PROP_RUN = "kodisorter.running"   # status text, e.g. "12 of 41" - empty when idle
PROP_STOP = "kodisorter.stop"     # STOP_NOW or STOP_AFTER
STOP_NOW, STOP_AFTER = "1", "after"


def home():
    return xbmcgui.Window(10000)


class Progress(object):
    """Full-screen progress with a Cancel button, or a small bar in the corner
    (background) that leaves Kodi free to use. Background runs are stopped by
    opening Kodi Sorter again. Both stop if Kodi is closing."""

    def __init__(self, background, heading, text):
        self.background = background
        self.monitor = xbmc.Monitor()
        self.dlg = xbmcgui.DialogProgressBG() if background else xbmcgui.DialogProgress()
        self.dlg.create(heading, text)

    def update(self, pct, text):
        if self.background:
            self.dlg.update(pct, message=text.replace("\n", " - "))
        else:
            self.dlg.update(pct, text)

    def canceled(self, mid_file=False):
        """mid_file=True is asked during a copy: only "stop now" interrupts it;
        "stop after this file" is seen between files."""
        if self.monitor.abortRequested():
            return True
        if self.background:
            flag = home().getProperty(PROP_STOP)
            return flag == STOP_NOW or (flag == STOP_AFTER and not mid_file)
        return self.dlg.iscanceled()

    def close(self):
        self.dlg.close()


# ---------- path helpers ----------
def log(msg):
    xbmc.log("[%s] %s" % (ADDON, msg), xbmc.LOGINFO)


def log_block(title, text):
    """Write a whole report into kodi.log between clear markers, so it can be
    shared with Kodi Logfile Uploader instead of photographing the screen."""
    log("===== %s - START =====" % title)
    for line in text.splitlines():
        if line.strip():
            log("  " + line)
    log("===== %s - END =====" % title)


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


def in_archive(path):
    return path.split("://", 1)[0].lower() in ("archive", "rar", "zip") if "://" in path else False


def size_of(path):
    """File size in bytes, or -1 if unknown. Kodi's Stat() reports 0 (or the
    packed size) for files inside archives, so those are opened and asked."""
    if in_archive(path):
        try:
            f = xbmcvfs.File(path)
            try:
                n = f.size()
            finally:
                f.close()
            if n > 0:
                return n
        except Exception as e:
            log("size of %s: %s" % (path, e))
        return -1
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
        if d.lower() in ("_replaced", "_no english", "_unpacked", LOG_DIR.lower()):
            continue
        for item in walk(folder + d):
            yield item


# ---------- archives (.rar / .zip / .7z) ----------
# Kodi opens archives through its own file system: zip:// is built in, rar and
# 7z need the "Archive support" add-on (vfs.libarchive). Videos inside are
# copied out; the archive is then parked in an _Unpacked folder next to it.
ARCHIVES = (".rar", ".zip", ".7z")
LATER_VOLUME_RE = re.compile(r"\.part0*(?:[2-9]|\d{2,})\.rar$", re.I)
ARCHIVE_HELP = ("Some archives could not be opened. In Kodi go to Add-ons > Install from "
                "repository > Kodi Add-on repository > VFS add-ons > Archive support, "
                "install it, then run Kodi Sorter again.")


def _walk_archive(base):
    dirs, files = xbmcvfs.listdir(base)
    for f in files:
        yield base + f, f
    for d in dirs:
        for item in _walk_archive(base + d + "/"):
            yield item


def open_archive(path):
    """List of (url, name) for files inside the archive, or None if Kodi can't open it."""
    enc = quote(path, safe="")
    bases = ["archive://%s/" % enc]
    low = path.lower()
    if low.endswith(".rar"):
        bases.append("rar://%s/" % enc)
    if low.endswith(".zip"):
        bases.append("zip://%s/" % enc)
    for base in bases:
        try:
            items = list(_walk_archive(base))
        except Exception as e:
            log("can't open %s as %s: %s" % (path, base.split(":")[0], e))
            continue
        if items:
            return items
    return None


def archive_volumes(path):
    """The archive plus its other volumes (name.part2.rar, name.r00 ...)."""
    folder, name = parent_of(path), base_of(path)
    if not name.lower().endswith(".rar"):
        return [path]
    stem = re.sub(r"(?:\.part\d+)?\.rar$", "", name, flags=re.I)
    vol = re.compile(re.escape(stem) + r"(?:\.part\d+\.rar|\.rar|\.r\d{2})$", re.I)
    _, files = xbmcvfs.listdir(folder)
    return [folder + f for f in files if vol.match(f)] or [path]


def park_archive(path):
    """Move a fully unpacked archive (all volumes) into _Unpacked beside it.
    Rename only: on the Xbox that fails, and copying gigabytes of archive
    just to tidy up isn't worth it, so the archive is then left where it is."""
    results = []
    for vol in archive_volumes(path):
        target = join(parent_of(vol), "_Unpacked", base_of(vol))
        xbmcvfs.mkdirs(parent_of(target))
        results.append(bool(xbmcvfs.rename(vol, target)))
    return all(results)


# ---------- specials with no number ----------
def renumber_special(target, name, state):
    """Give an unnumbered OVA the next free S00Exx in its show's Season 00.
    The same OVA always gets the same number, so a second copy is treated as a
    duplicate instead of being added again: matched by its file name (numbers
    given out are remembered in specials.json) or by its title, e.g. an
    existing "Show S00E02 - The Long Road Home.mkv"."""
    folder = parent_of(target)
    key = folder.lower() + "|" + name.lower()
    base = base_of(target)
    title = re.search(r"S00E\d+( - .+)\.[^.]+$", base, re.I)
    if folder not in state["used"]:
        used, titles = set(), {}
        if xbmcvfs.exists(folder):
            for f in xbmcvfs.listdir(folder)[1]:
                m = re.search(r"S00E(\d+)( - .+)?\.[^.]+$", f, re.I)
                if m:
                    used.add(int(m.group(1)))
                    if m.group(2):
                        titles[m.group(2).lower()] = int(m.group(1))
        state["used"][folder], state["titles"][folder] = used, titles
    if key not in state["by_name"]:
        n = state["titles"][folder].get(title.group(1).lower()) if title else None
        if n is None:
            n = 1
            while n in state["used"][folder]:
                n += 1
        state["used"][folder].add(n)
        if title:
            state["titles"][folder][title.group(1).lower()] = n
        state["by_name"][key] = n
    n = state["by_name"][key]
    return folder + re.sub(r"S00E\d+", "S00E%02d" % n, base, count=1, flags=re.I)


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


def show_of(target, dest):
    """'<dest>/TV/Show Name/Season 01/x.mkv' -> 'Show Name'."""
    parts = re.split(r"[\\/]", target[len(ensure_slash(dest)):])
    return parts[1] if len(parts) > 2 else parts[-1]


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
# Set by the move loop: called as hook(bytes_done, bytes_total) while a file
# copies; returns True to stop the copy (the half-copied file is removed).
COPY_HOOK = [None]
COPY_CHUNK = 4 * 1024 * 1024
PART = ".kodisorter.part"


class CopyStopped(Exception):
    pass


# Set by the move loop: shows the step after copying (closing, renaming,
# checking, deleting) on screen. Every step is also logged with its time, so
# if one hangs, Kodi's log shows which.
STEP_HOOK = [None]


def step(name, text):
    log("  step: %s - %s" % (text, name))
    if STEP_HOOK[0]:
        STEP_HOOK[0](text)


def copy_with_progress(src, dst, total):
    """Copy in chunks so progress can be shown and a copy can be stopped part
    way. Writes straight to dst: the Xbox's drives can't rename files, so a
    temp-name-then-rename copy doesn't work there. A half copy is deleted on
    failure, and on Resume by remove_partial_copy (size check)."""
    hook = COPY_HOOK[0]
    part = dst + PART
    if xbmcvfs.exists(part):  # left by 1.11.x
        log("removing a half copy left by an earlier run: %s" % base_of(part))
        xbmcvfs.delete(part)
    fin = xbmcvfs.File(src)
    fout = xbmcvfs.File(dst, "w")
    done, ok = 0, False
    try:
        # Stop at the known size instead of reading until the end: on the Xbox
        # the final empty read past the end may never return.
        while total <= 0 or done < total:
            data = fin.readBytes(COPY_CHUNK if total <= 0 else min(COPY_CHUNK, total - done))
            if not data:
                break
            if not fout.write(data):
                raise IOError("write failed (drive full?)")
            done += len(data)
            if hook and hook(done, total):
                raise CopyStopped()
        if total > 0 and done != total:
            raise IOError("read %d of %d bytes" % (done, total))
        ok = True
    finally:
        name = base_of(dst)
        step(name, "copied - closing source file")
        fin.close()
        step(name, "closing new file (saving it to the drive)")
        fout.close()
        if not ok:
            xbmcvfs.delete(dst)
    return True


def move_file(src, dst):
    """Rename if possible (same drive, instant); else copy, check size, delete."""
    if xbmcvfs.exists(dst):
        return False, "destination already exists - nothing overwritten"
    xbmcvfs.mkdirs(parent_of(dst))
    if xbmcvfs.rename(src, dst) and xbmcvfs.exists(dst):
        return True, "moved"
    src_size = size_of(src)
    try:
        copy_with_progress(src, dst, src_size)
    except CopyStopped:
        return False, "stopped part way - half copy removed, original kept"
    except Exception as e:
        log("chunked copy of %s failed (%s), trying Kodi's copy" % (base_of(dst), e))
        step(base_of(dst), "trying again with Kodi's own copy (no progress shown)")
        if xbmcvfs.exists(dst):
            xbmcvfs.delete(dst)
        if not xbmcvfs.copy(src, dst):
            return False, "copy failed (%s) - original kept" % e
    step(base_of(dst), "checking the size of the copy")
    dst_size = size_of(dst)
    if in_archive(src):
        # The archive itself is kept (parked in _Unpacked), so nothing is lost
        # if this check is weaker than for normal files.
        if dst_size <= 0 or (src_size > 0 and src_size != dst_size):
            xbmcvfs.delete(dst)
            return False, "unpack failed (%s vs %s bytes) - archive kept" % (src_size, dst_size)
        return True, "unpacked" if src_size > 0 else "unpacked (size could not be checked)"
    if src_size < 0 or src_size != dst_size:
        xbmcvfs.delete(dst)
        return False, "size mismatch (%s vs %s) - copy removed, original kept" % (src_size, dst_size)
    step(base_of(dst), "deleting the original")
    if not xbmcvfs.delete(src):
        return True, "copied + size verified, but the original could not be deleted"
    step(base_of(dst), "done")
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
    # No renames here: the Xbox's drives can't rename, so every "move" is a
    # copy + delete. The new file stays at the source until its copy is checked.
    if delete_old:
        if old.replace("\\", "/").lower() == dst.replace("\\", "/").lower():
            step(base_of(dst), "deleting the old lower-quality copy")
            xbmcvfs.delete(old)  # same name: must go first (new one is still safe at the source)
            ok, how = move_file(src, dst)
            return (True, "replaced (old deleted)") if ok else (False, "new copy failed (%s) - "
                                                                "old copy was deleted, new one is still at the source" % how)
        ok, how = move_file(src, dst)
        if not ok:
            return False, "new copy failed (%s) - old copy kept" % how
        xbmcvfs.delete(old)
        return True, "replaced (old deleted)"
    parked = replaced_path(old, dest)
    step(base_of(dst), "moving the old copy to _Replaced first")
    ok, how = move_file(old, parked)
    if not ok:
        return False, "couldn't move old copy aside (%s) - nothing changed" % how
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


def data_file(name):
    try:
        folder = xbmcvfs.translatePath("special://profile/addon_data/script.kodisorter/")
        xbmcvfs.mkdirs(folder)
        return folder + name
    except Exception as e:
        log("no addon_data folder: %s" % e)
        return None


def cache_file():
    return data_file("scan_cache.json")


# ---------- resume an unfinished run ----------
# session.json exists only while a run is in progress. If Kodi is closed or
# crashes (or the run is stopped), it is still there next time and the add-on
# offers to resume with the same folders and choices.
def session_file():
    return data_file("session.json")


def clear_session(path):
    if path and xbmcvfs.exists(path):
        xbmcvfs.delete(path)


def remove_partial_copy(prev):
    """A file that was mid-copy when the run died is incomplete: delete it."""
    cur = prev.get("in_progress") or {}
    src, dst = cur.get("src"), cur.get("dst")
    if not dst:
        return
    for tmp in (dst + ".kodisorter.tmp", dst + PART):
        if xbmcvfs.exists(tmp):
            xbmcvfs.delete(tmp)
            log("removed half-copied %s" % tmp)
    src_size = size_of(src) if src else -1
    if src_size >= 0 and xbmcvfs.exists(dst) and size_of(dst) != src_size:
        xbmcvfs.delete(dst)
        log("removed half-copied %s" % dst)


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
    """Write JSON; returns True if it could be read back."""
    if not path:
        return False
    try:
        f = xbmcvfs.File(path, "w")
        try:
            f.write(json.dumps(cache))
        finally:
            f.close()
        return load_cache(path) == json.loads(json.dumps(cache))
    except Exception as e:
        log("could not save %s: %s" % (path, e))
        return False


def cache_key(path, size):
    return "%s|%d" % (stable_path(path), size)


# ---------- phone over Wi-Fi ----------
# The phone runs a file server (xbox-share = WebDAV for phone storage, or the
# primitive ftpd app = FTP for a USB drive on the phone). The Xbox is on the
# phone's hotspot, so the phone is the Xbox's gateway. Android can change the
# hotspot address each time it's switched on, so saved paths hold the word
# PHONE and it's swapped for the current address when a run starts.
PHONE = "PHONE"
PHONE_KINDS = {
    "dav": {"label": "phone storage (xbox-share on the phone)", "port": "8080", "user": "kodi"},
    "ftp": {"label": "USB drive on the phone (primitive ftpd app)", "port": "12345", "user": "user"},
}


def stable_path(path):
    """Path with the phone's address and password taken out (for cache keys)."""
    return re.sub(r"^(dav|davs|ftp)://[^/]*", r"\1://phone", path or "")


def masked(path):
    """Path safe to show or log: password hidden."""
    return re.sub(r"^([a-z]+://[^:/@]+):[^@/]*@", r"\1:***@", path or "")


def phone_address(dlg, ask=True):
    """The phone's address on the hotspot: Kodi's gateway, else the last one typed."""
    saved = load_cache(data_file("phone.json"))
    gw = (xbmc.getInfoLabel("Network.GatewayAddress") or "").strip()
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", gw) and not gw.startswith("0."):
        return gw
    if not ask:
        return saved.get("ip", "")
    ip = dlg.input("Phone's address (xbox-share shows it, e.g. 192.168.43.1)", saved.get("ip", ""))
    if ip:
        saved["ip"] = ip.strip()
        save_cache(data_file("phone.json"), saved)
    return ip.strip()


def resolve_src(src, dlg):
    """Swap PHONE for the phone's current address."""
    if "@%s:" % PHONE not in src:
        return src
    ip = phone_address(dlg)
    return src.replace("@%s:" % PHONE, "@%s:" % ip) if ip else src


def phone_source(dlg, kind):
    """Build (and test) the saved-path form of a phone share, or None."""
    info = PHONE_KINDS[kind]
    saved = load_cache(data_file("phone.json"))
    creds = saved.get(kind, {})
    if not creds.get("pass"):
        pw = dlg.input("Password for %s (shown on the phone)" % info["label"])
        if not pw:
            return None
        user = info["user"]
        if kind == "ftp":
            user = dlg.input("User name set in primitive ftpd", info["user"]) or info["user"]
        creds = {"user": user, "pass": pw, "port": creds.get("port", info["port"])}
        saved[kind] = creds
        save_cache(data_file("phone.json"), saved)
    base = "%s://%s:%s@%s:%s/" % (kind, quote(creds["user"], ""), quote(creds["pass"], ""),
                                  PHONE, creds["port"])
    real = resolve_src(base, dlg)
    if PHONE in real.split("@", 1)[-1].split("/")[0] or not phone_reachable(real):
        msg = ("Can't reach the phone (%s).\n" % masked(real) +
               ("Start xbox-share in Termux on the phone" if kind == "dav" else
                "Start primitive ftpd on the phone") +
               " and make sure the Xbox is on the phone's hotspot.")
        if dlg.yesno(ADDON, msg + "\nWrong password? Forget it and ask again next time.",
                     nolabel="OK", yeslabel="Forget password"):
            saved.pop(kind, None)
            save_cache(data_file("phone.json"), saved)
        return None
    # Optional: pick a folder inside the share (Back = the whole share).
    try:
        sub = dlg.browse(0, "Pick the downloads folder on the phone (Back = whole share)",
                         "files", "", False, False, real)
    except Exception:
        sub = ""
    if sub and sub.startswith(real) and sub != real:
        return base + sub[len(real):]
    return base


# ---------- send logs to the phone ----------
# When xbox-share runs on the phone, Kodi's logs are copied to
# Download/KodiSorterLogs on the phone over the hotspot (no mobile data), so
# Claude can read them there. Quiet and quick: skipped if the phone isn't sharing.
LOG_DIR = "KodiSorterLogs"
LOG_MAX = 3 * 1024 * 1024  # last 3 MB of each log is plenty


def _read_tail(path, limit):
    try:
        f = xbmcvfs.File(path)
        try:
            size = f.size()
            if size > limit:
                f.seek(size - limit, 0)
            return bytes(f.readBytes())
        finally:
            f.close()
    except Exception as e:
        log("can't read %s: %s" % (path, e))
        return b""


def _dav_ok(ip, port, user, pw):
    """True if the phone's share accepts this password."""
    import base64
    try:
        from urllib.request import Request, urlopen
    except ImportError:
        from urllib2 import Request, urlopen
    auth = base64.b64encode(("%s:%s" % (user, pw)).encode()).decode()
    req = Request("http://%s:%d/" % (ip, port), headers={"Authorization": "Basic " + auth, "Depth": "0"})
    req.get_method = lambda: "PROPFIND"
    try:
        urlopen(req, timeout=10).close()
        return True
    except Exception as e:
        return getattr(e, "code", None) in (207, 405)


def send_logs(why, dlg=None):
    """PUT kodi.log (and kodi.old.log on start-up) to the phone. Returns a short status.
    With dlg: if the phone is sharing but no password is saved yet, ask for it."""
    import socket
    saved = load_cache(data_file("phone.json"))
    creds = saved.get("dav") or {}
    ip = phone_address(None, ask=False)
    if not ip:
        return "phone address unknown"
    port = int(creds.get("port", 8080))
    try:
        socket.create_connection((ip, port), 2).close()
    except Exception:
        return "phone not sharing"
    if not creds.get("pass"):
        if dlg is None:
            return "phone share not set up"
        while True:
            pw = dlg.input("xbox-share is running on your phone - type the Password it shows (once)")
            if not pw:
                return "no password typed"
            if _dav_ok(ip, port, "kodi", pw.strip()):
                break
            if not dlg.yesno(ADDON, "That password didn't work. Try again?", nolabel="Skip", yeslabel="Try again"):
                return "wrong password"
        creds = {"user": "kodi", "pass": pw.strip(), "port": str(port)}
        saved["dav"] = creds
        save_cache(data_file("phone.json"), saved)
        toast("Password saved - logs now go to your phone automatically")
    import base64
    try:
        from urllib.request import Request, urlopen
    except ImportError:
        from urllib2 import Request, urlopen
    auth = base64.b64encode(("%s:%s" % (creds["user"], creds["pass"])).encode()).decode()
    base = "http://%s:%d/%s/" % (ip, port, LOG_DIR)

    def call(method, url, data=None):
        req = Request(url, data=data, headers={"Authorization": "Basic " + auth})
        req.get_method = lambda: method
        try:
            urlopen(req, timeout=20).close()
            return True
        except Exception as e:
            code = getattr(e, "code", None)
            return code == 405 and method == "MKCOL"  # 405 = folder already there

    call("MKCOL", base)
    logdir = "special://logpath/"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    names = [("kodi.log", "kodi-%s-%s.log" % (stamp, why))]
    if why == "start":
        names.append(("kodi.old.log", "kodi-%s-previous-session.log" % stamp))
    sent = 0
    for src, dst in names:
        data = _read_tail(logdir + src, LOG_MAX)
        if data and call("PUT", base + dst, data):
            sent += 1
    log("logs sent to phone: %d file(s) (%s)" % (sent, why))
    return "sent %d log(s) to the phone" % sent


def phone_reachable(url):
    try:
        dirs, files = xbmcvfs.listdir(url)
        return bool(dirs or files) or xbmcvfs.exists(url)
    except Exception:
        return False


# ---------- self-update ----------
# The "repository" add-on can't connect on this Xbox, but Kodi can read the
# same web page fine, so the add-on checks it directly on every run.
UPDATE_BASE = "https://akaguyver.github.io/kodi-repo/"
ADDON_ID = "script.kodisorter"


def _vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def _fetch_kodi(url):
    f = xbmcvfs.File(url)
    try:
        chunks = []
        while True:
            b = f.readBytes(65536)
            if not b:
                break
            chunks.append(bytes(b))
        return b"".join(chunks)
    finally:
        f.close()


def _fetch_python(url, headers=None):
    try:
        from urllib.request import urlopen, Request
    except ImportError:
        from urllib2 import urlopen, Request
    h = {"User-Agent": "KodiSorter", "Cache-Control": "no-cache"}
    h.update(headers or {})
    req = Request(url, headers=h)
    resp = urlopen(req, timeout=20)
    try:
        return resp.read()
    finally:
        resp.close()


FETCH_LOG = []


def _fetch(url):
    """Download a URL: Kodi's own downloader first (read in chunks - GitHub
    sends compressed replies with no length), then Python's as a fallback.
    The ?t= part stops any cache from handing back an old copy. What each
    method did is kept in FETCH_LOG so a failure can be shown on screen."""
    url += ("&" if "?" in url else "?") + "t=%d" % int(time.time())
    for name, method in (("Kodi", _fetch_kodi), ("Python", _fetch_python)):
        try:
            data = method(url)
        except Exception as e:
            FETCH_LOG.append("%s downloader: %s" % (name, e))
            continue
        if data:
            FETCH_LOG.append("%s downloader: OK, %d bytes" % (name, len(data)))
            return data
        FETCH_LOG.append("%s downloader: got nothing back" % name)
    raise IOError("could not download %s" % url.split("?")[0].rsplit("/", 1)[-1])


# GitHub's API serves the file straight from the repo. The Pages site sits
# behind a cache that can hand out the old addons.xml for ~10 minutes after
# a release, which looked like "no update" on the Xbox.
UPDATE_API = "https://api.github.com/repos/akaguyver/kodi-repo/contents/addons.xml"


def _fetch_api():
    hdr = {"Accept": "application/vnd.github.raw"}
    try:
        data = _fetch_kodi(UPDATE_API + "|" + "&".join("%s=%s" % (k, quote(v)) for k, v in
                                                        dict(hdr, **{"User-Agent": "KodiSorter"}).items()))
        if data and b"<addons" in data:
            FETCH_LOG.append("GitHub API (Kodi): OK")
            return data
    except Exception as e:
        FETCH_LOG.append("GitHub API (Kodi): %s" % e)
    try:
        data = _fetch_python(UPDATE_API, hdr)
        if data and b"<addons" in data:
            FETCH_LOG.append("GitHub API (Python): OK")
            return data
    except Exception as e:
        FETCH_LOG.append("GitHub API (Python): %s" % e)
    return None


def latest_version():
    """Newest version on GitHub. Raises if it can't be read."""
    data = _fetch_api() or _fetch(UPDATE_BASE + "addons.xml")
    xml = data.decode("utf-8", "ignore")
    if not xml.strip():
        raise IOError("empty reply from GitHub")
    m = re.search(r'<addon[^>]*id="%s"[^>]*version="([^"]+)"' % re.escape(ADDON_ID), xml)
    if not m:
        raise IOError("Kodi Sorter not listed on the update page")
    return m.group(1)


UPDATE_WAIT = 12  # seconds; with mobile data off the check would otherwise hang


def latest_version_within(seconds):
    """latest_version() with a time limit (no internet can mean long timeouts)."""
    import threading
    box = {}

    def work():
        try:
            box["v"] = latest_version()
        except Exception as e:
            box["e"] = e
    t = threading.Thread(target=work)
    t.daemon = True
    t.start()
    t.join(seconds)
    if "v" in box:
        return box["v"]
    raise box.get("e") or IOError("no reply within %d seconds - no internet?" % seconds)


def toast(msg, ms=4000):
    try:
        xbmcgui.Dialog().notification("Kodi Sorter", msg, xbmcgui.NOTIFICATION_INFO, ms)
    except Exception:
        log(msg)


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


def check_for_update(dlg, manual=False):
    """Returns True if an update was installed (caller should stop).
    Runs on every launch; manual=True is the "Check for updates now" item."""
    del FETCH_LOG[:]
    current = "?"
    try:
        me = xbmcaddon.Addon()
        current = me.getAddonInfo("version")
        folder = xbmcvfs.translatePath(me.getAddonInfo("path"))
        newest = latest_version_within(UPDATE_WAIT if not manual else 60)
    except Exception as e:
        log("update check failed: %s | %s" % (e, " | ".join(FETCH_LOG)))
        if manual:
            dlg.ok(ADDON, "Couldn't check for updates (you have %s).\n%s\n%s\n"
                   "Carrying on without updating." % (current, e, "\n".join(FETCH_LOG[-2:])))
        else:
            # Normal when the phone's mobile data is off: just say so in the corner.
            toast("No internet - skipped the update check (%s)" % current, 3000)
        return False
    log("update check: have %s, newest %s | %s" % (current, newest, " | ".join(FETCH_LOG)))
    if _vtuple(newest) <= _vtuple(current):
        if manual:
            dlg.ok(ADDON, "You have the newest version (%s)." % current)
        else:
            toast("Up to date (%s)" % current, 3000)
        return False
    if not yesno_default_yes(dlg, "Kodi Sorter %s is available (you have %s).\nUpdate now?" % (newest, current),
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


def yesno_default_yes(dlg, msg, nolabel, yeslabel):
    """Yes/no with the YES button highlighted (Kodi 20+), plain yes/no on older Kodi."""
    try:
        return dlg.yesno(ADDON, msg, nolabel=nolabel, yeslabel=yeslabel,
                         defaultbutton=xbmcgui.DLG_YESNO_YES_BTN)
    except (TypeError, AttributeError):
        return dlg.yesno(ADDON, msg, nolabel=nolabel, yeslabel=yeslabel)


# ---------- main ----------
def main():
    dlg = xbmcgui.Dialog()
    status = home().getProperty(PROP_RUN)
    if status:
        flag = home().getProperty(PROP_STOP)
        if flag == STOP_NOW:
            dlg.ok(ADDON, "Already stopping (%s) - give it a few seconds." % status)
            return
        opts = ["Keep going",
                "Stop after this file (finish it first)",
                "Stop now (the half-copied file is removed, the original stays)"]
        if flag == STOP_AFTER:
            opts[0] = "Keep going (cancel the stop)"
            opts[1] = "Stop after this file - already chosen"
        pick = dlg.select("Kodi Sorter is moving files (%s)" % status, opts)
        if pick == 0:
            home().clearProperty(PROP_STOP)
        elif pick == 1:
            home().setProperty(PROP_STOP, STOP_AFTER)
            toast("Will stop after this file. Open Kodi Sorter later and choose Resume.")
        elif pick == 2:
            home().setProperty(PROP_STOP, STOP_NOW)
            toast("Stopping now. Open Kodi Sorter later and choose Resume.")
        return
    send_logs("start", dlg)
    if check_for_update(dlg):
        return

    spath = session_file()
    prev = load_cache(spath)
    if prev.get("src") and prev.get("dest"):
        where = "while moving files" if prev.get("stage") == "moving" else "while scanning"
        if yesno_default_yes(dlg, "The last run (%s) didn't finish - it stopped %s.\nFrom: %s\nTo: %s\n"
                             "Resume with the same folders and choices?" % (
                                 prev.get("started", "?"), where, masked(prev["src"]), prev["dest"]),
                             nolabel="Start over", yeslabel="Resume"):
            remove_partial_copy(prev)
            run(dlg, spath, prev["src"], prev["dest"], prev["mode"], prev["delete_old"], prev["lang_mode"])
            return
        clear_session(spath)

    # Last finished run's folders and choices: offer to reuse them.
    last = load_cache(data_file("last_settings.json"))
    if last.get("src") and last.get("dest"):
        pick = dlg.select("Kodi Sorter - same as last time?",
                          ["Same as last time: %s  ->  %s" % (masked(last["src"]), last["dest"]),
                           "Choose folders and choices again",
                           "Check for updates now",
                           "View the report from the last move",
                           "Send Kodi's log to my phone now (xbox-share must be running)"])
        if pick < 0:
            return
        if pick == 2:
            check_for_update(dlg, manual=True)
            return
        if pick == 4:
            dlg.ok(ADDON, "Log: %s." % send_logs("manual", dlg))
            return
        if pick == 3:
            text = read_text(data_file("last_report.txt"))
            dlg.textviewer("%s - last report" % ADDON, text or "No report saved yet.")
            return
        if pick == 0:
            run(dlg, spath, last["src"], last["dest"], last["mode"], last["delete_old"], last["lang_mode"])
            return

    where = dlg.select("Where are the downloads?",
                       ["A folder or drive on the Xbox",
                        "My phone over Wi-Fi - %s" % PHONE_KINDS["dav"]["label"],
                        "My phone over Wi-Fi - %s" % PHONE_KINDS["ftp"]["label"]])
    if where < 0:
        return
    if where == 0:
        src = dlg.browse(0, "Kodi Sorter: pick SOURCE folder (downloads)", "files")
    else:
        src = phone_source(dlg, "dav" if where == 1 else "ftp")
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
    run(dlg, spath, src, dest, mode, delete_old, lang_mode)


MODE_NAMES = ["ask each time", "always keep the better copy", "never replace"]
LANG_NAMES = ["skip no-English files", "move no-English to _No English",
              "delete no-English files", "don't check audio"]


def read_text(path):
    try:
        f = xbmcvfs.File(path)
        try:
            return f.read()
        finally:
            f.close()
    except Exception:
        return ""


def write_text(path, text):
    try:
        f = xbmcvfs.File(path, "w")
        f.write(text)
        f.close()
        return True
    except Exception as e:
        log("could not write %s: %s" % (path, e))
        return False


def gb(n):
    # same units as the scan report (1 GB = 1024 MB)
    return "%.1f GB" % (n / 1024.0 ** 3) if n >= 1024 ** 3 else "%d MB" % (n / 1024.0 ** 2)


def file_progress(prog, i, count, short):
    """Progress hook for one file: bar moves through this file's share of the
    run; text shows e.g. "3 of 41 - 1.2 of 3.7 GB - 24 MB/s - about 2 min left"."""
    start = [time.time()]
    last = [0.0]
    prev = [0]

    def hook(done, total):
        now = time.time()
        if done < prev[0]:  # a second copy for this item (old copy to _Replaced, then the new one)
            start[0] = now
        prev[0] = done
        if now - last[0] >= 1 or (total > 0 and done >= total):
            last[0] = now
            frac = float(done) / total if total > 0 else 0
            speed = done / max(now - start[0], 0.001)
            line = "%d of %d - %s" % (i + 1, count, gb(done))
            if total > 0:
                line += " of %s (%d%%)" % (gb(total), frac * 100)
            line += " - %.0f MB/s" % (speed / 1024.0 ** 2)
            if total > 0 and speed > 0 and done < total:
                left = (total - done) / speed
                line += " - about %s left" % ("%d min" % (left // 60 + 1) if left >= 60 else "%d s" % left)
            prog.update(int((i + min(frac, 1)) * 100 / count), "%s\n%s" % (line, short))
            home().setProperty(PROP_RUN, "%d of %d, %d%% of this file" % (i + 1, count, frac * 100))
        return prog.canceled(mid_file=True)
    return hook


def step_progress(prog, i, count, short):
    def show(text):
        prog.update(int((i + 1) * 100 / count) - 1 if count else 0,
                    "%d of %d - %s (%s)\n%s" % (i + 1, count, text, time.strftime("%H:%M:%S"), short))
        home().setProperty(PROP_RUN, "%d of %d, %s" % (i + 1, count, text))
    return show


def run(dlg, spath, src, dest, mode, delete_old, lang_mode):
    log("RUN START  from=%s  to=%s  duplicates=%s%s  audio=%s" % (
        masked(src), dest, MODE_NAMES[mode], " (delete replaced)" if delete_old else "", LANG_NAMES[lang_mode]))
    try:
        _run(dlg, spath, src, dest, mode, delete_old, lang_mode)
    except Exception:
        import traceback
        log_block("ERROR", traceback.format_exc())
        dlg.ok(ADDON, "Something went wrong - nothing more was moved.\n"
               "Details are in Kodi's log: use the Kodi Logfile Uploader add-on.")
    finally:
        COPY_HOOK[0] = STEP_HOOK[0] = None
        home().clearProperty(PROP_RUN)
        home().clearProperty(PROP_STOP)
    log("RUN END")
    send_logs("end")


def _run(dlg, spath, src, dest, mode, delete_old, lang_mode):
    check_lang = lang_mode != 3
    session = {"src": src, "dest": dest, "mode": mode, "delete_old": delete_old,
               "lang_mode": lang_mode, "stage": "scanning",
               "started": time.strftime("%Y-%m-%d %H:%M")}
    if not save_cache(spath, session):
        toast("Couldn't save progress - Resume won't be offered if this run is interrupted", 6000)
    save_cache(data_file("last_settings.json"), dict((k, session[k]) for k in
                                                     ("src", "dest", "mode", "delete_old", "lang_mode")))
    src = resolve_src(src, dlg)
    if "://" in src and src.split("://")[0] in ("dav", "davs", "ftp") and not phone_reachable(src):
        dlg.ok(ADDON, "Can't reach %s.\nOn the phone: start xbox-share (Termux) or primitive ftpd, "
               "and keep the Xbox on the phone's hotspot. Then open Kodi Sorter and choose Resume."
               % masked(src))
        return

    busy = xbmcgui.DialogProgress()
    busy.create(ADDON, "Listing files...")
    groups, skipped, no_eng = {}, [], []
    files = []
    archive_fail = []
    archive_of = {}
    for path, name in walk(src):
        ext = split_name(name)[1]
        if ext not in ARCHIVES:
            files.append((path, name, None))
            continue
        if LATER_VOLUME_RE.search(name):
            continue  # opened through the first volume
        busy.update(0, "Opening archive\n%s" % name)
        inner = open_archive(path)
        if inner is None:
            archive_fail.append(name)
            skipped.append("ARCHIVE  %s  (can't open - see note at the top)" % name)
            continue
        archive_of[path] = name
        for url, iname in inner:
            files.append((url, iname, path))
    cpath = cache_file()
    cache = load_cache(cpath) if check_lang else {}
    seen, fresh, reused, by_name, other = set(), 0, 0, 0, 0

    def tally():
        # e.g. "39 already checked, 6 new, 29 skipped by name, 2 other"
        t = "%d already checked, %d new, %d skipped by name" % (reused, fresh, by_name)
        return t + (", %d other" % other if other else "")
    spec_path = data_file("specials.json")
    specials = {"by_name": load_cache(spec_path), "used": {}, "titles": {}}
    for i, (path, name, arc) in enumerate(files):
        if busy.iscanceled():
            save_cache(cpath, cache)
            busy.close()
            xbmcgui.Dialog().ok(ADDON, "Scan stopped after %d of %d files.\nNothing was moved. "
                                "Files already checked are remembered. Open Kodi Sorter "
                                "again and choose Resume to carry on." % (i, len(files)))
            return
        busy.update(int(i * 100 / max(len(files), 1)),
                    "Scanning %d of %d\n%s\n%s" % (i + 1, len(files), tally(), name))
        target, kind, note = plan_for(path, name, dest)
        if target is None and arc and "rename by hand" in kind:
            # Inner file named "movie.mkv" etc: try the archive's own name.
            target, kind, note = plan_for(path, split_name(archive_of[arc])[0] + split_name(name)[1], dest)
        label = ("%s  (inside %s)" % (name, archive_of[arc])) if arc else masked(path.replace(src, ""))
        if target is None:
            skipped.append("SKIP  %s  (%s)" % (label if arc else name, kind))
            by_name += 1
            continue
        if note == SPECIAL_GUESS_NOTE:
            target = renumber_special(target, name, specials)
        item = {"src": path, "name": name, "target": target, "kind": kind, "note": note, "arc": arc,
                "label": label, "res": resolution(name), "size": size_of(path), "eng": None, "langs": []}
        needs_audio = check_lang and not arc and kind in ("TV", "MOVIE") and split_name(name)[1] in VIDEO
        if not needs_audio:
            other += 1  # subtitles, comics, files inside archives, or audio check turned off
        if needs_audio:
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

    save_cache(spec_path, specials["by_name"])
    if check_lang:
        # Scan finished: forget files that are gone from this source folder.
        cache = dict((k, v) for k, v in cache.items() if k in seen or not k.startswith(stable_path(src)))
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
    # Notes are grouped by show and listed once at the top, not under every episode.
    notes, unknown_audio = {}, {}
    for it in plan:
        show = show_of(it["target"], dest)
        if it["note"]:
            notes.setdefault(it["note"], set()).add(show)
        if check_lang and it["kind"] in ("TV", "MOVIE") and it["eng"] is not True:
            unknown_audio[show] = unknown_audio.get(show, 0) + 1
    unpacking = sorted(set(archive_of[it["arc"]] for it in plan if it["arc"]))
    if notes or unknown_audio or archive_fail or unpacking:
        lines.append("Notes:")
        if unpacking:
            lines.append("  will unpack videos from %d archive(s), each archive is then moved to an "
                         "_Unpacked folder if the drive allows it, else left where it is: %s" % (len(unpacking), ", ".join(unpacking)))
        if archive_fail:
            lines.append("  " + ARCHIVE_HELP)
        for note, shows in sorted(notes.items()):
            lines.append("  %s: %s" % (note, ", ".join(sorted(shows))))
        if unknown_audio:
            lines.append("  audio language unknown, moved anyway to be safe: %s" % ", ".join(
                "%s (%d)" % (k, v) for k, v in sorted(unknown_audio.items())))
        lines.append("")
    for it in plan:
        tag = "REPLACE" if it.get("old") else it["kind"]
        lines.append("[%s] %s\n    -> %s" % (tag, it["label"], it["target"].replace(dest, "")))
        if it.get("old"):
            lines.append("    new: %s   vs   existing: %s" % (
                describe(it["res"], it["size"]), describe(it["old_res"], it["old_size"])))
    if no_eng:
        verb = "MOVE to _No English" if lang_mode == 1 else "DELETE"
        lines.append("\n--- No English audio: will %s ---" % verb)
        for it in no_eng:
            lines.append("%s  (%s)" % (it["name"], lang_note(False, it["langs"])))
    if skipped:
        lines.append("\n--- Skipped (left where they are) ---")
        lines.extend(sorted(skipped))
    preview = "\n".join(lines)
    log_block("SCAN RESULT (%d files: %s)" % (len(files), tally()), preview)
    title = "%s - scan finished: %d files (%s)" % (ADDON, len(files), tally())
    if not plan and not no_eng:
        clear_session(spath)
        while dlg.select(title + " - nothing to move",
                         ["View the full list", "Done"]) == 0:
            dlg.textviewer("%s - preview (nothing moved)" % ADDON, preview)
        return
    what = "%d file(s)" % len(plan)
    if no_eng:
        what += " + %s %d with no English audio" % (
            "move" if lang_mode == 1 else "DELETE", len(no_eng))
    while True:
        choice = dlg.select(title, ["Move %s in the BACKGROUND - keep using Kodi" % what,
                                    "Move %s now, full screen" % what,
                                    "View the full list first (%d to move, %d skipped)" % (len(plan), len(skipped)),
                                    "Cancel - move nothing"])
        if choice == 2:
            dlg.textviewer("%s - preview (nothing moved yet)" % ADDON, preview)
            continue
        log("menu choice: %s" % {0: "move in background", 1: "move full screen", 2: "view list",
                                 3: "cancel"}.get(choice, "back"))
        if choice == 3:
            clear_session(spath)  # you chose not to move anything: nothing to resume
            return
        if choice not in (0, 1):
            return  # Back button: keep the run so it can be resumed
        break
    background = choice == 0

    def ask_replace(it):
        short = it["target"].replace(dest, "")
        return dlg.yesno(ADDON, "Replace existing copy?\n%s\nNew: %s\nExisting: %s" % (
            short, describe(it["res"], it["size"]), describe(it["old_res"], it["old_size"])),
            nolabel="Keep existing", yeslabel="Replace")

    if background and mode == ASK:
        # Ask every "replace?" question now, so nothing pops up while you watch.
        for it in plan:
            if it.get("old"):
                it["keep_old"] = not ask_replace(it)

    session["stage"] = "moving"
    save_cache(spath, session)

    home().clearProperty(PROP_STOP)
    home().setProperty(PROP_RUN, "starting")
    prog = Progress(background, ADDON, "Moving files...")
    if background:
        toast("Moving %d file(s) in the background. Open Kodi Sorter again to stop." % len(plan), 6000)
    report, ok_count = [], 0
    arc_ok, arc_count = {}, {}
    cancelled = False
    for i, it in enumerate(plan):
        if prog.canceled():
            cancelled = True
            report.append("STOPPED - remaining files untouched. Open Kodi Sorter again and choose Resume.")
            break
        short = it["target"].replace(dest, "")
        home().setProperty(PROP_RUN, "%d of %d" % (i + 1, len(plan)))
        prog.update(int(i * 100 / len(plan)), "%d of %d\n%s" % (i + 1, len(plan), short))
        COPY_HOOK[0] = file_progress(prog, i, len(plan), short)
        STEP_HOOK[0] = step_progress(prog, i, len(plan), short)
        session["in_progress"] = {"src": it["src"], "dst": it["target"]}
        save_cache(spath, session)
        if it.get("old"):
            if it.get("keep_old") or (mode == ASK and not background and not ask_replace(it)):
                report.append("KEPT  %s  (you chose to keep the existing copy)" % short)
                continue
            ok, how = replace_file(it["src"], it["target"], it["old"], dest, delete_old)
        else:
            ok, how = move_file(it["src"], it["target"])
        ok_count += ok
        if it["arc"]:
            arc_ok[it["arc"]] = arc_ok.get(it["arc"], True) and ok
            arc_count[it["arc"]] = arc_count.get(it["arc"], 0) + 1
        COPY_HOOK[0] = STEP_HOOK[0] = None
        stopped = how.startswith("stopped part way")
        report.append("%s  %s -> %s  (%s)" % ("OK " if ok else ("STOP" if stopped else "ERR"),
                                              it["label"], short, how))
        log(report[-1])
        if stopped:
            cancelled = True
            report.append("STOPPED - remaining files untouched. Open Kodi Sorter again and choose Resume.")
            break
    for it in no_eng:
        if cancelled or prog.canceled():
            cancelled = True
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
    # Park archives only when every video planned from them was copied out OK.
    planned = {}
    for it in plan:
        if it["arc"]:
            planned[it["arc"]] = planned.get(it["arc"], 0) + 1
    for arc, n in planned.items():
        name = archive_of[arc]
        if arc_ok.get(arc) and arc_count.get(arc, 0) == n:
            parked = park_archive(arc)
            report.append("%s  %s  (%s)" % ("OK " if parked else "NOTE", name,
                          "archive moved to _Unpacked" if parked else "unpacked OK; archive left where it is - delete it when you're happy"))
        elif arc in arc_ok:
            report.append("NOTE  %s  (not every video came out OK - archive left where it is)" % name)
    prog.close()

    stamp = time.strftime("%Y-%m-%d %H:%M")
    text = "Kodi Sorter run %s\n%d of %d actions done OK\n\n%s\n" % (stamp, ok_count, len(plan) + len(no_eng), "\n".join(report))
    log_block("MOVE RESULT", text)
    write_text(join(dest, "kodi_sorter_log.txt"), text)
    write_text(data_file("last_report.txt"), text)
    done = "%s: %d of %d done OK." % ("Stopped" if cancelled else "Finished", ok_count, len(plan) + len(no_eng))
    if background and xbmc.Player().isPlayingVideo():
        # Don't cover what you're watching: a note in the corner instead.
        toast(done + " Report: open Kodi Sorter > View the report from the last move.", 10000)
    elif dlg.yesno(ADDON, done + "\nA log was saved as kodi_sorter_log.txt on the destination drive.",
                   nolabel="Close", yeslabel="View report"):
        dlg.textviewer("%s - done" % ADDON, text)
    if not cancelled:
        clear_session(spath)  # finished: nothing to resume next time
    if ok_count:
        xbmc.executebuiltin("UpdateLibrary(video)")


main()

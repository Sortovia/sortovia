"""Back up Kodi's video library, and notice when it suddenly shrinks.

A backup holds:
  videodb.xml       Kodi's own export (shows, episodes, movies, watched marks,
                    resume points). Kodi can put it back by itself:
                    Settings > Media > Library > Import library.
  MyVideosNNN.db    a copy of Kodi's database file, as a second safety net.
  backup-info.json  when it was made and how much was in the library.

It's saved in Kodi's home folder (reachable from any Kodi file browser as
"Home folder"), next to the library on the destination drive, and on the phone
when xbox-share runs. The newest KEEP backups are kept on the Xbox and the
drive; the phone keeps them all.
"""
import json
import re
import time

import xbmc
import xbmcvfs

HOME_DIR = "special://home/Kodi library backups/"
DRIVE_DIR = "_Kodi library backups"
KEEP = 5
EVERY = 24 * 3600          # automatic backup at most once a day
STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{4}$")
DB_RE = re.compile(r"^MyVideos(\d+)\.db$", re.I)
DB_MAX = 300 * 1024 * 1024  # a bigger database isn't copied (the XML still is)

RESTORE_HELP = (
    "How to put a library backup back\n\n"
    "1. In Kodi: Settings > Media > Library, and in the Videos part choose Import library.\n"
    "2. Choose Home folder > Kodi library backups > the date you want > OK.\n\n"
    "Kodi adds back every show, episode and movie whose video file is still there, with its "
    "information, watched marks and resume points. Artwork comes from Kodi's own cache where it can.\n\n"
    "The same backups are also on your library drive (folder _Kodi library backups) and on the "
    "phone (Download/KodiSorterBackups).\n\n"
    "Tip: a source that covers the whole drive with a content type set (Movies or TV shows) "
    "overrides the TV and Movies folders inside it. Changing it can remove those from the "
    "library. Add only the folders themselves as sources.")


def _rpc(method, params):
    reply = json.loads(xbmc.executeJSONRPC(json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    if "error" in reply:
        raise IOError("Kodi library: %s" % reply["error"].get("message"))
    return reply.get("result") or {}


def counts(rpc=_rpc):
    """{'movies': n, 'shows': n, 'episodes': n} from Kodi's library."""
    out = {}
    for key, method in (("movies", "VideoLibrary.GetMovies"), ("shows", "VideoLibrary.GetTVShows"),
                        ("episodes", "VideoLibrary.GetEpisodes")):
        r = rpc(method, {"limits": {"start": 0, "end": 1}})
        out[key] = int((r.get("limits") or {}).get("total", 0))
    return out


def counts_line(c):
    return "%d shows (%d episodes), %d movies" % (c.get("shows", 0), c.get("episodes", 0), c.get("movies", 0))


def shrunk(now, before):
    """A plain sentence if the library lost at least half its episodes or movies
    since the last backup, else ''."""
    lost = []
    for key, name in (("episodes", "TV episodes"), ("movies", "movies")):
        b, n = before.get(key, 0), now.get(key, 0)
        if b >= 10 and n * 2 <= b:
            lost.append("%s: %d then, %d now" % (name, b, n))
    return "; ".join(lost)


def _read(path):
    f = xbmcvfs.File(path)
    try:
        chunks = []
        while True:
            b = f.readBytes(1024 * 1024)
            if not b:
                break
            chunks.append(bytes(b))
        return b"".join(chunks)
    finally:
        f.close()


def _write(path, data):
    f = xbmcvfs.File(path, "w")
    try:
        ok = f.write(bytearray(data))
    finally:
        f.close()
    return ok is not False and xbmcvfs.exists(path)


def _find(folder, name, depth=3):
    """Path of a file called name in folder or its subfolders."""
    try:
        dirs, files = xbmcvfs.listdir(folder)
    except Exception:
        return None
    if name in files:
        return folder + name
    if depth:
        for d in dirs:
            hit = _find(folder + d + "/", name, depth - 1)
            if hit:
                return hit
    return None


def export_xml(rpc=_rpc, wait=600, sleep=time.sleep, work="special://temp/"):
    """Kodi's single-file library export, as bytes. Kodi also writes every poster
    and fan art into the export folder, so work should be on the big library
    drive, not the Xbox's own small storage."""
    tmp = "%skodisorter-export-%d/" % (work, int(time.time()))
    xbmcvfs.mkdirs(tmp)
    try:
        rpc("VideoLibrary.Export", {"options": {"path": tmp}})
        end = time.time() + wait
        while time.time() < end:  # the export can finish after the call returns
            path = _find(tmp, "videodb.xml")
            if path:
                data = _read(path)
                if data.rstrip().endswith(b"</videodb>"):
                    return data
            sleep(1)
        raise IOError("Kodi's library export didn't finish within %d seconds" % wait)
    finally:
        try:
            xbmcvfs.rmdir(tmp, True)
        except Exception:
            pass


def newest_db():
    """(name, bytes) of Kodi's video database file, or (None, None)."""
    try:
        files = xbmcvfs.listdir("special://database/")[1]
    except Exception:
        return None, None
    dbs = sorted((int(m.group(1)), f) for f in files for m in [DB_RE.match(f)] if m)
    if not dbs:
        return None, None
    name = dbs[-1][1]
    path = "special://database/" + name
    try:
        if xbmcvfs.Stat(path).st_size() > DB_MAX:
            return None, None
        return name, _read(path)
    except Exception:
        return None, None


def _prune(base, keep=KEEP):
    try:
        dirs = sorted(d for d in xbmcvfs.listdir(base)[0] if STAMP_RE.match(d))
    except Exception:
        return
    for d in dirs[:-keep] if keep else dirs:
        try:
            xbmcvfs.rmdir(base + d + "/", True)
        except Exception:
            pass


def drive_dir(dest):
    """'_Kodi library backups' at the root of the destination's drive (or in dest)."""
    if not dest:
        return None
    m = re.match(r"^(.*?(?<![A-Za-z])[A-Za-z]:[\\/]+)", dest)  # the drive letter, not "win-lib:"
    root = m.group(1) if m else (dest if dest.endswith(("/", "\\")) else dest + "/")
    return root + DRIVE_DIR + "/"


def make_backup(places, to_phone=None, rpc=_rpc, log=lambda m: None, work="special://temp/"):
    """Back up to each folder in places (each ending in a slash) and, with
    to_phone(stamp, files), to the phone. Returns (info, [where it was saved]).
    An empty library is never backed up, so a good backup isn't pushed out."""
    c = counts(rpc)
    if not (c["episodes"] or c["movies"]):
        raise IOError("Kodi's library is empty - nothing to back up (the older backups are kept)")
    xml = export_xml(rpc, work=work)
    db_name, db = newest_db()
    stamp = time.strftime("%Y-%m-%d %H%M")
    info = {"made": stamp, "counts": c, "kodi": xbmc.getInfoLabel("System.BuildVersion"),
            "xml_bytes": len(xml), "db": db_name}
    files = [("videodb.xml", xml), ("backup-info.json", json.dumps(info, indent=1).encode())]
    if db is not None:
        files.append((db_name, db))
    saved = []
    for base in places:
        if not base:
            continue
        folder = base + stamp + "/"
        try:
            xbmcvfs.mkdirs(folder)
            if all(_write(folder + n, d) for n, d in files):
                saved.append(base)
                _prune(base)
            else:
                log("backup: couldn't write everything to %s" % folder)
        except Exception as e:
            log("backup: %s failed: %s" % (base, e))
    if to_phone:
        try:
            if to_phone(stamp, files):
                saved.append("phone")
        except Exception as e:
            log("backup: phone failed: %s" % e)
    if not saved:
        raise IOError("the backup couldn't be saved anywhere")
    log("library backup %s: %s -> %s" % (stamp, counts_line(c), ", ".join(saved)))
    return info, saved


def list_backups():
    """[(stamp, info)] in Kodi's home folder, newest first."""
    out = []
    try:
        dirs = xbmcvfs.listdir(HOME_DIR)[0]
    except Exception:
        return out
    for d in sorted((d for d in dirs if STAMP_RE.match(d)), reverse=True):
        try:
            info = json.loads(_read(HOME_DIR + d + "/backup-info.json").decode("utf-8"))
        except Exception:
            info = {}
        out.append((d, info))
    return out

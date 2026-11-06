"""Check which music albums have cover art, and compare with an earlier copy of the library.

Reads Kodi's music database and changes nothing.
"""
import re
import sqlite3

try:
    from urllib.parse import unquote
except ImportError:
    from urllib import unquote

_FILE = re.compile(r"^(.*[\\/])([^\\/]+)$")
IMAGE_RE = re.compile(r"(?i)\.(?:jpe?g|png|webp|gif|bmp)$")
ALBUMS = """SELECT album.idAlbum, album.strAlbum, MIN(path.strPath), MIN(path.strPath || song.strFileName)
            FROM album JOIN song ON song.idAlbum = album.idAlbum JOIN path ON path.idPath = song.idPath
            GROUP BY album.idAlbum"""
ART = "SELECT media_id, url FROM art WHERE media_type = 'album' AND type = 'thumb'"


def status(db_path):
    """How much is in a music database, with a few of its folders, to see what state it's in."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        out = {}
        for table in ("song", "album", "artist", "path", "source"):
            try:
                out[table] = conn.execute('SELECT COUNT(*) FROM "%s"' % table).fetchone()[0]
            except sqlite3.Error:
                out[table] = -1
        try:  # a song pointing at a folder record that's gone is in the database, but Kodi can't show it
            out["linked"] = conn.execute("SELECT COUNT(*) FROM song JOIN path ON path.idPath = song.idPath").fetchone()[0]
        except sqlite3.Error:
            out["linked"] = -1
        out["folders"] = [r[0] for r in conn.execute("SELECT strPath FROM path ORDER BY idPath LIMIT 4").fetchall()]
        try:
            out["sources"] = [r[0] for r in conn.execute("SELECT strPath FROM source_path LIMIT 4").fetchall()]
        except sqlite3.Error:
            out["sources"] = []
        return out
    finally:
        conn.close()


def _folder_key(path):
    """One folder written two ways, "...\\\\Album\\" and "...\\\\Album/", gives the same key."""
    return re.sub(r"[\\/]+", "/", path or "").rstrip("/").lower()


def song_folders(db_path):
    """{folder key: the address Kodi has for it}, for folders holding songs. A rescan has to use this
    address: given the same folder written another way, Kodi adds its songs again as new ones."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        return dict((_folder_key(r[0]), r[0]) for r in conn.execute(
            "SELECT DISTINCT path.strPath FROM song JOIN path ON path.idPath = song.idPath ORDER BY path.idPath").fetchall())
    finally:
        conn.close()


def remove_duplicates(db_path):
    """Remove songs listed more than once for the same file, keeping the newest, which has the newest
    tags, and adding up play counts. One transaction, so it can't half finish. Returns how many went."""
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute("""SELECT song.idSong, path.strPath, song.strFileName, song.iTimesPlayed FROM song
                               JOIN path ON path.idPath = song.idPath ORDER BY song.idSong""").fetchall()
        newest, played, gone = {}, {}, []
        for song, folder, name, times in rows:
            key = (_folder_key(folder), (name or "").lower())
            if key in newest:
                gone.append(newest[key])
            newest[key] = song
            played[key] = played.get(key, 0) + (times or 0)
        for song in gone:
            conn.execute("DELETE FROM song WHERE idSong = ?", (song,))
        for key, song in newest.items():
            conn.execute("UPDATE song SET iTimesPlayed = ? WHERE idSong = ?", (played[key], song))
        conn.execute("COMMIT")
        return len(gone)
    finally:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.close()


def library_songs(db_path):
    """[{"file", "folder", "artist", "album"}] for every song Kodi lists, without touching the drive."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        return [{"file": r[0], "folder": r[1], "artist": r[2] or "", "album": r[3] or ""} for r in conn.execute(
            """SELECT song.strFileName, path.strPath, song.strArtistDisp, album.strAlbum FROM song
               JOIN path ON path.idPath = song.idPath JOIN album ON album.idAlbum = song.idAlbum""").fetchall()]
    finally:
        conn.close()


def read_artists(db_path):
    """[(artist id, name)] with whether Kodi already has a picture: {"id", "name", "thumb"}."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        art = dict(conn.execute("SELECT media_id, url FROM art WHERE media_type = 'artist' AND type = 'thumb'").fetchall())
        return [{"id": r[0], "name": r[1], "thumb": art.get(r[0], "")} for r in
                conn.execute("SELECT idArtist, strArtist FROM artist").fetchall() if r[1]]
    finally:
        conn.close()


ARTIST_IMAGE_RE = re.compile(r"(?i)^(artist|folder|cover|thumb|poster)\.(?:jpe?g|png|webp)$")
ARTIST_FANART_RE = re.compile(r"(?i)^(fanart|backdrop|background)\.(?:jpe?g|png|webp)$")


def artist_art_files(names):
    """{"thumb": file, "fanart": file}, from the file names in an artist's folder, for what's there."""
    out = {}
    for name in sorted(names):
        if ARTIST_IMAGE_RE.match(name):
            out.setdefault("thumb", name)
        elif ARTIST_FANART_RE.match(name):
            out.setdefault("fanart", name)
    return out


def status_lines(info):
    lines = ["Kodi's music database: %d songs (%d can be shown), %d albums, %d artists, %d folders, %d sources."
             % (info["song"], info.get("linked", -1), info["album"], info["artist"], info["path"], info["source"])]
    lines += ["  source: %s" % p for p in info["sources"]]
    lines += ["  folder: %s" % p for p in info["folders"]]
    return lines


def read_albums(db_path):
    """[{"id", "name", "folder", "art": address or ""}] for each album Kodi lists."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        art = dict(conn.execute(ART).fetchall())
        return [{"id": album_id, "name": name, "folder": folder, "art": art.get(album_id, "")}
                for album_id, name, folder, _ in conn.execute(ALBUMS).fetchall() if name]
    finally:
        conn.close()


def art_file(url):
    """The file an art address points to: the picture itself, or the song holding it. "" for web art."""
    if url.startswith("image://"):
        m = re.match(r"^image://(?:music@)?(.*?)/?$", url)
        url = unquote(m.group(1)) if m else ""
    return url if url.startswith("win-lib://") else ""


def _file_there(path, listdir):
    m = _FILE.match(path)
    return bool(m) and m.group(2) in listdir(m.group(1))[1]


def compare(now, before, listdir, progress=None):
    """Sort each album into one of: ok, missing_file, lost, cover_unused, none. Also "split": the
    names Kodi lists as several albums in one folder. progress(done, total, name) can return True to stop."""
    out = dict((key, []) for key in ("ok", "missing_file", "lost", "cover_unused", "none", "split"))
    had_art = set(a["name"].lower() for a in before or [] if a["art"])
    albums = sorted(now, key=lambda a: a["name"].lower())
    counts = {}
    for album in albums:
        key = (album["name"].lower(), album["folder"])
        counts[key] = counts.get(key, 0) + 1
    out["split"] = sorted(set("%s (%d albums)" % (a["name"], counts[(a["name"].lower(), a["folder"])]) for a in albums
                              if counts[(a["name"].lower(), a["folder"])] > 1))
    for i, album in enumerate(albums):
        name = album["name"]
        if progress and progress(i, len(albums), name):
            break
        if album["art"]:
            path = art_file(album["art"])
            out["missing_file" if path and not _file_there(path, listdir) else "ok"].append(name)
        elif name.lower() in had_art:
            out["lost"].append(name)
        else:
            images = sorted(f for f in listdir(album["folder"])[1] if IMAGE_RE.search(f))
            if images:
                out["cover_unused"].append("%s (%s)" % (name, images[0]))
            else:
                out["none"].append(name)
    return out


def best_image(names):
    """The picture to use as an album's cover from the images in its folder, or ""."""
    images = sorted(n for n in names if IMAGE_RE.search(n))
    for wanted in (r"^cover\.", r"^folder\.", r"^front\.", r"^album", r"cover|front|artwork"):
        for name in images:
            if re.search(wanted, name, re.I):
                return name
    return images[0] if images else ""


def needs_art(albums, listdir, progress=None):
    """[(album, picture address)] for albums with no art, or art whose file has gone, and a picture to use.
    progress(done, total, name) can return True to stop."""
    out = []
    for i, album in enumerate(albums):
        if progress and progress(i, len(albums), album["name"]):
            return []
        path = art_file(album["art"]) if album["art"] else ""
        if album["art"] and (not path or _file_there(path, listdir)):
            continue
        image = best_image(listdir(album["folder"])[1])
        if image:
            out.append((album, album["folder"] + image))
    return out


def report(found, had_backup, info=None):
    """The report as text for the screen and the phone."""
    total = sum(len(v) for k, v in found.items() if k != "split")
    lines = ["Music art check: %d albums, %d with art." % (total, len(found["ok"])), ""]
    if info:
        lines += status_lines(info) + [""]
    if not had_backup:
        lines += ["No earlier copy of the music library was found, so nothing could be compared.", ""]
    elif not found["lost"]:
        lines += ["No album lost its art compared with your backup from before the switch.", ""]
    sections = (("split", "Shown by Kodi as more than one album (Fix music tags can join them)"),
                ("lost", "Had art in your backup, but not now"),
                ("missing_file", "Art points to a file that isn't there"),
                ("cover_unused", "No art in Kodi, but an image is in the folder"),
                ("none", "No art in Kodi and no image in the folder"))
    for key, title in sections:
        if found[key]:
            lines += ["%s (%d):" % (title, len(found[key]))] + ["  %s" % n for n in found[key]] + [""]
    lines.append("Artwork can also take a while to appear while Kodi rebuilds its picture cache.")
    return "\n".join(lines)

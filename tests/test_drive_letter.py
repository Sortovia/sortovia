"""A drive's letter changed: finding the files, and changing the library in one safe step."""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon", "script.kodisorter"))
from test_library_folders import load_default  # noqa: E402
import drive_letter as dl  # noqa: E402

EP = "win-lib://removable/E:/TV/Made Up Show/Season 01/Made Up Show S01E0%d.mkv"
MOVIE = "win-lib://removable/E:\\\\Movies\\Pretend Film (2020)\\Pretend Film (2020).mkv"
ART = "image://video@win-lib%3a%2f%2fremovable%2fE%3a%5c%5cMovies%5cx.mkv/"


def make_db(path):
    c = sqlite3.connect(path)
    c.executescript("""
      CREATE TABLE path (idPath INTEGER PRIMARY KEY, strPath TEXT, strContent TEXT);
      CREATE UNIQUE INDEX ix_path ON path (strPath);
      CREATE TABLE episode (idEpisode INTEGER PRIMARY KEY, c18 TEXT);
      CREATE TABLE movie (idMovie INTEGER PRIMARY KEY, c22 TEXT);
      CREATE TABLE musicvideo (idMVideo INTEGER PRIMARY KEY, c13 TEXT);
      CREATE TABLE art (art_id INTEGER PRIMARY KEY, url TEXT);
      CREATE TABLE files (idFile INTEGER PRIMARY KEY, playCount INTEGER);""")
    c.execute("INSERT INTO path (strPath, strContent) VALUES (?, 'tvshows')", ("win-lib://removable/E:\\TV\\",))
    c.execute("INSERT INTO path (strPath) VALUES ('win-lib://removable/F:\\Other\\')")
    for i in (1, 2):
        c.execute("INSERT INTO episode (c18) VALUES (?)", (EP % i,))
    c.execute("INSERT INTO movie (c22) VALUES (?)", (MOVIE,))
    c.execute("INSERT INTO art (url) VALUES (?)", (ART,))
    c.execute("INSERT INTO art (url) VALUES ('https://image.example/removable/E:/poster.jpg')")
    c.execute("INSERT INTO files (playCount) VALUES (3)")
    c.commit()
    c.close()


def make_music_db(path, letter="E"):
    c = sqlite3.connect(path)
    c.executescript("""
      CREATE TABLE path (idPath INTEGER PRIMARY KEY, strPath TEXT, strHash TEXT);
      CREATE TABLE song (idSong INTEGER PRIMARY KEY, idPath INTEGER, strFileName TEXT, iTimesPlayed INTEGER);
      CREATE TABLE source_path (idSource INTEGER, idPath INTEGER, strPath TEXT);
      CREATE TABLE art (art_id INTEGER PRIMARY KEY, url TEXT);""")
    folder = "win-lib://removable/%s:\\Music\\Band\\Album\\" % letter
    c.execute("INSERT INTO path (strPath) VALUES (?)", (folder,))
    c.execute("INSERT INTO song (idPath, strFileName, iTimesPlayed) VALUES (1, '01 - Song.mp3', 7)")
    c.execute("INSERT INTO source_path VALUES (1, 1, ?)", ("win-lib://removable/%s:\\Music\\" % letter,))
    c.execute("INSERT INTO art (url) VALUES (?)", (folder + "cover.jpg",))
    c.commit()
    c.close()


def fake_listdir(drives):
    """drives: {"D": ["TV/Made Up Show/Season 01/a.mkv"]}"""
    def listdir(path):
        rest = path.split("removable/", 1)[1]
        letter, rest = rest[0], rest[2:].replace("\\", "/").strip("/")
        rest = rest + "/" if rest else ""
        names = [f[len(rest):] for f in drives.get(letter, []) if f.startswith(rest)]
        return [n.split("/")[0] for n in names if "/" in n], [n for n in names if "/" not in n]
    return listdir


ON_DISK = ["TV/Made Up Show/Season 01/Made Up Show S01E01.mkv", "TV/Made Up Show/Season 01/Made Up Show S01E02.mkv",
           "Movies/Pretend Film (2020)/Pretend Film (2020).mkv"]


class Addresses(unittest.TestCase):
    def test_plain_and_encoded_addresses_change_and_others_dont(self):
        self.assertEqual(dl.swap_text(EP % 1, "E", "D"), (EP % 1).replace("E:/", "D:/"))
        self.assertIn("removable%2fD%3a%5c", dl.swap_text(ART, "E", "D"))
        other = "win-lib://removable/F:\\Other\\"
        self.assertEqual(dl.swap_text(other, "E", "D"), other)
        self.assertEqual(dl.swap_text("C:/E:/notes", "E", "D"), "C:/E:/notes")


class Diagnose(unittest.TestCase):
    files = [EP % 1, EP % 2, MOVIE]

    def test_files_found_on_the_new_letter(self):
        out = dl.diagnose(self.files, fake_listdir({"D": ON_DISK}))
        self.assertEqual(out, {"ok": [], "moved": [("E", ["D"])], "lost": []})

    def test_nothing_to_do_when_the_old_letter_still_works(self):
        out = dl.diagnose(self.files, fake_listdir({"E": ON_DISK, "D": ON_DISK}))
        self.assertEqual(out["ok"], ["E"])
        self.assertEqual(out["moved"], [])

    def test_a_different_drive_on_that_letter_isnt_a_match(self):
        out = dl.diagnose(self.files, fake_listdir({"D": ["KodiThumbnails/a.jpg", "Movies/Something Else/x.mkv"]}))
        self.assertEqual(out["lost"], ["E"])

    def test_a_few_missing_files_dont_block_it(self):
        many = [EP % 1] * 9 + [EP % 2]
        out = dl.diagnose(many, fake_listdir({"D": ON_DISK[:1]}))
        self.assertEqual(out["moved"], [("E", ["D"])])

    def test_missing_folders_count_as_not_found(self):
        self.assertEqual(dl.share_found([EP % 1], "D", lambda p: ([], [])), 0.0)


class Rewrite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "MyVideos131.db")
        make_db(self.db)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rows(self, sql):
        c = sqlite3.connect(self.db)
        try:
            return [r[0] for r in c.execute(sql)]
        finally:
            c.close()

    def test_everything_moves_and_there_and_back_is_identical(self):
        self.assertEqual(dl.rewrite_db(self.db, "E", "D"), 5)
        self.assertEqual(self.rows("SELECT c18 FROM episode")[0], (EP % 1).replace("E:/", "D:/"))
        self.assertIn("D:", self.rows("SELECT c22 FROM movie")[0])
        self.assertEqual(self.rows("SELECT strPath FROM path"),
                         ["win-lib://removable/D:\\TV\\", "win-lib://removable/F:\\Other\\"])
        self.assertEqual(self.rows("SELECT strContent FROM path")[0], "tvshows")
        self.assertEqual(self.rows("SELECT playCount FROM files"), [3])
        self.assertEqual(self.rows("SELECT url FROM art")[1], "https://image.example/removable/E:/poster.jpg")
        dl.rewrite_db(self.db, "D", "E")
        self.assertEqual(self.rows("SELECT c18 FROM episode")[1], EP % 2)

    def test_old_records_already_on_the_new_letter_dont_block_it(self):
        c = sqlite3.connect(self.db)
        c.execute("INSERT INTO path (strPath) VALUES ('win-lib://removable/D:\\TV\\Old Folder\\')")
        c.commit()
        c.close()
        dl.rewrite_db(self.db, "E", "D")
        self.assertEqual(self.rows("SELECT count(*) FROM path WHERE strPath LIKE '%removable/D:%'"), [2])
        self.assertEqual(self.rows("SELECT count(*) FROM episode WHERE c18 LIKE '%removable/D:%'"), [2])

    def test_a_clash_leaves_the_database_untouched(self):
        c = sqlite3.connect(self.db)
        c.execute("INSERT INTO path (strPath) VALUES ('win-lib://removable/D:\\TV\\')")
        c.commit()
        c.close()
        with self.assertRaises(dl.DriveLetterError):
            dl.rewrite_db(self.db, "E", "D")
        self.assertEqual(self.rows("SELECT c18 FROM episode")[0], EP % 1)
        self.assertIn(ART, self.rows("SELECT url FROM art"))

    def test_a_locked_database_is_reported(self):
        other = sqlite3.connect(self.db, isolation_level=None)
        other.execute("BEGIN EXCLUSIVE")
        real = sqlite3.connect
        dl_connect = lambda path, timeout=30, **k: real(path, timeout=0.05, **k)
        sqlite3.connect = dl_connect
        try:
            with self.assertRaises(dl.DriveLetterError):
                dl.rewrite_db(self.db, "E", "D")
        finally:
            sqlite3.connect = real
            other.execute("ROLLBACK")
            other.close()


class ArtistFolders(unittest.TestCase):
    def test_organised_music_stays_and_loose_music_moves(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        d = load_default(os.path.join(tmp, "data"))
        d.FOLDER_NAMES["Music"] = "Music"
        d.read_music_tags = lambda p: {"artist": "Band", "album": "Record", "title": "Song", "track": 1}
        d.xbmcvfs.listdir = lambda p: ([], [])
        d.log = lambda m: None
        dest = "win-lib://removable/D:/"
        keep = dest + "Music/Band/Singles/2014 - Record/01 - Song.mp3"
        self.assertEqual(d.plan_for(keep, "01 - Song.mp3", dest)[0], keep)
        self.assertEqual(d.plan_for(dest + "Music/Band/Record/x.mp3", "x.mp3", dest)[0], dest + "Music/Band/Record/x.mp3")
        for loose in (dest + "Music/x.mp3", dest + "Music/Band/x.mp3", dest + "Download/x.mp3"):
            self.assertTrue(d.plan_for(loose, "x.mp3", dest)[0].endswith("Music/Band/Record/01 - Song.mp3"), loose)


class Tool(unittest.TestCase):
    """The whole tool, with a real database and backups on a pretend drive."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        data = os.path.join(self.tmp, "data")
        os.makedirs(data)
        d = self.d = load_default(data)
        tmp = self.tmp
        self.dbdir = os.path.join(tmp, "database")
        os.makedirs(self.dbdir)
        self.db = os.path.join(self.dbdir, "MyVideos131.db")
        make_db(self.db)
        self.music = os.path.join(self.dbdir, "MyMusic83.db")
        make_music_db(self.music)
        os.makedirs(os.path.join(tmp, "profile"))
        self.sources = os.path.join(tmp, "profile", "sources.xml")
        with open(self.sources, "w") as f:
            f.write("<path>win-lib://removable/E:\\TV\\</path><path>win-lib://removable/F:\\Other\\</path>")
        for f in ON_DISK + ["Music/Band/Album/01 - Song.mp3"]:
            p = os.path.join(tmp, "drive-D", f)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").close()

        def real(p):
            if p.startswith("special://database/"):
                return os.path.join(self.dbdir, p.split("/")[-1])
            if p.startswith("special://profile/"):
                return os.path.join(tmp, "profile", p.split("/")[-1])
            if "removable/" in p:
                rest = p.split("removable/", 1)[1]
                return os.path.join(tmp, "drive-" + rest[0], rest[2:].lstrip("\\/").replace("\\", "/"))
            return p

        class File:
            def __init__(s, p, mode="r"):
                s.f = open(real(p), "wb" if mode == "w" else "rb")
            def read(s): return s.f.read().decode()
            def readBytes(s, n=-1): return s.f.read(n)
            def write(s, b):
                s.f.write(b.encode() if isinstance(b, str) else bytes(b))
                return True
            def close(s): s.f.close()

        class Stat:
            def __init__(s, p): s.p = real(p)
            def st_size(s): return os.path.getsize(s.p)

        def listdir(p):
            r = real(p)
            if not os.path.isdir(r):
                return [], []
            names = os.listdir(r)
            return ([n for n in names if os.path.isdir(os.path.join(r, n))],
                    [n for n in names if os.path.isfile(os.path.join(r, n))])
        vfs = d.xbmcvfs
        vfs.File, vfs.Stat, vfs.listdir = File, Stat, listdir
        vfs.exists = lambda p: os.path.exists(real(p))
        vfs.mkdirs = lambda p: os.makedirs(real(p), exist_ok=True)
        vfs.rmdir = lambda p, force=False: shutil.rmtree(real(p), ignore_errors=True)
        base_translate = vfs.translatePath
        vfs.translatePath = lambda p: real(p) if p.startswith("special://database/") else base_translate(p)
        d.xbmc.getInfoLabel = lambda k: "21.2"
        self.built = []
        d.xbmc.executebuiltin = self.built.append
        self.replace(d.backup, "xbmc", d.xbmc)
        self.replace(d.backup, "xbmcvfs", vfs)
        self.exports = 0

        def export(work=None, **k):
            self.exports += 1
            if self.export_fails:
                raise IOError("no export")
            return ("<videodb><path>%s</path></videodb>" % (EP % 1)).encode()
        self.export_fails = False
        self.replace(d.backup, "export_xml", export)
        self.replace(d.backup, "counts", lambda rpc=None: {"movies": 1, "shows": 1, "episodes": 2})
        d.work_dir = lambda near=None: "special://temp/"

        class Progress:
            def create(s, *a): pass
            def update(s, *a): pass
            def close(s): pass
        d.xbmcgui.DialogProgress = Progress
        d.save_cache(d.data_file("last_settings.json"),
                     {"src": "win-lib://removable/E:\\\\in/", "dest": "win-lib://removable/E:\\\\"}, verify=False)
        d.my_device = lambda: "windows"
        self.rpc_calls = []
        import missing
        self.replace(missing, "_rpc", lambda method, params: self.rpc_calls.append(method) or {})
        self.said = []
        test = self

        class Dlg:
            def ok(s, title, text): test.said.append(text)
            def select(s, title, rows): return 0
            def yesno(s, title, text, **k):
                test.said.append(text)
                return test.answer
        self.dlg = Dlg()
        self.answer = True

    def replace(self, owner, name, value):
        patcher = mock.patch.object(owner, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def backups(self, letter):
        return os.path.join(self.tmp, "drive-D", "_Kodi library backups", "Drive " + letter)

    def episode(self):
        c = sqlite3.connect(self.db)
        try:
            return c.execute("SELECT c18 FROM episode").fetchone()[0]
        finally:
            c.close()

    def test_switches_and_keeps_a_backup_for_each_letter(self):
        self.assertTrue(self.d.fix_drive_letter(self.dlg), self.said)
        self.assertIn("removable/D:/", self.episode())
        self.assertEqual(open(self.sources).read(),
                         "<path>win-lib://removable/D:\\TV\\</path><path>win-lib://removable/F:\\Other\\</path>")
        self.assertEqual(self.d.load_cache(self.d.data_file("last_settings.json"))["dest"], "win-lib://removable/D:\\\\")
        for letter, other in (("E", "D"), ("D", "E")):
            stamp = os.listdir(self.backups(letter))[0]
            folder = os.path.join(self.backups(letter), stamp)
            self.assertIn("removable/%s:/" % letter, open(os.path.join(folder, "videodb.xml")).read())
            self.assertIn("removable/%s:\\TV" % letter, open(os.path.join(folder, "sources.xml")).read())
            self.assertEqual(json.load(open(os.path.join(folder, "backup-info.json")))["drive"], letter)
            c = sqlite3.connect(os.path.join(folder, "MyVideos131.db"))
            self.assertIn("removable/%s:/" % letter, c.execute("SELECT c18 FROM episode").fetchone()[0])
            c.close()
        self.assertEqual(self.built, ["Quit"])
        # Both show up for restoring.
        self.assertEqual(sorted(r[2]["drive"] for r in self.d.letter_backups()), ["D", "E"])

    def query(self, db, sql):
        c = sqlite3.connect(db)
        try:
            return c.execute(sql).fetchone()[0]
        finally:
            c.close()

    def test_music_comes_too_and_keeps_its_play_counts(self):
        self.assertTrue(self.d.fix_drive_letter(self.dlg), self.said)
        self.assertIn("removable/D:\\Music", self.query(self.music, "SELECT strPath FROM path"))
        self.assertIn("removable/D:\\Music", self.query(self.music, "SELECT strPath FROM source_path"))
        self.assertIn("removable/D:\\Music", self.query(self.music, "SELECT url FROM art"))
        self.assertEqual(self.query(self.music, "SELECT iTimesPlayed FROM song"), 7)
        for letter in "ED":
            folder = os.path.join(self.backups(letter), os.listdir(self.backups(letter))[0])
            self.assertIn("removable/%s:" % letter, self.query(os.path.join(folder, "MyMusic83.db"), "SELECT strPath FROM path"))

    def test_only_music_left_behind_after_the_first_version(self):
        """Videos were already switched to D: and music wasn't, so the backups hold only the music."""
        self.d.drive_letter.rewrite_db(self.db, "E", "D")
        with open(self.sources, "w") as f:
            f.write("<path>win-lib://removable/D:\\TV\\</path>")
        self.assertTrue(self.d.fix_drive_letter(self.dlg), self.said)
        self.assertIn("removable/D:", self.query(self.music, "SELECT strPath FROM path"))
        self.assertEqual(self.exports, 0)
        for letter in "ED":
            names = os.listdir(os.path.join(self.backups(letter), os.listdir(self.backups(letter))[0]))
            self.assertIn("MyMusic83.db", names)
            self.assertNotIn("MyVideos131.db", names)
            self.assertNotIn("videodb.xml", names)

    def test_no_music_library_still_works(self):
        os.remove(self.music)
        self.assertTrue(self.d.fix_drive_letter(self.dlg), self.said)
        self.assertIn("removable/D:/", self.episode())

    def test_says_when_an_up_to_date_backup_exists_and_doesnt_make_another(self):
        base = os.path.join(self.tmp, "drive-D", "_Kodi library backups")
        for name, source in (("MyVideos131.db", self.db), ("MyMusic83.db", self.music)):
            folder = os.path.join(base, "Drive E", "2026-11-05 2010")
            os.makedirs(folder, exist_ok=True)
            shutil.copy(source, os.path.join(folder, name))
            with open(os.path.join(folder, "backup-info.json"), "w") as f:
                f.write("{}")
        self.assertTrue(self.d.fix_drive_letter(self.dlg), self.said)
        self.assertIn("up-to-date backup of your video and music library from 2026-11-05 2010", self.said[0])
        self.assertEqual(self.exports, 0)
        self.assertEqual(os.listdir(self.backups("E")), ["2026-11-05 2010"])
        self.assertEqual(len(os.listdir(self.backups("D"))), 1)

    def test_a_different_backup_doesnt_count(self):
        folder = os.path.join(self.backups("E"), "2026-11-05 2010")
        os.makedirs(folder)
        with open(os.path.join(folder, "MyVideos131.db"), "wb") as f:
            f.write(b"an older library")
        with open(os.path.join(folder, "backup-info.json"), "w") as f:
            f.write("{}")
        self.assertTrue(self.d.fix_drive_letter(self.dlg), self.said)
        self.assertIn("will first back up", self.said[0])
        self.assertEqual(len(os.listdir(self.backups("E"))), 2)

    def test_the_message_names_only_the_library_being_changed(self):
        self.d.drive_letter.rewrite_db(self.db, "E", "D")
        self.d.fix_drive_letter(self.dlg)
        self.assertIn("Kodi's music library points to E:", self.said[0])

    def test_xbox_gets_the_xbox_menu_steps_not_a_quit(self):
        self.d.my_device = lambda: "xbox"
        self.assertTrue(self.d.fix_drive_letter(self.dlg), self.said)
        self.assertEqual(self.built, [])
        self.assertIn("press the Xbox button", self.said[-1])

    def add_art_tables(self, db, art):
        c = sqlite3.connect(db)
        c.executescript("""
          ALTER TABLE song ADD COLUMN idAlbum INTEGER;
          CREATE TABLE album (idAlbum INTEGER PRIMARY KEY, strAlbum TEXT);
          DROP TABLE art;
          CREATE TABLE art (art_id INTEGER PRIMARY KEY, media_id INTEGER, media_type TEXT, type TEXT, url TEXT);
          UPDATE song SET idAlbum = 1;""")
        c.execute("INSERT INTO album VALUES (1, 'Pretend LP')")
        if art:
            c.execute("INSERT INTO art (media_id, media_type, type, url) VALUES (1, 'album', 'thumb', ?)", (art,))
        c.commit()
        c.close()

    def art_check(self, now, before, disk=()):
        for f in disk:
            with open(os.path.join(self.tmp, "drive-D", "Music", "Band", "Album", f), "w"):
                pass
        make_copy = os.path.join(self.tmp, "before.db")
        make_music_db(make_copy, "E")
        self.add_art_tables(make_copy, before)
        folder = os.path.join(self.backups("E"), "2026-11-05 2010")
        os.makedirs(folder)
        shutil.move(make_copy, os.path.join(folder, "MyMusic83.db"))
        with open(os.path.join(folder, "backup-info.json"), "w") as f:
            json.dump({"db": "MyMusic83.db", "drive": "E"}, f)
        d = self.d
        d.xbmcgui.DialogProgress = type("P", (), {"create": lambda s, *a: None, "update": lambda s, *a: None,
                                                  "close": lambda s: None, "iscanceled": lambda s: False})
        props = {}
        d.home = lambda: type("W", (), {"getProperty": lambda s, k: props.get(k, ""),
                                        "setProperty": lambda s, k, v: props.__setitem__(k, v),
                                        "clearProperty": lambda s, k: props.pop(k, None)})()
        self.d.drive_letter.rewrite_db(self.music, "E", "D")
        self.d.save_cache(self.d.data_file("last_settings.json"), {"dest": "win-lib://removable/D:\\\\"}, verify=False)
        self.add_art_tables(self.music, now)
        self.dlg.textviewer = lambda title, text: self.said.append(text)
        return self.d.check_music_art(self.dlg)

    def test_art_kept_and_the_file_is_there(self):
        art = "win-lib://removable/D:\\Music\\Band\\Album\\cover.jpg"
        found = self.art_check(art, art.replace("D:", "E:"), disk=["cover.jpg"])
        self.assertEqual(found["ok"], ["Pretend LP"])
        self.assertIn("No album lost its art", self.said[-1])

    def test_art_lost_since_the_backup(self):
        found = self.art_check("", "win-lib://removable/E:\\Music\\Band\\Album\\cover.jpg")
        self.assertEqual(found["lost"], ["Pretend LP"])

    def test_art_pointing_at_a_missing_file(self):
        found = self.art_check("win-lib://removable/D:\\Music\\Band\\Album\\gone.jpg", "")
        self.assertEqual(found["missing_file"], ["Pretend LP"])

    def test_cover_in_the_folder_but_kodi_isnt_using_it(self):
        self.assertEqual(self.art_check("", "", disk=["Some Name.webp"])["cover_unused"], ["Pretend LP (Some Name.webp)"])

    def test_never_had_art(self):
        self.assertEqual(self.art_check("", "")["none"], ["Pretend LP"])

    def test_art_inside_a_song_counts_as_art(self):
        url = "image://music@win-lib%3a%2f%2fremovable%2fD%3a%5cMusic%5cBand%5cAlbum%5c01%20-%20Song.mp3/"
        self.assertEqual(self.art_check(url, "")["ok"], ["Pretend LP"])

    def test_clicking_twice_doesnt_start_it_twice(self):
        self.art_check("", "")
        props = {}
        self.d.home = lambda: type("W", (), {"getProperty": lambda s, k: props.get(k, ""),
                                             "setProperty": lambda s, k, v: props.__setitem__(k, v),
                                             "clearProperty": lambda s, k: props.pop(k, None)})()
        ran = []
        tool = self.d.one_at_a_time(lambda dlg: (ran.append(1), tool(dlg), "first")[-1])
        self.assertEqual(tool(self.dlg), "first")
        self.assertEqual(ran, [1])
        self.assertIn("already working", self.said[-1])
        tool2 = self.d.one_at_a_time(lambda dlg: "again")
        self.assertEqual(tool2(self.dlg), "again")  # free again afterwards

    def saved_copy(self, stamp, songs):
        folder = os.path.join(self.backups("D"), stamp)
        os.makedirs(folder)
        path = os.path.join(folder, "MyMusic83.db")
        make_music_db(path, "D")
        c = sqlite3.connect(path)
        if not songs:
            c.execute("DELETE FROM song")
        c.commit()
        c.close()
        with open(os.path.join(folder, "backup-info.json"), "w") as f:
            json.dump({"db": "MyMusic83.db", "drive": "D"}, f)

    def restore_setup(self):
        self.art_check_props()
        self.d.drive_letter.rewrite_db(self.music, "E", "D")
        self.d.save_cache(self.d.data_file("last_settings.json"), {"dest": "win-lib://removable/D:\\\\"}, verify=False)
        c = sqlite3.connect(self.music)
        c.execute("DELETE FROM song")
        c.commit()
        c.close()
        self.saved_copy("2026-11-05 2010", 1)

    def art_check_props(self):
        props = {}
        self.d.home = lambda: type("W", (), {"getProperty": lambda s, k: props.get(k, ""),
                                             "setProperty": lambda s, k, v: props.__setitem__(k, v),
                                             "clearProperty": lambda s, k: props.pop(k, None)})()

    def test_restore_puts_the_music_library_back(self):
        self.restore_setup()
        self.assertEqual(self.query(self.music, "SELECT COUNT(*) FROM song"), 0)
        self.assertTrue(self.d.restore_music_library(self.dlg), self.said)
        self.assertEqual(self.query(self.music, "SELECT COUNT(*) FROM song"), 1)
        self.assertEqual(self.query(self.music, "SELECT iTimesPlayed FROM song"), 7)
        self.assertIn("Restored: 1 songs", self.said[-1])
        self.assertEqual(len(os.listdir(self.backups("D"))), 2)  # the empty one was saved first

    @unittest.skipUnless(os.path.exists(os.path.join(os.path.dirname(__file__), "..", "addon", "script.kodisorter", "devtools.py")),
                         "dev tools aren't in public builds")
    def test_sending_includes_the_current_library_and_saved_copies(self):
        self.restore_setup()
        self.d.devtools.bind(vars(self.d))
        names = [n for n, _ in self.d.devtools.music_library_files()]
        self.assertEqual(names, ["music-now.db", "music-D-2026-11-05-2010.db"])

    def test_restore_can_be_cancelled(self):
        self.restore_setup()
        self.answer = False
        self.assertFalse(self.d.restore_music_library(self.dlg))
        self.assertEqual(self.query(self.music, "SELECT COUNT(*) FROM song"), 0)

    def test_restore_ignores_copies_for_another_letter(self):
        self.art_check_props()
        self.d.save_cache(self.d.data_file("last_settings.json"), {"dest": "win-lib://removable/D:\\\\"}, verify=False)
        self.assertFalse(self.d.restore_music_library(self.dlg))
        self.assertIn("no saved copies", self.said[-1])

    def test_clean_music_runs_when_the_files_are_there(self):
        self.d.drive_letter.rewrite_db(self.music, "E", "D")
        self.assertTrue(self.d.clean_music_library(self.dlg), self.said)
        self.assertEqual(self.rpc_calls, ["AudioLibrary.Clean"])

    def test_clean_music_refuses_while_the_drive_looks_missing(self):
        self.assertFalse(self.d.clean_music_library(self.dlg))  # the library says E:, the files are on D:
        self.assertEqual(self.rpc_calls, [])
        self.assertIn("wasn't found", self.said[-1])

    def test_clean_music_can_be_cancelled(self):
        self.d.drive_letter.rewrite_db(self.music, "E", "D")
        self.answer = False
        self.assertFalse(self.d.clean_music_library(self.dlg))
        self.assertEqual(self.rpc_calls, [])

    def test_cancel_changes_nothing(self):
        self.answer = False
        self.assertFalse(self.d.fix_drive_letter(self.dlg))
        self.assertIn("removable/E:/", self.episode())
        self.assertIn("removable/E:", self.query(self.music, "SELECT strPath FROM path"))
        self.assertFalse(os.path.exists(self.backups("E")))

    def test_no_change_if_the_backup_cant_be_saved(self):
        def refuse(*a, **k):
            raise IOError("drive is full")
        self.replace(self.d.backup, "save_letter_copy", refuse)
        self.assertFalse(self.d.fix_drive_letter(self.dlg))
        self.assertIn("removable/E:/", self.episode())
        self.assertIn("drive is full", self.said[-1])
        with open(self.sources) as f:
            self.assertIn("E:\\TV", f.read())

    def test_a_failed_export_still_saves_the_database_and_switches(self):
        self.export_fails = True
        self.assertTrue(self.d.fix_drive_letter(self.dlg))
        stamp = os.listdir(self.backups("E"))[0]
        self.assertFalse(os.path.exists(os.path.join(self.backups("E"), stamp, "videodb.xml")))
        self.assertTrue(os.path.exists(os.path.join(self.backups("E"), stamp, "MyVideos131.db")))
        self.assertEqual(self.d.letter_backups()[0][2]["xml_bytes"], 0)

    def test_files_not_found_changes_nothing(self):
        shutil.rmtree(os.path.join(self.tmp, "drive-D"))
        self.assertFalse(self.d.fix_drive_letter(self.dlg))
        self.assertIn("removable/E:/", self.episode())
        self.assertIn("weren't found", self.said[-1])


if __name__ == "__main__":
    unittest.main()

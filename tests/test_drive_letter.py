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
        os.makedirs(os.path.join(tmp, "profile"))
        self.sources = os.path.join(tmp, "profile", "sources.xml")
        with open(self.sources, "w") as f:
            f.write("<path>win-lib://removable/E:\\TV\\</path><path>win-lib://removable/F:\\Other\\</path>")
        for f in ON_DISK:
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

    def test_cancel_changes_nothing(self):
        self.answer = False
        self.assertFalse(self.d.fix_drive_letter(self.dlg))
        self.assertIn("removable/E:/", self.episode())
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

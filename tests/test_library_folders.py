"""default.py's library-folder logic, run against a real temp folder tree with a fake Kodi."""
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

ADDON = Path(__file__).resolve().parents[1] / "addon" / "script.kodisorter"


def load_default(data_dir):
    for n in ("xbmc", "xbmcgui", "xbmcaddon", "xbmcvfs"):
        sys.modules[n] = types.ModuleType(n)
    vfs = sys.modules["xbmcvfs"]

    class Addon:
        def getAddonInfo(self, k):
            return {"version": "9.9.9", "path": str(ADDON)}[k]

    class Stat:
        def __init__(self, p):
            self.p = p

        def st_size(self):
            return os.path.getsize(self.p) if os.path.isfile(self.p) else 200 * 1024 * 1024

    sys.modules["xbmcaddon"].Addon = Addon
    vfs.translatePath = lambda p: data_dir + "/" if "addon_data" in p else p
    vfs.mkdirs = lambda p: os.makedirs(p, exist_ok=True)
    vfs.exists = os.path.exists
    vfs.listdir = lambda p: ([d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d))],
                             [f for f in os.listdir(p) if os.path.isfile(os.path.join(p, f))])
    vfs.Stat = Stat
    sys.modules["xbmc"].log = lambda *a, **k: None
    sys.modules["xbmc"].LOGINFO = 1
    sys.path.insert(0, str(ADDON))
    src = (ADDON / "default.py").read_text(encoding="utf-8").rstrip()
    assert src.endswith("main()")
    mod = types.ModuleType("default_under_test")
    exec(compile(src[:-6], "default.py", "exec"), mod.__dict__)
    return mod


class LibraryFolders(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = load_default(os.path.join(self.tmp, "data"))
        self.dest = os.path.join(self.tmp, "E") + "/"
        self.shows = os.path.join(self.tmp, "D", "My Shows") + "/"
        for p in ("E/Movies/The Matrix (1999)", "D/My Shows/Sam's Sandwiches/Season 1",
                  "D/My Shows/Doctor Who (2005)/Season 01", "D/My Shows/Doctor Who (1963)", "D/My Shows/Fargo (2014)",
                  "D/My Shows/Fargo"):
            os.makedirs(os.path.join(self.tmp, p))
        self.d.KIND_DIRS.clear()
        self.d.DIR_CACHE.clear()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def plan(self, name):
        return self.d.plan_for("/src/" + name, name, self.dest)

    def test_standard_folders_unchanged(self):
        t, kind, _ = self.plan("New.Show.S01E02.1080p.mkv")
        self.assertEqual(t, self.dest + "TV/New Show/Season 01/New Show S01E02.mkv")

    def test_own_tv_folder_and_its_names(self):
        self.d.KIND_DIRS["TV"] = self.shows
        t, _, _ = self.plan("Sams.Sandwiches.S01E03.720p.mkv")
        self.assertEqual(t, self.shows + "Sam's Sandwiches/Season 1/Sam's Sandwiches S01E03.mkv")
        t, _, _ = self.plan("New.Show.S02E01.mkv")  # new show: standard layout inside their folder
        self.assertEqual(t, self.shows + "New Show/Season 02/New Show S02E01.mkv")
        t, _, _ = self.plan("Sams.Sandwiches.S01E03.en.srt")
        self.assertEqual(t, self.shows + "Sam's Sandwiches/Season 1/Subs/Sam's Sandwiches S01E03.en.srt")

    def test_years_must_agree(self):
        self.d.KIND_DIRS["TV"] = self.shows
        self.assertEqual(self.plan("Doctor.Who.2005.S01E01.mkv")[0],
                         self.shows + "Doctor Who (2005)/Season 01/Doctor Who (2005) S01E01.mkv")
        # no year in the download, two shows of that name: don't guess
        self.assertEqual(self.d.match_folder(self.shows, "Doctor Who"), None)
        # Fargo and Fargo (2014) both exist: the exact name wins
        self.assertEqual(self.d.match_folder(self.shows, "Fargo"), "Fargo")

    def test_movies_need_same_year(self):
        self.assertEqual(self.plan("Matrix.1999.1080p.mkv")[0],
                         self.dest + "Movies/The Matrix (1999)/The Matrix (1999).mkv")
        self.assertEqual(self.plan("The.Matrix.2021.mkv")[0],
                         self.dest + "Movies/The Matrix (2021)/The Matrix (2021).mkv")

    def test_rel_of_and_replaced_path(self):
        self.d.KIND_DIRS["TV"] = self.shows
        target = self.shows + "Fargo/Season 01/Fargo S01E01.mkv"
        self.assertEqual(self.d.rel_of(target, self.dest), ["TV", "Fargo", "Season 01", "Fargo S01E01.mkv"])
        self.assertEqual(self.d.from_rel(["TV", "Fargo", "Season 01", "Fargo S01E01.mkv"], self.dest), target)
        self.assertEqual(self.d.show_of(target, self.dest), "Fargo")
        self.assertEqual(self.d.replaced_path(target, self.dest),
                         self.dest + "_Replaced/TV/Fargo/Season 01/Fargo S01E01.mkv")

    def test_own_folder_skipped_when_scanning(self):
        self.d.KIND_DIRS["TV"] = self.shows
        self.assertIn(self.d._norm(self.shows), self.d.sorted_folders(self.dest))


class LibraryCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = load_default(os.path.join(self.tmp, "data"))
        self.shows = os.path.join(self.tmp, "D", "My Shows") + "/"
        self.files = {
            "Fargo/Season 1/Fargo S01E01.mkv": "in library",
            "Fargo/Season 1/fargo.s01e02.720p.mkv": "readable",
            "Sams Sandwiches 3x04.mkv": "loose in the root",
            "Random Show/episode 7.mkv": "no number",
        }
        for rel in self.files:
            p = os.path.join(self.shows, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.truncate(51 * 1024 * 1024)
        self.d.KIND_DIRS.clear()
        self.d.DIR_CACHE.clear()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def lib(self):
        return {self.d._lib_key(self.shows + "Fargo/Season 1/Fargo S01E01.mkv")}

    def test_report(self):
        self.d.KIND_DIRS["TV"] = self.shows
        rep = self.d.folder_report("TV", self.shows, self.d.parent_of(self.shows), self.lib(),
                                   [self.d._lib_key(os.path.join(self.tmp, "D"))])
        self.assertEqual((rep["videos"], rep["in_library"], rep["readable"]), (4, 1, 1))
        self.assertEqual(sorted(rep["unreadable"]), ["Random Show/episode 7.mkv", "Sams Sandwiches 3x04.mkv"])
        self.assertTrue(rep["is_source"])
        # fargo.s01e02.720p gets its Kodi name, Sams Sandwiches 3x04 gets a show folder; the in-library
        # file is already right and "episode 7" can't be placed: 2 moves
        self.assertEqual(rep["moves"], 2)

    def test_in_library_counts_as_source(self):
        # Kodi reported its sources in another path form on the Xbox: 356 of 357 videos in the
        # library but "not a source". Videos in the library prove the folder is scanned.
        rep = self.d.folder_report("TV", self.shows, self.d.parent_of(self.shows), self.lib(), ["x:/elsewhere"])
        self.assertTrue(rep["is_source"])
        self.assertEqual(self.d._lib_key("win-lib://removable/E%3A%5CTV%5C"), "e:/tv")

    def test_not_a_source(self):
        rep = self.d.folder_report("TV", self.shows, self.d.parent_of(self.shows), set(), ["/somewhere/else"])
        self.assertFalse(rep["is_source"])

    def test_dialogs(self):
        import missing
        lib = self.lib()
        shows = self.d._lib_key(self.shows)
        missing._rpc = lambda m, p: ({"episodes": [{"file": f} for f in lib]} if m == "VideoLibrary.GetEpisodes"
                                     else {"sources": [{"file": shows}]})
        gui = sys.modules["xbmcgui"]

        class Prog:
            def create(self, *a): pass
            def update(self, *a): pass
            def close(self): pass
        gui.DialogProgress = Prog
        seen = []

        class Dlg:
            def textviewer(self, h, t): seen.append(t)
            def yesno(self, h, m, **k): seen.append(m); return True
            def ok(self, h, m): seen.append(m)
        self.assertTrue(self.d.check_library_folder(Dlg(), "TV", self.shows))
        self.assertIn("2 of 4 videos have names or folders Kodi can't read", seen[0])
        self.assertIn("Reorganize", seen[1])
        self.assertFalse(self.d.check_library_folder(Dlg(), "COMIC", self.shows))  # only TV/Movies are checked


if __name__ == "__main__":
    unittest.main()

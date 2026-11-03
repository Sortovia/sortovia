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


if __name__ == "__main__":
    unittest.main()

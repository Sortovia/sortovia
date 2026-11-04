"""Movie entries that are really TV episodes are found; real movies are left alone."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_library_folders import load_default  # noqa: E402


class WrongMovies(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.d = load_default(os.path.join(self.tmp, "data"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_finds_episodes_listed_as_movies(self):
        d = self.d
        movies = [
            {"movieid": 1, "label": "Cesium Hollow", "file": "win-lib://removable/E:\\\\TV/Hollow (2024)/Season 02/Hollow (2024) S02E01.mkv"},
            {"movieid": 2, "label": "Cesium Hollow", "file": "win-lib://removable/E:\\\\Other/fallout.s02e02.mkv"},
            {"movieid": 3, "label": "Amber Hollow Story", "file": "win-lib://removable/E:\\\\Stuff/ahs13.mkv"},
            {"movieid": 4, "label": "Road Deputies 3", "file": "win-lib://removable/E:\\\\Movies/Road Deputies 3 (2026)/Road Deputies 3 (2026).mkv"},
        ]
        eps = {d._lib_key("win-lib://removable/E:\\\\Stuff/ahs13.mkv")}
        bad = d.wrong_movies(movies, eps, d._lib_key("win-lib://removable/E:\\\\TV\\\\"))
        self.assertEqual([(m["movieid"], why) for m, why in bad],
                         [(1, "its file is in your TV folder"), (2, "its file is named like an episode"),
                          (3, "also in your TV library as an episode")])

    def test_finds_entries_that_are_not_tv_episodes(self):
        d = self.d
        k = lambda p: d._lib_key("win-lib://removable/E:\\\\" + p)
        eps = [
            {"episodeid": 1, "label": "a", "file": "win-lib://removable/E:\\\\TV/Show/Season 01/Show S01E01.mkv"},
            {"episodeid": 2, "label": "b", "file": "win-lib://removable/E:\\\\TV/_Replaced/Show S01E02.mkv"},
            {"episodeid": 3, "label": "c", "file": "win-lib://removable/E:\\\\Movies/Heat (1995)/Heat S01E01.mkv"},
            {"episodeid": 4, "label": "d", "file": "win-lib://removable/E:\\\\Tutorials/Revit/Revit 1x02.mp4"},
            {"episodeid": 5, "label": "e", "file": "win-lib://removable/E:\\\\Other/x S01E05.mkv"},
            {"episodeid": 6, "label": "f", "file": "win-lib://removable/E:\\\\TV/_No English/y S01E06.mkv"},
        ]
        roots = {"TV": k("TV"), "Movies": k("Movies"), "Tutorials": k("Tutorials")}
        bad = d.wrong_episodes(eps, {k("Other/x S01E05.mkv")}, roots)
        self.assertEqual([(e["episodeid"], why) for e, why in bad],
                         [(2, "its file is in a set-aside folder (_replaced)"), (3, "its file is in your Movies folder"),
                          (4, "its file is in Tutorials"), (5, "it's also in your Movies library"),
                          (6, "its file is in a set-aside folder (_no english)")])


if __name__ == "__main__":
    unittest.main()

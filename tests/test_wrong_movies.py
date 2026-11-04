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


if __name__ == "__main__":
    unittest.main()

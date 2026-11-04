"""Converting comics: Cancel stops after the comic being done; the rest carries on later."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_library_folders import load_default  # noqa: E402


class Resume(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        d = self.d = load_default(os.path.join(self.tmp, "data"))
        store = self.store = {}
        d.load_cache = lambda path: dict(store.get(os.path.basename(path), {}))
        d.save_cache = lambda path, v, verify=True: store.__setitem__(os.path.basename(path), dict(v)) or True
        sys.modules["xbmcvfs"].exists = lambda p: True
        d.log = lambda m: None
        self.done = []
        self.cancel_after = 1
        test = self

        def convert(p, turn):
            test.done.append(p)
            return True, "ok", p
        d.convert_comic = convert

        class Prog:
            def create(self, *a): pass
            def update(self, *a): pass
            def close(self): pass
            def iscanceled(self): return len(test.done) >= test.cancel_after
        sys.modules["xbmcgui"].DialogProgress = Prog

        class Dlg:
            def textviewer(self, h, t): test.text = t
        self.dlg = Dlg()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_stop_then_carry_on(self):
        paths = ["E/Comics/H/v01.cbr", "E/Comics/H/v02.cbr", "E/Comics/H/v03.cbr"]
        self.d.convert_many(self.dlg, paths, 8)
        self.assertEqual(self.done, paths[:1])  # the comic being done was finished, then it stopped
        self.assertEqual(self.d.comics_pending(), (paths[1:], 8))
        self.assertIn("STOPPED", self.text)
        self.cancel_after = 99
        todo, turn = self.d.comics_pending()
        self.d.convert_many(self.dlg, todo, turn)
        self.assertEqual(self.done, paths)
        self.assertEqual(self.d.comics_pending(), ([], 1))  # nothing left


if __name__ == "__main__":
    unittest.main()

"""The daily backup is skipped when the library database hasn't changed; asking for one always runs."""
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
from test_library_folders import load_default  # noqa: E402


class Skip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        d = self.d = load_default(os.path.join(self.tmp, "data"))
        store = self.store = {}
        d.load_cache = lambda path: dict(store.get(os.path.basename(path), {}))
        d.save_cache = lambda path, v, verify=True: store.__setitem__(os.path.basename(path), dict(v)) or True
        d.log = lambda m: None
        d.toast = lambda m, ms=0: None
        d._backup_places = lambda: ["E/"]
        d.work_dir = lambda: "E/"
        self.print = "same"
        self.made = []

        def make(places, phone, log=None, work=None):
            self.made.append(1)
            return {"made": "today", "counts": {"episodes": 5, "movies": 1}}, ["E/"]
        for name, fake in (("fingerprint", lambda: self.print), ("make_backup", make)):
            patcher = mock.patch.object(d.backup, name, fake)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_first_backup_runs_and_saves_the_fingerprint(self):
        self.assertTrue(self.d.backup_if_changed())
        self.assertEqual(self.store["backup.json"]["fingerprint"], "same")

    def test_unchanged_is_skipped_but_checks_again_tomorrow(self):
        self.d.backup_if_changed()
        self.store["backup.json"]["time"] = 1
        self.assertFalse(self.d.backup_if_changed())
        self.assertEqual(len(self.made), 1)
        self.assertGreater(self.store["backup.json"]["time"], 1)
        self.assertEqual(self.store["backup.json"]["made"], "today")  # the backup it still has

    def test_any_change_backs_up(self):
        self.d.backup_if_changed()
        self.print = "changed"
        self.assertTrue(self.d.backup_if_changed())
        self.assertEqual(len(self.made), 2)

    def test_unreadable_database_still_backs_up(self):
        self.print = ""
        self.d.backup_if_changed()
        self.d.backup_if_changed()
        self.assertEqual(len(self.made), 2)

    def test_asking_for_a_backup_always_runs(self):
        self.d.backup_if_changed()
        self.assertTrue(self.d.backup_now())
        self.assertEqual(len(self.made), 2)


class Fingerprint(unittest.TestCase):
    """Runs the real reading code against a stand-in for Kodi's database folder."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bk = load_default(os.path.join(self.tmp, "data")).backup
        self.data = [b"one"]
        data = self.data

        class File:
            def __init__(self, p): self.left = [data[0]]
            def readBytes(self, n): return self.left.pop() if self.left else b""
            def close(self): pass

        class Stat:
            def __init__(self, p): pass
            def st_size(self): return len(data[0])
        self.files = ["MyVideos131.db"]
        vfs = types.SimpleNamespace(File=File, Stat=Stat, listdir=lambda p: ([], self.files))
        patcher = mock.patch.object(self.bk, "xbmcvfs", vfs)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_same_library_same_print_and_any_change_differs(self):
        first = self.bk.fingerprint()
        self.assertEqual(len(first), 32)
        self.assertEqual(first, self.bk.fingerprint())
        self.data[0] = b"two"
        self.assertNotEqual(first, self.bk.fingerprint())

    def test_no_database_gives_no_print(self):
        self.files[:] = []
        self.assertEqual(self.bk.fingerprint(), "")

    def test_a_database_too_big_to_copy_gives_no_print(self):
        with mock.patch.object(self.bk, "DB_MAX", 1):
            self.assertEqual(self.bk.fingerprint(), "")


if __name__ == "__main__":
    unittest.main()

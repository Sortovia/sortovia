"""Free up space: measures the Xbox's temp, packages and older backups; never offers Kodi's log."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_library_folders import load_default  # noqa: E402


class FreeSpace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        d = self.d = load_default(os.path.join(self.tmp, "data"))
        vfs = sys.modules["xbmcvfs"]
        root = self.tmp
        real = lambda p: os.path.join(root, p[len("special://"):]) if p.startswith("special://") else p

        class Stat:
            def __init__(self, p): self.p = real(p)
            def st_size(self): return os.path.getsize(self.p)
        vfs.Stat = Stat
        vfs.listdir = lambda p: ([x for x in os.listdir(real(p)) if os.path.isdir(os.path.join(real(p), x))],
                                 [x for x in os.listdir(real(p)) if os.path.isfile(os.path.join(real(p), x))])
        d.backup.list_backups = lambda base=None: [("2026-11-04 1200", {}), ("2026-11-03 1200", {})]
        d.backup.HOME_DIR = "special://home/Kodi library backups/"
        d.load_cache = lambda path: {"dest": "win-lib://removable/E:\\"} if str(path).endswith("last_settings.json") else {}

        def mk(p, n):
            os.makedirs(os.path.dirname(real(p)), exist_ok=True)
            open(real(p), "wb").write(b"x" * n)
        mk("special://temp/kodisorter-export-1/kodi_videodb/tvshows/a-thumb.jpg", 5000)
        mk("special://temp/kodi.log", 9000)
        mk("special://temp/something-kodi-uses/f.bin", 3000)
        mk("special://home/addons/packages/old.zip", 2000)
        mk("special://home/Kodi library backups/2026-11-03 1200/videodb.xml", 1000)
        mk("special://home/Kodi library backups/2026-11-04 1200/videodb.xml", 1000)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_rows(self):
        rows = self.d.space_rows()
        got = [(label, size, pre) for label, size, _, _, pre in rows]
        self.assertEqual(got, [("Kodi Sorter's leftover backup export 1 (safe)", 5000, True),
                               ('Kodi\'s temporary folder "something-kodi-uses" (delete only if you know what it is)', 3000, False),
                               ("Old add-on install files (addons/packages)", 2000, True),
                               ("Library backup 2026-11-04 1200 on this device (backups now go on the drive)", 1000, True),
                               ("Library backup 2026-11-03 1200 on this device (backups now go on the drive)", 1000, True)])


if __name__ == "__main__":
    unittest.main()

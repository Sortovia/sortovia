"""A size check on the phone that fails (0) must not throw away a good copy."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_library_folders import load_default  # noqa: E402


class ZeroSize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        d = self.d = load_default(os.path.join(self.tmp, "data"))
        vfs = sys.modules["xbmcvfs"]
        phone = os.path.join(self.tmp, "phone")
        os.makedirs(phone)
        self.data = b"v" * 300000
        open(os.path.join(phone, "a.mp4"), "wb").write(self.data)
        real = lambda p: os.path.join(phone, p[len("dav://phone/"):]) if p.startswith("dav://phone/") else p
        self.stat_calls = [0]
        test = self

        class Stat:
            def __init__(self, p): self.p = real(p)
            def st_size(self):
                test.stat_calls[0] += 1
                if self.p.startswith(phone) and test.stat_calls[0] <= 2:
                    return 0  # the busy share: size check timed out
                return os.path.getsize(self.p) if os.path.exists(self.p) else 0

        class File:
            def __init__(self, p, mode="r"):
                self.p = real(p)
                self.f = open(self.p, "wb" if mode == "w" else "rb")
                self.fail_size = self.p.startswith(phone) and test.stat_calls[0] <= 2
            def size(self): return 0 if self.fail_size else os.path.getsize(self.p)
            def readBytes(self, n=-1): return self.f.read(n)
            def write(self, b): self.f.write(bytes(b)); return True
            def close(self): self.f.close()
        vfs.Stat, vfs.File = Stat, File
        vfs.rename = lambda a, b: False
        vfs.exists = lambda p: os.path.exists(real(p))
        vfs.delete = lambda p: (os.remove(real(p)), True)[1] if os.path.exists(real(p)) else False
        vfs.mkdirs = lambda p: os.makedirs(real(p), exist_ok=True)
        d.log = lambda m: None
        d.step = lambda *a: None
        d.mark_nomedia = lambda p: None
        d.NO_RENAME[0] = True

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_good_copy_is_kept(self):
        dst = os.path.join(self.tmp, "E", "Tutorials", "a.mp4")
        ok, how = self.d.move_file("dav://phone/a.mp4", dst)
        self.assertTrue(ok, how)
        self.assertEqual(open(dst, "rb").read(), self.data)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "phone", "a.mp4")))  # original removed after the check


if __name__ == "__main__":
    unittest.main()

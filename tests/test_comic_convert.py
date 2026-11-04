"""convert_comic end to end with a fake Kodi: .cbr pages -> verified .cbz, original removed only after."""
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(__file__))
from test_library_folders import load_default  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdapixels\xff\xd9"


class Convert(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        d = self.d = load_default(os.path.join(self.tmp, "data"))
        vfs = sys.modules["xbmcvfs"]

        temp = os.path.join(self.tmp, "temp")

        class File:
            def __init__(self, p, mode="r"):
                # Like the Xbox: Kodi's file functions read nothing from the real temp path,
                # only through special://temp/.
                if p.startswith(temp):
                    raise IOError("Kodi can't open the real temp path on the Xbox")
                p = p.replace("special://temp/", temp + "/")
                self.f = open(p, "wb" if mode == "w" else "rb")
            def size(self): return os.fstat(self.f.fileno()).st_size
            def readBytes(self, n=-1): return self.f.read(n)
            def write(self, b): self.f.write(bytes(b)); return True
            def close(self): self.f.close()
        vfs.File = File
        vfs.delete = lambda p: (os.remove(p), True)[1] if os.path.exists(p) else False
        def copy(a, b):
            if a.startswith(temp):
                return False  # like the Xbox
            shutil.copy(a.replace("special://temp/", temp + "/"), b)
            return True
        vfs.copy = copy
        os.makedirs(temp)
        vfs.translatePath = lambda p: temp + "/" if p.startswith("special://temp") else p
        d.log = lambda m: None
        d.step = lambda *a: None
        self.comic = os.path.join(self.tmp, "Comics", "Ironclad") + "/Ironclad v01.cbr"
        os.makedirs(os.path.dirname(self.comic))
        open(self.comic, "wb").write(b"rar data")
        pages = os.path.join(self.tmp, "inside")
        os.makedirs(pages + "/Vol 1")
        for n in ("p10.jpg", "p2.jpg", "p1.jpg"):
            open(pages + "/Vol 1/" + n, "wb").write(JPEG)
        open(pages + "/ComicInfo.xml", "wb").write(b"<x/>")
        d.open_archive = lambda path: [(pages + "/Vol 1/" + n, n) for n in ("p10.jpg", "p2.jpg", "p1.jpg")] + \
            [(pages + "/ComicInfo.xml", "ComicInfo.xml")]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cbr_becomes_turned_cbz(self):
        ok, msg, new = self.d.convert_comic(self.comic, 8)
        self.assertTrue(ok, msg)
        self.assertTrue(new.endswith("Ironclad v01.cbz"))
        self.assertFalse(os.path.exists(self.comic))
        with zipfile.ZipFile(new) as z:
            self.assertEqual(z.namelist(), ["ComicInfo.xml", "Vol 1/p1.jpg", "Vol 1/p2.jpg", "Vol 1/p10.jpg"])
            self.assertEqual(self.d.comics.orientation_of(z.read("Vol 1/p1.jpg")), 8)
        self.assertIn("turned", msg)
        self.assertEqual(os.listdir(os.path.join(self.tmp, "temp")), [])  # temp file cleaned up

    def test_upright_leaves_pages_untouched_and_keeps_existing_cbz(self):
        open(self.comic[:-4] + ".cbz", "wb").write(b"already here")
        ok, msg, new = self.d.convert_comic(self.comic, 1)
        self.assertFalse(ok)
        self.assertTrue(os.path.exists(self.comic))  # original kept
        os.remove(self.comic[:-4] + ".cbz")
        ok, msg, new = self.d.convert_comic(self.comic, 1)
        with zipfile.ZipFile(new) as z:
            self.assertEqual(z.read("Vol 1/p1.jpg"), JPEG)

    def test_unreadable_archive_keeps_original(self):
        self.d.open_archive = lambda path: None
        ok, msg, new = self.d.convert_comic(self.comic, 8)
        self.assertFalse(ok)
        self.assertIn("Archive support", msg)
        self.assertTrue(os.path.exists(self.comic))


if __name__ == "__main__":
    unittest.main()

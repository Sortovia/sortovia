"""Real-Debrid sign-in screen: QR code + code, waits for approval, cleans up its images."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_library_folders import load_default  # noqa: E402


class QrScreen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        d = self.d = load_default(os.path.join(self.tmp, "data"))
        gui, xbmc, vfs = sys.modules["xbmcgui"], sys.modules["xbmc"], sys.modules["xbmcvfs"]
        files = self.files = {}

        class File:
            def __init__(self, p, mode="r"): self.p = p; files[p] = b""
            def write(self, b): files[self.p] += bytes(b); return True
            def close(self): pass
        vfs.File = File
        vfs.delete = lambda p: files.pop(p, None) is not None
        shown = self.shown = []

        class Win:
            def addControl(self, c): shown.append(c)
            def show(self): shown.append("show")
            def close(self): shown.append("close")

        class Ctl:
            def __init__(self, *a, **k): self.a = a
            def setText(self, t): shown.append(t)
        gui.WindowDialog, gui.ControlImage, gui.ControlTextBox = Win, Ctl, Ctl

        class Mon:
            def abortRequested(self): return False
            def waitForAbort(self, s): return False
        xbmc.Monitor = Mon

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_waits_for_approval(self):
        polls = []

        class RD:
            def device_poll(self, dev):
                polls.append(1)
                return len(polls) >= 3
        dev = {"user_code": "ABCD1234", "device_code": "x", "interval": 5, "expires_in": 600,
               "direct_verification_url": "https://real-debrid.com/authorize?client_id=A&device_id=B"}
        self.d._rd_qr_wait(RD(), dev)
        self.assertEqual(len(polls), 3)
        self.assertIn("close", self.shown)
        self.assertTrue(any(isinstance(t, str) and "ABCD1234" in t for t in self.shown))
        self.assertEqual(self.files, {})  # QR and backdrop images removed


if __name__ == "__main__":
    unittest.main()

"""Start-up: splash, update check that Cancel skips, logs in the background, no double start."""
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_library_folders import load_default  # noqa: E402


class StartUp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        d = self.d = load_default(os.path.join(self.tmp, "data"))
        os.makedirs(os.path.join(self.tmp, "data"))
        props = self.props = {}

        class Win:
            def getProperty(self, k): return props.get(k, "")
            def setProperty(self, k, v): props[k] = v
            def clearProperty(self, k): props.pop(k, None)
        gui = sys.modules["xbmcgui"]
        gui.Window = lambda n: Win()
        self.events = events = []
        self.cancel = False
        test = self

        class Prog:
            def create(self, *a): events.append("splash")
            def update(self, pct, msg=""): events.append("tick")
            def iscanceled(self): return test.cancel
            def close(self): events.append("closed")
        gui.DialogProgress = Prog
        d.toast = lambda msg, ms=0: events.append("toast:" + msg)
        d.log = lambda msg: None
        d.send_logs = lambda why, dlg=None: events.append("logs:" + why)
        d.phone_address = lambda dlg, ask=True, port=8080: ""

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_up_to_date_shows_splash_then_closes_it(self):
        self.d.latest_version = lambda: "9.9.9"
        self.assertFalse(self.d.start_up(None))
        self.assertEqual(self.events[0], "splash")
        self.assertIn("closed", self.events)
        self.assertTrue(any(e.startswith("toast:Up to date") for e in self.events))
        self.assertEqual(self.props, {})  # start-up flag cleared

    def test_cancel_skips_a_slow_check(self):
        self.d.latest_version = lambda: time.sleep(5) or "9.9.9"
        self.cancel = True
        t = time.time()
        self.assertFalse(self.d.start_up(None))
        self.assertLess(time.time() - t, 2)
        self.assertTrue(any(e.startswith("toast:Update check skipped") for e in self.events))

    def test_logs_go_in_the_background_when_password_saved(self):
        self.d.load_cache = lambda path: {"dav": {"pass": "x"}} if path.endswith("phone.json") else {}
        self.d.latest_version = lambda: "9.9.9"
        self.d.start_up(None)
        time.sleep(0.3)
        self.assertIn("logs:start", self.events)

    def test_second_click_is_ignored_while_starting(self):
        self.assertFalse(self.d.already_starting())
        self.props[self.d.PROP_STARTING] = str(time.time())
        self.assertTrue(self.d.already_starting())
        self.props[self.d.PROP_STARTING] = str(time.time() - 600)  # stale after a crash
        self.assertFalse(self.d.already_starting())


if __name__ == "__main__":
    unittest.main()

"""The category menu: every entry opens a real folder or runs a real action."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_library_folders import load_default  # noqa: E402


class Menu(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        d = self.d = load_default(os.path.join(self.tmp, "data"))
        props = {}

        class Win:
            def getProperty(self, k): return props.get(k, "")
            def setProperty(self, k, v): props[k] = v
            def clearProperty(self, k): props.pop(k, None)
        sys.modules["xbmcgui"].Window = lambda n: Win()
        self.props = props
        saved = {"last_settings.json": {"src": "dav://kodi:pw@PHONE:8080/", "dest": "win-lib://removable/E:\\\\"}}
        d.load_cache = lambda path: saved.get(os.path.basename(path or ""), {})
        d.onboarding_state = lambda: None

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def walk(self, name, seen):
        for it in self.d.menu_items(name):
            self.assertTrue(it["label"])
            self.assertTrue(bool(it["menu"]) != bool(it["action"]), it)
            if it["menu"]:
                self.assertNotIn(it["menu"], seen)
                seen.add(it["menu"])
                self.assertTrue(self.d.menu_items(it["menu"]), it["menu"])
                self.walk(it["menu"], seen)
            else:
                self.assertIn(it["action"], self.d.ACTIONS, it["action"])
                seen.add("action:" + it["action"])

    def test_every_entry_leads_somewhere(self):
        seen = set()
        self.walk("root", seen)
        self.assertEqual({m for m in seen if not m.startswith("action:")}, {"sort", "youtube", "tidy", "library", "help"})
        self.assertIn("action:same", seen)  # last settings exist
        self.assertIn("action:yt2", seen)

    def test_running_move_shows_first(self):
        self.props[self.d.PROP_RUN] = "3 of 41"
        first = self.d.menu_items("root")[0]
        self.assertEqual(first["action"], "running")

    def test_a_second_sort_is_not_started_during_a_move(self):
        self.props[self.d.PROP_RUN] = "3 of 41"
        called = []
        self.d.running_menu = lambda dlg, status: called.append(status)
        self.d.ACTIONS["same"] = lambda dlg, spath: called.append("ran")
        sys.modules["xbmcgui"].Dialog = lambda: None
        sys.modules["xbmc"].executebuiltin = lambda c: None
        self.d.do_action("same")
        self.assertEqual(called, ["3 of 41"])


if __name__ == "__main__":
    unittest.main()

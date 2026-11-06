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
        expected = {"downloads", "sort", "youtube", "realdebrid", "file", "library", "library_backups", "help"}
        if self.d.devtools:
            expected.add("dev")
        self.assertEqual({m for m in seen if not m.startswith("action:")}, expected)
        self.assertIn("action:same", seen)  # last settings exist
        self.assertIn("action:yt2", seen)

    def test_the_main_menu_is_in_order(self):
        labels = [i["label"] for i in self.d.menu_items("root")]
        wanted = ["Downloads", "File", "Library", "Settings", "Help"]
        self.assertEqual([l for l in labels if l in wanted], wanted)
        self.assertEqual([i["label"] for i in self.d.menu_items("downloads")], ["Transfer and sort", "YouTube", "Real-Debrid"])

    def test_tools_that_change_files_are_under_file(self):
        self.assertIn("music_tags", [i["action"] for i in self.d.menu_items("file")])
        self.assertNotIn("music_tags", [i["action"] for i in self.d.menu_items("library")])

    def test_clean_asks_which_then_runs_each(self):
        ran = []
        self.d.clean_tv_library = lambda dlg: ran.append("TV")
        self.d.fix_wrong_movies = lambda dlg: ran.append("Movies")
        self.d.clean_music_library = lambda dlg: ran.append("Music")
        self.assertIn("clean_library", [i["action"] for i in self.d.menu_items("library")])
        self.d.clean_library(type("D", (), {"multiselect": lambda s, title, rows: [0, 2]})())
        self.assertEqual(ran, ["TV", "Music"])

    def test_dev_tools_only_appear_with_the_dev_file(self):
        real = self.d.devtools
        self.addCleanup(setattr, self.d, "devtools", real)
        self.d.devtools = None
        self.assertNotIn("Dev", [i["label"] for i in self.d.menu_items("root")])
        self.assertEqual(self.d.menu_items("dev"), [])

    def test_organise_runs_each_folder_ticked(self):
        ran = []
        self.d.tidy_library = lambda dlg, spath, kind: ran.append(kind)
        self.d._comics = lambda fn: (lambda dlg, spath: ran.append("Comics"))
        dlg = type("D", (), {"multiselect": lambda s, title, rows: [0, 2, 3]})()
        self.d.organise_folders(dlg, "s")
        self.assertEqual(ran, ["TV", "Music", "Comics"])
        dlg = type("D", (), {"multiselect": lambda s, title, rows: None})()
        ran.clear()
        self.d.organise_folders(dlg, "s")
        self.assertEqual(ran, [])

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


class AfterAnUpdate(unittest.TestCase):
    def test_the_menu_reloads_instead_of_going_blank(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        d = load_default(os.path.join(tmp, "data"))
        calls = []
        plugin = type(sys)("xbmcplugin")
        plugin.endOfDirectory = lambda handle, succeeded=True, **k: calls.append(("end", succeeded))
        sys.modules["xbmcplugin"] = plugin
        self.addCleanup(sys.modules.pop, "xbmcplugin", None)
        d.xbmc.sleep = lambda ms: None
        d.xbmc.executebuiltin = lambda c: calls.append(("builtin", c))

        class Win:
            def getProperty(self, k): return ""
        d.home = lambda: Win()
        d.startup_due = lambda: True
        d.startup_checks = lambda dlg: True
        listed = []
        d.list_menu = lambda handle, name: listed.append(name)
        d.xbmcgui.Dialog = lambda: None
        d.plugin_main(["plugin://script.kodisorter/", "7", ""])
        self.assertEqual(calls[-1], ("builtin", "Container.Refresh"))
        self.assertEqual(listed, ["root"])  # the menu is shown, so nothing flashes blank


if __name__ == "__main__":
    unittest.main()

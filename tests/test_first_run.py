"""A stranger's first start: no phone, no saved anything, and the settings page switches."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_library_folders import load_default  # noqa: E402


class Dlg:
    """Says yes to nothing and cancels every list, like someone backing out of each question."""
    def __init__(self, phone=False):
        self.phone = phone
        self.shown = []

    def ok(self, h, m): self.shown.append(m)

    def yesno(self, h, m, **k):
        self.shown.append(m)
        return self.phone if "Android phone" in m else False

    def select(self, h, opts, **k):
        self.shown.append(h)
        self.shown.extend(opts)
        return -1

    def multiselect(self, h, opts, **k): return None
    def browse(self, *a, **k): return ""
    def input(self, *a, **k): return ""
    def textviewer(self, h, t): self.shown.append(t)


class FirstRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data = os.path.join(self.tmp, "data")
        os.makedirs(self.data)
        d = self.d = load_default(self.data)
        settings = self.settings = {}

        class Addon(sys.modules["xbmcaddon"].Addon):
            def getSetting(self, k): return settings.get(k, "true")
            def setSetting(self, k, v): settings[k] = v
        sys.modules["xbmcaddon"].Addon = Addon
        props = self.props = {}

        class Win:
            def getProperty(self, k): return props.get(k, "")
            def setProperty(self, k, v): props[k] = v
            def clearProperty(self, k): props.pop(k, None)

        class Prog:
            def create(self, *a): pass
            def update(self, *a): pass
            def iscanceled(self): return False
            def close(self): pass
        gui = sys.modules["xbmcgui"]
        gui.Window = lambda n: Win()
        gui.DialogProgress = Prog
        d.log = lambda m: None
        d.toast = lambda m, ms=0: None
        d.xbmc.getCondVisibility = lambda c: False
        d.xbmc.getInfoLabel = lambda k: ""
        d.xbmc.getLanguage = lambda *a, **k: "English"
        d.xbmc.ISO_639_1 = 0
        self.searched = []
        d.phone_address = lambda dlg, ask=True, port=8080: self.searched.append(1) or ""
        self.update_checks = []
        d.check_for_update = lambda dlg, splash=None, manual=False: self.update_checks.append(1) or False
        d.check_library_backup = lambda dlg: None

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_first_start_never_searches_the_network_for_a_phone(self):
        self.assertFalse(self.d.startup_checks(Dlg()))
        self.assertEqual(self.searched, [])
        self.settings["use_phone"] = "true"  # even with the helper on, until a phone is set up
        self.assertEqual(self.d.send_logs("end"), "phone share not set up")
        self.assertEqual(self.d.send_logs("backup", files=[]), "phone share not set up")
        self.assertEqual(self.searched, [])

    def test_asking_for_the_log_can_still_find_the_phone(self):
        self.d.send_logs("manual", Dlg())
        self.assertTrue(self.searched)

    def test_welcome_answer_no_hides_the_phone_options(self):
        self.d.startup_checks(Dlg(phone=False))
        self.assertEqual(self.settings.get("use_phone"), "false")
        self.assertNotIn("YouTube", [i["label"] for i in self.d.menu_items("root")])
        self.assertNotIn("Send Kodi's log to my phone now", [i["label"] for i in self.d.menu_items("help")])
        dlg = Dlg()
        self.d.new_sort(dlg, None)  # goes straight to choosing a folder
        self.assertFalse([s for s in dlg.shown if "My phone" in s])

    def test_welcome_answer_yes_keeps_them_and_says_where_the_steps_are(self):
        dlg = Dlg(phone=True)
        self.d.startup_checks(dlg)
        self.assertEqual(self.settings.get("use_phone"), "true")
        self.assertIn("YouTube", [i["label"] for i in self.d.menu_items("root")])
        self.assertTrue([s for s in dlg.shown if "section 3" in s or "kodi-repo" in s])

    def test_update_check_switch(self):
        self.d.startup_checks(Dlg())
        self.assertEqual(len(self.update_checks), 1)
        self.props.clear()
        self.settings["check_updates"] = "false"
        self.d.startup_checks(Dlg())
        self.assertEqual(len(self.update_checks), 1)

    def test_log_switch_applies_once_a_phone_is_set_up(self):
        with open(os.path.join(self.data, "phone.json"), "w") as f:
            json.dump({"dav": {"pass": "x", "user": "kodi", "port": "8080"}}, f)
        self.settings["send_logs"] = "false"
        self.assertIn("off", self.d.send_logs("start"))
        self.assertEqual(self.searched, [])

    def test_no_screen_assumes_an_xbox(self):
        for name in ("root", "sort", "tidy", "library", "help"):
            for it in self.d.menu_items(name):
                self.assertNotIn("Xbox", it["label"] + str(it.get("plot", "")), it)
                self.assertNotIn("on the phone's hotspot", it["label"], it)


class ExistingUserDefaults(unittest.TestCase):
    def test_a_copy_without_the_settings_behaves_as_before(self):
        tmp = tempfile.mkdtemp()
        try:
            d = load_default(os.path.join(tmp, "data"))  # its fake Addon has no getSetting
            self.assertTrue(d.setting_on("use_phone"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

"""The Downloads and search lists: two short lines per entry, so nothing scrolls."""
import os
import sys
import types
import unittest

ADDON = os.path.join(os.path.dirname(__file__), "..", "addon", "script.kodisorter")


class Lines(unittest.TestCase):
    def setUp(self):
        for n in ("xbmc", "xbmcgui", "xbmcaddon", "xbmcvfs"):
            sys.modules.setdefault(n, types.ModuleType(n))
        gui = sys.modules["xbmcgui"]

        class ListItem:
            def __init__(self, a, b=""): self.a, self.b = a, b
        gui.ListItem = ListItem
        sys.path.insert(0, ADDON)
        sys.modules.pop("youtube", None)
        import youtube
        self.y = youtube

    def test_long_download_fits(self):
        j = {"state": "downloading", "title": "Ultimate Claude Code Tutorial: How to Use Every Feature "
             "for Beginners and Pros (2026 Full Course)", "pct": 45.2, "mb": 312, "speed": "1.2MiB/s", "eta": "03:10"}
        t, st = self.y.job_lines(j)
        self.assertLessEqual(len(t), self.y.SHORT)
        self.assertTrue(t.startswith("Ultimate Claude Code Tutorial"))
        self.assertTrue(t.endswith("…"))
        self.assertEqual(st, "Downloading: 45%, 312 MB, 1.2MiB/s, 03:10 left")

    def test_states(self):
        self.assertEqual(self.y.job_lines({"state": "done", "file": "a.mp4"}), ("a.mp4", "Done"))
        self.assertEqual(self.y.job_lines({"state": "queued", "title": "x"})[1], "Waiting")
        self.assertTrue(self.y.job_lines({"state": "failed", "title": "x", "error": "boom"})[1].startswith("FAILED: boom"))

    def test_select2_two_lines_and_fallback(self):
        seen = {}

        class Dlg:
            def select(self, h, items, useDetails=False):
                seen["items"], seen["details"] = items, useDetails
                return 0
        self.y.select2(Dlg(), "h", [("a", "b")])
        self.assertTrue(seen["details"])
        self.assertEqual((seen["items"][0].a, seen["items"][0].b), ("a", "b"))

        class OldDlg:
            def select(self, h, labels):
                seen["labels"] = labels
                return 0
        self.y.select2(OldDlg(), "h", [("a", "b")])
        self.assertEqual(seen["labels"], ["a  [b]"])


if __name__ == "__main__":
    unittest.main()

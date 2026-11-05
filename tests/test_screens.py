"""The reader moves one line at a time, and the bigger windows fall back to Kodi's own dialogs."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon", "script.kodisorter"))
import screens  # noqa: E402


class Reader(unittest.TestCase):
    def test_never_skips_a_line(self):
        s = screens.Scroller(50, rows=19, delay=2, hold=5, now=0)
        seen = [s.pos]
        for t in range(0, 200):
            if s.tick(t):
                seen.append(s.pos)
        self.assertEqual(seen, list(range(0, 32)))  # 0 to the last screenful, one by one
        self.assertFalse(s.playing)

    def test_waits_before_starting(self):
        s = screens.Scroller(50, hold=5, now=0)
        self.assertFalse(s.tick(4))
        self.assertTrue(s.tick(5))

    def test_short_text_never_scrolls(self):
        self.assertFalse(screens.Scroller(5, rows=19).playing)

    def test_moving_by_hand_pauses_and_stays_in_range(self):
        s = screens.Scroller(50, rows=19, now=0)
        s.move(-3, 1)
        self.assertEqual(s.pos, 0)
        self.assertFalse(s.playing)
        s.move(500, 1)
        self.assertEqual(s.pos, 31)

    def test_ok_pauses_and_plays(self):
        s = screens.Scroller(50, now=0)
        s.toggle(1)
        self.assertFalse(s.playing)
        s.toggle(2)
        self.assertTrue(s.playing)
        self.assertIn("Scrolling", s.hint())

    def test_speed_has_limits(self):
        s = screens.Scroller(50)
        for _ in range(30):
            s.faster()
        self.assertEqual(s.delay, 1.0)
        for _ in range(30):
            s.slower()
        self.assertEqual(s.delay, 8.0)

    def test_line_count_wraps_and_ignores_tags(self):
        self.assertEqual(screens.line_count("[B]" + "x" * 100 + "[/B]\n" + "y" * 101, 100), 3)


class Plain:
    def __init__(self): self.seen = []
    def ok(self, h, m): self.seen.append("ok"); return True
    def yesno(self, h, m, nolabel="", yeslabel="", **k): self.seen.append("yesno"); return True
    def textviewer(self, h, t): self.seen.append("text")
    def select(self, h, o): return 2


class Fallback(unittest.TestCase):
    def setUp(self):
        self.plain = Plain()
        self.d = screens.Friendly(self.plain)
        self.calls = []
        self._page, self._read = screens.show_page, screens.read_text
        self.addCleanup(lambda: (setattr(screens, "show_page", self._page), setattr(screens, "read_text", self._read)))

    def test_long_messages_use_the_full_window(self):
        screens.show_page = lambda t, b, buttons: self.calls.append(buttons) or 1
        self.assertTrue(self.d.yesno("H", "x" * 200, nolabel="No", yeslabel="Yes"))
        self.assertTrue(self.d.ok("H", "x" * 200))
        self.assertEqual(self.calls, [["No", "Yes"], ["OK"]])
        self.assertEqual(self.plain.seen, [])

    def test_short_messages_stay_small(self):
        self.d.ok("H", "Short.")
        self.assertEqual(self.plain.seen, ["ok"])

    def test_if_the_window_fails_kodis_dialog_shows_it(self):
        def boom(*a):
            raise RuntimeError("no such control")
        screens.show_page = screens.read_text = boom
        self.d.ok("H", "x" * 200)
        self.d.yesno("H", "x" * 200)
        self.d.textviewer("H", "text")
        self.assertEqual(self.plain.seen, ["ok", "yesno", "text"])

    def test_everything_else_passes_through(self):
        self.assertEqual(self.d.select("H", []), 2)


if __name__ == "__main__":
    unittest.main()

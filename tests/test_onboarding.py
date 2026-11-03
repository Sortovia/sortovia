import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon" / "script.kodisorter"))
import onboarding as ob  # noqa: E402


class MarkdownForKodi(unittest.TestCase):
    def test_basics(self):
        t = ob.md_to_kodi("# Title\n\nSome **bold** and `code` and [a link](http://x).\n- item\n---\n| A | B |\n|---|---|\n| 1 | 2 |\n")
        self.assertIn("[B]TITLE[/B]", t)
        self.assertIn("Some [B]bold[/B] and code and a link.", t)
        self.assertIn("• item", t)
        self.assertIn("A  -  B", t)
        self.assertNotIn("---", t)

    def test_real_readme_has_no_markdown_left(self):
        t = ob.md_to_kodi((ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("FIRST-TIME SETUP", t)
        for junk in ("**", "```", "](", "|---"):
            self.assertNotIn(junk, t)


class WhatsNew(unittest.TestCase):
    def test_versions_between(self):
        cl = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        t = ob.changes_since(cl, "1.23.1", "1.25.0")
        self.assertIn("1.25.0", t)
        self.assertIn("1.24.0", t)
        self.assertIn("Search YouTube", t)  # the indented details under 1.25.0 come too
        self.assertNotIn("1.23.1", t)
        self.assertEqual(ob.changes_since(cl, "1.25.0", "1.25.0"), "")


class Dlg:
    def __init__(self, answers):
        self.answers, self.seen = list(answers), []

    def _a(self, what):
        self.seen.append(what)
        return self.answers.pop(0)

    def ok(self, h, m): self.seen.append("ok")
    def yesno(self, h, m, **k): return self._a("yesno")
    def multiselect(self, h, opts, preselect=None): return self._a(("multi", tuple(preselect or ())))
    def select(self, h, opts): return self._a("select")
    def textviewer(self, h, t): self.seen.append(("text", t[:30]))


class FirstRun(unittest.TestCase):
    def make(self, d):
        res = Path(d) / "addon" / "resources"
        res.mkdir(parents=True)
        for doc in ("README.md", "CHANGELOG.md"):
            (res / doc).write_text((ROOT / doc).read_text(encoding="utf-8"), encoding="utf-8")
        return ob.Onboarding(str(Path(d) / "addon"), os.path.join(d, "onboarding.json"), "1.26.0", "Kodi Sorter")

    def test_welcome_once_then_kinds_kept(self):
        with tempfile.TemporaryDirectory() as d:
            o = self.make(d)
            dlg = Dlg([[1, 3], True])  # Movies + Tutorials, read the guide
            self.assertTrue(o.first_run(dlg))
            self.assertEqual(o.wanted(), ["MOVIE", "TUTORIAL"])
            self.assertTrue(any(isinstance(x, tuple) and x[0] == "text" for x in dlg.seen))
            o2 = ob.Onboarding(str(Path(d) / "addon"), os.path.join(d, "onboarding.json"), "1.26.0", "Kodi Sorter")
            self.assertFalse(o2.first_run(Dlg([])))  # not shown again
            self.assertEqual(o2.wanted_line(), "Movies, Tutorials")

    def test_back_on_first_run_keeps_everything(self):
        with tempfile.TemporaryDirectory() as d:
            o = self.make(d)
            o.first_run(Dlg([None, False]))
            self.assertEqual(o.wanted(), ob.ALL_KINDS)
            self.assertEqual(o.wanted_line(), "everything")

    def test_whats_new_after_update(self):
        with tempfile.TemporaryDirectory() as d:
            o = self.make(d)
            o.state.update({"welcomed": "1.24.0", "seen_version": "1.24.0"})
            dlg = Dlg([])
            o.whats_new(dlg)
            self.assertEqual(len(dlg.seen), 1)
            dlg2 = Dlg([])
            o.whats_new(dlg2)  # only once per version
            self.assertEqual(dlg2.seen, [])


if __name__ == "__main__":
    unittest.main()

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


    def test_wrapped_lines_joined(self):
        t = ob.md_to_kodi("- Movies go to\n  their folder. More\n  text here.\n- Next item\n\nA paragraph\nwrapped.\n\n```\nkeep\nlines\n```\n")
        self.assertIn("\u2022 Movies go to their folder. More text here.", t)
        self.assertIn("\u2022 Next item", t)
        self.assertIn("A paragraph wrapped.", t)
        self.assertIn("    keep\n    lines", t)

    def test_real_readme_sentences_not_split(self):
        t = ob.md_to_kodi((ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("a movie named in another language gets its English title", t)


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
    def browse(self, t, h, kind): return self._a("browse")


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
            dlg = Dlg([0, [1, 3], 3, False, True])  # Movies + Tutorials, 3rd language in the list, no own folders, guide
            self.assertTrue(o.first_run(dlg))
            self.assertEqual(o.wanted(), ["MOVIE", "TUTORIAL"])
            self.assertEqual((o.device(), o.device_line()), ("xbox", "Xbox"))
            self.assertTrue(any(isinstance(x, tuple) and x[0] == "text" for x in dlg.seen))
            o2 = ob.Onboarding(str(Path(d) / "addon"), os.path.join(d, "onboarding.json"), "1.26.0", "Kodi Sorter")
            self.assertFalse(o2.first_run(Dlg([])))  # not shown again
            self.assertEqual(o2.wanted_line(), "Movies, Tutorials")

    def test_pick_own_tv_folder(self):
        with tempfile.TemporaryDirectory() as d:
            o = self.make(d)
            # kinds: all; yes I have folders; pick row 0 (TV) -> existing -> browse; Done (row 4); no guide
            o.first_run(Dlg([0, [0, 1, 2, 3], -1, True, 0, 0, "win-lib://removable/D:\\My Shows/", 4, False]))
            self.assertEqual(o.folders(), {"TV": "win-lib://removable/D:\\My Shows/"})
            self.assertEqual(o.folders_line(), "TV episodes -> D:\\My Shows")
            # Help > My library folders > TV > use the standard folder again
            o.choose_folders(Dlg([0, 1, 4]))
            self.assertEqual(o.folders(), {})

    def test_standard_folder_shows_the_drive(self):
        with tempfile.TemporaryDirectory() as d:
            o = self.make(d)
            self.assertIn("on the drive you sort to", o._std_line("MOVIE"))
            o.std_folder = lambda k: {"MOVIE": "E:\\Movies"}.get(k)
            self.assertEqual(o._std_line("MOVIE"), "standard folder: E:\\Movies")
            self.assertEqual(o._std_line("MOVIE", short=True), "E:\\Movies")

    def test_language_choice(self):
        with tempfile.TemporaryDirectory() as d:
            o = self.make(d)
            self.assertEqual(o.language().code, "en")  # default
            o.kodi_lang = "de"
            o.choose_language(Dlg([0]))  # "Use Kodi's language"
            self.assertEqual((o.language().code, o.language_line()), ("de", "German (Kodi's language)"))
            import lang
            spanish = [c for c, _ in lang.choices()].index("es") + 1
            o.choose_language(Dlg([spanish]))
            self.assertEqual(o.language().name, "Spanish")

    def test_back_on_first_run_keeps_everything(self):
        with tempfile.TemporaryDirectory() as d:
            o = self.make(d)
            o.first_run(Dlg([-1, None, -1, False, False]))
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


class Devices(unittest.TestCase):
    def test_detect(self):
        import devices
        xbox = lambda k: "Microsoft Xbox One S with WINDOWS 10.0.26100" if k == "System.OSVersionInfo" else ""
        self.assertEqual(devices.detect(lambda c: c == "System.Platform.UWP", xbox), "xbox")
        self.assertEqual(devices.detect(lambda c: c == "System.Platform.UWP", lambda k: "Windows 11"), "windows")
        self.assertEqual(devices.detect(lambda c: c == "System.Platform.Android", lambda k: ""), "android_tv")
        self.assertEqual(devices.detect(lambda c: False, lambda k: ""), "other")
        self.assertFalse(devices.can_rename("xbox"))
        self.assertIn("win-lib://removable/E:\\Tutorials\\", devices.add_source_help("xbox", "E:\\Tutorials"))
        self.assertIn("Browse", devices.add_source_help("android_tv"))


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon" / "script.kodisorter"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lang  # noqa: E402


class Language(unittest.TestCase):
    def test_codes(self):
        es = lang.Language("es")
        self.assertTrue(es.matches("spa") and es.matches("es") and es.matches("es-MX"))
        self.assertFalse(es.matches("eng"))
        self.assertEqual((es.no_folder, es.tmdb), ("_No Spanish", "es"))
        self.assertEqual(lang.Language("en").tmdb, "en-US")
        self.assertEqual(lang.Language("xx").code, "en")  # unknown -> English

    def test_file_hints(self):
        self.assertTrue(lang.Language("es").hint_re.search("Movie.2020.CASTELLANO.1080p"))
        self.assertTrue(lang.Language("fr").hint_re.search("Film.2019.TRUEFRENCH.mkv"))
        self.assertFalse(lang.Language("es").hint_re.search("Espanola.Beach.mkv"))

    def test_kodi_language(self):
        self.assertEqual(lang.resolve("kodi", "pt").name, "Portuguese")
        self.assertEqual(lang.resolve("", "zz").code, "en")
        self.assertEqual(lang.resolve("fr", "de").code, "fr")


class InTheAddon(unittest.TestCase):
    def test_audio_check_uses_the_language(self):
        import tempfile
        from test_library_folders import load_default
        with tempfile.TemporaryDirectory() as d:
            m = load_default(d)
            m.audio_languages = lambda path: ["eng", "spa"]
            m.PREF[0] = lang.Language("es")
            self.assertEqual(m.english_status("/x", "x.mkv")[0], True)
            m.audio_languages = lambda path: ["eng"]
            self.assertEqual(m.english_status("/x", "x.mkv")[0], False)
            self.assertEqual(m.lang_note(False, ["eng"]), "no Spanish audio: eng")
            self.assertEqual(m.lang_mode_name(1), "move no-Spanish to _No Spanish")
            self.assertTrue(m.NO_LANG_RE.match("_No Spanish"))
            self.assertTrue(m.PARK_RE.match("E:\\\\_No Spanish\\\\Movie.mkv"))
            m.PREF[0] = lang.Language("en")
            self.assertEqual(m.english_status("/x", "x.mkv")[0], True)


if __name__ == "__main__":
    unittest.main()

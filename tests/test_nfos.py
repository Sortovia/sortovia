import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addon" / "script.kodisorter"))
import nfos  # noqa: E402


class ReleaseNfos(unittest.TestCase):
    def test_kodi_xml_is_not_a_release_nfo(self):
        self.assertTrue(nfos.is_kodi_nfo("<?xml version='1.0'?>\n<movie><title>X</title></movie>"))
        self.assertTrue(nfos.is_kodi_nfo("﻿<tvshow>\n</tvshow>"))
        self.assertFalse(nfos.is_kodi_nfo("╔═╗ ELiTE presents\nIMDB: tt0121955"))

    def test_imdb_ids(self):
        text = ("IMDB....: https://www.imdb.com/title/tt0121955/\n"
                "also http://imdb.com/de/title/tt1877830 and tt0121955 again")
        self.assertEqual(nfos.imdb_ids(text), ["tt0121955", "tt1877830"])
        self.assertEqual(nfos.imdb_ids("no links here, button tt12 too short"), [])

    def test_url_nfo(self):
        self.assertEqual(nfos.url_nfo("tt0121955"), "https://www.imdb.com/title/tt0121955/\n")

    def test_same_show(self):
        self.assertTrue(nfos.same_show("The Office", "Office (US)"))
        self.assertTrue(nfos.same_show("North Quay", "North Quay"))
        self.assertFalse(nfos.same_show("North Quay", "Family Guy"))


class AudioFromNfo(unittest.TestCase):
    def test_audio_lines(self):
        self.assertEqual(nfos.audio_languages("AUDIO......: English DD5.1\nVIDEO: x265"), ["en"])
        self.assertEqual(nfos.audio_languages("Audio 1: Japanese AAC\nAudio 2: English AAC"), ["en", "ja"])
        self.assertEqual(nfos.audio_languages("Language: Spanish (Latino)"), ["es"])

    def test_subtitle_lines_ignored(self):
        text = "Audio: Japanese FLAC\nSubtitles: English, Spanish"
        self.assertEqual(nfos.audio_languages(text), ["ja"])

    def test_value_on_next_line(self):
        self.assertEqual(nfos.audio_languages("[ Audio ]\nEnglish 5.1 AC3"), ["en"])

    def test_nothing_useful(self):
        self.assertEqual(nfos.audio_languages("Dual Audio\nGreetings to all the crew"), [])
        self.assertEqual(nfos.audio_languages("Video: 1080p, it is great"), [])


if __name__ == "__main__":
    unittest.main()

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


class QualityTags(unittest.TestCase):
    def test_from_name(self):
        self.assertEqual(nfos.quality_tags(["The.Nightwarden.2022.1080p.REPACK.BluRay.DDP.5.1.10bit.H265-ALPHA.mkv"]),
                         ["x265", "10-bit", "BluRay"])

    def test_one_source_only(self):
        self.assertEqual(nfos.quality_tags(["Movie.2020.BluRay.Remux.mkv"]), ["Remux"])

    def test_bitrate_from_nfo(self):
        tags = nfos.quality_tags(["Movie.2020.WEB-DL.mkv"], "Format : HEVC\nOverall bit rate : 5 432 kb/s\nBit depth : 10 bits")
        self.assertEqual(tags, ["x265", "WEB-DL", "10-bit", "5.4 Mbps"])

    def test_bitrate_estimate(self):
        self.assertEqual(nfos.quality_tags(["Fin (2021).mkv"], "", 6 * 10 ** 9, 100), ["~8.0 Mbps"])

    def test_title_words_not_tags(self):
        self.assertEqual(nfos.quality_tags(["Multiverse.Avenue.2019.mkv", "Dvdland (2001)"]), [])

    def test_combination_nfo_keeps_link_last(self):
        text = nfos.quality_nfo(["x265", "A&B"], "https://www.imdb.com/title/tt1877830/\n")
        self.assertTrue(text.rstrip().endswith("https://www.imdb.com/title/tt1877830/"))
        self.assertIn("<tag>A&amp;B</tag>", text)
        self.assertTrue(nfos.is_kodi_nfo(text))

    def test_only_link_nfos_are_upgraded(self):
        self.assertTrue(nfos.our_url_nfo("https://www.imdb.com/title/tt1/\n"))
        self.assertFalse(nfos.our_url_nfo("<movie><title>x</title></movie>"))


if __name__ == "__main__":
    unittest.main()

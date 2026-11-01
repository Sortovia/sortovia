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


if __name__ == "__main__":
    unittest.main()

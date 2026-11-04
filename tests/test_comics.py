"""Comics: orientation tags on JPEG pages, page order, tidying the Comics folder."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon", "script.kodisorter"))
import comics  # noqa: E402

JFIF = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
OLD_EXIF = b"\xff\xe1\x00\x0aExif\x00\x00II"
BODY = b"\xff\xdb\x00\x03\x00" + b"\xff\xda\x00\x02" + b"pixels" + b"\xff\xd9"


class Orientation(unittest.TestCase):
    def test_tag_set_replaced_and_removed(self):
        page = b"\xff\xd8" + JFIF + OLD_EXIF + BODY
        turned = comics.set_orientation(page, 8)
        self.assertEqual(comics.orientation_of(turned), 8)
        self.assertTrue(turned.startswith(b"\xff\xd8" + JFIF))  # JFIF stays first
        self.assertNotIn(OLD_EXIF, turned)
        self.assertTrue(turned.endswith(BODY))
        again = comics.set_orientation(turned, 6)
        self.assertEqual(comics.orientation_of(again), 6)
        self.assertEqual(again.count(b"Exif\x00\x00"), 1)
        upright = comics.set_orientation(again, 1)
        self.assertEqual(comics.orientation_of(upright), 1)
        self.assertEqual(upright, b"\xff\xd8" + JFIF + BODY)

    def test_non_jpeg_and_damaged_left_alone(self):
        png = b"\x89PNG\r\n\x1a\nrest"
        self.assertEqual(comics.set_orientation(png, 8), png)
        bad = b"\xff\xd8\xff\xe1\xff\xffshort"
        self.assertEqual(comics.set_orientation(bad, 8), bad)

    def test_page_order(self):
        self.assertEqual(comics.page_order(["p10.jpg", "p2.jpg", "P1.jpg"]), ["P1.jpg", "p2.jpg", "p10.jpg"])


class Tidy(unittest.TestCase):
    def test_plan(self):
        files = [([], "Tinman Meadow v01.cbz"),
                 (["Ironclad (2)"], "Ironclad v01.cbr"),
                 (["ironclad[2]"], "Ironclad v02.cbr"),
                 (["Ironclad"], "Ironclad v03.cbz"),            # already right
                 (["Nightwarden", "Year One"], "Nightwarden 001.cbz"),    # own layout: left alone
                 (["Saga"], "Saga 054.cbr"),
                 ([], "Verizon_bill_December_18_2022.pdf"),
                 (["Manga"], "Some manga.pdf"),
                 ([], "notes.txt")]
        moves, docs = comics.plan_tidy(files)
        self.assertEqual(moves, [([], "Tinman Meadow v01.cbz", "Tinman Meadow"),
                                 (["Ironclad (2)"], "Ironclad v01.cbr", "Ironclad"),
                                 (["ironclad[2]"], "Ironclad v02.cbr", "Ironclad")])
        self.assertEqual(docs, [([], "Verizon_bill_December_18_2022.pdf")])


if __name__ == "__main__":
    unittest.main()

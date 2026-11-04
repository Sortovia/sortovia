"""Phone helper: YouTube's search reply -> results with dates and views, sorted as chosen."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import yt_helper as h  # noqa: E402


def vr(vid, title, length, published, views):
    return {"videoRenderer": {"videoId": vid, "title": {"runs": [{"text": title}]}, "lengthText": {"simpleText": length},
                              "publishedTimeText": {"simpleText": published},
                              "viewCountText": {"simpleText": views}, "ownerText": {"runs": [{"text": "Chan"}]}}}


REPLY = {"contents": {"x": [{"itemSectionRenderer": {"contents": [
    vr("a", "Old long", "1:22:03", "4 years ago", "1,007,515 views"),
    vr("b", "New short", "4:13", "1 day ago", "559 views"),
    vr("c", "Mid", "36:27", "2 weeks ago", "75,093 views"),
    {"adSlotRenderer": {}}]}}]}}


class Search(unittest.TestCase):
    def test_parse(self):
        r = h.parse_api_results(REPLY)
        self.assertEqual([x["id"] for x in r], ["a", "b", "c"])
        self.assertEqual(r[0]["duration"], 4923)
        self.assertEqual(r[0]["views"], 1007515)
        self.assertEqual(r[0]["published"], "4 years ago")
        self.assertEqual(r[0]["channel"], "Chan")

    def test_sorting(self):
        ids = lambda o: [x["id"] for x in h.sort_results(h.parse_api_results(REPLY), o)]
        self.assertEqual(ids("newest"), ["b", "c", "a"])
        self.assertEqual(ids("longest"), ["a", "c", "b"])
        self.assertEqual(ids("shortest"), ["b", "c", "a"])
        self.assertEqual(ids("best"), ["a", "b", "c"])

    def test_age(self):
        self.assertEqual(h.age_days("1 day ago"), 1)
        self.assertAlmostEqual(h.age_days("Streamed 2 years ago"), 730.5)
        self.assertIsNone(h.age_days(""))


if __name__ == "__main__":
    unittest.main()

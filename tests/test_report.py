"""Problem reports: nothing private survives the clean-up, and the useful detail does."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon", "script.kodisorter"))
import report  # noqa: E402


class Scrub(unittest.TestCase):
    def test_private_details_are_removed(self):
        for secret, line in (
                ("hunter2", "opening dav://kodi:hunter2@192.168.1.5:8080/Download"),
                ("abc123", "reading https://tracker.example/rss?passkey=abc123&x=1"),
                ("abc123", "https://t.example/f?torrent_pass=abc123"),
                ("tok99", "Authorization: Bearer tok99"),
                ("tok99", '{"access_token": "tok99", "n": 1}'),
                ("sec99", '"client_secret": "sec99"'),
                ("pw9", "password=pw9"),
                ("JaneDoe", r"File U:\Users\JaneDoe\AppData\Local\Kodi\x.py"),
                ("192.168.1.5", "connected to 192.168.1.5"),
                ("me@example.com", "account me@example.com")):
            self.assertNotIn(secret, report.scrub(line), line)

    def test_useful_detail_stays(self):
        line = "2026-11-05 error <general>: [Sortovia 1.40.0] copy failed: Show S01E02.mkv size 0 vs 100"
        self.assertEqual(report.scrub(line), line)

    def test_keeps_only_the_newest_lines(self):
        text = "\n".join(str(i) for i in range(report.MAX_LINES + 50))
        out = report.scrub(text).splitlines()
        self.assertEqual(len(out), report.MAX_LINES)
        self.assertEqual(out[-1], str(report.MAX_LINES + 49))




if __name__ == "__main__":
    unittest.main()

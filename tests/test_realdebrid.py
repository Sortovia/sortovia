"""Real-Debrid client against a fake server: device sign-in, token refresh, torrent files, errors."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon", "script.kodisorter"))
import realdebrid as rdm  # noqa: E402


class FakeRD(object):
    def __init__(self):
        self.approved = False
        self.calls = []
        self.token = "tok1"

    def __call__(self, url, data=None, headers=None, timeout=30):
        self.calls.append((url, data, (headers or {}).get("Authorization")))
        j = lambda o, c=200: (c, json.dumps(o).encode())
        if "/device/code" in url:
            return j({"device_code": "DEV", "user_code": "ABCD", "interval": 5, "expires_in": 600,
                      "verification_url": "https://real-debrid.com/device"})
        if "/device/credentials" in url:
            return j({"client_id": "cid", "client_secret": "sec"}) if self.approved else j({"error": "pending"}, 403)
        if url.endswith("/oauth/v2/token"):
            assert data["grant_type"] == "http://oauth.net/grant_type/device/1.0"
            return j({"access_token": self.token, "refresh_token": "ref", "expires_in": 3600})
        if (headers or {}).get("Authorization") != "Bearer " + self.token:
            return j({"error": "bad_token"}, 401)
        if url.endswith("/torrents/info/T1"):
            return j({"status": "downloaded", "files": [
                {"path": "/Show/S01E01.mkv", "bytes": 100, "selected": 1},
                {"path": "/Show/sample.txt", "bytes": 1, "selected": 0},
                {"path": "/Show/S01E02.mkv", "bytes": 200, "selected": 1}], "links": ["L1", "L2"]})
        if url.endswith("/unrestrict/link"):
            return j({"download": "https://dl/" + data["link"], "filename": "x.mkv", "filesize": 100})
        return j({"error": "unknown"}, 404)


class RD(unittest.TestCase):
    def setUp(self):
        self.saved = {}
        self.http = FakeRD()
        self.t = [1000.0]
        self.rd = rdm.RD(lambda: dict(self.saved), lambda st: self.saved.update(st) or self.saved.clear() or
                         self.saved.update(st), http=self.http, now=lambda: self.t[0])

    def test_device_sign_in(self):
        dev = self.rd.device_start()
        self.assertEqual(dev["user_code"], "ABCD")
        self.assertFalse(self.rd.device_poll(dev))
        self.http.approved = True
        self.assertTrue(self.rd.device_poll(dev))
        self.assertTrue(self.rd.signed_in())
        self.assertEqual(self.saved["access_token"], "tok1")
        self.assertEqual(self.saved["refresh_token"], "ref")

    def test_files_links_and_refresh(self):
        self.http.approved = True
        self.rd.device_poll(self.rd.device_start())
        self.assertEqual(self.rd.torrent_files("T1"), [("S01E01.mkv", 100, "L1"), ("S01E02.mkv", 200, "L2")])
        self.http.token = "tok2"  # Real-Debrid expired the old token
        self.assertEqual(self.rd.unrestrict("L1"), ("https://dl/L1", "x.mkv", 100))
        self.assertEqual(self.saved["access_token"], "tok2")

    def test_errors(self):
        with self.assertRaises(rdm.RDError):
            self.rd.torrents()  # not signed in
        self.rd.use_api_token("tokX")
        with self.assertRaises(rdm.RDError):
            self.rd.torrents()  # 401 with no refresh token

    def test_lines(self):
        self.assertEqual(rdm.torrent_lines({"filename": "A", "status": "downloading", "progress": 45, "bytes": 4.2e9}),
                         ("A", "Real-Debrid is fetching it - 45% - 4.2 GB"))
        self.assertTrue(rdm.is_video("x.MKV"))


if __name__ == "__main__":
    unittest.main()

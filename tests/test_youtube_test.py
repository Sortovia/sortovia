"""The YouTube test refuses a bad download, reads format lists correctly, and cleans up after itself."""
import hashlib
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon", "script.kodisorter"))
import youtube_test as yt  # noqa: E402


class Parts(unittest.TestCase):
    def test_checksum_list(self):
        self.assertEqual(yt.checksum_for(b"aaa  yt-dlp.exe\nBBB  yt-dlp\n"), "bbb")
        self.assertEqual(yt.checksum_for(b"aaa  other\n"), "")

    def test_only_complete_files_count_without_ffmpeg(self):
        s = yt.summarize([
            {"vcodec": "avc1", "acodec": "mp4a", "height": 360, "url": "u", "protocol": "https"},
            {"vcodec": "vp9", "acodec": "none", "height": 2160, "url": "u", "protocol": "https"},
            {"vcodec": "none", "acodec": "opus", "url": "u", "protocol": "https"},
            {"vcodec": "avc1", "acodec": "mp4a", "height": 720, "url": "u", "protocol": "m3u8_native"}])
        self.assertEqual(s, {"total": 4, "whole_files": 1, "best_height": 360, "stream_files": 1, "stream_height": 720})


class Run(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def serve(self, app, want=None):
        def http(url):
            if url.endswith("SHA2-256SUMS"):
                return 200, ("%s  yt-dlp\n" % (want or hashlib.sha256(app).hexdigest())).encode()
            return 200, app
        return http

    def test_a_tampered_download_is_never_run(self):
        probe = mock.Mock()
        with mock.patch.object(yt, "_probe", probe):
            works, lines = yt.run(self.serve(b"evil", want="0" * 64), self.tmp)
        self.assertFalse(works)
        probe.assert_not_called()
        self.assertTrue(any("didn't match" in l for l in lines))
        self.assertEqual(os.listdir(self.tmp), [])

    def test_a_good_result_is_reported_and_the_copy_removed(self):
        def fake(path, url, out):
            self.assertTrue(os.path.exists(path))
            out.update(version="2026.1", summary={"total": 9, "whole_files": 1, "best_height": 360,
                                                  "stream_files": 0, "stream_height": 0})
        with mock.patch.object(yt, "_probe", fake):
            works, lines = yt.run(self.serve(b"app"), self.tmp)
        self.assertTrue(works)
        self.assertIn("up to 360p", lines[-1])
        self.assertEqual(os.listdir(self.tmp), [])

    def test_streams_alone_still_count(self):
        def fake(path, url, out):
            out.update(version="2026.1", summary={"total": 9, "whole_files": 0, "best_height": 0,
                                                  "stream_files": 3, "stream_height": 720})
        with mock.patch.object(yt, "_probe", fake):
            works, lines = yt.run(self.serve(b"app"), self.tmp)
        self.assertTrue(works)
        self.assertIn("720p", lines[-1])

    def test_youtube_refusing_is_reported(self):
        def fake(path, url, out):
            out.update(version="2026.1", error="Sign in to confirm you're not a bot")
        with mock.patch.object(yt, "_probe", fake):
            works, lines = yt.run(self.serve(b"app"), self.tmp)
        self.assertFalse(works)
        self.assertTrue(any("not a bot" in l for l in lines))

    def test_old_python_stops_before_downloading(self):
        http = mock.Mock()
        with mock.patch.object(yt, "MIN_PYTHON", (99, 0)):
            works, _ = yt.run(http, self.tmp)
        self.assertFalse(works)
        http.assert_not_called()


if __name__ == "__main__":
    unittest.main()

"""My releases: reading feeds, sending picks to Real-Debrid, and downloading them once ready."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon", "script.kodisorter"))
import feeds  # noqa: E402
import realdebrid as rdm  # noqa: E402
from test_library_folders import load_default  # noqa: E402

H1 = "a" * 40
RSS = ("""<?xml version="1.0"?><rss xmlns:torrent="http://xmlns.ezrss.it/0.1/" xmlns:torznab="http://torznab.com/schemas/2015/feed"><channel>
<item><title>My Short Film</title><torrent:magnetURI>magnet:?xt=urn:btih:%s&amp;dn=x</torrent:magnetURI>
<enclosure url="https://t.example/f.torrent?key=SECRET" length="1000" type="application/x-bittorrent"/></item>
<item><title>Podcast 12</title><link>https://t.example/dl/12.torrent?key=SECRET</link><size>500</size></item>
<item><title>Torznab one</title><torznab:attr name="infohash" value="%s"/><torznab:attr name="size" value="77"/></item>
<item><title>Just a web page</title><link>https://t.example/about</link></item>
</channel></rss>""" % (H1, "b" * 40)).encode()


class Parsing(unittest.TestCase):
    def test_rss_with_magnet_torrent_and_torznab(self):
        rows = feeds.parse(RSS, "Mine")
        self.assertEqual([r["title"] for r in rows], ["My Short Film", "Podcast 12", "Torznab one"])
        self.assertEqual(rows[0]["hash"], H1)
        self.assertEqual(rows[0]["size"], 1000)
        self.assertEqual(rows[1]["torrent_url"], "https://t.example/dl/12.torrent?key=SECRET")
        self.assertEqual(rows[2]["size"], 77)
        self.assertTrue(rows[2]["magnet"].startswith("magnet:?xt=urn:btih:" + "b" * 40))

    def test_atom(self):
        atom = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom film</title>'
                '<link href="magnet:?xt=urn:btih:%s"/></entry></feed>' % H1).encode()
        self.assertEqual(feeds.parse(atom)[0]["hash"], H1)

    def test_simple_json_list(self):
        body = json.dumps({"releases": [{"title": "Film", "magnet": "magnet:?xt=urn:btih:" + H1, "size": 5},
                                        {"title": "No link"}]}).encode()
        rows = feeds.parse(body)
        self.assertEqual([(r["title"], r["size"]) for r in rows], [("Film", 5)])

    def test_not_a_feed(self):
        for bad in (b"<html><body><p>Log in</html", b"{not json", b"plain words"):
            with self.assertRaises(ValueError):
                feeds.parse(bad)

    def test_same_release_on_two_sites_shows_once(self):
        a = feeds.parse(RSS, "A")
        b = feeds.parse(RSS, "B")
        self.assertEqual(len(feeds.merge([a, b])), 3)

    def test_filter_is_local_and_needs_every_word(self):
        rows = feeds.parse(RSS)
        self.assertEqual([r["title"] for r in feeds.matching(rows, "short FILM")], ["My Short Film"])
        self.assertEqual(len(feeds.matching(rows, "")), 3)


class FakeServer(object):
    """Real-Debrid and the tracker's file server."""
    def __init__(self):
        self.calls = []
        self.status = {"T1": "waiting_files_selection"}
        self.fail = None

    def __call__(self, url, data=None, headers=None, timeout=30):
        self.calls.append((url, data, (headers or {}).get("Authorization")))
        j = lambda o, c=200: (c, json.dumps(o).encode())
        if self.fail:
            raise OSError(self.fail)
        if url.endswith(".torrent?key=SECRET"):
            return 200, b"d8:announce3:urle"
        if url.endswith("/torrents/addMagnet"):
            return j({"id": "T1"}, 201)
        if url.endswith("/torrents/addTorrent"):
            self.status["T2"] = "downloaded"
            return j({"id": "T2"}, 201)
        if "/torrents/selectFiles/" in url:
            self.status[url.rsplit("/", 1)[-1]] = "downloading"
            return 204, b""
        if "/torrents/info/" in url:
            tid = url.rsplit("/", 1)[-1]
            st = self.status[tid]
            info = {"status": st, "filename": "Film", "progress": 40, "bytes": 100}
            if st == "downloaded":
                info.update(files=[{"path": "/Film/a.mkv", "bytes": 100, "selected": 1},
                                   {"path": "/Film/a.mp3", "bytes": 5, "selected": 1},
                                   {"path": "/Film/x.txt", "bytes": 1, "selected": 0}], links=["L1", "L2"])
            return j(info)
        if url.endswith("/unrestrict/link"):
            return j({"download": "https://dl/" + data["link"], "filename": data["link"] + ".bin", "filesize": 5})
        return j({"error": "unknown"}, 404)


def client(server):
    state = {"access_token": "tok", "expires": 9e12}
    return rdm.RD(lambda: dict(state), lambda st: None, http=server)


class Client(unittest.TestCase):
    def test_magnet_picks_files_then_is_ready_with_all_of_them(self):
        s = FakeServer()
        rd = client(s)
        self.assertEqual(rd.add_source({"magnet": "magnet:?xt=urn:btih:" + H1}), "T1")
        self.assertEqual(rd.check("T1")[0], "wait")
        self.assertEqual(s.status["T1"], "downloading")  # its files were picked
        kind, text = rd.check("T1")
        self.assertEqual(kind, "wait")
        self.assertIn("40%", text)
        s.status["T1"] = "downloaded"
        kind, files = rd.check("T1")
        self.assertEqual(kind, "ready")
        self.assertEqual([f[0] for f in files], ["a.mkv", "a.mp3"])  # audio too: podcasts count

    def test_torrent_file_is_uploaded_without_the_real_debrid_token(self):
        s = FakeServer()
        self.assertEqual(client(s).add_source({"torrent_url": "https://t.example/1.torrent?key=SECRET"}), "T2")
        tracker = [c for c in s.calls if "SECRET" in c[0]][0]
        self.assertIsNone(tracker[2])
        self.assertEqual([c for c in s.calls if c[0].endswith("addTorrent")][0][1], b"d8:announce3:urle")

    def test_a_page_instead_of_a_torrent_is_refused(self):
        rd = client(lambda url, data=None, headers=None, timeout=30: (200, b"<html>log in</html>"))
        with self.assertRaises(rdm.RDError):
            rd.add_source({"torrent_url": "https://t.example/1.torrent"})

    def test_bad_torrents_are_reported(self):
        for st in ("magnet_error", "error", "virus", "dead"):
            s = FakeServer()
            s.status["T1"] = st
            self.assertEqual(client(s).check("T1")[0], "failed")


class Watching(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        data = os.path.join(self.tmp, "data")
        os.makedirs(data)
        d = self.d = load_default(data)
        store = {}
        d.load_cache = lambda path: json.loads(store.get(os.path.basename(path), "{}"))
        d.save_cache = lambda path, v, verify=True: store.__setitem__(os.path.basename(path), json.dumps(v)) or True
        props = self.props = {}

        class Win:
            def getProperty(self, k): return props.get(k, "")
            def setProperty(self, k, v): props[k] = v
            def clearProperty(self, k): props.pop(k, None)
        sys.modules["xbmcgui"].Window = lambda n: Win()
        self.toasts = []
        self.logged = []
        d.toast = lambda m, ms=0: self.toasts.append(m)
        d.log = self.logged.append
        self.server = FakeServer()
        d.rd_client = lambda: client(self.server)
        self.got = []
        self.result = "done"

        def download(dlg, files, group="", folder=None, auto=False):
            self.got.append((files, group, folder, auto))
            return self.result
        d.rd_download = download
        self.rounds = 0
        test = self

        class Monitor:
            def waitForAbort(self, secs):
                test.rounds += 1
                test.tick(test.rounds)
                return test.rounds > 50  # Kodi is closing
        d.xbmc.Monitor = Monitor
        self.tick = lambda n: None

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def queue(self, *ids):
        self.d.rd_queue_save([{"id": i, "name": "Film", "folder": "E/"} for i in ids])

    def test_downloads_by_itself_when_real_debrid_has_it(self):
        self.queue("T1")

        def tick(n):
            if n == 3:
                self.server.status["T1"] = "downloaded"
        self.tick = tick
        self.d.rd_watch()
        self.assertEqual(len(self.got), 1)
        files, group, folder, auto = self.got[0]
        self.assertEqual([f[1] for f in files], ["L1.bin", "L2.bin"])
        self.assertEqual((group, folder, auto), ("Film", "E/", True))
        self.assertEqual(self.d.rd_queue(), [])
        self.assertEqual(self.props, {})

    def test_a_lost_connection_keeps_waiting(self):
        self.queue("T1")
        self.server.status["T1"] = "downloaded"
        self.server.fail = "connection reset"

        def tick(n):
            if n == 2:
                self.server.fail = None
        self.tick = tick
        self.d.rd_watch()
        self.assertEqual(len(self.got), 1)

    def test_stop_while_waiting_clears_the_list(self):
        self.queue("T1")

        def tick(n):
            self.props[self.d.PROP_RD_STOP] = "1"
        self.tick = tick
        self.d.rd_watch()
        self.assertEqual(self.got, [])
        self.assertEqual(self.d.rd_queue(), [])

    def test_stop_during_the_download_clears_the_list(self):
        self.queue("T1", "T2")
        self.server.status.update(T1="downloaded", T2="downloaded")
        self.result = "stopped"
        self.d.rd_watch()
        self.assertEqual(len(self.got), 1)
        self.assertEqual(self.d.rd_queue(), [])

    def test_kodi_closing_keeps_the_list_for_next_time(self):
        self.queue("T1")
        self.server.status["T1"] = "downloading"
        self.d.rd_watch()
        self.assertEqual(self.got, [])
        self.assertEqual([i["id"] for i in self.d.rd_queue()], ["T1"])
        self.assertEqual(self.props, {})

    def test_dead_torrent_is_dropped_and_said_out_loud(self):
        self.queue("T1")
        self.server.status["T1"] = "dead"
        self.d.rd_watch()
        self.assertEqual(self.got, [])
        self.assertTrue([t for t in self.toasts if "Film" in t])

    def test_opening_the_menu_shows_the_wait_with_a_stop(self):
        self.props[self.d.PROP_RD_WAIT] = "1 at Real-Debrid"
        items = self.d.menu_items("root")
        self.assertEqual(items[0]["action"], "rd_stop")

    def test_feed_addresses_with_keys_are_never_logged(self):
        self.d.save_cache(self.d.data_file(self.d.FEEDS_FILE), {"feeds": [{"name": "Mine", "url": "https://t/x?key=SECRET"}]})
        self.server.fail = "failed for https://t/x?key=SECRET"
        rows, failed = self.d.rd_read_feeds(self.server)
        self.assertEqual(rows, [])
        self.assertEqual(failed, ["Mine"])
        self.assertFalse([m for m in self.logged if "SECRET" in m])


if __name__ == "__main__":
    unittest.main()

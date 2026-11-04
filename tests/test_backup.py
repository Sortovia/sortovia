"""Library backup: counts, shrink warning, where it's saved, never backing up an empty library."""
import os
import shutil
import sys
import tempfile
import types
import unittest

ADDON = os.path.join(os.path.dirname(__file__), "..", "addon", "script.kodisorter")


class Backup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for n in ("xbmc", "xbmcvfs"):
            sys.modules[n] = types.ModuleType(n)
        vfs = sys.modules["xbmcvfs"]
        tmp = self.tmp

        def real(p):
            for pre in ("special://", "win-lib://removable/"):
                if p.startswith(pre):
                    p = os.path.join(tmp, p[len(pre):].replace(":", "").replace("\\", "/"))
            return p

        class File:
            def __init__(self, p, mode="r"):
                self.f = open(real(p), "wb" if mode == "w" else "rb")
            def readBytes(self, n=-1): return self.f.read(n)
            def write(self, b): self.f.write(bytes(b)); return True
            def close(self): self.f.close()

        class Stat:
            def __init__(self, p): self.p = real(p)
            def st_size(self): return os.path.getsize(self.p)
        vfs.File, vfs.Stat = File, Stat
        vfs.mkdirs = lambda p: os.makedirs(real(p), exist_ok=True)
        vfs.exists = lambda p: os.path.exists(real(p))
        vfs.listdir = lambda p: ([d for d in os.listdir(real(p)) if os.path.isdir(os.path.join(real(p), d))],
                                 [f for f in os.listdir(real(p)) if os.path.isfile(os.path.join(real(p), f))])
        vfs.rmdir = lambda p, force=False: shutil.rmtree(real(p), ignore_errors=True)
        sys.modules["xbmc"].getInfoLabel = lambda k: "21.2"
        self.real = real
        os.makedirs(real("special://database/"))
        open(real("special://database/MyVideos121.db"), "wb").write(b"old")
        open(real("special://database/MyVideos131.db"), "wb").write(b"sqlite-data")
        sys.path.insert(0, ADDON)
        sys.modules.pop("backup", None)
        import backup
        self.b = backup
        self.lib = {"VideoLibrary.GetMovies": 40, "VideoLibrary.GetTVShows": 12, "VideoLibrary.GetEpisodes": 357}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rpc(self, method, params):
        if method == "VideoLibrary.Export":
            out = self.real(params["options"]["path"]) + "/kodi_videodb_2026-11-04/"
            os.makedirs(out)
            open(out + "videodb.xml", "wb").write(b"<videodb><tvshow/></videodb>\n")
            return "OK"
        return {"limits": {"total": self.lib[method]}}

    def test_counts_and_shrink(self):
        c = self.b.counts(self.rpc)
        self.assertEqual(c, {"movies": 40, "shows": 12, "episodes": 357})
        self.assertEqual(self.b.shrunk(dict(c, episodes=0), c), "TV episodes: 357 then, 0 now")
        self.assertEqual(self.b.shrunk(dict(c, episodes=300), c), "")
        self.assertEqual(self.b.shrunk(c, {}), "")  # no backup yet

    def test_backup_saved_everywhere_and_pruned(self):
        places = [self.b.HOME_DIR, self.b.drive_dir("win-lib://removable/E:\\TV\\")]
        self.assertEqual(places[1], "win-lib://removable/E:\\_Kodi library backups/")
        sent = []
        for i in range(7):
            self.b.time.strftime = lambda f, i=i: "2026-11-0%d 1200" % (i + 1)
            info, saved = self.b.make_backup(places, lambda st, files: sent.append((st, [n for n, _ in files])) or True,
                                             rpc=self.rpc)
        self.assertEqual(saved, places + ["phone"])
        self.assertEqual(sent[-1][1], ["videodb.xml", "backup-info.json", "MyVideos131.db"])
        home = self.real(self.b.HOME_DIR)
        self.assertEqual(sorted(os.listdir(home)), ["2026-11-0%d 1200" % d for d in range(3, 8)])  # newest 5
        newest = os.path.join(home, "2026-11-07 1200")
        self.assertEqual(open(os.path.join(newest, "MyVideos131.db"), "rb").read(), b"sqlite-data")
        self.assertEqual(self.b.list_backups()[0][1]["counts"]["episodes"], 357)
        self.assertFalse([d for d in os.listdir(self.real("special://temp/")) if d.startswith("kodisorter-export")])

    def test_empty_library_is_never_backed_up(self):
        self.lib = dict.fromkeys(self.lib, 0)
        with self.assertRaises(IOError):
            self.b.make_backup([self.b.HOME_DIR], rpc=self.rpc)


if __name__ == "__main__":
    unittest.main()

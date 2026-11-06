"""Fix music tags: ID3v2.4 rewriting that keeps the audio, and how albums and artists are worked out."""
import os
import shutil
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon", "script.kodisorter"))
import id3write as iw  # noqa: E402
import musicfix as mf  # noqa: E402
import musictags  # noqa: E402

AUDIO = b"\xff\xfb\x90\x00" + bytes(range(256)) * 20 + b"\xff\x00\xff"
ART = b"\x00image/jpeg\x00\x03\x00" + b"\xff\xd8pretend-picture\xff\x00\xff\xd9" * 50


def v23(frames, flags=0, body_change=None):
    body = b""
    for name, data in frames:
        body += name.encode() + struct.pack(">I", len(data)) + b"\x00\x00" + data
    body = body_change(body) if body_change else body
    return b"ID3\x03\x00" + bytes([flags]) + iw.synchsafe(len(body)) + body


def latin(text):
    return b"\x00" + text.encode("latin-1")


def utf16(text):
    return b"\x01" + text.encode("utf-16")


def tags_of(data):
    return musictags.read_tags(lambda o, n: data[o:o + n], len(data))


def frames_of(data):
    return iw.parse(data[:iw.tag_size(data[:10])])


class Rewrite(unittest.TestCase):
    def old(self):
        return v23([("TPE1", latin("Band/Guest")), ("TALB", utf16("Café Record")), ("TIT2", latin("Song")),
                    ("TRCK", latin("3/12")), ("TYER", latin("2020")), ("TDAT", latin("1503")),
                    ("APIC", ART), ("COMM", b"\x00eng\x00a comment")]) + AUDIO

    def test_upgrades_and_keeps_audio_and_every_other_frame(self):
        new, old = iw.retag(self.old(), artists=["Band", "Guest"], display="Band & Guest", album_artist="Band")
        self.assertTrue(new.endswith(AUDIO))
        self.assertEqual(new[3], 4)
        version, frames = frames_of(new)
        self.assertEqual(version, 4)
        d = dict(frames)
        self.assertEqual(d["APIC"], ART)
        self.assertEqual(d["COMM"], b"\x00eng\x00a comment")
        self.assertEqual(iw.text_values(frames, "TALB"), ["Café Record"])
        self.assertEqual(iw.text_values(frames, "TPE1"), ["Band & Guest"])
        self.assertEqual(iw.text_values(frames, "TPE2"), ["Band"])
        self.assertEqual(iw.text_values(frames, "TDRC"), ["2020-03-15"])
        self.assertEqual(iw.user_values(frames, "ARTISTS"), ["Band", "Guest"])
        self.assertNotIn("TYER", d)
        t = tags_of(new)
        self.assertEqual((t["artist"], t["albumartist"], t["album"], t["track"]), ("Band & Guest", "Band", "Café Record", 3))

    def test_year_replaces_a_bad_date(self):
        data = v23([("TPE1", latin("Band")), ("TYER", latin("0000"))]) + AUDIO
        once = iw.retag(data, year="2022")[0]
        self.assertEqual(iw.text_values(frames_of(once)[1], "TDRC"), ["2022"])
        self.assertEqual(iw.text_values(frames_of(iw.retag(once, year="2021")[0])[1], "TDRC"), ["2021"])

    def test_undo_gives_back_the_exact_file(self):
        data = self.old()
        new, old = iw.retag(data, artists=["Band", "Guest"], display="Band & Guest", album_artist="Band")
        self.assertEqual(iw.put_back(new, old), data)

    def test_running_twice_doesnt_duplicate(self):
        once = iw.retag(self.old(), artists=["Band", "Guest"], display="Band & Guest", album_artist="Band")[0]
        twice = iw.retag(once, artists=["Band", "Guest"], display="Band & Guest", album_artist="Band")[0]
        self.assertEqual(once, twice)

    def test_a_file_with_no_tag_keeps_its_audio(self):
        new, old = iw.retag(AUDIO, display="Band", album_artist="Band")
        self.assertEqual(old, b"")
        self.assertTrue(new.endswith(AUDIO))
        self.assertEqual(iw.put_back(new, old), AUDIO)

    def test_id3v1_tail_is_part_of_the_audio_kept(self):
        tail = b"TAG" + b"\0" * 125
        new = iw.retag(AUDIO + tail, display="Band")[0]
        self.assertTrue(new.endswith(AUDIO + tail))

    def test_v22_frames_are_renamed(self):
        body = b"TP1" + b"\x00\x00\x05" + latin("Band") + b"PIC" + struct.pack(">I", 9)[1:] + b"\x00JPG\x03\x00abc"
        data = b"ID3\x02\x00\x00" + iw.synchsafe(len(body)) + body + AUDIO
        new = iw.retag(data, album_artist="Band")[0]
        version, frames = frames_of(new)
        self.assertEqual(iw.text_values(frames, "TPE1"), ["Band"])
        self.assertTrue(dict(frames)["APIC"].startswith(b"\x00image/jpeg\x00\x03\x00abc"))
        self.assertTrue(new.endswith(AUDIO))

    def test_unsynchronised_v23(self):
        data = v23([("TPE1", latin("Band"))], flags=0x80, body_change=lambda b: b.replace(b"\xff", b"\xff\x00"))
        self.assertEqual(iw.text_values(iw.parse(data)[1], "TPE1"), ["Band"])

    def test_true_multi_values_are_read(self):
        data = b"\x03" + b"One\x00Two"
        self.assertEqual(iw._text(data), ["One", "Two"])
        two = b"\x01" + "One".encode("utf-16") + b"\x00\x00" + "Two".encode("utf-16")
        self.assertEqual(iw._text(two), ["One", "Two"])

    def test_tags_it_cant_safely_change_are_refused(self):
        compressed = b"TPE1" + struct.pack(">I", 2) + b"\x00\x80" + b"ab"
        for bad in (b"ID3\x03\x00\x00" + iw.synchsafe(len(compressed)) + compressed,
                    b"ID3\x03\x00\x00" + iw.synchsafe(14) + b"TPE1" + struct.pack(">I", 500) + b"\0\0xxxx",
                    b"ID3\x03\x00\x00" + iw.synchsafe(14) + b"\xff\xfe\xfd\xfc" + b"\0" * 10):
            with self.assertRaises(iw.Unsupported):
                iw.retag(bad + AUDIO, album_artist="Band")


def track(name, artist, albumartist="", version=3, artists=None):
    return {"name": name, "version": version, "album": "Record", "artist": artist, "albumartist": albumartist, "artists": artists}


class Plans(unittest.TestCase):
    def test_splitting_credits(self):
        for credit in ("Band/Guest", "Band & Guest", "Band, Guest", "Band and Guest", "Band feat. Guest", "Band ft. Guest",
                       "Band x Guest", "Band; Guest"):
            self.assertEqual(mf.split_artists(credit), ["Band", "Guest"], credit)
        self.assertEqual(mf.split_artists("One, Two, One, Three"), ["One", "Two", "Three"])
        self.assertEqual(mf.split_artists("BAND"), ["BAND"])

    def test_a_folder_name_keeps_a_band_whole(self):
        self.assertEqual(mf.split_artists("One & Two", ["One & Two"]), ["One & Two"])
        self.assertEqual(mf.split_artists("One & Two/Guest", ["One & Two"]), ["One & Two", "Guest"])
        self.assertEqual(mf.split_artists("Bandx & Guest", ["Band"]), ["Bandx", "Guest"])

    def test_mixed_album_artists_become_one(self):
        plan = mf.plan_album([track("1.mp3", "Band/Guest"), track("2.mp3", "GUEST & BAND", "GUEST & BAND")], ["Band"])
        self.assertEqual(plan["album_artist"], "Band")
        self.assertEqual([c["artists"] for c in plan["changes"]], [["Band", "Guest"], ["GUEST", "BAND"]])

    def test_spelling_follows_the_folder(self):
        plan = mf.plan_album([track("1.mp3", "BAND, Guest")], ["Band"], {"band": "Band"})
        self.assertEqual(plan["changes"][0]["artists"], ["Band", "Guest"])
        self.assertEqual(plan["changes"][0]["display"], "Band & Guest")

    def test_an_agreed_album_artist_stays_unless_its_a_list(self):
        keep = mf.plan_album([track("1.mp3", "Other", "Other Band"), track("2.mp3", "Guest", "Other Band")], ["Band"])
        self.assertEqual(keep["album_artist"], "Other Band")
        fixed = mf.plan_album([track("1.mp3", "Band & One", "Band & One")], ["Band"])
        self.assertEqual(fixed["album_artist"], "Band")

    def test_album_by_someone_else_in_the_folder(self):
        names = mf.plan_album([track("1.mp3", "Alias & Friend")], ["Band", "Alias"])
        self.assertEqual(names["album_artist"], "Alias")
        shared = mf.plan_album([track("1.mp3", "Star/One"), track("2.mp3", "Star/Two")], ["Band"])
        self.assertEqual(shared["album_artist"], "Star")
        nobody = mf.plan_album([track("1.mp3", "One"), track("2.mp3", "Two")], ["Band"])
        self.assertEqual(nobody["album_artist"], "Band")

    def test_nothing_to_do_when_already_right(self):
        t = track("1.mp3", "Band & Guest", "Band", version=4, artists=["Band", "Guest"])
        self.assertEqual(mf.plan_album([t], ["Band"])["changes"], [])

    def test_year_of_0000_takes_the_albums_year(self):
        tracks = [dict(track("%d.mp3" % i, "Band", "Band", version=4), date="2022") for i in range(3)]
        tracks.append(dict(track("10.mp3", "Band", "Band", version=4), date="0000"))
        plan = mf.plan_album(tracks, ["Band"])
        self.assertEqual([(c["name"], c["year"], c["why"]) for c in plan["changes"]], [("10.mp3", "2022", "year")])

    def test_no_year_to_borrow_changes_nothing(self):
        t = dict(track("1.mp3", "Band", "Band", version=4), date="0000")
        self.assertEqual(mf.plan_album([t], ["Band"])["changes"], [])

    def test_only_the_version_changes_when_tags_are_right(self):
        c = mf.plan_album([track("1.mp3", "Band", "Band")], ["Band"])["changes"]
        self.assertEqual(c[0]["why"], "ID3v2.3 to ID3v2.4")
        self.assertIsNone(c[0]["artists"])


class Spellings(unittest.TestCase):
    def test_one_spelling_for_each_artist(self):
        out = mf.spellings_from(["BAND/Guest", "Band", "GUEST", "ONLY CAPS", "guest & Band"], ["Top Band"])
        self.assertEqual(out["band"], "Band")
        self.assertEqual(out["guest"], "Guest")
        self.assertEqual(out["only caps"], "ONLY CAPS")
        self.assertEqual(out["top band"], "Top Band")
        self.assertEqual(mf.spellings_from(["TOP BAND", "TOP BAND"], ["Top Band"])["top band"], "Top Band")


class WholeTool(unittest.TestCase):
    """Fix music tags from the menu, on a pretend drive, then undo."""
    def setUp(self):
        from test_library_folders import load_default
        from unittest import mock
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        d = self.d = load_default(os.path.join(self.tmp, "data"))
        drive = os.path.join(self.tmp, "drive")

        def real(p):
            return os.path.join(drive, p.split("D:/", 1)[1]) if "D:/" in p else p

        class File:
            def __init__(s, p, mode="r"):
                s.f = open(real(p), "wb" if mode == "w" else "rb")
            def read(s): return s.f.read().decode()
            def readBytes(s, n=-1): return s.f.read(n)
            def seek(s, o, w=0): s.f.seek(o, w)
            def write(s, b):
                s.f.write(b.encode() if isinstance(b, str) else bytes(b))
                return True
            def close(s): s.f.close()

        def listdir(p):
            r = real(p)
            names = os.listdir(r) if os.path.isdir(r) else []
            return ([n for n in names if os.path.isdir(os.path.join(r, n))],
                    [n for n in names if os.path.isfile(os.path.join(r, n))])
        vfs = d.xbmcvfs
        vfs.File, vfs.listdir = File, listdir
        vfs.exists = lambda p: os.path.exists(real(p))
        vfs.mkdirs = lambda p: os.makedirs(real(p), exist_ok=True)
        vfs.delete = lambda p: os.path.exists(real(p)) and os.remove(real(p))
        vfs.rmdir = lambda p, force=False: shutil.rmtree(real(p), True) or True
        for name, value in (("xbmcvfs", vfs), ("xbmc", d.xbmc)):
            patcher = mock.patch.object(d.backup, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        d.xbmc.getInfoLabel = lambda k: "21.2"
        d.log = lambda m: None
        props = {}
        d.home = lambda: type("W", (), {"getProperty": lambda s, k: props.get(k, ""),
                                        "setProperty": lambda s, k, v: props.__setitem__(k, v),
                                        "clearProperty": lambda s, k: props.pop(k, None)})()
        d.xbmcgui.DialogProgress = type("P", (), {"create": lambda s, *a: None, "update": lambda s, *a: None,
                                                  "close": lambda s: None, "iscanceled": lambda s: False})
        self.addCleanup(d.save_cache, d.data_file("music_tags.json"), {}, False)
        self.root = "win-lib://removable/D:/Music/"
        d.library_folder = lambda kind, dlg=None: self.root
        self.folder = os.path.join(drive, "Music", "Band", "Singles", "2025.05.30 - Record (With Guest)")
        os.makedirs(self.folder)
        self.files = {}
        for name, frames in (("01 - Song.mp3", [("TPE1", latin("Band/Guest")), ("TALB", latin("Record")), ("APIC", ART)]),
                             ("02 - Mix.mp3", [("TPE1", latin("GUEST & BAND")), ("TALB", latin("Record")),
                                               ("TPE2", latin("GUEST & BAND"))]),
                             ("no album.mp3", [("TPE1", latin("Band"))])):
            self.files[name] = v23(frames) + AUDIO
            with open(os.path.join(self.folder, name), "wb") as f:
                f.write(self.files[name])
        with open(os.path.join(self.folder, "cover.webp"), "wb") as f:
            f.write(b"pic")
        self.rpc = []
        import missing
        patcher = mock.patch.object(missing, "_rpc", lambda m, p: self.rpc.append((m, p)) or {})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.said = []
        self.copy_ok = True
        self.removed = 0
        self.mode = 0
        self.choices = []
        self.picks = [0]
        test = self

        class Dlg:
            def ok(s, title, text): test.said.append(text)
            def textviewer(s, title, text): test.said.append(text)
            def multiselect(s, title, rows, **k): return test.picks
            def select(s, title, rows, **k):
                test.choices.append(title)
                return test.mode if title.startswith("Fix music") else 0
            def yesno(s, title, text, **k):
                test.said.append(text)
                return True
        self.dlg = Dlg()

    def read(self, name):
        with open(os.path.join(self.folder, name), "rb") as f:
            return f.read()

    def test_fix_then_undo(self):
        self.d._update_music_library = lambda folders, stage, start=0: self.scanned.append(list(folders)) or "All done."
        self.scanned = []
        self.assertEqual(self.d.fix_music_tags(self.dlg), 2, self.said)
        self.assertEqual(self.scanned, [[self.root + "Band/Singles/2025.05.30 - Record (With Guest)/"]])
        self.assertIn("All done.", self.said[-1])
        for name in ("01 - Song.mp3", "02 - Mix.mp3"):
            new = self.read(name)
            self.assertTrue(new.endswith(AUDIO))
            version, frames = frames_of(new)
            self.assertEqual(version, 4)
            self.assertEqual(iw.text_values(frames, "TPE2"), ["Band"])
            self.assertEqual(sorted(iw.user_values(frames, "ARTISTS")), ["Band", "Guest"])
        self.assertEqual(iw.user_values(frames_of(self.read("01 - Song.mp3"))[1], "ARTISTS"), ["Band", "Guest"])
        self.assertEqual(iw.user_values(frames_of(self.read("02 - Mix.mp3"))[1], "ARTISTS"), ["Guest", "Band"])  # as credited
        self.assertEqual(dict(frames_of(self.read("01 - Song.mp3"))[1])["APIC"], ART)
        self.assertEqual(self.read("no album.mp3"), self.files["no album.mp3"])  # left alone
        self.assertEqual([n for n in os.listdir(self.folder) if n.endswith(".tmp")], [])
        self.assertEqual(self.d.undo_music_tags(self.dlg), 2, self.said)
        for name in self.files:
            self.assertEqual(self.read(name), self.files[name], name)

    def test_one_choice_and_one_result_popup(self):
        self.d._update_music_library = lambda folders, stage, start=0: "All done."
        self.said.clear()
        self.assertEqual(self.d.fix_music_tags(self.dlg), 2)
        self.assertEqual(self.choices, ["Fix music tags (MP3)", "Fix tags by"])
        self.assertEqual(len(self.said), 1)  # the result, nothing in between

    def test_show_changes_mode_shows_them_first(self):
        self.d._update_music_library = lambda folders, stage, start=0: "All done."
        self.mode = 2
        self.said.clear()
        self.d.fix_music_tags(self.dlg)
        self.assertIn("Record  (album artist: Band)", self.said[0])
        self.assertIn("no album.mp3 (no album tag)", self.said[0])

    def test_tags_only_mode_doesnt_touch_the_library(self):
        self.d._update_music_library = lambda *a, **k: self.fail("shouldn't update")
        self.mode = 3
        self.assertEqual(self.d.fix_music_tags(self.dlg), 2)

    def update_with(self, counts, files_ok=True, folders=("win-lib://a/", "win-lib://a/", "win-lib://b/"), known=None):
        """_update_music_library with a song count for each time it's asked. Returns its message."""
        import musicart
        from unittest import mock
        seq = list(counts)
        d = self.d
        d._song_count = lambda: seq.pop(0) if len(seq) > 1 else seq[0]
        d._run_music_job = lambda start, limit=1800, is_scan=True: start() or True
        d._apply_music_art = lambda wanted, step=None: (3, [])
        d._music_albums = lambda n: []
        d._save_music_copy = lambda: self.copy_ok
        d._remove_duplicate_songs_now = lambda: self.removed
        patches = [mock.patch.object(d.backup, "newest_db", lambda p=None: ("MyMusic83.db", b"x")),
                   mock.patch.object(musicart, "song_folders", lambda path: known or {}),
                   mock.patch.object(d.drive_letter, "library_files", lambda *a: []),
                   mock.patch.object(d.drive_letter, "diagnose", lambda *a: {"moved": [], "lost": [] if files_ok else ["D"], "ok": ["D"]})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        stage = lambda a, b, t: (lambda done, total, name: False)
        return d._update_music_library(list(folders), stage)

    def test_update_scans_only_changed_folders_then_cleans(self):
        self.assertIn("up to date: 175 songs", self.update_with([175, 175, 175]))
        self.assertEqual([(m, p.get("directory")) for m, p in self.rpc],
                         [("AudioLibrary.Scan", "win-lib://a/"), ("AudioLibrary.Scan", "win-lib://b/"), ("AudioLibrary.Clean", None)])

    def test_update_uses_the_address_kodi_already_has(self):
        """Scanning the same folder written another way is what added every song twice."""
        import musicart
        kodi = "win-lib://removable/D:\\\\Music\\Band\\Record\\"
        key = musicart._folder_key(kodi)
        self.update_with([5, 5, 5], folders=["win-lib://removable/D:\\\\Music\\Band\\Record/"], known={key: kodi})
        self.assertEqual(self.rpc[0][1]["directory"], kodi)
        self.assertFalse(self.rpc[0][1]["showdialogs"])

    def test_update_stops_before_cleaning_if_the_library_shrank(self):
        self.assertIn("can now show 0 songs, down from 175", self.update_with([175, 0]))
        self.assertEqual([m for m, _ in self.rpc], ["AudioLibrary.Scan", "AudioLibrary.Scan"])

    def test_rescan_one_album_scans_only_the_folder_picked(self):
        from unittest import mock
        d = self.d
        d._music_albums = lambda n: [{"name": "Zed", "folder": "win-lib://z/", "art": ""},
                                     {"name": "Alpha", "folder": "win-lib://a/", "art": ""},
                                     {"name": "Alpha", "folder": "win-lib://a/", "art": ""}]
        patcher = mock.patch.object(d.backup, "newest_db", lambda p=None: ("MyMusic83.db", b"x"))
        patcher.start()
        self.addCleanup(patcher.stop)
        seen = {}
        self.dlg.select = lambda title, rows: seen.setdefault("rows", rows) and 0
        d._update_music_library = lambda folders, stage, start=0: seen.update(folders=folders) or "Done."
        self.assertTrue(d.rescan_one_album(self.dlg))
        self.assertEqual(seen["rows"], ["Alpha", "Zed"])
        self.assertEqual(seen["folders"], ["win-lib://a/"])
        self.assertEqual(self.said[-1], "Done.")

    def test_no_scan_without_a_saved_copy(self):
        self.copy_ok = False
        self.assertIn("wasn't updated", self.update_with([175, 175]))
        self.assertEqual(self.rpc, [])

    def test_art_check_after_an_update_skips_albums_already_fine(self):
        import musicart
        from unittest import mock
        looked = []
        patcher = mock.patch.object(musicart, "needs_art", lambda albums, listdir, step=None: looked.extend(a["name"] for a in albums) or [])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.update_with([175, 175, 175])
        looked.clear()
        self.d._music_albums = lambda n: [{"name": "Fine", "folder": "win-lib://other/", "art": "x"},
                                          {"name": "No art", "folder": "win-lib://other2/", "art": ""},
                                          {"name": "Changed", "folder": "win-lib://a/", "art": "x"}]
        self.d._update_music_library(["win-lib://a/"], lambda a, b, t: (lambda done, total, name: False))
        self.assertEqual(looked, ["No art", "Changed"])

    def test_songs_left_pointing_at_missing_folders_dont_count(self):
        import musicart
        import sqlite3
        path = os.path.join(self.tmp, "m.db")
        c = sqlite3.connect(path)
        c.executescript("""CREATE TABLE song (idSong INTEGER PRIMARY KEY, idPath INTEGER);
          CREATE TABLE album (idAlbum INTEGER); CREATE TABLE artist (idArtist INTEGER); CREATE TABLE source (idSource INTEGER);
          CREATE TABLE path (idPath INTEGER PRIMARY KEY, strPath TEXT);
          INSERT INTO song (idPath) VALUES (4), (4), (163); INSERT INTO path VALUES (163, 'x');""")
        c.commit()
        c.close()
        info = musicart.status(path)
        self.assertEqual((info["song"], info["linked"]), (3, 1))
        self.assertIn("3 songs (1 can be shown)", musicart.status_lines(info)[0])

    def test_update_doesnt_clean_if_music_is_missing_from_the_drive(self):
        self.update_with([175, 175], files_ok=False)
        self.assertNotIn("AudioLibrary.Clean", [m for m, _ in self.rpc])

    def make_dupes(self):
        import sqlite3
        path = os.path.join(self.tmp, "dupes.db")
        c = sqlite3.connect(path)
        c.executescript("""CREATE TABLE path (idPath INTEGER PRIMARY KEY, strPath TEXT);
          CREATE TABLE song (idSong INTEGER PRIMARY KEY, idPath INTEGER, strFileName TEXT, iTimesPlayed INTEGER);
          CREATE TABLE gone (idSong INTEGER);
          CREATE TRIGGER tgrDeleteSong AFTER DELETE ON song FOR EACH ROW BEGIN INSERT INTO gone VALUES (old.idSong); END;""")
        c.execute("INSERT INTO path VALUES (1, ?)", ("win-lib://removable/D:\\\\Music\\Band\\Record\\",))
        c.execute("INSERT INTO path VALUES (2, ?)", ("win-lib://removable/D:\\\\Music\\Band\\Record/",))
        c.execute("INSERT INTO path VALUES (3, ?)", ("win-lib://removable/D:\\\\Music\\Band\\Other\\",))
        c.executemany("INSERT INTO song (idSong, idPath, strFileName, iTimesPlayed) VALUES (?,?,?,?)",
                      [(1, 1, "01 - Song.mp3", 3), (2, 1, "02 - Mix.mp3", 0), (3, 3, "01 - Song.mp3", 1), (4, 2, "01 - song.MP3", 2)])
        c.commit()
        c.close()
        return path

    def test_duplicates_keep_the_newest_and_add_up_plays(self):
        import musicart
        import sqlite3
        path = self.make_dupes()
        self.assertEqual(musicart.remove_duplicates(path), 1)
        c = sqlite3.connect(path)
        self.assertEqual(c.execute("SELECT idSong, iTimesPlayed FROM song ORDER BY idSong").fetchall(), [(2, 0), (3, 1), (4, 5)])
        self.assertEqual(c.execute("SELECT idSong FROM gone").fetchall(), [(1,)])  # Kodi's own clean-up trigger ran
        c.close()
        self.assertEqual(musicart.remove_duplicates(path), 0)

    def test_same_file_name_in_another_folder_isnt_a_duplicate(self):
        import musicart
        import sqlite3
        musicart.remove_duplicates(self.make_dupes())
        c = sqlite3.connect(os.path.join(self.tmp, "dupes.db"))
        self.assertEqual(c.execute("SELECT COUNT(*) FROM song WHERE idPath = 3").fetchone()[0], 1)
        c.close()

    def test_song_folders_gives_kodis_own_address(self):
        import musicart
        path = self.make_dupes()
        found = musicart.song_folders(path)
        self.assertEqual(found[musicart._folder_key("win-lib://removable/D:/Music/Band/Other/")],
                         "win-lib://removable/D:\\\\Music\\Band\\Other\\")

    def test_second_run_doesnt_read_unchanged_files_again(self):
        vfs = self.d.xbmcvfs
        drive = os.path.join(self.tmp, "drive")
        vfs.Stat = lambda p: type("S", (), {"st_size": lambda s: os.path.getsize(os.path.join(drive, p.split("D:/", 1)[1])),
                                            "st_mtime": lambda s: 1000})()
        step = lambda done, total, name: False
        real = self.d._track_info
        reads = []
        self.d._track_info = lambda p, n: reads.append(n) or real(p, n)
        self.d._plan_music_tags(self.root, step)
        self.assertEqual(len(reads), 3)
        reads.clear()
        plans, _, _ = self.d._plan_music_tags(self.root, step)
        self.assertEqual(reads, [])
        self.assertEqual(len(plans), 1)
        with open(os.path.join(self.folder, "01 - Song.mp3"), "ab") as f:
            f.write(b"x")
        self.d._plan_music_tags(self.root, step, quick=True)
        self.assertEqual(reads, [])  # a quick scan trusts what it saved
        self.d._plan_music_tags(self.root, step)
        self.assertEqual(reads, ["01 - Song.mp3"])  # a full scan notices

    def test_quick_scan_doesnt_ask_the_drive_about_known_files(self):
        vfs = self.d.xbmcvfs
        drive = os.path.join(self.tmp, "drive")
        asked = []

        def stat(p):
            asked.append(p)
            return type("S", (), {"st_size": lambda s: os.path.getsize(os.path.join(drive, p.split("D:/", 1)[1])),
                                  "st_mtime": lambda s: 1000})()
        vfs.Stat = stat
        step = lambda done, total, name: False
        self.d._plan_music_tags(self.root, step)
        self.assertEqual(len(asked), 3)
        asked.clear()
        self.d._plan_music_tags(self.root, step, quick=True)
        self.assertEqual(asked, [])

    def test_a_fix_updates_what_a_quick_scan_trusts(self):
        vfs = self.d.xbmcvfs
        drive = os.path.join(self.tmp, "drive")
        vfs.Stat = lambda p: type("S", (), {"st_size": lambda s: os.path.getsize(os.path.join(drive, p.split("D:/", 1)[1])),
                                            "st_mtime": lambda s: 1000})()
        self.d._update_music_library = lambda folders, stage, start=0: "All done."
        self.assertEqual(self.d.fix_music_tags(self.dlg), 2)
        self.assertEqual(self.d.fix_music_tags(self.dlg), 0)
        self.assertIn("already up to date", self.said[-1])

    def fake_plans(self):
        one = ("Record", "f1", {"album_artist": "Band", "changes": [{"name": "1"}]}, [{"artist": "Band/Guest"}])
        two = ("Other", "f2", {"album_artist": "Band", "changes": [{"name": "2"}, {"name": "3"}]}, [{"artist": "Band"}])
        three = ("Solo", "f3", {"album_artist": "Star", "changes": [{"name": "4"}]}, [{"artist": "Star & Guest"}])
        return [one, two, three]

    def library(self):
        return [{"file": "1.mp3", "folder": "win-lib://x\\Rec\\", "artist": "Band/Guest", "album": "Record"},
                {"file": "2.mp3", "folder": "win-lib://x\\Rec\\", "artist": "BAND", "album": "Record"},
                {"file": "1.mp3", "folder": "win-lib://x\\Sol\\", "artist": "Star & Guest", "album": "Solo"},
                {"file": "1.mp3", "folder": "win-lib://x\\Oth\\", "artist": "Other", "album": "Else"}]

    def test_choosing_by_artist_lists_each_person(self):
        seen = {}
        self.dlg.select = lambda title, rows: seen.update(how=rows) or 0
        self.dlg.multiselect = lambda title, rows: seen.setdefault("rows", rows) and [rows.index("Guest")]
        chosen = self.d._pick_music(self.dlg, self.library())
        self.assertEqual(seen["how"], ["Artist", "Album"])
        self.assertEqual(seen["rows"], ["Band", "Guest", "Other", "Star"])
        self.assertEqual([s["album"] for s in chosen], ["Record", "Solo"])

    def test_choosing_by_album(self):
        seen = {}
        self.dlg.select = lambda title, rows: 1
        self.dlg.multiselect = lambda title, rows: seen.setdefault("rows", rows) and [0]
        chosen = self.d._pick_music(self.dlg, self.library())
        self.assertEqual(seen["rows"], ["Else (1 tracks)", "Record (2 tracks)", "Solo (1 tracks)"])
        self.assertEqual([s["artist"] for s in chosen], ["Other"])

    def test_a_chosen_song_brings_its_whole_album_folder(self):
        songs = self.library()
        out = self.d._whole_folders(songs, [songs[0]])
        self.assertEqual([n for _, n in out], ["1.mp3", "2.mp3"])
        self.assertEqual(out[0][0], "win-lib://x\\Rec\\1.mp3")

    def test_quick_scan_starts_from_kodis_list_and_never_lists_the_drive(self):
        songs = [{"file": "01 - Song.mp3", "folder": self.root + "Band/Singles/2025.05.30 - Record (With Guest)/", "artist": "Band/Guest", "album": "Record"},
                 {"file": "99 - Elsewhere.mp3", "folder": self.root + "Nobody/", "artist": "Nobody", "album": "Else"}]
        self.d._library_mp3s = lambda: songs
        self.d.walk = lambda root: self.fail("a quick scan shouldn't list the drive")
        read = []
        real = self.d._track_info
        self.d._track_info = lambda p, n: read.append(n) or real(p, n)
        self.d._update_music_library = lambda folders, stage, start=0: "All done."
        self.picks = [0]  # Band
        self.assertEqual(self.d.fix_music_tags(self.dlg), 1)
        self.assertNotIn("99 - Elsewhere.mp3", read)

    def test_holding_an_artist_reads_only_that_artist(self):
        songs = [{"file": "01 - Song.mp3", "folder": self.root + "Band/Singles/2025.05.30 - Record (With Guest)/", "artist": "Band/Guest", "album": "Record"},
                 {"file": "99 - Elsewhere.mp3", "folder": self.root + "Nobody/", "artist": "Nobody", "album": "Else"}]
        self.d._library_mp3s = lambda: songs
        self.d.walk = lambda root: self.fail("shouldn't list the drive")
        read = []
        real = self.d._track_info
        self.d._track_info = lambda p, n: read.append(n) or real(p, n)
        self.d._update_music_library = lambda folders, stage, start=0: "All done."
        self.choices.clear()
        self.assertEqual(self.d.fix_music_tags(self.dlg, "Guest"), 1)
        self.assertEqual(self.choices, [])
        self.assertNotIn("99 - Elsewhere.mp3", read)
        self.assertEqual(self.d.fix_music_tags(self.dlg, "Who"), 0)
        self.assertIn("no MP3s for Who", self.said[-1])

    def test_skipping_the_question_is_off_until_chosen(self):
        addon = sys.modules["xbmcaddon"].Addon
        self.addCleanup(lambda: delattr(addon, "getSetting") if hasattr(addon, "getSetting") else None)
        addon.getSetting = lambda s, k: ""  # Kodi hasn't loaded the new setting yet
        self.assertFalse(self.d.setting_on("context_auto", False))
        self.assertTrue(self.d.setting_on("check_updates"))
        addon.getSetting = lambda s, k: "true"
        self.assertTrue(self.d.setting_on("context_auto", False))
        addon.getSetting = lambda s, k: "false"
        self.assertFalse(self.d.setting_on("check_updates"))

    def test_artist_setting_skips_the_question(self):
        self.d._update_music_library = lambda folders, stage, start=0: "All done."
        self.d.setting_on = lambda name, default=True: name == "context_auto"
        self.said.clear()
        self.assertEqual(self.d.fix_music_tags(self.dlg, "Guest"), 2)
        self.assertEqual(len(self.said), 1)  # the result only

    def test_context_menu_finds_the_artists_albums(self):
        plans = self.fake_plans()
        self.assertEqual([c[0] for c in self.d._plans_for_artist(plans, "Guest")], ["Record", "Solo"])
        self.assertEqual([c[0] for c in self.d._plans_for_artist(plans, "band")], ["Record", "Other"])
        self.assertEqual(self.d._plans_for_artist(plans, "Ban"), [])

    def test_context_menu_runs_for_one_artist_and_asks_once(self):
        self.d._update_music_library = lambda folders, stage, start=0: "All done."
        self.said.clear()
        self.choices.clear()
        self.assertEqual(self.d.fix_music_tags(self.dlg, "Guest"), 2)
        self.assertEqual(self.choices, [])  # no choice of how
        self.assertIn("for Guest", self.said[0])
        self.said.clear()
        self.assertEqual(self.d.fix_music_tags(self.dlg, "Nobody Here"), 0)
        self.assertIn("Nobody Here's MP3 tags are already up to date", self.said[-1])

    def test_nothing_chosen_changes_nothing(self):
        self.picks = []
        self.assertEqual(self.d.fix_music_tags(self.dlg), 0)
        for name in self.files:
            self.assertEqual(self.read(name), self.files[name])

    def test_running_again_finds_nothing_more(self):
        self.d._update_music_library = lambda folders, stage, start=0: "All done."
        self.d.fix_music_tags(self.dlg)
        self.assertEqual(self.d.fix_music_tags(self.dlg), 0)
        self.assertIn("already up to date", self.said[-1])


class PictureCache(unittest.TestCase):
    def setUp(self):
        from test_library_folders import load_default
        from unittest import mock
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        d = self.d = load_default(os.path.join(self.tmp, "data"))
        self.made = []
        self.there = {"special://profile/advancedsettings.xml"}
        d.xbmcvfs.exists = lambda p: p in self.there
        d.xbmcvfs.mkdirs = lambda p: self.made.append(p)
        d.log = lambda m: None
        self.drive = True
        d._listdir_or_nothing = lambda p: (["Music"], []) if self.drive else ([], [])
        self.xml = (b"<advancedsettings><pathsubstitution><substitute><from>special://profile/Thumbnails/</from>"
                    b"<to>win-lib://removable/D://KodiThumbnails/</to></substitute></pathsubstitution></advancedsettings>")
        patcher = mock.patch.object(d.backup, "_read", lambda p: self.xml)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_makes_the_folder_and_its_sixteen_parts(self):
        self.assertEqual(self.d.ensure_picture_cache_folder(), "win-lib://removable/D://KodiThumbnails/")
        self.assertEqual(len(self.made), 16)
        self.assertIn("win-lib://removable/D://KodiThumbnails/f/", self.made)

    def test_leaves_it_alone_when_its_there(self):
        self.there.update("win-lib://removable/D://KodiThumbnails/%s/" % c for c in "0123456789abcdef")
        self.assertEqual(self.d.ensure_picture_cache_folder(), "")
        self.assertEqual(self.made, [])

    def test_does_nothing_if_the_drive_is_missing_or_theres_no_such_setting(self):
        self.drive = False
        self.assertEqual(self.d.ensure_picture_cache_folder(), "")
        self.drive = True
        self.xml = b"<advancedsettings/>"
        self.assertEqual(self.d.ensure_picture_cache_folder(), "")
        self.assertEqual(self.made, [])


class ArtistArt(unittest.TestCase):
    def test_picture_names(self):
        import musicart
        self.assertEqual(musicart.artist_art_files(["Artist.JPG", "fanart.png", "x.jpg", "cover.webp"]),
                         {"thumb": "Artist.JPG", "fanart": "fanart.png"})
        self.assertEqual(musicart.artist_art_files(["pic.jpg"]), {})


class FindingFiles(unittest.TestCase):
    def test_progress_moves_while_listing(self):
        import tempfile as tf
        from test_library_folders import load_default
        tmp = tf.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        d = load_default(os.path.join(tmp, "data"))
        d.walk = lambda root: iter([("r/a.mp3", "a.mp3"), ("r/b.txt", "b.txt")])
        d._track_info = lambda p, n: {"name": n, "path": p, "unsupported": "test"}
        calls = []
        plans, left, stopped = d._plan_music_tags("r/", lambda done, total, name: calls.append((done, total, name)))
        self.assertEqual(calls[:2], [(0, 0, "Finding your MP3s: 0 so far"), (0, 0, "Finding your MP3s: 1 so far")])
        self.assertEqual(calls[-1], (0, 1, "a.mp3"))
        self.assertFalse(stopped)
        self.assertEqual(d._plan_music_tags("r/", lambda *a: True), ([], [], True))


class Writing(unittest.TestCase):
    """_write_checked against files on disk, including a write that goes wrong."""
    def setUp(self):
        from test_library_folders import load_default
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        d = self.d = load_default(os.path.join(self.tmp, "data"))
        vfs = d.xbmcvfs

        class File:
            def __init__(s, p, mode="r"):
                s.f = open(p, "wb" if mode == "w" else "rb")
            def readBytes(s, n=-1): return s.f.read(n)
            def write(s, b):
                s.f.write(bytes(b))
                return True
            def close(s): s.f.close()
        vfs.File = File
        vfs.delete = lambda p: os.path.exists(p) and os.remove(p)
        self.addCleanup(setattr, d.backup, "xbmcvfs", d.backup.xbmcvfs)
        d.backup.xbmcvfs = vfs
        d.log = lambda m: None
        self.path = os.path.join(self.tmp, "song.mp3")
        with open(self.path, "wb") as f:
            f.write(b"original")

    def temp_files(self):
        return [n for n in os.listdir(self.tmp) if n.endswith(".tmp")]

    def test_a_good_write_leaves_only_the_new_file(self):
        self.assertTrue(self.d._write_checked(self.path, b"new data"))
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), b"new data")
        self.assertEqual(self.temp_files(), [])

    def test_a_failed_copy_leaves_the_file_alone(self):
        real = self.d.backup._read
        self.d.backup._read = lambda p: b"wrong"
        self.addCleanup(setattr, self.d.backup, "_read", real)
        self.assertFalse(self.d._write_checked(self.path, b"new data"))
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), b"original")
        self.assertEqual(self.temp_files(), [])

    def test_a_failed_overwrite_keeps_the_full_copy(self):
        real = self.d.backup._read
        self.d.backup._read = lambda p: b"wrong" if p == self.path else real(p)
        self.addCleanup(setattr, self.d.backup, "_read", real)
        self.assertFalse(self.d._write_checked(self.path, b"new data"))
        kept = self.temp_files()
        self.assertEqual(len(kept), 1)
        with open(os.path.join(self.tmp, kept[0]), "rb") as f:
            self.assertEqual(f.read(), b"new data")


if __name__ == "__main__":
    unittest.main()

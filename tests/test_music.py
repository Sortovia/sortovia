"""Music: reading tags from real file layouts, and where each song goes."""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "addon", "script.kodisorter"))
import musictags  # noqa: E402
import sortlib as sl  # noqa: E402


def reader(data):
    return (lambda offset, count: data[offset:offset + count]), len(data)


def read(data):
    return musictags.read_tags(*reader(data))


def id3v23(frames):
    body = b""
    for name, text in frames:
        raw = b"\x03" + text.encode("utf-8")
        body += name.encode() + struct.pack(">I", len(raw)) + b"\x00\x00" + raw
    n = len(body)
    size = bytes([(n >> 21) & 127, (n >> 14) & 127, (n >> 7) & 127, n & 127])
    return b"ID3\x03\x00\x00" + size + body + b"\xff\xfb" + b"\x00" * 200


def comments(pairs):
    out = struct.pack("<I", 3) + b"sov" + struct.pack("<I", len(pairs))
    for k, v in pairs:
        raw = ("%s=%s" % (k, v)).encode()
        out += struct.pack("<I", len(raw)) + raw
    return out


def atom(name, body=b""):
    return struct.pack(">I", len(body) + 8) + name + body


def text_item(name, text):
    return atom(name, atom(b"data", b"\x00\x00\x00\x01\x00\x00\x00\x00" + text.encode()))


class Tags(unittest.TestCase):
    def test_id3(self):
        t = read(id3v23([("TPE1", "Made Up Band"), ("TALB", "Pretend Album"), ("TIT2", "First Song"),
                         ("TRCK", "3/12"), ("TPOS", "2/2"), ("TCON", "Rock")]))
        self.assertEqual(t, {"artist": "Made Up Band", "album": "Pretend Album", "title": "First Song",
                             "track": 3, "disc": 2, "genre": "Rock"})

    def test_id3_utf16(self):
        raw = b"\x01" + "Caf\u00e9".encode("utf-16")
        body = b"TPE1" + struct.pack(">I", len(raw)) + b"\x00\x00" + raw
        data = b"ID3\x03\x00\x00" + bytes([0, 0, 0, len(body)]) + body
        self.assertEqual(read(data)["artist"], "Caf\u00e9")

    def test_id3_version_1_at_the_end(self):
        tail = b"TAG" + b"Song".ljust(30, b"\0") + b"Band".ljust(30, b"\0") + b"Album".ljust(30, b"\0") + \
            b"2020" + b"\0" * 28 + b"\0\x07\xff"
        self.assertEqual(read(b"\xff\xfb" + b"\0" * 500 + tail),
                         {"title": "Song", "artist": "Band", "album": "Album", "track": 7})

    def test_flac_after_a_large_block(self):
        vc = comments([("ARTIST", "Band"), ("album", "Album"), ("TRACKNUMBER", "04"), ("COMPILATION", "1")])
        blocks = bytes([0, 0, 1, 0]) + b"\0" * 256 + bytes([0x84, 0, (len(vc) >> 8) & 255, len(vc) & 255]) + vc
        t = read(b"fLaC" + blocks + b"\0" * 50)
        self.assertEqual(t, {"artist": "Band", "album": "Album", "track": 4, "compilation": True})

    def test_ogg(self):
        data = b"OggS" + b"\0" * 40 + b"\x03vorbis" + comments([("ARTIST", "Band"), ("TITLE", "Song")])
        self.assertEqual(read(data), {"artist": "Band", "title": "Song"})
        data = b"OggS" + b"\0" * 40 + b"OpusTags" + comments([("ALBUM", "Album")])
        self.assertEqual(read(data), {"album": "Album"})

    def test_m4a_with_tags_after_the_audio(self):
        ilst = atom(b"ilst", text_item(b"\xa9ART", "Band") + text_item(b"\xa9alb", "Album") +
                    atom(b"trkn", atom(b"data", b"\0" * 8 + b"\0\0\0\x05\0\x09\0\0")) +
                    atom(b"cpil", atom(b"data", b"\0\0\0\x15\0\0\0\0\x01")))
        moov = atom(b"moov", atom(b"udta", atom(b"meta", b"\0\0\0\0" + ilst)))
        t = read(atom(b"ftyp", b"M4A \0\0\0\0") + atom(b"mdat", b"\0" * 5000) + moov)
        self.assertEqual(t, {"artist": "Band", "album": "Album", "track": 5, "compilation": True})

    def test_damaged_files_give_no_tags(self):
        for bad in (b"", b"ID3", b"fLaC\x00", b"OggS" + b"\x03vorbis\xff\xff", b"\0\0\0\x20ftyp", b"random bytes" * 20,
                    b"ID3\x03\x00\x00\x00\x00\x7f\x7fTPE1\xff\xff\xff\xff"):
            self.assertIsInstance(read(bad), dict)


class Places(unittest.TestCase):
    def test_tags_decide(self):
        tags = {"artist": "Band", "album": "Album", "title": "A: Song?", "track": 3}
        self.assertEqual(sl.plan_music("x.MP3", "E:/Download", tags)[0], ("Music", "Band", "Album", "03 - A - Song.mp3"))

    def test_second_disc_keeps_its_number(self):
        tags = {"artist": "Band", "album": "Album", "title": "Song", "track": 3, "disc": 2}
        self.assertEqual(sl.plan_music("x.flac", "E:/Download", tags)[0][-1], "2-03 - Song.flac")

    def test_album_artist_beats_track_artist(self):
        tags = {"artist": "Guest", "albumartist": "Band", "album": "Album", "title": "Song"}
        self.assertEqual(sl.plan_music("x.mp3", "E:/a", tags)[0][1], "Band")

    def test_mixed_artists_stay_together(self):
        for tags, various in (({"artist": "Band", "album": "Mix"}, True), ({"artist": "Band", "album": "Mix", "compilation": True}, False)):
            self.assertEqual(sl.plan_music("x.mp3", "E:/a", tags, various)[0][1], sl.VARIOUS)

    def test_artist_without_album_goes_to_singles(self):
        self.assertEqual(sl.plan_music("x.mp3", "E:/Download", {"artist": "Band"})[0][1:3], ("Band", "Singles"))

    def test_folders_used_when_there_are_no_tags(self):
        parts, kind, note = sl.plan_music("01 Song.mp3", "E:/Music/Band/Some Album", {})
        self.assertEqual(parts, ("Music", "Band", "Some Album", "01 Song.mp3"))
        self.assertIn("no tags", note)
        self.assertEqual(sl.plan_music("a.mp3", "E:/Download/Band - Some Album", {})[0][1:3], ("Band", "Some Album"))
        self.assertEqual(sl.plan_music("a.mp3", "E:/Music/Band/Some Album/CD2", {})[0][1:3], ("Band", "Some Album"))
        self.assertEqual(sl.plan_music("Band - Song.mp3", "E:/Download", {})[0][1:3], ("Band", "Singles"))

    def test_one_artist_all_in_their_own_folder(self):
        for root in ("win-lib://removable/D:\\Music\\Mollusk", "win-lib://removable/D:\\Mollusk", "E:/Download/Mollusk"):
            tagged = sl.plan_music("x.mp3", root, {"artist": "Mollusk", "title": "Song"})[0]
            self.assertEqual(tagged, ("Music", "Mollusk", "Singles", "Song.mp3"), root)
            album = sl.plan_music("x.mp3", root, {"artist": "Mollusk", "album": "Record", "title": "Song", "track": 2})[0]
            self.assertEqual(album, ("Music", "Mollusk", "Record", "02 - Song.mp3"), root)
            collab = sl.plan_music("x.mp3", root, {"artist": "Mollusk & Guest", "title": "Song"})[0]
            self.assertEqual(collab[1:3], ("Mollusk", "Singles"), root)
            mixed = sl.plan_music("x.mp3", root, {"artist": "Guest x Mollusk", "album": "Record"}, various=True)[0]
            self.assertEqual(mixed[1:3], ("Mollusk", "Record"), root)
        for root in ("win-lib://removable/D:\\Music\\Mollusk", "win-lib://removable/D:\\Mollusk"):
            self.assertEqual(sl.plan_music("Song.mp3", root, {})[0], ("Music", "Mollusk", "Singles", "Song.mp3"), root)
        self.assertEqual(sl.plan_music("Mollusk - Song.mp3", "E:/Download/Mollusk", {})[0][1:3], ("Mollusk", "Singles"))

    def test_several_artists_in_one_credit(self):
        for credit in ("Band/Guest", "Band, Guest", "Band; Guest", "Band feat. Guest", "Band ft. Guest", "Band/Guest/Other"):
            self.assertEqual(sl.plan_music("x.mp3", "E:/Download", {"artist": credit})[0][1], "Band", credit)
        self.assertEqual(sl.plan_music("x.mp3", "E:/Download", {"artist": "Band & Guest"})[0][1], "Band & Guest")
        self.assertEqual(sl.plan_music("x.mp3", "E:/a", {"artist": "Guest", "albumartist": "Band/Other"})[0][1], "Band")

    def test_the_artist_on_every_track_keeps_the_album_together(self):
        self.assertEqual(sl.shared_artist(["Band/One", "Band/Two", "Three & Band", "BAND feat. Four", "Band"]), "Band")
        self.assertEqual(sl.shared_artist(["One", "Two"]), "")
        self.assertEqual(sl.shared_artist(["Bandit/One", "Band"]), "")
        parts = sl.plan_music("x.mp3", "E:/Download", {"artist": "Band/One", "album": "Record"}, False, "Band")[0]
        self.assertEqual(parts[1:3], ("Band", "Record"))

    def test_dates_and_category_folders_arent_artists_or_albums(self):
        for folder in ("Albums/2017.10.20 - Pretend LP", "EP/2021.03.10 - Pretend LP", "Singles/2013 - Pretend LP"):
            root = "win-lib://removable/D://Music/Mollusk/" + folder
            self.assertEqual(sl.plan_music("01 - Song.mp3", root, {})[0][1:3], ("Mollusk", "Pretend LP"), folder)
        self.assertIsNone(sl.plan_music("x.mp3", "E:/Download/2013 - Pretend LP", {})[0])
        self.assertEqual(sl.plan_music("x.mp3", "E:/Download/2013 - Pretend LP", {"artist": "Band"})[0][1:3], ("Band", "Pretend LP"))

    def test_someone_elses_track_in_the_folder_keeps_its_artist(self):
        self.assertEqual(sl.plan_music("x.mp3", "E:/Music/Mollusk", {"artist": "Guest", "title": "Song"})[0][1], "Guest")
        self.assertEqual(sl.plan_music("x.mp3", "E:/Music/Olluskband", {"artist": "Mollusk", "title": "Song"})[0][1], "Mollusk")

    def test_no_artist_is_left_alone(self):
        for name, folder in (("clip.mp3", "E:/Download"), ("clip.mp3", "E:/Download/Thing"), ("03 Song.mp3", "E:/Music")):
            parts, reason, _ = sl.plan_music(name, folder, {})
            self.assertIsNone(parts, folder)
            self.assertIn("no artist", reason)

    def test_not_music_is_left_alone(self):
        tagged = {"artist": "Host", "album": "Show"}
        cases = [("x.mp3", "E:/Podcasts/Show", tagged, {}), ("x.mp3", "E:/Audiobooks", tagged, {}),
                 ("x.mp3", "E:/phone/WhatsApp/Audio", tagged, {}), ("x.mp3", "E:/a", dict(tagged, podcast=True), {}),
                 ("x.mp3", "E:/a", dict(tagged, genre="Podcast"), {}), ("x.wav", "E:/Samples/Kicks", {}, {})]
        for name, folder, tags, _ in cases:
            self.assertIsNone(sl.plan_music(name, folder, tags)[0], (folder, tags))
        self.assertIsNone(sl.plan_music("x.mp3", "E:/YouTube", tagged)[0])

    def test_a_band_with_a_word_inside_isnt_mistaken(self):
        self.assertIsNotNone(sl.plan_music("x.mp3", "E:/Music/Resample Band/Some Album", {})[0])


if __name__ == "__main__":
    unittest.main()

"""Read the artist, album and track tags from music files, using nothing but Python.

Handles ID3 (MP3, some AAC), FLAC, Ogg (Vorbis and Opus) and MP4 (M4A). read_at(offset, count)
returns bytes from the file, so only the small parts holding the tags are read. A damaged or
unusual file just gives fewer tags.
"""
import struct

MAX_TAG = 2 * 1024 * 1024
ID3_FRAMES = {"TPE1": "artist", "TP1": "artist", "TPE2": "albumartist", "TP2": "albumartist", "TALB": "album",
              "TAL": "album", "TIT2": "title", "TT2": "title", "TRCK": "track", "TRK": "track", "TPOS": "disc",
              "TPA": "disc", "TCON": "genre", "TCO": "genre", "TCMP": "compilation", "TCP": "compilation",
              "PCST": "podcast"}
VORBIS = {"ARTIST": "artist", "ALBUMARTIST": "albumartist", "ALBUM ARTIST": "albumartist", "ALBUM": "album",
          "TITLE": "title", "TRACKNUMBER": "track", "DISCNUMBER": "disc", "GENRE": "genre",
          "COMPILATION": "compilation"}
MP4_ITEMS = {b"\xa9ART": "artist", b"aART": "albumartist", b"\xa9alb": "album", b"\xa9nam": "title",
             b"\xa9gen": "genre", b"trkn": "track", b"disk": "disc", b"cpil": "compilation", b"pcst": "podcast"}


def _number(value):
    """"3/12" -> 3, anything else -> 0."""
    digits = str(value or "").split("/")[0].strip()
    return int(digits) if digits.isdigit() else 0


def _tidy(tags):
    out = {}
    for key, value in tags.items():
        if key in ("track", "disc"):
            value = _number(value)
        elif key in ("compilation", "podcast"):
            value = str(value).strip() not in ("", "0", "False", "false")
        else:
            value = " ".join(str(value).replace("\x00", " ").split())
        if value:
            out[key] = value
    return out


def _synchsafe(b):
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def _id3_text(data):
    if not data:
        return ""
    encoding = {0: "latin-1", 1: "utf-16", 2: "utf-16-be", 3: "utf-8"}.get(data[0])
    text = data[1:].decode(encoding, "replace") if encoding else data.decode("latin-1")
    return text.split("\x00")[0]  # the first of several values


def _id3(read_at):
    head = read_at(0, 10)
    if len(head) < 10 or head[:3] != b"ID3":
        return {}
    version, flags = head[3], head[5]
    data = read_at(10, min(_synchsafe(head[6:10]), MAX_TAG))
    pos = 0
    if flags & 0x40 and version >= 3 and len(data) > 4:  # an extended header comes first
        pos = _synchsafe(data[:4]) if version == 4 else struct.unpack(">I", data[:4])[0] + 4
    head_len, id_len = (6, 3) if version == 2 else (10, 4)
    tags = {}
    while pos + head_len <= len(data):
        frame = data[pos:pos + id_len]
        if not frame.strip(b"\x00"):
            break
        raw = data[pos + id_len:pos + head_len]
        if version == 2:
            size = (raw[0] << 16) | (raw[1] << 8) | raw[2]
        elif version == 4:
            size = _synchsafe(raw[:4])
        else:
            size = struct.unpack(">I", raw[:4])[0]
        key = ID3_FRAMES.get(frame.decode("latin-1"))
        if key:
            tags.setdefault(key, "1" if key == "podcast" else _id3_text(data[pos + head_len:pos + head_len + size]))
        pos += head_len + size
    return tags


def _id3v1(read_at, size):
    if size < 128:
        return {}
    tail = read_at(size - 128, 128)
    if tail[:3] != b"TAG":
        return {}

    def text(a, b):
        return tail[a:b].split(b"\x00")[0].decode("latin-1").strip()
    tags = {"title": text(3, 33), "artist": text(33, 63), "album": text(63, 93)}
    if tail[125] == 0 and tail[126]:
        tags["track"] = str(tail[126])
    return tags


def _vorbis_comments(data):
    pos = struct.unpack("<I", data[:4])[0] + 4
    count = struct.unpack("<I", data[pos:pos + 4])[0]
    pos += 4
    tags = {}
    for _ in range(min(count, 1000)):
        size = struct.unpack("<I", data[pos:pos + 4])[0]
        entry = data[pos + 4:pos + 4 + size].decode("utf-8", "replace")
        pos += 4 + size
        name, _, value = entry.partition("=")
        key = VORBIS.get(name.upper())
        if key:
            tags.setdefault(key, value)
    return tags


def _flac(read_at):
    pos = 4
    while True:
        head = read_at(pos, 4)
        if len(head) < 4:
            return {}
        size = (head[1] << 16) | (head[2] << 8) | head[3]
        if head[0] & 0x7f == 4:
            return _vorbis_comments(read_at(pos + 4, min(size, MAX_TAG)))
        if head[0] & 0x80:
            return {}
        pos += 4 + size


def _ogg(read_at):
    data = read_at(0, 256 * 1024)
    for mark in (b"\x03vorbis", b"OpusTags"):
        at = data.find(mark)
        if at >= 0:
            return _vorbis_comments(data[at + len(mark):])
    return {}


def _atoms(data, start=0, end=None):
    pos, end = start, len(data) if end is None else end
    while pos + 8 <= end:
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        if size < 8 or pos + size > end:
            return
        yield data[pos + 4:pos + 8], pos + 8, pos + size
        pos += size


def _child(data, name, start, end):
    for kind, a, b in _atoms(data, start, end):
        if kind == name:
            return a, b
    return None


def _mp4(read_at, size):
    pos = 0
    while pos + 8 <= size:
        head = read_at(pos, 8)
        if len(head) < 8:
            return {}
        length = struct.unpack(">I", head[:4])[0]
        if head[4:8] == b"moov":
            data = read_at(pos, min(length, 8 * MAX_TAG))
            break
        if length < 8:
            return {}  # a form this reader doesn't handle
        pos += length
    else:
        return {}
    span = (8, len(data))
    for name in (b"udta", b"meta"):
        span = _child(data, name, *span)
        if not span:
            return {}
    ilst = _child(data, b"ilst", span[0] + 4, span[1])  # meta starts with 4 bytes of version
    if not ilst:
        return {}
    tags = {}
    for kind, a, b in _atoms(data, *ilst):
        key = MP4_ITEMS.get(kind)
        value = _child(data, b"data", a, b) if key else None
        if not value:
            continue
        body = data[value[0] + 8:value[1]]
        if key in ("track", "disc"):
            tags[key] = str(struct.unpack(">H", body[2:4])[0]) if len(body) >= 4 else ""
        elif key in ("compilation", "podcast"):
            tags[key] = str(body[0]) if body else ""
        else:
            tags[key] = body.decode("utf-8", "replace")
    return tags


def read_tags(read_at, size):
    """{artist, albumartist, album, title, track, disc, genre, compilation, podcast}, with what was found."""
    try:
        start = read_at(0, 12)
        if start[:4] == b"fLaC":
            tags = _flac(read_at)
        elif start[:4] == b"OggS":
            tags = _ogg(read_at)
        elif start[4:8] == b"ftyp":
            tags = _mp4(read_at, size)
        else:
            tags = _id3(read_at) or _id3v1(read_at, size)
    except (IndexError, ValueError, struct.error, TypeError):
        tags = {}
    return _tidy(tags)

"""Rewrite an MP3's ID3 tag as ID3v2.4, keeping the audio and every other frame.

ID3v2.4 stores true multi-value tags, which is how a track can be linked to each of its artists.
Works on bytes only. Nothing here touches a file.
"""
import struct


class Unsupported(Exception):
    """A plain reason this file's tag is left alone."""


# Frames that were renamed between ID3v2.2 and later versions.
V22 = {"TT2": "TIT2", "TP1": "TPE1", "TP2": "TPE2", "TP3": "TPE3", "TP4": "TPE4", "TAL": "TALB", "TRK": "TRCK",
       "TPA": "TPOS", "TYE": "TYER", "TCO": "TCON", "TCM": "TCOM", "TCP": "TCMP", "COM": "COMM", "ULT": "USLT",
       "TXX": "TXXX", "WXX": "WXXX", "UFI": "UFID", "TEN": "TENC", "TBP": "TBPM", "TPB": "TPUB", "TLE": "TLEN"}
ENCODINGS = {0: "latin-1", 1: "utf-16", 2: "utf-16-be", 3: "utf-8"}


def synchsafe(n):
    return bytes([(n >> 21) & 127, (n >> 14) & 127, (n >> 7) & 127, n & 127])


def _unsafe(b):
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def tag_size(head):
    """The whole tag's length in bytes from a file's first 10 bytes, or 0 if it has no ID3v2 tag."""
    if len(head) < 10 or head[:3] != b"ID3" or any(b & 0x80 for b in head[6:10]):
        return 0
    return 10 + _unsafe(head[6:10]) + (10 if head[3] == 4 and head[5] & 0x10 else 0)


def parse(tag):
    """(version, [(frame id, frame body)]) from a whole tag's bytes."""
    if tag[:3] != b"ID3":
        raise Unsupported("no ID3v2 tag")
    version, flags = tag[3], tag[5]
    if version not in (2, 3, 4):
        raise Unsupported("ID3v2.%d isn't a known version" % version)
    body = tag[10:10 + _unsafe(tag[6:10])]
    if flags & 0x80:
        if version == 4:
            raise Unsupported("unusual ID3v2.4 encoding")
        body = body.replace(b"\xff\x00", b"\xff")
    if version == 2 and flags & 0x40:
        raise Unsupported("compressed tag")
    pos = 0
    if version >= 3 and flags & 0x40 and len(body) >= 4:
        pos = _unsafe(body[:4]) if version == 4 else struct.unpack(">I", body[:4])[0] + 4
    frames = []
    head, id_len = (6, 3) if version == 2 else (10, 4)
    while pos + head <= len(body):
        raw_id = body[pos:pos + id_len]
        if not raw_id.strip(b"\x00"):
            break
        if not raw_id.isalnum():
            raise Unsupported("damaged tag")
        raw = body[pos + id_len:pos + head]
        if version == 2:
            size = (raw[0] << 16) | (raw[1] << 8) | raw[2]
        elif version == 4:
            size = _unsafe(raw[:4])
        else:
            size = struct.unpack(">I", raw[:4])[0]
        if pos + head + size > len(body):
            raise Unsupported("damaged tag")
        if version >= 3 and raw[5] & (0x0f if version == 4 else 0xe0):
            raise Unsupported("compressed or encrypted frames")
        frames.append((raw_id.decode("latin-1"), body[pos + head:pos + head + size]))
        pos += head + size
    return version, frames


def _text(body):
    """The values in a text frame."""
    if not body:
        return []
    encoding = ENCODINGS.get(body[0])
    if not encoding:
        return []
    raw = body[1:]
    if encoding in ("utf-16", "utf-16-be"):
        parts, start = [], 0
        for i in range(0, len(raw) - 1, 2):
            if raw[i:i + 2] == b"\x00\x00":
                parts.append(raw[start:i])
                start = i + 2
        parts.append(raw[start:])
        bom = raw[:2] if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else b""
        values = []
        for p in parts:
            if p:
                values.append(p.decode(encoding, "replace") if p[:2] in (b"\xff\xfe", b"\xfe\xff") or encoding != "utf-16"
                              else (bom + p).decode("utf-16", "replace"))
    else:
        values = [p.decode(encoding, "replace") for p in raw.split(b"\x00")]
    return [v.strip() for v in values if v.strip()]


def text_values(frames, frame_id):
    for name, body in frames:
        if name == frame_id:
            return _text(body)
    return []


def user_values(frames, description):
    """The values of a TXXX frame with this description."""
    for name, body in frames:
        if name == "TXXX":
            values = _text(body)
            if values and values[0].lower() == description.lower():
                return values[1:]
    return []


def text_frame(values):
    return b"\x03" + "\x00".join(values).encode("utf-8")


def user_frame(description, values):
    return b"\x03" + "\x00".join([description] + list(values)).encode("utf-8")


def _upgrade(version, frames):
    """Frames in their ID3v2.4 form."""
    out = []
    date = {}
    for name, body in frames:
        if version == 2:
            if name == "PIC" and len(body) > 4:  # a three-letter image type became a MIME type
                kind = {b"JPG": b"image/jpeg", b"PNG": b"image/png"}.get(body[1:4].upper(), b"image/" + body[1:4].lower())
                name, body = "APIC", body[:1] + kind + b"\x00" + body[4:]
            else:
                name = V22.get(name, name)
            if len(name) != 4:
                continue  # no ID3v2.4 equivalent
        if name in ("TYER", "TDAT"):
            date[name] = "".join(_text(body))
            continue
        if name == "TORY":
            name = "TDOR"
        elif name in ("TRDA", "TSIZ"):
            continue  # removed in ID3v2.4
        if name[0] == "T" and name != "TXXX" and body[:1] in (b"\x00", b"\x01", b"\x02"):
            values = _text(body)
            if values:
                body = text_frame(values)
        out.append((name, body))
    if date.get("TYER") and not any(n == "TDRC" for n, _ in out):
        when = date["TYER"]
        day = date.get("TDAT", "")
        if len(day) == 4 and day.isdigit():  # stored as DDMM
            when = "%s-%s-%s" % (when, day[2:], day[:2])
        out.append(("TDRC", text_frame([when])))
    return out


def build(frames):
    """A complete ID3v2.4 tag from [(frame id, frame body)]."""
    body = b"".join(name.encode("latin-1") + synchsafe(len(data)) + b"\x00\x00" + data for name, data in frames)
    return b"ID3\x04\x00\x00" + synchsafe(len(body)) + body


def retag(data, artists=None, display=None, album_artist=None, title_album=None, year=None):
    """(new file bytes, old tag bytes). artists: the list for TXXX:ARTISTS. display: the TPE1 text.
    year: replaces the track's date. title_album: {frame id: text} used only for frames the file doesn't
    have. The audio is copied as it is."""
    size = tag_size(data[:10])
    old, audio = data[:size], data[size:]
    version, frames = parse(old) if size else (4, [])
    frames = _upgrade(version, frames)
    replaced = set()
    if display:
        replaced.add("TPE1")
    if album_artist:
        replaced.add("TPE2")
    if year:
        replaced.add("TDRC")
    kept = [(n, b) for n, b in frames if n not in replaced and
            not (artists is not None and n == "TXXX" and (_text(b) or [""])[0].lower() == "artists")]
    if display:
        kept.append(("TPE1", text_frame([display])))
    if album_artist:
        kept.append(("TPE2", text_frame([album_artist])))
    if year:
        kept.append(("TDRC", text_frame([year])))
    if artists:
        kept.append(("TXXX", user_frame("ARTISTS", artists)))
    for name, text in (title_album or {}).items():
        if text and not any(n == name for n, _ in kept):
            kept.append((name, text_frame([text])))
    return build(kept) + audio, old


def put_back(data, old_tag):
    """The file with its current tag replaced by old_tag, for undoing a change."""
    return old_tag + data[tag_size(data[:10]):]

"""Comics: tidy the Comics folder, turn .cbr into .cbz, and turn pages for a
monitor stood on its side.

Why .cbz: Kodi opens a .cbz (a zip) by itself, page by page. A .cbr (a rar)
needs the Archive support add-on, which unpacks it first, so it's slow to open
and sometimes fails.

Turning pages: each JPEG page gets an orientation tag (EXIF), the same tag a
phone camera writes. Kodi turns the picture to match when it shows it. Nothing
is re-encoded, so it's quick and loses no quality, and it can be undone.
Pages in other formats (PNG ...) stay as they are.
"""
import re
import struct
import zlib

from sortlib import COMICS, comic_series

IMAGES = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")
DOCS = (".pdf", ".epub")
COMICS_ALL = tuple(COMICS) + DOCS

# EXIF orientation values: 1 = upright, 6 = show turned 90 degrees clockwise,
# 8 = show turned 90 degrees counter-clockwise.
TURNS = [
    (1, "Upright (normal screen) - also undoes turning"),
    (8, "Monitor turned clockwise (its top is now on the right)"),
    (6, "Monitor turned counter-clockwise (its top is now on the left)"),
]


def turn_label(o):
    return {1: "upright", 8: "for a monitor turned clockwise", 6: "for a monitor turned counter-clockwise"}.get(o, "?")


def _exif_app1(orientation):
    tiff = (b"MM\x00\x2a\x00\x00\x00\x08"            # big-endian TIFF header, IFD at 8
            b"\x00\x01"                              # one entry
            b"\x01\x12\x00\x03\x00\x00\x00\x01" +    # Orientation, SHORT, count 1
            struct.pack(">HH", orientation, 0) +
            b"\x00\x00\x00\x00")                     # no next IFD
    payload = b"Exif\x00\x00" + tiff
    return b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload


def set_orientation(data, orientation):
    """The JPEG with its EXIF replaced by just an orientation tag (none for 1).
    Anything that isn't a JPEG we can read comes back unchanged."""
    if not data.startswith(b"\xff\xd8"):
        return data
    i, keep, n = 2, [], len(data)
    while i + 4 <= n and data[i] == 0xFF:
        marker = data[i + 1]
        if not (0xE0 <= marker <= 0xEF or marker == 0xFE):
            break  # end of the APPn/comment segments: the image itself starts here
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        if length < 2 or i + 2 + length > n:
            return data  # damaged header: leave the page alone
        seg = data[i:i + 2 + length]
        if not (marker == 0xE1 and seg[4:10] == b"Exif\x00\x00"):
            keep.append(seg)
        i += 2 + length
    head = [s for s in keep if s[1] == 0xE0]  # JFIF (APP0) stays first
    rest = [s for s in keep if s[1] != 0xE0]
    exif = [_exif_app1(orientation)] if orientation != 1 else []
    return b"\xff\xd8" + b"".join(head + exif + rest) + data[i:]


def orientation_of(data):
    """The orientation tag of a JPEG we wrote (or any big/little-endian EXIF), or 1."""
    m = re.search(b"Exif\x00\x00(MM\x00\x2a|II\x2a\x00)", data[:65536])
    if not m:
        return 1
    tiff = m.start(1)
    big = data[tiff:tiff + 2] == b"MM"
    fmt = ">" if big else "<"
    try:
        ifd = tiff + struct.unpack(fmt + "I", data[tiff + 4:tiff + 8])[0]
        count = struct.unpack(fmt + "H", data[ifd:ifd + 2])[0]
        for k in range(count):
            e = ifd + 2 + 12 * k
            tag, typ = struct.unpack(fmt + "HH", data[e:e + 4])
            if tag == 0x0112 and typ == 3:
                return struct.unpack(fmt + "H", data[e + 8:e + 10])[0]
    except struct.error:
        pass
    return 1


def ext_of(name):
    return ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""


def page_order(names):
    """Natural order: page2 before page10."""
    return sorted(names, key=lambda n: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", n)])


def plan_tidy(files, folder_series=comic_series):
    """files: [(relative folder parts, name)] under the Comics folder.
    Returns (moves, documents):
      moves: [(parts, name, series)] comics to move into Comics/<series>/:
             loose ones in the Comics folder itself, and ones in a near-duplicate
             folder such as "Ironclad (2)" or "ironclad[2]" when the series is "Ironclad".
      documents: [(parts, name)] PDFs/EPUBs lying loose in the Comics folder
             (an old version filed bills and manuals there).
    Deeper folders (Nightwarden/Year One/...) are the person's own layout: left alone."""
    moves, documents = [], []
    for parts, name in files:
        ext = ext_of(name)
        if ext in DOCS and not parts:
            documents.append((parts, name))
            continue
        if ext not in COMICS:
            continue
        series = comic_series(name)
        if not parts:
            moves.append((parts, name, series))
        elif len(parts) == 1 and parts[0] != series and folder_series(parts[0] + ".cbz").lower() == series.lower():
            moves.append((parts, name, series))
    return moves, documents


class StoredZip(object):
    """A .cbz writer that only ever appends (no seeking), so it can write through
    Kodi's file functions to the external drive. Pages are stored, not compressed:
    JPEGs don't shrink, and Kodi opens stored pages fastest."""
    DOS_DATE = (2026 - 1980) << 9 | 1 << 5 | 1  # a fixed date: the content is what matters

    def __init__(self, write):
        self.write, self.offset, self.entries = write, 0, []

    def _put(self, b):
        self.write(b)
        self.offset += len(b)

    def add(self, name, data):
        raw = name.replace("\\", "/").encode("utf-8")
        flag = 0x800 if any(c > 127 for c in bytearray(raw)) else 0  # UTF-8 names
        crc = zlib.crc32(data) & 0xFFFFFFFF
        if self.offset + len(data) > 0xFFFFFFF0:
            raise IOError("comic too big for a plain .cbz (over 4 GB)")
        self.entries.append((raw, flag, crc, len(data), self.offset))
        self._put(struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, flag, 0, 0, self.DOS_DATE, crc,
                              len(data), len(data), len(raw), 0) + raw)
        self._put(data)

    def close(self):
        start = self.offset
        for raw, flag, crc, size, off in self.entries:
            self._put(struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, flag, 0, 0, self.DOS_DATE, crc,
                                  size, size, len(raw), 0, 0, 0, 0, 0, off) + raw)
        n = len(self.entries)
        self._put(struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, n, n, self.offset - start, start, 0))
        return self.offset

"""A QR code as a PNG (black on white), drawn here - nothing is sent to a website.
Uses qrcodegen.py (Project Nayuki, MIT licence)."""
import struct
import zlib

from qrcodegen import QrCode


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def png(width, height, rows):
    """8-bit greyscale PNG from rows of bytes (one byte per pixel)."""
    raw = b"".join(b"\x00" + r for r in rows)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)) +
            _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b""))


def qr_png(text, scale=10, border=4):
    qr = QrCode.encode_text(text, QrCode.Ecc.MEDIUM)
    n = qr.get_size()
    rows = []
    for y in range(-border, n + border):
        line = bytes(0 if qr.get_module(x, y) else 255 for x in range(-border, n + border)
                     for _ in range(scale))
        rows.extend([line] * scale)
    side = (n + 2 * border) * scale
    return png(side, side, rows)


def solid_png(shade=16, size=8):
    """A small one-colour PNG (stretched as a dark backdrop)."""
    return png(size, size, [bytes([shade]) * size] * size)

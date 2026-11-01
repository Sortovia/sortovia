"""Release .nfo files (the text notes that come with downloads).

Kodi only reads .nfo files named like the video (or tvshow.nfo / movie.nfo),
in its own XML format or holding a link to the title's page. Release NFOs are
neither, but many contain an IMDb link: that link is turned into a small
Kodi .nfo next to the sorted video, so Kodi's scraper matches exactly the
right title. Pure functions only (no Kodi imports), so they can be tested.
"""
import re

IMDB_RE = re.compile(r"(?:imdb\.com/(?:[a-z]{2}/)?title/|\b)(tt\d{7,9})\b", re.I)
KODI_ROOTS = ("<movie", "<tvshow", "<episodedetails", "<musicvideo")

# Release-NFO choices (also stored as nfo_mode in the run settings)
NFO_CHOICES = ["Make Kodi .nfo files from them (IMDb links), then move them to _Unpacked",
               "Make Kodi .nfo files from them, then delete them",
               "Just move them to _Unpacked",
               "Leave them where they are"]
MAKE_KODI = (0, 1)
MOVE_AWAY, DELETE, LEAVE = 0, 1, 3  # 2 also moves away


def is_kodi_nfo(text):
    """Kodi's own XML nfo (keep it with the video) vs a release NFO."""
    head = text.lstrip("﻿ \r\n\t")[:400].lower()
    if head.startswith("<?xml"):
        head = head[head.find("?>") + 2:].lstrip()
    return head.startswith(KODI_ROOTS)


def imdb_ids(text):
    """IMDb ids in the order they appear, without repeats."""
    out = []
    for m in IMDB_RE.finditer(text or ""):
        tid = m.group(1).lower()
        if tid not in out:
            out.append(tid)
    return out


def url_nfo(imdb_id):
    """A Kodi 'URL nfo': Kodi's scraper uses the link to identify the title."""
    return "https://www.imdb.com/title/%s/\n" % imdb_id


def same_show(a, b):
    """Loose title match: 'The Office (US)' ~ 'The Office'."""
    def norm(s):
        s = re.sub(r"\(.*?\)", " ", s or "").lower()
        s = re.sub(r"^the\s+", "", s.strip())
        return re.sub(r"[^a-z0-9]+", "", s)
    a, b = norm(a), norm(b)
    return bool(a) and bool(b) and (a == b or a.startswith(b) or b.startswith(a))

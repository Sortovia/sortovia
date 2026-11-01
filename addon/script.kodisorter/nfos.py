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


# ---------- audio language from a release NFO (fallback only) ----------
# Full names and 3-letter codes only: 2-letter ones ("it", "de") are ordinary words.
LANG_WORDS = {
    "en": ("english", "eng"), "ja": ("japanese", "jpn", "jap"),
    "es": ("spanish", "espanol", "español", "castellano", "latino", "spa"),
    "fr": ("french", "français", "francais", "fre", "fra"), "de": ("german", "deutsch", "ger", "deu"),
    "it": ("italian", "italiano", "ita"), "pt": ("portuguese", "português", "portugues", "por"),
    "ru": ("russian", "rus"), "ko": ("korean", "kor"),
    "zh": ("chinese", "mandarin", "cantonese", "chi", "zho"), "hi": ("hindi", "hin"),
    "nl": ("dutch", "nld", "dut"), "pl": ("polish", "pol"), "sv": ("swedish", "swe"),
    "ar": ("arabic", "ara"), "tr": ("turkish", "tur"), "th": ("thai", "tha"),
}
_WORD_TO_LANG = dict((w, code) for code, words in LANG_WORDS.items() for w in words)
_LANG_WORD_RE = re.compile(r"(?<![a-z])(%s)(?![a-z])" % "|".join(
    sorted((re.escape(w) for w in _WORD_TO_LANG), key=len, reverse=True)), re.I)
_AUDIO_LINE_RE = re.compile(r"audio|language|lang\b|dub", re.I)
_SUB_LINE_RE = re.compile(r"sub|caption|cc\b", re.I)


def audio_languages(text):
    """Audio languages named in a release NFO, as 2-letter codes (sorted).
    Only lines about audio/language count; subtitle lines are ignored.
    'Dual Audio' alone names no language, so it adds nothing."""
    found = set()
    lines = (text or "").splitlines()
    for i, line in enumerate(lines):
        if not _AUDIO_LINE_RE.search(line) or _SUB_LINE_RE.search(line):
            continue
        # "Audio:" headers sometimes put the value on the next line
        chunk = line + (" " + lines[i + 1] if i + 1 < len(lines) and not _SUB_LINE_RE.search(lines[i + 1]) else "")
        for m in _LANG_WORD_RE.finditer(chunk):
            found.add(_WORD_TO_LANG[m.group(1).lower()])
    return sorted(found)

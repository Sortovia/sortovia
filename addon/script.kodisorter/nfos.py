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
    # full names, plus 3-letter codes only where they aren't ordinary words
    "fi": ("finnish", "fin"), "da": ("danish", "dan"), "no": ("norwegian", "norsk", "nob"),
    "el": ("greek", "ell", "gre"), "he": ("hebrew", "heb"), "hu": ("hungarian", "magyar"),
    "cs": ("czech", "cze", "ces"), "ro": ("romanian", "rum", "ron"), "vi": ("vietnamese", "vie"),
    "id": ("indonesian",), "ms": ("malay",), "uk": ("ukrainian", "ukr"), "bg": ("bulgarian", "bul"),
    "hr": ("croatian", "hrv"), "sr": ("serbian", "srp"), "sl": ("slovenian", "slv"),
    "et": ("estonian",), "lv": ("latvian", "lav"), "lt": ("lithuanian",), "is": ("icelandic", "isl"),
    "ca": ("catalan",), "eu": ("basque",), "gl": ("galician", "glg"), "fa": ("persian", "farsi", "fas"),
    "tl": ("filipino", "tagalog"), "ta": ("tamil", "tam"), "te": ("telugu", "tel"), "bn": ("bengali",),
    "sk": ("slovak",),
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


# ---------- subtitles named only by language ("11_English.srt") ----------
LEFTOVER_EXTS = (".nfo", ".sfv", ".txt", ".url", ".jpg", ".jpeg", ".png", ".md5", ".srr", ".htm", ".html")
SUBS_FOLDERS = ("subs", "sub", "subtitles", "subtitle")
_FLAG_RE = re.compile(r"(?<![a-z])(forced|sdh|cc|hi)(?![a-z])", re.I)
RELEASE_RE = re.compile(r"(?i)(?:[ ._\-]s\d{1,2}(?:[ ._\-]|$)|\b(?:480|576|720|1080|2160)[pi]\b|"
                        r"\[(?:480|576|720|1080|2160)p?\]|x26[45]|hevc|"
                        r"web[ ._\-]?(?:dl|rip)?\b|bluray|bdrip|dvdrip|hdtv)")


def sub_suffix(name):
    """'11_English.srt' -> '.en', '3_English [Forced].srt' -> '.en.forced',
    'Spanish (Latin America) SDH.srt' -> '.es.sdh'. '' if no language found."""
    stem = name.rsplit(".", 1)[0]
    lang = ""
    for m in _LANG_WORD_RE.finditer(stem):
        lang = _WORD_TO_LANG[m.group(1).lower()]
        break
    if not lang:
        m = re.search(r"(?:^|[ ._\-])([a-z]{2})$", stem, re.I)  # "....en"
        lang = m.group(1).lower() if m and m.group(1).lower() in LANG_WORDS else ""
    flags = sorted(set(f.lower().replace("cc", "sdh").replace("hi", "sdh") for f in _FLAG_RE.findall(stem)))
    return ("." + lang if lang else "") + "".join("." + f for f in flags)


def looks_like_release(folder_name):
    """'Sams.Sandwiches.S15.1080p.x265-GAMMA' yes; 'complete', 'Movies', 'Other' no."""
    return bool(RELEASE_RE.search(" " + folder_name + " "))

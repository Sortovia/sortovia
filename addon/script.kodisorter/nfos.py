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
               "Leave them where they are",
               "Make Kodi .nfo files WITH QUALITY TAGS for movies (codec, 10-bit, source, bit rate), "
               "then move them to _Unpacked"]
MAKE_KODI = (0, 1, 4)
QUALITY = 4
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


# ---------- quality tags for movie .nfo files ----------
# Things Kodi can't read from the file itself. Resolution, HDR, audio codec and
# languages are left out: Kodi shows those from the video already.
_Q_RULES = [
    ("x265", r"x\.?265|h\.?265|hevc"), ("x264", r"x\.?264|h\.?264|\bavc\b"), ("AV1", r"\bav1\b"),
    ("XviD", r"xvid"), ("DivX", r"divx"),
    ("10-bit", r"10[ ._\-]?bits?\b|hi10p?"),
    ("Remux", r"remux"), ("BluRay", r"blu[ ._\-]?ray|bdrip|brrip|\bbd(?:25|50)?\b|bd\d{3,4}p?"),
    ("WEB-DL", r"web[ ._\-]?dl"), ("WEBRip", r"web[ ._\-]?rip"), ("HDTV", r"hdtv"),
    ("DVDRip", r"dvd[ ._\-]?rip"), ("DVD", r"\bdvd(?:5|9|r)?\b"),
    ("Dual Audio", r"dual[ ._\-]?audio"), ("Multi Audio", r"\bmulti\b"), ("Atmos", r"atmos"),
]
_Q_RE = [(tag, re.compile(r"(?<![a-z0-9])(?:%s)" % rx, re.I)) for tag, rx in _Q_RULES]
_SOURCES = ("Remux", "BluRay", "WEB-DL", "WEBRip", "HDTV", "DVDRip", "DVD")
_BITRATE_RE = re.compile(r"^\s*overall\s*bit\s*rate\s*[:.]*\s*([\d\s.,]+)\s*([kM])b(?:it)?/?s", re.I | re.M)
_BITDEPTH_RE = re.compile(r"bit\s*depth\s*[:.]*\s*10\s*bits?", re.I)


def nfo_bitrate(text):
    """Overall bit rate (Mbps) from MediaInfo text in a release NFO, or None."""
    m = _BITRATE_RE.search(text or "")
    if not m:
        return None
    num = re.sub(r"\s", "", m.group(1)).replace(",", ".")
    if num.count(".") > 1:
        num = num.replace(".", "", num.count(".") - 1)
    try:
        val = float(num)
    except ValueError:
        return None
    return val / 1000.0 if m.group(2).lower() == "k" else val


def mbps(value, estimated=False):
    return "%s%.1f Mbps" % ("~" if estimated else "", value) if value < 10 else \
        "%s%d Mbps" % ("~" if estimated else "", round(value))


def quality_tags(names, nfo_text="", size=0, runtime_min=0):
    """Tags for a movie from its file/folder names and release NFO text.
    Bit rate: the NFO's MediaInfo figure, else file size / running time (~)."""
    hay = " ".join(n for n in names if n)
    text = nfo_text or ""
    tags = []
    for tag, rx in _Q_RE:
        if rx.search(hay) and tag not in tags:
            tags.append(tag)
    if "10-bit" not in tags and _BITDEPTH_RE.search(text):
        tags.append("10-bit")
    if not any(t in tags for t in ("x265", "x264", "AV1")):
        if re.search(r"format\s*[:.]*\s*hevc", text, re.I):
            tags.insert(0, "x265")
        elif re.search(r"format\s*[:.]*\s*avc\b", text, re.I):
            tags.insert(0, "x264")
    src = [t for t in tags if t in _SOURCES]
    for extra in src[1:]:  # one source: the first rule that matched is the most specific
        tags.remove(extra)
    rate = nfo_bitrate(text)
    if rate:
        tags.append(mbps(rate))
    elif size and runtime_min:
        tags.append(mbps(size * 8 / (runtime_min * 60.0) / 1e6, estimated=True))
    return tags


def _xml(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def quality_nfo(tags, url):
    """A Kodi 'combination' nfo: the scraper still identifies the movie from the
    URL on the last line and fetches everything; only the tags come from here."""
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<movie>\n%s</movie>\n%s\n'
            % ("".join("    <tag>%s</tag>\n" % _xml(t) for t in tags), url.strip()))


def our_url_nfo(text):
    """An nfo that is only a link (what Kodi Sorter writes): safe to upgrade."""
    lines = [l for l in (text or "").strip().splitlines() if l.strip()]
    return len(lines) == 1 and re.match(r"^https?://\S+$", lines[0].strip()) is not None

"""Filename -> Kodi folder/name logic. Pure: no disk access, no Kodi imports.

Shared by the Kodi add-on (default.py) and the command-line kodi_sort.py, so a
naming fix made here applies to both.

  TV:     TV/Show Name (Year)/Season 01/Show Name (Year) S01E02.mkv
  Movies: Movies/Movie Name (Year)/Movie Name (Year).mkv
  Comics: Comics/<original file name>
"""
import re
from pathlib import PurePath

VIDEO = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".ts", ".webm"}
SUBS = {".srt", ".ass", ".ssa", ".sub", ".vtt"}
COMICS = {".cbz", ".cbr", ".cb7", ".cbt"}
# PDFs/EPUBs are usually bills, manuals, receipts: only comics when they sit
# in a folder whose name says so ("Comics", "Manga", "Nightwarden comics" ...).
BOOKS = {".pdf", ".epub"}
COMIC_FOLDER_RE = re.compile(r"comic|manga", re.I)
MIN_VIDEO_BYTES = 50 * 1024 * 1024  # smaller videos are samples/clips

# SxxEyy, optional second episode only with an explicit E / -E (never resolution digits)
TV_RE = re.compile(
    r"^(?P<show>.*?)[ ._\-\[\(]*(?<![a-z])s(?P<s>\d{1,2})[ ._\-]?e(?P<e>\d{1,3})"
    r"(?:-?e(?P<e2>\d{1,3}))?(?!\d)",
    re.I,
)
TV_X_RE = re.compile(r"^(?P<show>.*?)[ ._\-]+(?P<s>\d{1,2})x(?P<e>\d{2,3})(?!\d)", re.I)
# Fansub style "Show - 03" / "Show_-_03" / "Show -subtitle- 03" (absolute numbering,
# assumed Season 01). The dash needs a space on at least one side, so "Spider-Man"
# or "Apollo-13" never count as an episode number.
ANIME_RE = re.compile(
    r"^(?P<show>.+?)(?:\s+-\s*|\s*-\s+)(?P<e>\d{1,3})(?:v\d)?(?=\s|$|[\[\(])")
# OVA / OAD / ONA, or "Special" followed by a number -> Season 00 (Kodi's Specials).
# A number right after the word is used; otherwise the number is a guess.
SPECIAL_RE = re.compile(
    r"^(?P<show>.+?)[ ._\-]+(?:(?:ova|oad|ona)(?:[ ._\-]*(?P<n>\d{1,2}))?|specials?[ ._\-]*(?P<n2>\d{1,2}))(?![a-z0-9])",
    re.I)
SPECIAL_GUESS_NOTE = "special with no number - put in Season 00 as the next free episode, check it matches TMDb"
SPECIAL_NOTE = "special - Season 00"
# Download-site prefixes: "www.ExampleSite.org  -  ", "[TGx]", "www.DownloadSite.com - "
SITE_PREFIX_RE = re.compile(
    r"^\s*(?:www\.)?[a-z0-9\-]+\.(?:org|com|net|to|io|cc|me|tv|xyz|info|ws|se|ag|is|lol)\s*-+\s*", re.I)
# Release-group tags at the start: "[SubTeam] ", "(Group_One)_"
LEADING_TAGS_RE = re.compile(r"^(?:\s*(?:\[[^\]]*\]|\([^)]*\)))+\s*")
YEAR_RE = re.compile(r"[ ._\-\(\[]((?:19|20)\d{2})(?=[ ._\-\)\]]|$)")
# Opening/ending credits videos: "NCOP", "NCED2", "Textless Opening", "Creditless ED"
CREDITS_RE = re.compile(r"(?<![a-z])(?:nc(?:op|ed)\d*|textless|creditless)(?![a-z])", re.I)

RELEASE_TOKENS = {
    "480p", "576p", "720p", "1080p", "1080i", "2160p", "4k", "uhd",
    "web", "webrip", "webdl", "bluray", "brrip", "bdrip", "dvdrip", "hdtv", "hdrip",
    "x264", "x265", "h264", "h265", "hevc", "avc", "xvid", "hdr", "hdr10", "10bit",
    "aac", "ac3", "dts", "ddp5", "dd5", "proper", "repack", "remux", "amzn", "dsnp",
    "hmax", "atvp", "unrated", "internal", "multi",
}

LANGS = {
    "en": "en", "eng": "en", "english": "en",
    "es": "es", "spa": "es", "spanish": "es",
    "fr": "fr", "fre": "fr", "fra": "fr", "french": "fr",
    "de": "de", "ger": "de", "deu": "de", "german": "de",
    "it": "it", "ita": "it", "italian": "it",
    "pt": "pt", "por": "pt", "portuguese": "pt",
    "ru": "ru", "rus": "ru", "russian": "ru",
    "ja": "ja", "jpn": "ja", "japanese": "ja",
    "zh": "zh", "chi": "zh", "zho": "zh", "chinese": "zh",
    "ko": "ko", "kor": "ko", "korean": "ko",
    "nl": "nl", "dut": "nl", "nld": "nl", "dutch": "nl",
    "ar": "ar", "ara": "ar", "arabic": "ar",
    "pl": "pl", "pol": "pl", "polish": "pl",
    "sv": "sv", "swe": "sv", "swedish": "sv",
    "fi": "fi", "fin": "fi", "finnish": "fi", "da": "da", "dan": "da", "danish": "da",
    "no": "no", "nob": "no", "nor": "no", "norwegian": "no", "el": "el", "ell": "el", "gre": "el", "greek": "el",
    "he": "he", "heb": "he", "hebrew": "he", "hu": "hu", "hun": "hu", "hungarian": "hu",
    "cs": "cs", "cze": "cs", "ces": "cs", "czech": "cs", "ro": "ro", "rum": "ro", "ron": "ro", "romanian": "ro",
    "vi": "vi", "vie": "vi", "vietnamese": "vi", "id": "id", "ind": "id", "indonesian": "id",
    "uk": "uk", "ukr": "uk", "ukrainian": "uk", "bg": "bg", "bul": "bg", "bulgarian": "bg",
    "hr": "hr", "hrv": "hr", "croatian": "hr", "sr": "sr", "srp": "sr", "serbian": "sr",
    "sl": "sl", "slv": "sl", "slovenian": "sl", "sk": "sk", "slo": "sk", "slk": "sk", "slovak": "sk",
    "tr": "tr", "tur": "tr", "turkish": "tr", "th": "th", "tha": "th", "thai": "th",
    "hi": "hi", "hin": "hi", "hindi": "hi", "ms": "ms", "may": "ms", "msa": "ms", "malay": "ms",
    "fa": "fa", "per": "fa", "fas": "fa", "persian": "fa", "et": "et", "est": "et", "estonian": "et",
    "lv": "lv", "lav": "lv", "latvian": "lv", "lt": "lt", "lit": "lt", "lithuanian": "lt",
    "is": "is", "ice": "is", "isl": "is", "icelandic": "is", "ca": "ca", "cat": "ca", "catalan": "ca",
    "tl": "tl", "fil": "tl", "filipino": "tl", "ta": "ta", "tam": "ta", "tamil": "ta",
    "te": "te", "tel": "te", "telugu": "te", "bn": "bn", "ben": "bn", "bengali": "bn",
    "gl": "gl", "glg": "gl", "galician": "gl", "eu": "eu", "baq": "eu", "eus": "eu", "basque": "eu",
}

SMALL = {"a", "an", "the", "and", "of", "in", "on", "to", "for", "at", "by", "or"}


def clean(name):
    """Dots/underscores to spaces, drop brackets, tidy capitalisation."""
    name = re.sub(r"[._]+", " ", name)
    name = re.sub(r"[\[\(\{].*?[\]\)\}]", " ", name)
    # Stray dashes stuck to one word ("Paragon -the motto-") become spaces;
    # "Spider-Man" and "Show - Subtitle" are left alone.
    name = re.sub(r"(?<=\s)-+(?=\S)|(?<=\S)-+(?=\s|$)", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" -")
    out = []
    for i, w in enumerate(name.split(" ")):
        if w.isupper() and len(w) > 1:
            out.append(w)  # keep acronyms like FBI
        elif i > 0 and w.lower() in SMALL:
            out.append(w.lower())
        else:
            out.append("-".join(p[:1].upper() + p[1:].lower() for p in w.split("-")))
    return " ".join(out)


def safe(part):
    """Make a generated name safe for FAT/exFAT/NTFS drives."""
    part = part.replace(":", " -")
    part = re.sub(r'[<>"/\\|?*]', "", part)
    part = re.sub(r"\s+", " ", part)
    return part.strip().rstrip(". ")


def cut_release(raw):
    """Drop everything from the first release token (1080p, WEB, x264...) on.
    The first word is never cut, so a title like 'Web Therapy' survives."""
    for i, m in enumerate(re.finditer(r"[^ ._\-\[\]\(\)]+", raw)):
        if i > 0 and m.group().lower() in RELEASE_TOKENS:
            return raw[: m.start()]
    return raw


def split_year(raw):
    """'Show.Name.2019' -> ('Show Name', '2019'). Uses the last year that still
    leaves a title in front of it, so '2001.A.Space.Odyssey.1968' -> 1968."""
    padded = " " + cut_release(raw) + " "
    best = None
    for m in YEAR_RE.finditer(padded):
        if clean(padded[: m.start()]):
            best = m
    if best:
        return clean(padded[: best.start()]), best.group(1)
    return clean(cut_release(raw)), None


def sub_lang(stem):
    """'Movie.2019.en' -> ('Movie.2019', '.en'). Only known language codes count."""
    m = re.search(r"\.([a-z]{2,10})$", stem, re.I)
    if m and m.group(1).lower() in LANGS:
        return stem[: m.start()], "." + LANGS[m.group(1).lower()]
    return stem, ""


# Volume / issue / chapter markers: "v01", "Vol. 2", "Volume 3", "#001", "Issue 4",
# "Chapter 5", "c006", "ch.7", "TPB" ... everything from the first one is cut.
# Without one, only a bare number at the very end is the issue ("Saga 054"),
# so "Spider-Man 2099 001" keeps its "2099".
COMIC_MARK_RE = re.compile(
    r"[ ._\-]+(?:v(?:ol(?:ume)?)?\.?\s*\d+|#\s*\d+|issue\s*\d+|chapters?\s*\d+|ch\.?\s*\d+|c\d{2,4}"
    r"|book\s*\d+|part\s*\d+|tpb|omnibus|annual)(?![a-z]).*$", re.I)
COMIC_TRAIL_NUM_RE = re.compile(r"[ ._\-]+\d{1,4}(?:\.\d)?$")


def comic_series(name):
    """'Ironclad v01 (Digital) (Zone).cbz' -> 'Ironclad'; 'Ironclad (2).cbz' -> 'Ironclad';
    'Saga 054 (2018).cbr' -> 'Saga'. Falls back to the cleaned name."""
    stem = name.rsplit(".", 1)[0] if "." in name else name
    stem = LEADING_TAGS_RE.sub("", stem)                    # "[Group] Name" -> "Name"
    stem = re.sub(r"[\[\(\{][^\]\)\}]*[\]\)\}]", " ", stem)   # "(2)", "(Digital)", "[1080p]"
    stem = re.sub(r"[._]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" -")
    series = COMIC_MARK_RE.sub("", " " + stem).strip(" -")
    if series == stem:
        series = COMIC_TRAIL_NUM_RE.sub("", " " + stem).strip(" -")
    return safe(clean(series or stem)) or "Unsorted"


def parse_special(stem):
    """'Show OVA - Title' -> (show_raw, number or None, title). None if not a special."""
    spaced = LEADING_TAGS_RE.sub("", re.sub(r"_+", " ", stem))
    m = SPECIAL_RE.match(spaced)
    if not m or not m.group("show").strip(" ._-"):
        return None
    n = m.group("n") or m.group("n2")
    show = re.sub(r"[ ._\-]+\d{1,3}$", "", m.group("show"))  # "Show - 13 OVA" -> "Show"
    rest = re.sub(r"[\[\(\{][^\]\)\}]*[\]\)\}]", " ", spaced[m.end():])  # drop (BD 1080p), [Group]
    title = clean(re.sub(r"[\[\]\(\)\{\}]", " ", cut_release(rest)))
    return show, (int(n) if n else None), title


def parse_episode(stem):
    """Return (show_raw, season, episode_tag, absolute) or None.
    absolute is True for fansub numbering, "special" / "special?" for OVAs."""
    m = TV_RE.match(stem) or TV_X_RE.match(stem)
    if m and m.group("show").strip(" ._-"):
        ep = "S%02dE%02d" % (int(m.group("s")), int(m.group("e")))
        if m.groupdict().get("e2"):
            ep += "E%02d" % int(m.group("e2"))
        return m.group("show"), int(m.group("s")), ep, False
    sp = parse_special(stem)
    if sp:
        show, n, title = sp
        tag = "S00E%02d" % (n or 1)
        if title:
            tag += " - " + title  # "S00E01 - The Long Road Home": easy to check against TMDb
        return show, 0, tag, ("special" if n else "special?")
    spaced = re.sub(r"_+", " ", stem)
    m = ANIME_RE.match(LEADING_TAGS_RE.sub("", spaced))
    if m and m.group("show").strip(" ._-"):
        return m.group("show"), 1, "S01E%02d" % int(m.group("e")), True
    return None


def plan_name(name, folder=""):
    """Where a file called `name` belongs, relative to the destination.
    `folder` is the folder it's in (only used to decide if a PDF is a comic).
    Returns (parts or None, kind, note). kind is 'tv', 'movie' or 'comic' when
    parts is set, otherwise the reason it was skipped."""
    path = PurePath(name)
    ext = path.suffix.lower()
    stem = path.stem

    if name.startswith("."):
        return None, "hidden / still downloading", ""
    if ext in COMICS:
        return ("Comics", comic_series(name), name), "comic", ""
    if ext in BOOKS:
        if COMIC_FOLDER_RE.search(folder or ""):
            return ("Comics", comic_series(name), name), "comic", ""
        return None, "document - PDFs/EPUBs are only moved from a Comics or Manga folder", ""
    if ext not in VIDEO and ext not in SUBS:
        return None, "not video/sub/comic", ""
    if ext in VIDEO and "sample" in stem.lower():
        return None, "sample", ""
    if ext in VIDEO and CREDITS_RE.search(stem):
        return None, "opening/ending credits clip", ""

    stem = SITE_PREFIX_RE.sub("", stem)
    lang = ""
    if ext in SUBS:
        stem, lang = sub_lang(stem)

    ep = parse_episode(stem)
    if ep:
        show_raw, season, tag, absolute = ep
        show, year = split_year(show_raw)
        show_dir = safe("%s (%s)" % (show, year) if year else show)
        new = safe("%s %s%s" % (show_dir, tag, lang)) + ext
        note = {True: "absolute episode number - check the season",
                "special": SPECIAL_NOTE, "special?": SPECIAL_GUESS_NOTE}.get(absolute, "")
        return ("TV", show_dir, "Season %02d" % season, new), "tv", note

    title, year = split_year(stem)
    if year:
        movie = safe("%s (%s)" % (title, year))
        return ("Movies", movie, movie + lang + ext), "movie", ""

    return None, "can't tell TV vs movie - rename by hand", ""

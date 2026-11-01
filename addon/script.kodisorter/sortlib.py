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
COMICS = {".cbz", ".cbr", ".cb7", ".cbt", ".pdf", ".epub"}
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
# Release-group tags at the start: "[SubTeam] ", "(Group_One)_"
LEADING_TAGS_RE = re.compile(r"^(?:\s*(?:\[[^\]]*\]|\([^)]*\)))+\s*")
YEAR_RE = re.compile(r"[ ._\-\(\[]((?:19|20)\d{2})(?=[ ._\-\)\]]|$)")
CREDITS_RE = re.compile(r"(?<![a-z])nc(?:op|ed)\d*(?![a-z])", re.I)

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


def parse_episode(stem):
    """Return (show_raw, season, episode_tag, absolute) or None."""
    m = TV_RE.match(stem) or TV_X_RE.match(stem)
    if m and m.group("show").strip(" ._-"):
        ep = "S%02dE%02d" % (int(m.group("s")), int(m.group("e")))
        if m.groupdict().get("e2"):
            ep += "E%02d" % int(m.group("e2"))
        return m.group("show"), int(m.group("s")), ep, False
    spaced = re.sub(r"_+", " ", stem)
    m = ANIME_RE.match(LEADING_TAGS_RE.sub("", spaced))
    if m and m.group("show").strip(" ._-"):
        return m.group("show"), 1, "S01E%02d" % int(m.group("e")), True
    return None


def plan_name(name):
    """Where a file called `name` belongs, relative to the destination.
    Returns (parts or None, kind, note). kind is 'tv', 'movie' or 'comic' when
    parts is set, otherwise the reason it was skipped."""
    path = PurePath(name)
    ext = path.suffix.lower()
    stem = path.stem

    if name.startswith("."):
        return None, "hidden / still downloading", ""
    if ext in COMICS:
        return ("Comics", name), "comic", ""
    if ext not in VIDEO and ext not in SUBS:
        return None, "not video/sub/comic", ""
    if ext in VIDEO and "sample" in stem.lower():
        return None, "sample", ""
    if ext in VIDEO and CREDITS_RE.search(stem):
        return None, "opening/ending credits clip", ""

    lang = ""
    if ext in SUBS:
        stem, lang = sub_lang(stem)

    ep = parse_episode(stem)
    if ep:
        show_raw, season, tag, absolute = ep
        show, year = split_year(show_raw)
        show_dir = safe("%s (%s)" % (show, year) if year else show)
        new = "%s %s%s%s" % (show_dir, tag, lang, ext)
        note = "absolute episode number - check the season" if absolute else ""
        return ("TV", show_dir, "Season %02d" % season, new), "tv", note

    title, year = split_year(stem)
    if year:
        movie = safe("%s (%s)" % (title, year))
        return ("Movies", movie, movie + lang + ext), "movie", ""

    return None, "can't tell TV vs movie - rename by hand", ""

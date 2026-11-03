"""Filename -> Kodi folder/name logic. Pure: no disk access, no Kodi imports.

Shared by the Kodi add-on (default.py) and the command-line kodi_sort.py, so a
naming fix made here applies to both.

  TV:     TV/Show Name (Year)/Season 01/Show Name (Year) S01E02.mkv
  Movies: Movies/Movie Name (Year)/Movie Name (Year).mkv
  Comics: Comics/<original file name>
  Tutorials: Tutorials/<Subject>/<original file name>   (AutoCAD, Revit ...)
"""
import re
from pathlib import PurePath

VIDEO = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".ts", ".webm"}
SUBS = {".srt", ".ass", ".ssa", ".sub", ".vtt"}
# Separate audio tracks (usually an English dub shipped next to the video):
# moved next to their video with the same name, so Kodi offers them as an extra track.
AUDIO = {".mka", ".ac3", ".eac3", ".dts"}
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
CREDITS_NOTE = "opening/ending credits clip - put in Season 00 as the next free episode (Kodi lists it only if TMDb has that special)"
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

# Tutorials: a name that says so ("AutoCAD 2026 FULL Course For BEGINNERS!",
# "Revit Tutorial - Walls"), or a file inside a "Tutorials"/"Courses" folder.
# Words like "how to", "lesson", "training" are left out: they are film titles too
# ("How to Train Your Dragon", "Training Day").
TUTORIAL_RE = re.compile(
    r"(?<![a-z])(?:tutorials?|full course|crash course|masterclass|master class|course for beginners|"
    r"beginners? course|beginner'?s guide|for beginners|for absolute beginners|step[ ._\-]by[ ._\-]step guide|"
    r"udemy|lynda|linkedin learning|skillshare|pluralsight|coursera)(?![a-z])", re.I)
TUTORIAL_FOLDER_RE = re.compile(r"^(?:tutorials?|courses?|training|lessons|learning)$", re.I)
# Subject folder from a name: the first match wins, so the specific names come first
# ("AutoCAD Civil 3D" -> Civil 3D, "Autodesk Revit" -> Revit).
TUTORIAL_SUBJECTS = [
    ("Civil 3D", r"civil[ ._\-]?3d"), ("AutoCAD", r"auto[ ._\-]?cad"), ("Revit", r"revit"),
    ("SketchUp", r"sketch[ ._\-]?up"), ("Blender", r"blender"), ("Fusion 360", r"fusion[ ._\-]?360"),
    ("SolidWorks", r"solid[ ._\-]?works"), ("Inventor", r"inventor"), ("3ds Max", r"3ds[ ._\-]?max"),
    ("Maya", r"maya"), ("Rhino", r"rhino(?:ceros)?|grasshopper"), ("ArchiCAD", r"archi[ ._\-]?cad"),
    ("Navisworks", r"navisworks"), ("Lumion", r"lumion"), ("Enscape", r"enscape"), ("V-Ray", r"v[ ._\-]?ray"),
    ("Twinmotion", r"twinmotion"), ("FreeCAD", r"free[ ._\-]?cad"), ("Cinema 4D", r"cinema[ ._\-]?4d|c4d"),
    ("ZBrush", r"z[ ._\-]?brush"), ("Unreal Engine", r"unreal"), ("Unity", r"unity"),
    ("Photoshop", r"photoshop"), ("Illustrator", r"illustrator"), ("InDesign", r"indesign"),
    ("Premiere Pro", r"premiere"), ("After Effects", r"after[ ._\-]?effects"), ("Lightroom", r"lightroom"),
    ("DaVinci Resolve", r"davinci|resolve"), ("Excel", r"excel"), ("PowerPoint", r"power[ ._\-]?point"),
    ("Word", r"ms[ ._\-]?word|microsoft[ ._\-]?word"), ("Python", r"python"), ("Kodi", r"kodi"),
    ("Ableton Live", r"ableton"), ("Claude Code", r"claude[ ._\-]?code"),
    ("OpenClaw", r"open[ ._\-]?claw|clawdbot|moltbot"),
    # 20/20 (kitchen/bath design). "/" can't be in a file name, so 20-20 / 20 20; a bare
    # "2020" is a year, so that spelling only counts with Design/Fusion/Giza/CAP after it.
    ("2020 Design", r"20[ ._\-]20(?![0-9])|2020[ ._\-]*(?:design|fusion|giza|cap)"),
]
TUTORIAL_SUBJECT_RES = [(n, re.compile(r"(?<![a-z0-9])(?:%s)(?![a-z])" % rx, re.I)) for n, rx in TUTORIAL_SUBJECTS]


def tutorial_subject(stem):
    """'Autodesk Revit - Full Beginner Course' -> 'Revit'. None when no known program is named."""
    for name, rx in TUTORIAL_SUBJECT_RES:
        if rx.search(stem.replace("_", " ")):
            return name
    return None


def tutorial_folder(folder):
    """The subject folder the user already put a file in: '.../Tutorials/AutoCAD/x' -> 'AutoCAD'.
    '' when it sits straight in Tutorials, None when it isn't under a Tutorials folder."""
    parts = [p for p in re.split(r"[\\/]", folder or "") if p]
    for i in range(len(parts) - 1, -1, -1):
        if TUTORIAL_FOLDER_RE.match(parts[i].strip()):
            return parts[i + 1].strip() if i + 1 < len(parts) else ""
    return None


def plan_tutorial(name, stem, folder):
    """('Tutorials', subject, name) or None."""
    sub = tutorial_folder(folder)
    if sub is None and not TUTORIAL_RE.search(stem.replace("_", " ").replace(".", " ")):
        return None
    subject = sub or tutorial_subject(stem) or "Other"
    return ("Tutorials", safe(subject), safe(PurePath(name).stem) + PurePath(name).suffix)


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


def parse_credits(stem):
    """'Show (Uncensored Textless Opening) [Group]' -> ('Show', 'Uncensored Textless Opening');
    '[Group] Show - NCOP1 (BD)' -> ('Show', 'NCOP1'). None if no show name is in front."""
    spaced = LEADING_TAGS_RE.sub("", re.sub(r"_+", " ", stem))
    if " " not in spaced.strip():
        spaced = spaced.replace(".", " ")
    m = CREDITS_RE.search(spaced)
    if not m:
        return None
    head = spaced[:m.start()]
    opened = max(head.rfind("("), head.rfind("["))
    if opened > head.rfind(")") and opened > head.rfind("]"):
        close = spaced.find(")" if spaced[opened] == "(" else "]", m.end())
        title = spaced[opened + 1:close if close > 0 else None]
        head = head[:opened]
    else:
        title = re.sub(r"[\[\(\{][^\]\)\}]*[\]\)\}]", " ", spaced[m.start():])
        title = cut_release(title)
    show = re.sub(r"[\[\(].*$", "", head)
    show = re.sub(r"[ ._\-]+\d{1,3}$", "", show.strip(" ._-")).strip(" ._-")
    show = re.sub(r"(?i)[ ._\-]+(?:s\d{1,2}|season[ ._\-]*\d{1,2})$", "", show).strip(" ._-")
    title = clean(re.sub(r"[\[\]\(\)\{\}]", " ", title))
    if not show or not re.search(r"[a-z]", show, re.I):
        return None
    return show, title or m.group(0)


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


def episode_tag(name):
    """'S01E05 - Quiet Streets.mka' -> 'S01E05'. Works with no show name in
    front (extras folders often drop it). None when there's no episode number."""
    stem = SITE_PREFIX_RE.sub("", PurePath(name).stem)
    ep = parse_episode("x " + stem)
    return ep[2].split(" ")[0].upper() if ep else None


def plan_name(name, folder=""):
    """Where a file called `name` belongs, relative to the destination.
    `folder` is the folder it's in (only used to decide if a PDF is a comic).
    Returns (parts or None, kind, note). kind is 'tv', 'movie', 'comic' or 'tutorial' when
    parts is set, otherwise the reason it was skipped."""
    if re.search(r"%[0-9a-fA-F]{2}", name):
        # URL-encoded name from an early version: "%5bsubcrew%5dtinman" -> "[subcrew]tinman"
        try:
            from urllib.parse import unquote
        except ImportError:
            from urllib import unquote
        name = unquote(name)
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
    if ext in VIDEO or ext in SUBS:
        tut = plan_tutorial(name, stem, folder)
        if tut and not (TV_RE.search(stem) or TV_X_RE.search(stem)):
            return tut, "tutorial", ""
    if ext in VIDEO and CREDITS_RE.search(stem) and not re.search(r"(?i)(?<![a-z0-9])s00e\d{2}(?![0-9])", stem):
        # (an S00Exx name is one already sorted into Specials: treated like any episode below)
        cr = parse_credits(SITE_PREFIX_RE.sub("", stem))
        parent = re.split(r"[\\/]", (folder or "").rstrip("/\\"))[-1]
        if not cr and parent and not re.match(r"(?i)^(?:extras?|bonus|specials?|nc|credits|op|ed|"
                                              r"openings?|endings?|ncop|nced|creditless|textless)$", parent):
            cr = parse_credits(SITE_PREFIX_RE.sub("", parent) + " " + stem)
        if not cr:
            return None, "opening/ending credits clip (no show name in the file name)", ""
        show, year = split_year(cr[0])
        show_dir = safe("%s (%s)" % (show, year) if year else show)
        new = safe("%s S00E01 - %s" % (show_dir, cr[1])) + ext
        return ("TV", show_dir, "Season 00", new), "tv", CREDITS_NOTE

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

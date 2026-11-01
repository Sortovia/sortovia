#!/usr/bin/env python3
"""
kodi_sort.py - move finished downloads into Kodi-friendly folders.

  TV:     <dest>/TV/Show Name (Year)/Season 01/Show Name (Year) S01E02.mkv
  Movies: <dest>/Movies/Movie Name (Year)/Movie Name (Year).mkv
  Comics: <dest>/Comics/<original file name>

Dry run by default (shows what it WOULD do). Add --go to actually move files.
Hidden files (names starting with ".", e.g. downloads still in progress) are
never touched. --dest may be the same drive as --src (sort in place).

Usage:
  python kodi_sort.py --src /storage/XXXX-XXXX --dest /storage/YYYY-YYYY
  python kodi_sort.py --src /storage/XXXX-XXXX --dest /storage/YYYY-YYYY --go
"""
import argparse
import os
import re
import shutil
from pathlib import Path

VIDEO = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".ts", ".webm"}
SUBS = {".srt", ".ass", ".ssa", ".sub", ".vtt"}
COMICS = {".cbz", ".cbr", ".cb7", ".cbt", ".pdf", ".epub"}
MIN_VIDEO_BYTES = 50 * 1024 * 1024  # skip "sample" clips
KODI_FOLDERS = ("TV", "Movies", "Comics")

# SxxEyy, optional second episode only with an explicit E / -E (never resolution digits)
TV_RE = re.compile(
    r"^(?P<show>.*?)[ ._\-\[\(]*(?<![a-z])s(?P<s>\d{1,2})[ ._\-]?e(?P<e>\d{1,3})"
    r"(?:-?e(?P<e2>\d{1,3}))?(?!\d)",
    re.I,
)
TV_X_RE = re.compile(r"^(?P<show>.*?)[ ._\-]+(?P<s>\d{1,2})x(?P<e>\d{2,3})(?!\d)", re.I)
# Fansub style "Show - 03" (absolute numbering, assumed Season 01)
ANIME_RE = re.compile(r"^(?P<show>.+?)\s+-\s+(?P<e>\d{1,3})(?:v\d)?(?=\s|$|[\[\(])")
LEADING_TAGS_RE = re.compile(r"^(?:\s*\[[^\]]*\])+\s*")
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


def clean(name: str) -> str:
    """Dots/underscores to spaces, drop brackets, tidy capitalisation."""
    name = re.sub(r"[._]+", " ", name)
    name = re.sub(r"[\[\(\{].*?[\]\)\}]", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" -")
    small = {"a", "an", "the", "and", "of", "in", "on", "to", "for", "at", "by", "or"}
    words = name.split(" ")
    out = []
    for i, w in enumerate(words):
        if w.isupper() and len(w) > 1:
            out.append(w)  # keep acronyms like FBI
        elif i > 0 and w.lower() in small:
            out.append(w.lower())
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return " ".join(out)


def safe(part: str) -> str:
    """Make a generated name safe for FAT/exFAT/NTFS drives."""
    part = part.replace(":", " -")
    part = re.sub(r'[<>"/\\|?*]', "", part)
    part = re.sub(r"\s+", " ", part)
    return part.strip().rstrip(". ")


def cut_release(raw: str) -> str:
    """Drop everything from the first release token (1080p, WEB, x264...) on.
    The first word is never cut, so a title like 'Web Therapy' survives."""
    for i, m in enumerate(re.finditer(r"[^ ._\-\[\]\(\)]+", raw)):
        if i > 0 and m.group().lower() in RELEASE_TOKENS:
            return raw[: m.start()]
    return raw


def split_year(raw: str):
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


def sub_lang(stem: str):
    """'Movie.2019.en' -> ('Movie.2019', '.en'). Only known language codes count."""
    m = re.search(r"\.([a-z]{2,10})$", stem, re.I)
    if m and m.group(1).lower() in LANGS:
        return stem[: m.start()], "." + LANGS[m.group(1).lower()]
    return stem, ""


def parse_episode(stem: str):
    """Return (show_raw, season, episode_tag, absolute) or None."""
    m = TV_RE.match(stem) or TV_X_RE.match(stem)
    if m and m.group("show").strip(" ._-"):
        ep = f"S{int(m.group('s')):02d}E{int(m.group('e')):02d}"
        if m.groupdict().get("e2"):
            ep += f"E{int(m.group('e2')):02d}"
        return m.group("show"), int(m.group("s")), ep, False
    m = ANIME_RE.match(LEADING_TAGS_RE.sub("", stem))
    if m and m.group("show").strip(" ._-"):
        return m.group("show"), 1, f"S01E{int(m.group('e')):02d}", True
    return None


def target_for(name: str, dest: Path):
    """Work out where a file called `name` belongs. Pure: no disk access.
    Returns (target or None, kind, note)."""
    path = Path(name)
    ext = path.suffix.lower()
    stem = path.stem

    if ext in COMICS:
        return dest / "Comics" / path.name, "comic", ""

    if ext not in VIDEO and ext not in SUBS:
        return None, "skip (not video/sub/comic)", ""

    if ext in VIDEO and "sample" in stem.lower():
        return None, "skip (sample)", ""
    if ext in VIDEO and CREDITS_RE.search(stem):
        return None, "skip (opening/ending credits clip)", ""

    lang = ""
    if ext in SUBS:
        stem, lang = sub_lang(stem)

    ep = parse_episode(stem)
    if ep:
        show_raw, season, tag, absolute = ep
        show, year = split_year(show_raw)
        show_dir = safe(f"{show} ({year})" if year else show)
        new = f"{show_dir} {tag}{lang}{ext}"
        note = "absolute episode number - check the season" if absolute else ""
        return dest / "TV" / show_dir / f"Season {season:02d}" / new, "tv", note

    title, year = split_year(stem)
    if year:
        movie = safe(f"{title} ({year})")
        return dest / "Movies" / movie / f"{movie}{lang}{ext}", "movie", ""

    return None, "skip (couldn't tell TV vs movie - rename by hand)", ""


def plan_for(path: Path, dest: Path):
    """target_for plus the checks that need the real file."""
    if path.name.startswith("."):
        return None, "skip (hidden / still downloading)", ""
    if path.suffix.lower() in VIDEO and path.stat().st_size < MIN_VIDEO_BYTES:
        return None, "skip (too small - sample?)", ""
    return target_for(path.name, dest)


def under(p: Path, folder: Path) -> bool:
    try:
        p.relative_to(folder)
        return True
    except ValueError:
        return False


def move(src: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    if src.stat().st_dev == target.parent.stat().st_dev:
        os.rename(src, target)  # same drive: instant, nothing copied
    else:
        shutil.move(str(src), str(target))


def main():
    ap = argparse.ArgumentParser(description="Sort downloads into Kodi folders")
    ap.add_argument("--src", required=True, help="folder with finished downloads (thumb drive)")
    ap.add_argument("--dest", required=True, help="drive root that holds TV/Movies/Comics")
    ap.add_argument("--go", action="store_true", help="actually move files (default is dry run)")
    args = ap.parse_args()

    src, dest = Path(args.src).resolve(), Path(args.dest).resolve()
    if not src.is_dir() or not dest.is_dir():
        raise SystemExit(f"Can't find folder: {src if not src.is_dir() else dest}")

    # If dest is inside src (sorting in place), don't re-sort what's already sorted.
    done_dirs = [dest / k for k in KODI_FOLDERS]

    moved = skipped = 0
    for f in sorted(p for p in src.rglob("*") if p.is_file()):
        if any(under(f, d) for d in done_dirs):
            continue
        target, kind, note = plan_for(f, dest)
        rel = f.relative_to(src)
        if target is None:
            print(f"  SKIP  {rel}  -> {kind}")
            skipped += 1
            continue
        if target.exists():
            print(f"  EXISTS {rel}  -> {target} (left alone)")
            skipped += 1
            continue
        print(f"  {kind.upper():6} {rel}\n         -> {target.relative_to(dest)}")
        if note:
            print(f"         !! {note}")
        if args.go:
            move(f, target)
        moved += 1

    mode = "Moved" if args.go else "Would move"
    print(f"\n{mode} {moved} file(s), skipped {skipped}.")
    if not args.go:
        print("Dry run only. Re-run with --go to move them.")


if __name__ == "__main__":
    main()

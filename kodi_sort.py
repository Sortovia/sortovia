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
import shutil
import sys
from pathlib import Path

# Naming rules live in the add-on folder so the Xbox add-on and this script
# always agree.
sys.path.insert(0, str(Path(__file__).resolve().parent / "addon" / "script.kodisorter"))
from sortlib import (  # noqa: E402,F401
    VIDEO, SUBS, COMICS, MIN_VIDEO_BYTES, clean, safe, cut_release, split_year,
    sub_lang, parse_episode, plan_name,
)

KODI_FOLDERS = ("TV", "Movies", "Comics")


def target_for(name: str, dest: Path, folder: str = ""):
    """Work out where a file called `name` belongs. Pure: no disk access.
    Returns (target or None, kind, note)."""
    parts, kind, note = plan_name(name, folder)
    if parts is None:
        return None, f"skip ({kind})", note
    return dest.joinpath(*parts), kind, note


def plan_for(path: Path, dest: Path):
    """target_for plus the checks that need the real file."""
    if path.name.startswith("."):
        return None, "skip (hidden / still downloading)", ""
    if path.suffix.lower() in VIDEO and path.stat().st_size < MIN_VIDEO_BYTES:
        return None, "skip (too small - sample?)", ""
    return target_for(path.name, dest, str(path.parent))


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

"""Work out how an album's tags should read so Kodi shows it as one album, linked to each artist.

Each track gets one ALBUM ARTIST (the main artist), ARTISTS with one entry per person, and ARTIST
as display text. Reads what's on the drive and returns a plan. Nothing here writes a file.
"""
import re

from sortlib import _names

# "&", "and" and "x" can be part of a band's name, so names used as folders are protected below.
SPLIT = re.compile(r"\s*(?:[/;,&]|\s(?:feat\.?|ft\.?|featuring|and|x|vs\.?)\s)\s*", re.I)
_HAS_SEPARATOR = re.compile(r"[/;,&]|\s(?:feat\.?|ft\.?|featuring|and|x|vs\.?)\s", re.I)


def split_artists(credit, protected=()):
    """Each artist once, in order. A protected name such as a folder called "One & Two" stays whole."""
    text = credit or ""
    held = []
    for i, name in enumerate(n for n in protected if n and _HAS_SEPARATOR.search(n)):
        pattern = re.compile(r"(?<![^\W_])%s(?![^\W_])" % re.escape(name), re.I)
        if pattern.search(text):
            held.append(name)
            text = pattern.sub("\x01%d\x01" % (len(held) - 1), text)
    out, seen = [], set()
    for part in SPLIT.split(text):
        part = part.strip()
        m = re.match("^\x01(\\d+)\x01$", part)
        if m:
            part = held[int(m.group(1))]
        if part and part.lower() not in seen:
            seen.add(part.lower())
            out.append(part)
    return out


def spellings_from(credits, folders):
    """{lower case name: the spelling to use} so "BAND" and "Band" are one artist: a folder's spelling,
    else the most common, preferring one that isn't all capitals."""
    seen = {}
    for credit in credits:
        for name in split_artists(credit, folders):
            variants = seen.setdefault(name.lower(), {})
            variants[name] = variants.get(name, 0) + 1
    out = dict((key, sorted(v, key=lambda n: (-v[n], n.isupper(), n))[0]) for key, v in seen.items())
    out.update((f.lower(), f) for f in folders)
    return out


def _spell(name, spellings):
    return spellings.get(name.lower(), name)


def album_artist(credits, existing, folders):
    """The main artist for one album. An album artist all the tracks already agree on stays, unless
    it's really a list of names. Otherwise: a folder naming an artist on every track, then the artist
    named on every track, then the top folder."""
    agreed = set(existing)
    if len(agreed) == 1 and "" not in agreed and not _HAS_SEPARATOR.search(existing[0]):
        return existing[0]
    credits = [c for c in credits if c]
    for folder in folders:
        if credits and all(_names(folder, c) for c in credits):
            return folder
    if credits:
        for name in split_artists(credits[0], folders):
            if all(_names(name, c) for c in credits):
                return name
    return folders[0] if folders else (split_artists(credits[0])[0] if credits else "")


def _year(date):
    """The usable year in a date, or "" for a blank one or one like 0000."""
    m = re.match(r"^(\d{4})", date or "")
    return m.group(1) if m and m.group(1) != "0000" else ""


def album_year(tracks):
    """The year most tracks on an album agree on, or ""."""
    counts = {}
    for t in tracks:
        y = _year(t.get("date"))
        if y:
            counts[y] = counts.get(y, 0) + 1
    return sorted(counts, key=lambda y: (-counts[y], y))[0] if counts else ""


def plan_album(tracks, folders, spellings=None):
    """tracks: [{"name", "version", "album", "artist", "artists", "albumartist"}] from one album in one folder.
    folders: names from the artist's folder downwards that could name an artist.
    Returns {"album_artist", "changes": [{"name", "artists", "display", "year", "why"}]}, with only tracks that
    change. A track with no year, or a year of 0000, takes the album's."""
    spellings = spellings or {}
    main = _spell(album_artist([t.get("artist", "") for t in tracks],
                               [t.get("albumartist", "") for t in tracks], folders), spellings)
    year = album_year(tracks)
    changes = []
    for t in tracks:
        names = list(t.get("artists") or []) or [_spell(n, spellings) for n in split_artists(t.get("artist", ""), folders)]
        display = " & ".join(names) if names else ""
        why = []
        if t.get("version") != 4:
            why.append("ID3v2.%s to ID3v2.4" % t.get("version", "?") if t.get("version") else "new ID3v2.4 tag")
        if t.get("albumartist", "") != main:
            why.append("album artist")
        if display and t.get("artist", "") != display:
            why.append("artist")
        if len(names) > 1 and list(t.get("artists") or []) != names:
            why.append("artists")
        new_year = year if year and not _year(t.get("date")) else None
        if new_year:
            why.append("year")
        if why:
            changes.append({"name": t["name"], "artists": names if len(names) > 1 else None,
                            "display": display or None, "year": new_year, "why": ", ".join(why)})
    return {"album_artist": main, "changes": changes}


def preview(album, plan):
    lines = ["%s  (album artist: %s)" % (album, plan["album_artist"])]
    for c in plan["changes"]:
        lines.append("   %s" % c["name"])
        if c["artists"]:
            lines.append("      artists: %s" % "; ".join(c["artists"]))
        lines.append("      changes: %s" % c["why"])
    return "\n".join(lines)

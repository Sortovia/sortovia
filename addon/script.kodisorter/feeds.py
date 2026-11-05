"""My releases: read the RSS, Atom or JSON feeds a person adds for their own uploads.

No trackers are built in, and no search is sent to any site: a feed is read as it is,
and filtering happens on this device. Feed addresses often contain a private key,
so they are never logged or shown once saved.
"""
import json
import re
import xml.etree.ElementTree as ET

MAX_FEED = 5 * 1024 * 1024
_HEX = re.compile(r"^[0-9a-fA-F]{40}$")
_B32 = re.compile(r"^[A-Za-z2-7]{32}$")
_BTIH = re.compile(r"urn:btih:([0-9a-zA-Z]{32,40})")


def _local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def info_hash(text):
    """The torrent's ID from a magnet link or a bare hash, in lower case; '' if there is none."""
    text = (text or "").strip()
    m = _BTIH.search(text)
    if m:
        return m.group(1).lower()
    return text.lower() if _HEX.match(text) or _B32.match(text) else ""


def _magnet(h, title):
    try:
        from urllib.parse import quote
    except ImportError:
        from urllib import quote
    return "magnet:?xt=urn:btih:%s&dn=%s" % (h, quote(title.encode("utf-8")))


def _to_int(text):
    try:
        return int(text)
    except (TypeError, ValueError):
        return 0


def _item(title, feed, candidates, size=0):
    """One release from the links found for it, or None if it has nothing to fetch."""
    title = (title or "").strip() or "Untitled"
    out = {"title": title, "feed": feed, "size": size, "magnet": "", "torrent_url": "", "hash": ""}
    for c in candidates:
        c = (c or "").strip()
        if c.lower().startswith("magnet:") and not out["magnet"]:
            out["magnet"], out["hash"] = c, info_hash(c)
        elif info_hash(c) and not out["hash"] and "://" not in c:
            out["hash"] = info_hash(c)
        elif re.match(r"^https?://", c, re.I) and not out["torrent_url"] and ".torrent" in c.lower():
            out["torrent_url"] = c
    if out["hash"] and not out["magnet"]:
        out["magnet"] = _magnet(out["hash"], title)
    return out if out["magnet"] or out["torrent_url"] else None


def _parse_xml(body, feed):
    out = []
    root = ET.fromstring(body)
    for node in root.iter():
        if _local(node.tag) not in ("item", "entry"):
            continue
        title, size, found = "", 0, []
        for child in node:
            name = _local(child.tag)
            if name == "title":
                title = child.text or ""
            elif name in ("link", "guid", "magneturi", "infohash", "id"):
                found += [child.text, child.get("href")]
            elif name == "enclosure":
                url = child.get("url") or ""
                if "bittorrent" in (child.get("type") or "") and url and ".torrent" not in url.lower():
                    url += "#.torrent"  # a torrent link whose address doesn't say so
                found.append(url)
                size = size or _to_int(child.get("length"))
            elif name in ("contentlength", "size"):
                size = size or _to_int(child.text)
            elif name == "attr":  # Torznab
                key = (child.get("name") or "").lower()
                if key in ("magneturl", "infohash"):
                    found.insert(0, child.get("value"))
                elif key == "size":
                    size = size or _to_int(child.get("value"))
        item = _item(title, feed, found, size)
        if item:
            out.append(item)
    return out


def _parse_json(body, feed):
    data = json.loads(body.decode("utf-8"))
    rows = data.get("releases", []) if isinstance(data, dict) else data
    out = []
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict):
            item = _item(r.get("title") or r.get("name"), feed, [r.get("magnet"), r.get("infohash"), r.get("torrent")],
                         _to_int(r.get("size")))
            if item:
                out.append(item)
    return out


def parse(body, feed=""):
    """[release] from a feed's text. Raises ValueError if it isn't a feed."""
    if len(body) > MAX_FEED:
        raise ValueError("that feed is too big")
    start = body.lstrip()[:1]
    try:
        return _parse_json(body, feed) if start in (b"[", b"{") else _parse_xml(body, feed)
    except (ET.ParseError, ValueError, UnicodeDecodeError):
        raise ValueError("that address didn't return a feed")


def merge(lists):
    """All feeds' releases as one list. A release on several sites shows once when its ID matches."""
    seen, out = set(), []
    for rows in lists:
        for r in rows:
            key = r.get("hash") or r["title"].lower()
            if key not in seen:
                seen.add(key)
                out.append(r)
    return out


def matching(rows, words):
    """Releases whose title has every typed word. Nothing is sent anywhere."""
    want = (words or "").lower().split()
    return [r for r in rows if all(w in r["title"].lower() for w in want)]

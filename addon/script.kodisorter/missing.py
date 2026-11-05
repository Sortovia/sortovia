"""Find missing episodes in Kodi's TV library.

For every TV show in the library, the full episode list comes from TVmaze
(free, no key), matched by the show's IMDb or TVDB id from Kodi (name search
as a fallback). Only episodes that have already aired are counted, and only
in seasons you have at least one episode of. Specials (season 0) are skipped.
"""
import json
import re
import time

import xbmc

TVMAZE = "https://api.tvmaze.com"


def _rpc(method, params):
    reply = json.loads(xbmc.executeJSONRPC(json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))
    if "error" in reply:
        raise IOError("Kodi library: %s" % reply["error"].get("message"))
    return reply.get("result") or {}


def library_shows():
    shows = _rpc("VideoLibrary.GetTVShows", {"properties": ["title", "year", "uniqueid", "imdbnumber"]})
    return shows.get("tvshows", [])


def owned_episodes(tvshowid):
    eps = _rpc("VideoLibrary.GetEpisodes", {"tvshowid": tvshowid, "properties": ["season", "episode"]})
    return set((e["season"], e["episode"]) for e in eps.get("episodes", []))


def _get(url):
    try:
        from urllib.request import Request, urlopen
        from urllib.parse import quote
    except ImportError:
        from urllib2 import Request, urlopen
        from urllib import quote  # noqa: F401
    for attempt in range(3):
        try:
            resp = urlopen(Request(url, headers={"User-Agent": "Sortovia"}), timeout=20)
            try:
                return json.loads(resp.read().decode("utf-8"))
            finally:
                resp.close()
        except Exception as e:
            code = getattr(e, "code", None)
            if code == 404:
                return None
            if code == 429 and attempt < 2:  # TVmaze: 20 requests / 10 s
                time.sleep(5)
                continue
            raise


def tvmaze_show(show):
    try:
        from urllib.parse import quote
    except ImportError:
        from urllib import quote
    ids = show.get("uniqueid") or {}
    imdb = ids.get("imdb") or (show.get("imdbnumber") if str(show.get("imdbnumber", "")).startswith("tt") else "")
    if imdb:
        found = _get("%s/lookup/shows?imdb=%s" % (TVMAZE, imdb))
        if found:
            return found
    if ids.get("tvdb"):
        found = _get("%s/lookup/shows?thetvdb=%s" % (TVMAZE, ids["tvdb"]))
        if found:
            return found
    title = re.sub(r"\s*\(\d{4}\)$", "", show.get("title", ""))
    return _get("%s/singlesearch/shows?q=%s" % (TVMAZE, quote(title)))


def aired_episodes(maze_id, today):
    eps = _get("%s/shows/%d/episodes" % (TVMAZE, maze_id)) or []
    out = {}
    for e in eps:
        if e.get("type", "regular") != "regular" or not e.get("number") or not e.get("season"):
            continue
        if not e.get("airdate") or e["airdate"] > today:
            continue  # not aired yet
        out[(e["season"], e["number"])] = (e.get("name") or "", e["airdate"])
    return out


def find_missing(progress=None, cancelled=None):
    """Returns (report_text, data). progress(i, n, title) is called per show."""
    today = time.strftime("%Y-%m-%d")
    shows = sorted(library_shows(), key=lambda s: s.get("title", "").lower())
    results, problems = [], []
    for i, show in enumerate(shows):
        if cancelled and cancelled():
            problems.append("stopped after %d of %d shows" % (i, len(shows)))
            break
        title = show.get("title", "?")
        if progress:
            progress(i, len(shows), title)
        try:
            have = owned_episodes(show["tvshowid"])
            maze = tvmaze_show(show)
            if not maze:
                problems.append("%s: not found on TVmaze" % title)
                continue
            aired = aired_episodes(maze["id"], today)
        except Exception as e:
            problems.append("%s: %s" % (title, e))
            continue
        seasons = sorted(set(s for s, _ in have if s > 0))
        missing = sorted(k for k in aired if k[0] in seasons and k not in have)
        other = sorted(set(s for s, _ in aired) - set(seasons))
        results.append({"title": title, "tvmaze": maze.get("url"), "seasons": seasons,
                        "year": show.get("year"), "ids": show.get("uniqueid") or {},
                        "missing": [{"season": s, "episode": e, "name": aired[(s, e)][0],
                                     "aired": aired[(s, e)][1]} for s, e in missing],
                        "seasons_not_in_library": other})
        time.sleep(0.3)  # stay well under TVmaze's rate limit
    data = {"date": today, "shows": results, "problems": problems}
    return report(data), data


def _ranges(nums):
    out, start, prev = [], None, None
    for n in nums:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append((start, prev))
            start = prev = n
    if start is not None:
        out.append((start, prev))
    return ", ".join(str(a) if a == b else "%d-%d" % (a, b) for a, b in out)


def report(data, footer=""):
    results, problems = data["shows"], data["problems"]
    gaps = [r for r in results if r["missing"]]
    n_missing = sum(len(r["missing"]) for r in results)
    lines = ["Missing episodes - %s" % time.strftime("%Y-%m-%d %H:%M"),
             "%d shows checked, %d with gaps, %d episodes missing (only aired episodes, "
             "only in seasons you have)." % (len(results), len(gaps), n_missing), ""]
    for r in gaps:
        lines.append("%s  (%d missing)" % (r["title"], len(r["missing"])))
        by_season = {}
        for m in r["missing"]:
            by_season.setdefault(m["season"], []).append(m)
        where = r.get("where") or {}
        if "all" in where:
            lines.append("  Where to watch: " + where["all"])
        for season, eps in sorted(by_season.items()):
            lines.append("  Season %02d: E%s" % (season, _ranges([m["episode"] for m in eps]).replace(", ", ", E")))
            if str(season) in where:
                lines.append("    Where to watch: " + where[str(season)])
            for m in eps:
                lines.append("      S%02dE%02d  %s  (aired %s)" % (season, m["episode"], m["name"], m["aired"]))
        lines.append("")
    complete = [r["title"] for r in results if not r["missing"]]
    if complete:
        lines.append("Complete (every aired episode of the seasons you have): " + ", ".join(complete))
        lines.append("")
    other = [(r["title"], r["seasons_not_in_library"]) for r in results if r["seasons_not_in_library"]]
    if other:
        lines.append("Seasons that aired but you don't have any of (not counted above):")
        lines.extend("  %s: seasons %s" % (t, _ranges(s)) for t, s in other)
        lines.append("")
    if problems:
        lines.append("Couldn't check:")
        lines.extend("  " + p for p in problems)
    if footer:
        lines.extend(["", footer])
    return "\n".join(lines)

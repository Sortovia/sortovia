"""Where to watch: TMDb's streaming availability (data by JustWatch).

Needs a free TMDb API key (the 32-character "API Key", or the long "API Read
Access Token"). Settings live in addon_data/watch.json:
    {"key": "...", "region": "US", "services": [8, 531, ...]}
services are TMDb provider ids of the services the user pays for.
"""
import json
import re
import time

API = "https://api.themoviedb.org/3"
ATTRIBUTION = "Where-to-watch data: TMDb / JustWatch."


class TMDb(object):
    def __init__(self, key):
        self.key = (key or "").strip()

    def get(self, path, **params):
        try:
            from urllib.request import Request, urlopen
            from urllib.parse import urlencode
        except ImportError:
            from urllib2 import Request, urlopen
            from urllib import urlencode
        headers = {"User-Agent": "KodiSorter", "Accept": "application/json"}
        if len(self.key) > 40:  # v4 "API Read Access Token"
            headers["Authorization"] = "Bearer " + self.key
        else:
            params["api_key"] = self.key
        url = "%s%s?%s" % (API, path, urlencode(params))
        for attempt in range(3):
            try:
                resp = urlopen(Request(url, headers=headers), timeout=20)
                try:
                    return json.loads(resp.read().decode("utf-8"))
                finally:
                    resp.close()
            except Exception as e:
                code = getattr(e, "code", None)
                if code == 404:
                    return None
                if code == 401:
                    raise IOError("TMDb refused the API key")
                if code == 429 and attempt < 2:
                    time.sleep(3)
                    continue
                raise

    # --- setup lists ---
    def regions(self):
        res = (self.get("/watch/providers/regions") or {}).get("results", [])
        return sorted(((r["iso_3166_1"], r["english_name"]) for r in res), key=lambda r: r[1])

    def services(self, region):
        res = (self.get("/watch/providers/tv", watch_region=region) or {}).get("results", [])
        res.sort(key=lambda p: (p.get("display_priorities", {}).get(region, p.get("display_priority", 999)),
                                p["provider_name"].lower()))
        return [(p["provider_id"], p["provider_name"]) for p in res]

    # --- lookups ---
    def find_show(self, title, year=None, ids=None):
        """TMDb id for a show: Kodi's own tmdb id, else IMDb/TVDB id, else name search."""
        ids = ids or {}
        if str(ids.get("tmdb", "")).isdigit():
            return int(ids["tmdb"])
        for source, key in (("imdb_id", "imdb"), ("tvdb_id", "tvdb")):
            if ids.get(key):
                hit = (self.get("/find/%s" % ids[key], external_source=source) or {}).get("tv_results")
                if hit:
                    return hit[0]["id"]
        title = re.sub(r"\s*\(\d{4}\)$", "", title or "")
        params = {"query": title}
        if year:
            params["first_air_date_year"] = year
        res = (self.get("/search/tv", **params) or {}).get("results") or []
        if not res and year:
            res = (self.get("/search/tv", query=title) or {}).get("results") or []
        return res[0]["id"] if res else None

    def search(self, title):
        res = (self.get("/search/tv", query=title) or {}).get("results") or []
        return [(r["id"], "%s (%s)" % (r["name"], (r.get("first_air_date") or "????")[:4])) for r in res[:15]]

    def providers(self, tmdb_id, region, season=None):
        path = "/tv/%d/season/%d/watch/providers" % (tmdb_id, season) if season else \
            "/tv/%d/watch/providers" % tmdb_id
        res = ((self.get(path) or {}).get("results") or {}).get(region)
        if not res and season:  # no season-level data: fall back to the whole show
            return self.providers(tmdb_id, region)
        return res or {}


def summarize(prov, mine):
    """Group one providers block into what matters to the user."""
    def names(kind, only=None, skip=None):
        out = []
        for p in prov.get(kind, []) or []:
            if only is not None and p["provider_id"] not in only:
                continue
            if skip is not None and p["provider_id"] in skip:
                continue
            if p["provider_name"] not in out:
                out.append(p["provider_name"])
        return out
    mine = set(mine or [])
    yours = names("flatrate", only=mine) + names("free", only=mine) + names("ads", only=mine)
    free = names("free", skip=mine) + names("ads", skip=mine)
    other = names("flatrate", skip=mine)
    buy = names("buy") or names("rent")
    return {"yours": yours, "free": free, "other_subs": other, "buy_rent": buy, "link": prov.get("link")}


def line(s):
    parts = []
    if s["yours"]:
        parts.append("ON YOUR SERVICES: " + ", ".join(s["yours"]))
    if s["free"]:
        parts.append("free: " + ", ".join(s["free"][:4]))
    if not s["yours"] and s["other_subs"]:
        parts.append("other subscriptions: " + ", ".join(s["other_subs"][:4]))
    if not s["yours"] and not s["free"] and s["buy_rent"]:
        parts.append("buy/rent: " + ", ".join(s["buy_rent"][:4]))
    return " | ".join(parts) or "not streaming in your country right now"


def annotate(data, tm, region, mine, progress=None):
    """Add 'where' (season -> line) to each show with missing episodes."""
    shows = [r for r in data.get("shows", []) if r.get("missing")]
    for i, r in enumerate(shows):
        if progress:
            progress(i, len(shows), r["title"])
        try:
            tid = tm.find_show(r["title"], r.get("year"), r.get("ids"))
            if not tid:
                r["where"] = {"all": "not found on TMDb"}
                continue
            r["tmdb"] = tid
            where = {}
            for season in sorted(set(m["season"] for m in r["missing"])):
                where[str(season)] = line(summarize(tm.providers(tid, region, season), mine))
            r["where"] = where
        except Exception as e:
            r["where"] = {"all": "couldn't check (%s)" % e}
        time.sleep(0.1)
    return data

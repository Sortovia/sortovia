#!/usr/bin/env python3
"""YouTube downloads for Kodi Sorter, run on the phone next to xbox-share.

The Xbox can't run yt-dlp (Kodi's sandboxed Python has no ffmpeg or JavaScript
runtime), so the add-on asks this helper to do it. Videos are saved to
Download/YouTube, where Kodi Sorter picks them up (tutorials -> Tutorials/<program>).

YouTube asks for a signed-in browser's cookies ("Sign in to confirm you're not a
bot"). Android won't let other apps read a browser's cookies, so export them once
as a cookies.txt file into Download; this helper moves it out of the shared
folder into ~/.config/xbox-share/youtube-cookies.txt and uses it from there.

HTTP on port 8081, same user/password as xbox-share (Basic auth):
  GET  /yt/ping              helper + cookies status
  GET  /yt/search?q=..&n=15&order=best|newest|views|longest|shortest  search results
  POST /yt/add   {"url", "title"}   queue a download
  GET  /yt/jobs              queue with progress
  POST /yt/cancel {"id"}     stop / remove one
  POST /yt/pause  {"id"} or {"all": true}   pause (the part downloaded is kept)
  POST /yt/resume {"id"} or {"all": true}   carry on
  POST /yt/clear             remove finished and failed
"""
import base64
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("YT_HELPER_PORT", "8081"))
CONF = os.path.expanduser("~/.config/xbox-share")
SHARE = os.environ.get("YT_SHARE", "/storage/emulated/0/Download")
OUT = os.path.join(SHARE, "YouTube")
TMP = os.path.expanduser("~/.cache/xbox-share/yt")  # half-done files stay out of the share
COOKIES = os.path.join(CONF, "youtube-cookies.txt")
JOBS_FILE = os.path.join(CONF, "yt-jobs.json")
SETTINGS_FILE = os.path.join(CONF, "yt-settings.json")

# Download quality (Kodi Sorter > YouTube > Download quality). Each is "the best up to this",
# preferring H.264/AAC in .mp4, which every Kodi plays; 4K on YouTube is VP9/AV1 only.
QUALITIES = {
    "2160": ("Best, up to 4K (big files)", ["-S", "res:2160,vcodec:h264,acodec:aac,ext:mp4:m4a", "--merge-output-format", "mp4"]),
    "1080": ("Full HD 1080p (recommended)", ["-S", "res:1080,vcodec:h264,acodec:aac,ext:mp4:m4a", "--merge-output-format", "mp4"]),
    "720": ("HD 720p (smaller, saves data)", ["-S", "res:720,vcodec:h264,acodec:aac,ext:mp4:m4a", "--merge-output-format", "mp4"]),
    "480": ("SD 480p (smallest video)", ["-S", "res:480,vcodec:h264,acodec:aac,ext:mp4:m4a", "--merge-output-format", "mp4"]),
    "audio": ("Sound only (.m4a - not sorted into the library)", ["-f", "bestaudio[ext=m4a]/bestaudio", "-x", "--audio-format", "m4a"]),
}
DEFAULT_QUALITY = "1080"


def settings():
    try:
        with open(SETTINGS_FILE) as f:
            s = json.load(f)
    except (OSError, ValueError):
        s = {}
    if s.get("quality") not in QUALITIES:
        s["quality"] = DEFAULT_QUALITY
    return s


def save_settings(s):
    os.makedirs(CONF, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(s, f)
TERMUX_BIN = "/data/data/com.termux/files/usr/bin"


def tool(name):
    return shutil.which(name) or (os.path.join(TERMUX_BIN, name) if os.path.exists(os.path.join(TERMUX_BIN, name)) else None)


def password():
    with open(os.path.join(CONF, "password")) as f:
        return f.read().strip()


def log(msg):
    print(time.strftime("%H:%M:%S"), "[youtube]", msg, flush=True)


# ---------- cookies ----------
def import_cookies():
    """Move the newest exported cookies file (with YouTube cookies) out of Download."""
    found = []
    for pat in ("*cookie*.txt", "*Cookie*.txt", "*.cookies"):
        found += glob.glob(os.path.join(SHARE, pat))
    for path in sorted(set(found), key=os.path.getmtime, reverse=True):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        if "youtube.com" not in text:
            continue
        if not text.lstrip().startswith("# Netscape") and "\tTRUE\t" not in text and "\tFALSE\t" not in text:
            continue  # not a cookies.txt (Netscape format) file
        os.makedirs(CONF, exist_ok=True)
        with open(COOKIES, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(COOKIES, 0o600)
        try:
            os.remove(path)  # don't leave sign-in cookies in the shared folder
        except OSError:
            pass
        log("cookies imported from %s" % os.path.basename(path))
        LAST_IMPORT["name"], LAST_IMPORT["when"] = os.path.basename(path), time.time()
        return os.path.basename(path)
    return None


LAST_IMPORT = {"name": None, "when": 0}


def cookies_status():
    just = import_cookies()
    if not os.path.exists(COOKIES):
        return {"present": False, "imported": None}
    age = (time.time() - os.path.getmtime(COOKIES)) / 86400
    signed_in = False
    try:
        with open(COOKIES, encoding="utf-8", errors="replace") as f:
            signed_in = any(n in f.read() for n in ("\tSAPISID\t", "\tLOGIN_INFO\t", "\t__Secure-3PSID\t"))
    except OSError:
        pass
    return {"present": True, "age_days": round(age, 1), "signed_in": signed_in, "imported": just,
            "last_import": LAST_IMPORT["name"], "last_import_ago_s": int(time.time() - LAST_IMPORT["when"]) if LAST_IMPORT["when"] else None}


def base_cmd():
    cmd = [tool("yt-dlp") or "yt-dlp", "--no-warnings"]
    node = tool("node")
    if node:
        cmd += ["--js-runtimes", "node:" + node]
    ff = tool("ffmpeg")
    if ff:
        cmd += ["--ffmpeg-location", ff]  # joins the video and sound tracks
    if os.path.exists(COOKIES):
        cmd += ["--cookies", COOKIES]
    return cmd


def explain(err):
    """yt-dlp's error, said plainly."""
    if "not a bot" in err or "Sign in to confirm" in err:
        return "YouTube wants a signed-in browser's cookies - export a new cookies.txt into Download"
    if "Private video" in err or "members-only" in err or "Join this channel" in err:
        return "private or members-only video (needs cookies from an account that can watch it)"
    if "Video unavailable" in err:
        return "video unavailable"
    if "No space left" in err:
        return "the phone is full"
    m = re.findall(r"ERROR: (.*)", err)
    return (m[-1] if m else err.strip().splitlines()[-1] if err.strip() else "failed")[:300]


# ---------- search ----------
# YouTube's own search API: one request, and unlike yt-dlp's search it says when
# each video came out ("4 years ago") and how many views it has. yt-dlp is the
# fallback (links, playlists, or if YouTube changes this reply).
ORDERS = [["best", "Best match"], ["newest", "Newest first"], ["views", "Most viewed"],
          ["longest", "Longest first"], ["shortest", "Shortest first"]]
API_SORT = {"views": "CAM="}  # YouTube sorts these itself; the rest are sorted here
AGE_RE = re.compile(r"(\d+)\s+(second|minute|hour|day|week|month|year)", re.I)
AGE_DAYS = {"second": 1 / 86400., "minute": 1 / 1440., "hour": 1 / 24., "day": 1, "week": 7, "month": 30.4, "year": 365.25}


def age_days(text):
    """'4 years ago' -> about 1461 (days); unknown -> None."""
    m = AGE_RE.search(text or "")
    return int(m.group(1)) * AGE_DAYS[m.group(2).lower()] if m else None


def _text(o):
    o = o or {}
    return o.get("simpleText") or "".join(r.get("text", "") for r in o.get("runs", []))


def _seconds(text):
    secs = 0
    for part in (text or "").split(":"):
        if not part.strip().isdigit():
            return 0
        secs = secs * 60 + int(part)
    return secs


def _video_renderers(o, out):
    if isinstance(o, dict):
        if "videoRenderer" in o:
            out.append(o["videoRenderer"])
        for v in o.values():
            _video_renderers(v, out)
    elif isinstance(o, list):
        for v in o:
            _video_renderers(v, out)
    return out


def parse_api_results(data):
    out = []
    for v in _video_renderers(data, []):
        vid = v.get("videoId")
        if not vid:
            continue
        views = re.sub(r"[^0-9]", "", _text(v.get("viewCountText")).split(" ")[0])
        out.append({"id": vid, "url": "https://www.youtube.com/watch?v=%s" % vid,
                    "title": _text(v.get("title")) or vid,
                    "channel": _text(v.get("ownerText") or v.get("longBylineText")),
                    "duration": _seconds(_text(v.get("lengthText"))),
                    "published": _text(v.get("publishedTimeText")),
                    "views": int(views) if views else None})
    return out


def api_search(q, order):
    from urllib.request import Request, urlopen
    body = {"context": {"client": {"clientName": "WEB", "clientVersion": "2.20250101.00.00", "hl": "en", "gl": "US"}},
            "query": q}
    if API_SORT.get(order):
        body["params"] = API_SORT[order]
    req = Request("https://www.youtube.com/youtubei/v1/search?prettyPrint=false", data=json.dumps(body).encode(),
                  headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    resp = urlopen(req, timeout=170)
    try:
        return parse_api_results(json.loads(resp.read().decode("utf-8")))
    finally:
        resp.close()


def sort_results(res, order):
    big = float("inf")
    if order == "newest":
        res.sort(key=lambda r: age_days(r.get("published")) if age_days(r.get("published")) is not None else big)
    elif order == "longest":
        res.sort(key=lambda r: -(r.get("duration") or 0))
    elif order == "shortest":
        res.sort(key=lambda r: r.get("duration") or big)
    return res


def search(q, n, order="best"):
    if not re.match(r"https?://", q):
        try:
            res = api_search(q, order)
            if res:
                return sort_results(res[:max(n, 20)], order)
        except Exception as e:
            log("YouTube search API failed (%s), using yt-dlp" % e)
        return sort_results(ytdlp_search(q, n), order)
    return ytdlp_search(q, n)


def ytdlp_search(q, n):
    cmd = base_cmd() + ["--flat-playlist", "-J", "ytsearch%d:%s" % (n, q)]
    if re.match(r"https?://", q):
        cmd = base_cmd() + ["--flat-playlist", "-J", q]  # a link: list it (or a playlist's videos)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        raise RuntimeError("YouTube didn't answer within 3 minutes. The phone's internet is very slow right now "
                           "(a download or Kodi's library scan may be using it). Try again in a while.")
    if p.returncode != 0:
        raise RuntimeError(explain(p.stderr))
    data = json.loads(p.stdout)
    entries = data.get("entries") or [data]
    out = []
    for e in entries:
        vid = e.get("id")
        if not vid:
            continue
        url = e.get("url") or e.get("webpage_url") or "https://www.youtube.com/watch?v=%s" % vid
        if not url.startswith("http"):
            url = "https://www.youtube.com/watch?v=%s" % vid
        out.append({"id": vid, "url": url, "title": e.get("title") or vid,
                    "channel": e.get("channel") or e.get("uploader") or "",
                    "duration": e.get("duration") or 0})
    return out


# ---------- queue ----------
LOCK = threading.Lock()
WAKE = threading.Event()
JOBS = []
CURRENT = {"proc": None, "id": None}


def save_jobs():
    os.makedirs(CONF, exist_ok=True)
    tmp = JOBS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(JOBS, f, indent=1)
    os.replace(tmp, JOBS_FILE)


def load_jobs():
    try:
        with open(JOBS_FILE) as f:
            JOBS.extend(json.load(f))
    except (OSError, ValueError):
        return
    for j in JOBS:
        if j["state"] in ("downloading", "copying"):
            j["state"] = "queued"  # helper was stopped part way: start that one again


def add_job(url, title="", quality=None):
    with LOCK:
        for j in JOBS:
            if j["url"] == url and j["state"] in ("queued", "downloading", "paused"):
                return j
        job = {"id": "%d%03d" % (time.time(), len(JOBS) % 1000), "url": url, "title": title or url,
               "state": "queued", "pct": 0.0, "speed": "", "eta": "", "file": "", "error": "",
               "quality": quality if quality in QUALITIES else settings()["quality"],
               "added": time.strftime("%Y-%m-%d %H:%M")}
        JOBS.append(job)
        save_jobs()
    WAKE.set()
    return job


TRANSIENT_RE = re.compile(r"Did not get any data blocks|timed out|Connection reset|Connection aborted|"
                          r"Temporary failure|Network is unreachable|IncompleteRead|HTTP Error 5\d\d|"
                          r"Remote end closed|EOF occurred", re.I)
PROG_RE = re.compile(r"^KSPROG\s*(.*)$")


def parse_progress(line):
    """KSPROG percent|speed|eta|fragment|fragments|bytes -> (pct or None, speed, eta, bytes).
    Videos YouTube sends in pieces (HLS) often have no percent: it comes from the pieces then."""
    f = (line.split(" ", 1)[1] if " " in line else "").split("|")
    f += [""] * (6 - len(f))
    num = lambda x: float(x) if re.match(r"^\d+(\.\d+)?$", (x or "").strip()) else None
    pct = num(f[0].strip().rstrip("%"))
    idx, cnt = num(f[3]), num(f[4])
    if pct is None and idx and cnt:
        pct = min(100.0, 100.0 * idx / cnt)
    clean = lambda x: "" if x.strip() in ("NA", "N/A", "Unknown", "None") else x.strip()
    return pct, clean(f[1]), clean(f[2]), num(f[5])


def run_job(job):
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    cmd = base_cmd() + [
        "--no-playlist", "--newline", "--quiet", "--progress", "--no-simulate",
    ] + QUALITIES[job.get("quality") if job.get("quality") in QUALITIES else DEFAULT_QUALITY][1] + [
        "--windows-filenames", "--trim-filenames", "180", "--no-mtime",
        # The hotspot / mobile data drops out now and then ("Did not get any data blocks"):
        # keep retrying pieces instead of failing the whole video.
        "--retries", "15", "--fragment-retries", "30", "--retry-sleep", "fragment:exp=1:30",
        "--socket-timeout", "30",
        # Whole download (and the final merge) happens in TMP, outside the share; publish() then
        # copies it in under a hidden name and renames it, so Kodi Sorter never sees half a file.
        "-P", TMP, "-o", "%(title)s.%(ext)s",
        "--progress-template", "download:KSPROG %(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s"
                               "|%(progress.fragment_index)s|%(progress.fragment_count)s|%(progress.downloaded_bytes)s",
        "--print", "before_dl:KSTITLE %(title)s",
        "--print", "after_move:KSFILE %(filepath)s",
        job["url"],
    ]
    log("downloading %s" % job["url"])
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    CURRENT["proc"], CURRENT["id"] = proc, job["id"]
    err_lines = []
    t = threading.Thread(target=lambda: err_lines.extend(proc.stderr), daemon=True)
    t.start()
    part = 0
    last_pct = -1.0
    for line in proc.stdout:
        line = line.strip()
        m = PROG_RE.match(line)
        with LOCK:
            if m:
                pct, speed, eta, got = parse_progress(line)
                if pct is not None:
                    if pct < last_pct - 50:
                        part += 1  # video done, now the sound track
                    last_pct = pct
                    job["pct"] = pct
                job["speed"], job["eta"] = speed, eta
                if got:
                    job["mb"] = round(got / 1e6, 1)
                job["part"] = part + 1
            elif line.startswith("KSTITLE "):
                job["title"] = line[8:]
            elif line.startswith("KSFILE "):
                job["file"] = line[7:]
    proc.wait()
    t.join(5)
    with LOCK:
        CURRENT["proc"] = CURRENT["id"] = None
        if job["state"] in ("cancelled", "paused"):
            pass
        elif proc.returncode == 0 and job["file"]:
            job["state"], job["eta"], job["speed"] = "copying", "", ""
    if job["state"] == "copying":
        try:
            name = publish(job["file"])
            with LOCK:
                job["state"], job["pct"], job["file"] = "done", 100.0, name
            log("done: %s" % name)
        except OSError as e:
            with LOCK:
                job["state"], job["error"] = "failed", explain(str(e)) or "couldn't copy into Download/YouTube"
    with LOCK:
        if job["state"] in ("done", "failed", "cancelled", "paused"):
            pass
        else:
            err = "".join(err_lines)
            if TRANSIENT_RE.search(err) and job.get("tries", 0) < 3:
                # a dropped connection: try again by itself (the part already downloaded is kept)
                job["tries"] = job.get("tries", 0) + 1
                job["state"], job["error"] = "queued", ""
                log("connection dropped, trying again (%d of 3): %s" % (job["tries"], job["url"]))
                WAKE.set()
            else:
                job["state"], job["error"] = "failed", explain(err)
                log("failed: %s - %s" % (job["url"], job["error"]))
        save_jobs()


def publish(path):
    """Copy a finished download from TMP into Download/YouTube: hidden .part name first
    (Kodi Sorter skips hidden files), then renamed. Returns the final file name."""
    name = os.path.basename(path)
    stem, ext = os.path.splitext(name)
    final, n = os.path.join(OUT, name), 2
    while os.path.exists(final):
        final = os.path.join(OUT, "%s (%d)%s" % (stem, n, ext))
        n += 1
    part = os.path.join(OUT, "." + os.path.basename(final) + ".part")
    shutil.copyfile(path, part)
    if os.path.getsize(part) != os.path.getsize(path):
        os.remove(part)
        raise OSError("copy into Download/YouTube came out short")
    os.replace(part, final)
    os.remove(path)
    return os.path.basename(final)


def worker():
    while True:
        with LOCK:
            job = next((j for j in JOBS if j["state"] == "queued"), None)
            if job:
                job["state"] = "downloading"
                save_jobs()
        if not job:
            WAKE.wait(30)
            WAKE.clear()
            continue
        try:
            run_job(job)
        except Exception as e:
            with LOCK:
                job["state"], job["error"] = "failed", str(e)[:300]
                save_jobs()


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    server_version = "KodiSorterYT/1"

    def log_message(self, fmt, *args):
        pass

    def _authed(self):
        h = self.headers.get("Authorization", "")
        try:
            user, _, pw = base64.b64decode(h.split(" ", 1)[1]).decode().partition(":")
        except Exception:
            user = pw = None
        if user == "kodi" and pw == password():
            return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="kodisorter-youtube"')
        self.end_headers()
        return False

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def do_GET(self):
        if not self._authed():
            return
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/yt/ping":
            ver = subprocess.run([tool("yt-dlp") or "yt-dlp", "--version"], capture_output=True, text=True).stdout.strip()
            return self._send({"ok": True, "cookies": cookies_status(), "yt_dlp": ver,
                               "node": bool(tool("node")), "folder": OUT})
        if u.path == "/yt/search":
            cookies_status()
            try:
                return self._send({"results": search(q.get("q", [""])[0], min(int(q.get("n", ["15"])[0]), 40),
                                                     q.get("order", ["best"])[0]), "orders": ORDERS})
            except Exception as e:
                return self._send({"error": str(e)}, 502)
        if u.path == "/yt/jobs":
            with LOCK:
                return self._send({"jobs": JOBS})
        self._send({"error": "not found"}, 404)

    def do_POST(self):
        if not self._authed():
            return
        u = urlparse(self.path)
        b = self._body()
        if u.path == "/yt/add":
            url = (b.get("url") or "").strip()
            if not re.match(r"https?://", url):
                url = "https://www.youtube.com/watch?v=" + url if re.match(r"^[\w-]{11}$", url) else ""
            if not url:
                return self._send({"error": "that isn't a YouTube link"}, 400)
            cookies_status()
            return self._send({"job": add_job(url, b.get("title", ""), b.get("quality"))})
        if u.path in ("/yt/pause", "/yt/resume"):
            pause = u.path == "/yt/pause"
            with LOCK:
                hit = [j for j in JOBS if (b.get("all") or j["id"] == b.get("id")) and
                       j["state"] in (("queued", "downloading") if pause else ("paused",))]
                for j in hit:
                    if pause and j["state"] == "downloading" and CURRENT["id"] == j["id"] and CURRENT["proc"]:
                        CURRENT["proc"].terminate()  # yt-dlp keeps the part file and carries on from it later
                    j["state"] = "paused" if pause else "queued"
                    j["speed"] = j["eta"] = ""
                save_jobs()
            if hit:
                log("%s %d download(s)" % ("paused" if pause else "resumed", len(hit)))
                WAKE.set()
            return self._send({"ok": bool(hit), "count": len(hit)})
        if u.path == "/yt/cancel":
            with LOCK:
                job = next((j for j in JOBS if j["id"] == b.get("id")), None)
                if job and job["state"] == "downloading" and CURRENT["id"] == job["id"] and CURRENT["proc"]:
                    job["state"] = "cancelled"
                    CURRENT["proc"].terminate()
                elif job:
                    JOBS.remove(job)
                save_jobs()
            return self._send({"ok": bool(job)})
        if u.path == "/yt/settings":
            s = settings()
            if b.get("quality") in QUALITIES:
                s["quality"] = b["quality"]
                save_settings(s)
                log("download quality: %s" % QUALITIES[s["quality"]][0])
            if b.get("order") in dict(ORDERS):
                s["order"] = b["order"]
                save_settings(s)
            s.setdefault("order", "best")
            return self._send({"settings": s, "qualities": [[k, v[0]] for k, v in QUALITIES.items()],
                               "orders": ORDERS})
        if u.path == "/yt/cookies":
            # "Import cookies now": look in Download right away and say what happened
            st = cookies_status()
            return self._send({"cookies": st})
        if u.path == "/yt/clear":
            with LOCK:
                JOBS[:] = [j for j in JOBS if j["state"] in ("queued", "downloading", "paused")]
                save_jobs()
            return self._send({"ok": True})
        self._send({"error": "not found"}, 404)


def main():
    if not os.path.exists(os.path.join(CONF, "password")):
        sys.exit("no xbox-share password yet - start xbox-share once first")
    if not tool("yt-dlp"):
        log("yt-dlp is missing: in plain Termux run  pkg install yt-dlp ffmpeg nodejs")
    load_jobs()
    st = cookies_status()
    log("YouTube downloads on port %d -> %s (cookies: %s)" % (
        PORT, OUT, "OK" if st.get("present") else "none yet - export cookies.txt into Download"))
    threading.Thread(target=worker, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()

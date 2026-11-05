"""A one-off test: could this device download from YouTube by itself, without a phone?

It downloads the official yt-dlp from GitHub, checks its published checksum, asks for one short
test video's list of formats (nothing is downloaded from YouTube) and reports what it finds.
yt-dlp is deleted afterwards. No sign-in or cookies are used.
"""
import hashlib
import os
import platform
import sys
import threading

RELEASE = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"
ASSET = "yt-dlp"
TEST_VIDEO = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"  # Big Buck Bunny, the Blender Foundation's open film
MIN_PYTHON = (3, 10)
WAIT = 180


def checksum_for(sums, name=ASSET):
    """The expected SHA-256 from the release's checksum list."""
    for line in sums.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == name:
            return parts[0].lower()
    return ""


def summarize(formats):
    """What the format list means for a device without ffmpeg."""
    whole = [f for f in formats if f.get("vcodec") not in (None, "none") and f.get("acodec") not in (None, "none")
             and f.get("protocol", "https").startswith("http") and f.get("url")]
    streams = [f for f in formats if f.get("vcodec") not in (None, "none") and f.get("acodec") not in (None, "none")
               and f.get("protocol", "").startswith("m3u8")]
    best = lambda rows: max([f.get("height") or 0 for f in rows] or [0])
    return {"total": len(formats), "whole_files": len(whole), "best_height": best(whole),
            "stream_files": len(streams), "stream_height": best(streams)}


def _probe(path, url, out):
    class Quiet(object):
        def debug(self, m): pass
        def info(self, m): pass
        def warning(self, m): out.setdefault("warnings", []).append(str(m)[:300])
        def error(self, m): out["error"] = str(m)[:500]
    try:
        sys.path.insert(0, path)
        import yt_dlp
        out["version"] = yt_dlp.version.__version__
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": False, "skip_download": True, "noprogress": True,
                               "logger": Quiet(), "cachedir": False, "socket_timeout": 30}) as ydl:
            info = ydl.extract_info(url, download=False)
        out["summary"] = summarize((info or {}).get("formats") or [])
    except BaseException as e:
        out.setdefault("error", "%s: %s" % (type(e).__name__, str(e)[:500]))
    finally:
        if path in sys.path:
            sys.path.remove(path)


def run(http, folder, progress=lambda m: None):
    """Returns (works, report lines). http(url) -> (code, bytes). folder: a real folder Python can write to."""
    lines = ["Python %s on %s" % (platform.python_version(), sys.platform)]
    if sys.version_info[:2] < MIN_PYTHON:
        lines.append("RESULT: Kodi's Python is too old for yt-dlp (it needs %d.%d)." % MIN_PYTHON)
        return False, lines
    for name in ("ssl", "ctypes", "subprocess", "sqlite3"):
        try:
            __import__(name)
            lines.append("Module %s: OK" % name)
        except Exception as e:
            lines.append("Module %s: %s" % (name, type(e).__name__))
    try:
        import subprocess
        code = subprocess.call(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        lines.append("ffmpeg: %s" % ("found" if code == 0 else "not usable"))
    except Exception as e:
        lines.append("ffmpeg: not available (%s)" % type(e).__name__)

    path = os.path.join(folder, "sortovia-ytdlp-test.zip")
    try:
        progress("Downloading yt-dlp from GitHub...")
        code, sums = http(RELEASE + "SHA2-256SUMS")
        want = checksum_for(sums) if code == 200 else ""
        if not want:
            lines.append("RESULT: couldn't get yt-dlp's checksum list (%s)." % code)
            return False, lines
        code, app = http(RELEASE + ASSET)
        if code != 200:
            lines.append("RESULT: couldn't download yt-dlp (%s)." % code)
            return False, lines
        if hashlib.sha256(app).hexdigest() != want:
            lines.append("RESULT: the download didn't match its checksum, so it wasn't run.")
            return False, lines
        lines.append("yt-dlp: downloaded, %.1f MB, checksum OK" % (len(app) / 1e6))
        with open(path, "wb") as f:
            f.write(app)

        progress("Asking YouTube about a test video (up to 3 minutes)...")
        out = {}
        worker = threading.Thread(target=_probe, args=(path, TEST_VIDEO, out))
        worker.daemon = True
        worker.start()
        worker.join(WAIT)
        if worker.is_alive():
            lines.append("RESULT: yt-dlp was still working after %d seconds." % WAIT)
            return False, lines
        if out.get("version"):
            lines.append("yt-dlp %s loaded" % out["version"])
        for w in (out.get("warnings") or [])[:5]:
            lines.append("Warning: %s" % w)
        summary = out.get("summary")
        if summary:
            lines.append("Formats: %(total)d in all, %(whole_files)d complete video files (best %(best_height)dp), "
                         "%(stream_files)d complete streams (best %(stream_height)dp)" % summary)
        if out.get("error"):
            lines.append("Error: %s" % out["error"])
        if summary and summary["whole_files"]:
            lines.append("RESULT: this device can get YouTube videos by itself, up to %dp without ffmpeg."
                         % summary["best_height"])
            return True, lines
        if summary and summary["stream_files"]:
            lines.append("RESULT: this device could get YouTube videos by itself as streams, up to %dp, but they download "
                         "more slowly than complete files." % summary["stream_height"])
            return True, lines
        lines.append("RESULT: yt-dlp ran, but YouTube gave nothing this device could download by itself.")
        return False, lines
    except Exception as e:
        lines.append("RESULT: the test stopped: %s: %s" % (type(e).__name__, str(e)[:300]))
        return False, lines
    finally:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            lines.append("Couldn't delete the test copy: %s" % os.path.basename(path))

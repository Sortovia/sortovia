"""Download from YouTube - the Xbox side.

The phone does the downloading (tools/yt_helper.py, started by xbox-share on
port 8081, same password): Kodi on the Xbox can't run yt-dlp. This module is
the remote control: search, queue, progress, then sort the finished videos.
Videos land in the phone's Download/YouTube, which Kodi Sorter sorts
(tutorials -> Tutorials/<program>).
"""
import base64
import json
import re
import time

import xbmc
import xbmcgui

try:
    from urllib.request import Request, urlopen
    from urllib.parse import quote
except ImportError:  # Kodi 18 and older
    from urllib2 import Request, urlopen
    from urllib import quote

PORT = 8081
HEADING = "Download from YouTube"

COOKIE_HELP = """YouTube only lets the phone download when it sends the cookies of a browser that is signed in to YouTube ("Sign in to confirm you're not a bot"). Android doesn't let other apps read a browser's cookies, so you export them once as a file:

1. On the phone, install Firefox (Play Store) and sign in to youtube.com in it.
2. Firefox menu > Extensions > find "cookies.txt" (or "Get cookies.txt LOCALLY") > Add.
3. Tip from the yt-dlp team: open a PRIVATE tab, allow the extension in private tabs, sign in to youtube.com there, export, then close the private tab. Cookies from a normal tab get replaced by YouTube within a day or so; private-tab cookies last much longer.
4. With youtube.com open, tap the extension and export / download the cookies for this site. The file (cookies.txt or youtube.com_cookies.txt) goes into the phone's Download folder.
5. That's all. The phone's helper finds it, moves it out of the shared Download folder (so the Xbox share can't see your sign-in) and uses it for every download.

When downloads start failing with "export a new cookies.txt", repeat steps 3-4.

The cookies are your YouTube account's sign-in: don't send the file to anyone."""


class Phone(object):
    def __init__(self, ip, user, pw):
        self.base = "http://%s:%d" % (ip, PORT)
        self.auth = base64.b64encode(("%s:%s" % (user, pw)).encode()).decode()

    def call(self, path, body=None, timeout=20):
        data = json.dumps(body).encode() if body is not None else None
        req = Request(self.base + path, data=data,
                      headers={"Authorization": "Basic " + self.auth, "Content-Type": "application/json"})
        try:
            resp = urlopen(req, timeout=timeout)
            try:
                return json.loads(resp.read().decode("utf-8"))
            finally:
                resp.close()
        except Exception as e:
            code = getattr(e, "code", None)
            if code == 401:
                raise RuntimeError("the phone refused the password")
            if code:
                try:
                    return json.loads(e.read().decode("utf-8"))
                except Exception:
                    raise RuntimeError("phone answered %s" % code)
            raise RuntimeError("can't reach the phone's YouTube helper (%s)" % (getattr(e, "reason", None) or e))


def _mins(sec):
    sec = int(sec or 0)
    return "%d:%02d:%02d" % (sec // 3600, sec // 60 % 60, sec % 60) if sec >= 3600 else "%d:%02d" % (sec // 60, sec % 60)


def cookie_line(st):
    c = st.get("cookies") or {}
    if not c.get("present"):
        return "NO cookies yet - downloads will fail (see How to set up)"
    age = c.get("age_days", 0)
    when = "today" if age < 1 else "%d day%s ago" % (age, "" if int(age) == 1 else "s")
    return "cookies from %s%s" % (when, "" if c.get("signed_in") else " - NOT signed in, export again")


def job_label(j):
    t = j.get("title") or j.get("url")
    s = j.get("state")
    if s == "downloading":
        part = " (sound)" if (j.get("part") or 1) > 1 else ""
        extra = ", ".join(x for x in (j.get("speed"), j.get("eta") and "%s left" % j["eta"]) if x)
        return "%3d%%%s  %s%s" % (j.get("pct") or 0, part, t, ("   [%s]" % extra) if extra else "")
    if s == "copying":
        return "100%%  %s   [saving into Download/YouTube]" % t
    if s == "done":
        return "DONE    %s" % (j.get("file") or t)
    if s == "failed":
        return "FAILED  %s - %s" % (t, j.get("error"))
    if s == "cancelled":
        return "STOPPED %s" % t
    return "waiting %s" % t


def queue_line(jobs):
    waiting = sum(1 for j in jobs if j["state"] == "queued")
    now = [j for j in jobs if j["state"] in ("downloading", "copying")]
    done = sum(1 for j in jobs if j["state"] == "done")
    failed = sum(1 for j in jobs if j["state"] == "failed")
    bits = []
    if now:
        bits.append("%d%% %s" % (now[0].get("pct") or 0, (now[0].get("title") or "")[:40]))
    if waiting:
        bits.append("%d waiting" % waiting)
    if done:
        bits.append("%d done" % done)
    if failed:
        bits.append("%d failed" % failed)
    return ", ".join(bits) or "nothing queued"


def watch(phone):
    """Live progress until the queue is empty or Cancel (downloads carry on)."""
    prog = xbmcgui.DialogProgress()
    prog.create(HEADING, "Asking the phone...")
    try:
        while not prog.iscanceled():
            jobs = phone.call("/yt/jobs")["jobs"]
            now = [j for j in jobs if j["state"] in ("downloading", "copying")]
            waiting = sum(1 for j in jobs if j["state"] == "queued")
            if not now and not waiting:
                done = [j for j in jobs if j["state"] == "done"]
                failed = [j for j in jobs if j["state"] == "failed"]
                prog.close()
                msg = "%d downloaded, %d failed." % (len(done), len(failed))
                if failed:
                    msg += "\nLast problem: %s" % failed[-1].get("error")
                xbmcgui.Dialog().ok(HEADING, msg)
                return
            j = now[0] if now else None
            text = job_label(j) if j else "starting the next one..."
            prog.update(int(j.get("pct") or 0) if j else 0,
                        "%s\n%d more waiting\n(Cancel closes this window - downloads keep going on the phone)"
                        % (text, waiting))
            xbmc.sleep(2000)
    except RuntimeError as e:
        xbmcgui.Dialog().ok(HEADING, str(e))
    finally:
        prog.close()


def queue_videos(dlg, phone, items):
    added = 0
    for it in items:
        r = phone.call("/yt/add", {"url": it["url"], "title": it.get("title", "")})
        if r.get("job"):
            added += 1
        elif r.get("error"):
            dlg.ok(HEADING, r["error"])
    if added and dlg.yesno(HEADING, "%d video%s queued on the phone.\nWatch the download progress?"
                           % (added, "" if added == 1 else "s"), nolabel="Later", yeslabel="Watch"):
        watch(phone)


def search(dlg, phone, last):
    q = dlg.input("Search YouTube", last.get("q", ""))
    if not q:
        return
    last["q"] = q
    prog = xbmcgui.DialogProgress()
    prog.create(HEADING, "Searching YouTube for \"%s\" on the phone..." % q)
    try:
        r = phone.call("/yt/search?n=25&q=" + quote(q), timeout=100)
    finally:
        prog.close()
    if r.get("error"):
        dlg.ok(HEADING, "Search failed: %s" % r["error"])
        return
    res = r.get("results") or []
    if not res:
        dlg.ok(HEADING, "Nothing found for \"%s\"." % q)
        return
    labels = ["%s   [%s%s]" % (x["title"], _mins(x["duration"]) if x.get("duration") else "playlist/live",
                                 ", " + x["channel"] if x.get("channel") else "") for x in res]
    picks = dlg.multiselect("Pick the videos to download (select several, then OK)", labels)
    if picks:
        queue_videos(dlg, phone, [res[i] for i in picks])


def type_link(dlg, phone):
    url = dlg.input("YouTube link or video ID (e.g. youtu.be/abc123 or a playlist link)")
    if not url:
        return
    url = url.strip()
    if not re.match(r"^https?://", url) and not re.match(r"^[\w-]{11}$", url):
        url = "https://" + url
    if "list=" in url:
        # a playlist: show its videos and let them pick
        prog = xbmcgui.DialogProgress()
        prog.create(HEADING, "Reading the playlist on the phone...")
        try:
            r = phone.call("/yt/search?n=1&q=" + quote(url), timeout=100)
        finally:
            prog.close()
        res = r.get("results") or []
        if r.get("error") or not res:
            dlg.ok(HEADING, "Couldn't read that playlist: %s" % (r.get("error") or "empty"))
            return
        picks = dlg.multiselect("Playlist - pick the videos (all are selected)",
                                ["%s   [%s]" % (x["title"], _mins(x["duration"])) for x in res],
                                preselect=list(range(len(res))))
        if picks:
            queue_videos(dlg, phone, [res[i] for i in picks])
        return
    queue_videos(dlg, phone, [{"url": url}])


def downloads(dlg, phone):
    while True:
        jobs = phone.call("/yt/jobs")["jobs"]
        opts = ["Watch progress", "Refresh"] + [job_label(j) for j in jobs] + \
               (["Clear finished and failed from this list"] if jobs else [])
        pick = dlg.select("Downloads on the phone - %s" % queue_line(jobs), opts)
        if pick < 0:
            return
        if pick == 0:
            watch(phone)
        elif pick == 1:
            continue
        elif pick == len(opts) - 1 and jobs:
            phone.call("/yt/clear", {})
        else:
            j = jobs[pick - 2]
            if j["state"] == "failed":
                what = dlg.select(job_label(j)[:80], ["Try again", "Remove from the list"])
                if what == 0:
                    phone.call("/yt/cancel", {"id": j["id"]})
                    phone.call("/yt/add", {"url": j["url"], "title": j.get("title", "")})
                elif what == 1:
                    phone.call("/yt/cancel", {"id": j["id"]})
            elif j["state"] in ("queued", "downloading"):
                if dlg.yesno(HEADING, "Stop this download?\n%s" % j.get("title"), nolabel="Keep", yeslabel="Stop"):
                    phone.call("/yt/cancel", {"id": j["id"]})
            elif dlg.yesno(HEADING, "Remove from the list?\n(the video stays on the phone)\n%s" % job_label(j),
                           nolabel="Keep", yeslabel="Remove"):
                phone.call("/yt/cancel", {"id": j["id"]})


def menu(dlg, find_ip, creds, log):
    """Returns "sort" when the user wants the finished downloads sorted now."""
    c = creds()
    if not c or not c.get("pass"):
        dlg.ok(HEADING, "First set up the phone share: start xbox-share on the phone, then in Kodi Sorter "
                        "choose \"Send Kodi's log to my phone now\" and type the password it shows.")
        return None
    ip = find_ip()
    if not ip:
        dlg.ok(HEADING, "Can't find the phone. Start xbox-share in Termux on the phone and keep the "
                        "Xbox on the phone's hotspot.")
        return None
    phone = Phone(ip, c.get("user", "kodi"), c["pass"])
    last = {}
    while True:
        try:
            st = phone.call("/yt/ping", timeout=15)
            jobs = phone.call("/yt/jobs")["jobs"]
        except RuntimeError as e:
            log("youtube helper: %s" % e)
            dlg.ok(HEADING, "%s.\nThe phone is sharing, but its YouTube helper isn't answering. With xbox-share "
                            "in Termux: stop it (Ctrl+C) and start it again - it starts the helper too. The companion "
                            "app can't download from YouTube yet (coming in its next version)." % e)
            return None
        opts = ["Search YouTube (pick videos from the results)...",
                "Type a YouTube link (video or playlist)...",
                "Downloads: %s" % queue_line(jobs),
                "Sort the finished downloads into my library now",
                "How to set up cookies (sign-in) - %s" % cookie_line(st)]
        pick = dlg.select("%s - %s" % (HEADING, cookie_line(st)), opts)
        try:
            if pick < 0:
                return None
            if pick == 0:
                search(dlg, phone, last)
            elif pick == 1:
                type_link(dlg, phone)
            elif pick == 2:
                downloads(dlg, phone)
            elif pick == 3:
                busy = [j for j in jobs if j["state"] in ("queued", "downloading", "copying")]
                if busy and not dlg.yesno(HEADING, "%d download(s) aren't finished yet - only finished videos "
                                                   "are sorted. Go ahead?" % len(busy), nolabel="Wait", yeslabel="Sort now"):
                    continue
                return "sort"
            elif pick == 4:
                dlg.textviewer("%s - cookies" % HEADING, COOKIE_HELP)
        except RuntimeError as e:
            dlg.ok(HEADING, str(e))

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

COOKIE_HELP = """YouTube only lets the phone download when it sends the cookies of a browser that is signed in to YouTube ("Sign in to confirm you're not a bot"). Android doesn't let other apps read a browser's cookies, so you export them once as a file.

[B]1. Get Firefox and a cookie extension[/B]
- Install Firefox from the Play Store.
- In Firefox open addons.mozilla.org and search for "cookies.txt". Pick the one called just "cookies.txt" - it works on Android - and tap Add to Firefox, then Add.
- If Add to Firefox is greyed out (some extensions, like "Get cookies.txt LOCALLY", aren't marked for Android), install it from its file instead:
  a) Firefox menu > Settings > About Firefox, and tap the Firefox logo 5 times until it says the debug menu is on.
  b) Go back to Settings: a new item "Install extension from file" is near the bottom.
  c) Pick the extension's .xpi file in your Download folder. (Get it on a computer or in Firefox's "Desktop site" mode from the extension's page on addons.mozilla.org - "Download file". Only files from addons.mozilla.org install, because they are signed.)

[B]2. Let it work in private tabs[/B]
Firefox menu > Extensions > the cookie extension > Settings > turn on "Run in private browsing".

[B]3. Export the cookies[/B]
- Firefox menu > New private tab, go to youtube.com and sign in.
- Firefox menu > Extensions > the cookie extension > export the cookies for this site. Choose the "Netscape" format if it asks. The file (cookies.txt or youtube.com_cookies.txt) lands in your Download folder.
- Close the private tab - don't sign out, or the cookies stop working. (Cookies from a normal tab get replaced by YouTube within a day or so; private-tab cookies last much longer.)

[B]4. That's all[/B]
The phone's helper finds the file, moves it out of the shared Download folder (so the Xbox share can't see your sign-in) and uses it for every download. This menu then says "cookies from today".

When downloads start failing with "export a new cookies.txt", repeat step 3.

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


def _plain(text):
    try:
        from sortlib import plain_title
        return plain_title(text)
    except Exception:
        return text


def job_label(j):
    t = _plain(j.get("title") or j.get("url") or "")
    s = j.get("state")
    if s == "downloading":
        part = " (sound)" if (j.get("part") or 1) > 1 else ""
        extra = ", ".join(x for x in ("%.0f MB" % j["mb"] if j.get("mb") else "", j.get("speed"),
                                      j.get("eta") and "%s left" % j["eta"]) if x)
        pct = ("%3d%%" % j["pct"]) if j.get("pct") else ("%.0f MB" % j["mb"] if j.get("mb") else "  0%")
        return "%s%s  %s%s" % (pct, part, t, ("   [%s]" % extra) if extra else "")
    if s == "copying":
        return "100%%  %s   [saving into Download/YouTube]" % t
    if s == "done":
        return "DONE    %s" % _plain(j.get("file") or t)
    if s == "failed":
        return "FAILED  %s - %s" % (t, j.get("error"))
    if s == "cancelled":
        return "STOPPED %s" % t
    return "waiting %s" % t


SHORT = 52  # characters that fit across Kodi's list without scrolling


def _short(t, n=SHORT):
    t = " ".join(t.split())
    return t if len(t) <= n else t[:n - 1].rstrip(" -,.:|") + "\u2026"


def job_lines(j):
    """(title line, status line) for a download, both short enough not to scroll."""
    t = _plain(j.get("title") or j.get("url") or "")
    s = j.get("state")
    if s == "downloading":
        part = " (sound)" if (j.get("part") or 1) > 1 else ""
        pct = ("%d%%" % j["pct"]) if j.get("pct") else "0%"
        bits = [pct + part] + [x for x in ("%.0f MB" % j["mb"] if j.get("mb") else "", j.get("speed"),
                                           j.get("eta") and "%s left" % j["eta"]) if x]
        status = "Downloading: " + ", ".join(bits)
    elif s == "copying":
        status = "100% - saving into Download/YouTube"
    elif s == "done":
        t, status = _plain(j.get("file") or t), "Done"
    elif s == "failed":
        status = "FAILED: %s" % (j.get("error") or "?")
    elif s == "cancelled":
        status = "Stopped"
    else:
        status = "Waiting"
    return _short(t), _short(status, 70)


def select2(dlg, heading, rows, multi=False, **kw):
    """select/multiselect with two short lines per row ([(line1, line2)]); plain one-line
    rows on a Kodi that can't do that."""
    try:
        items = [xbmcgui.ListItem(a, b) for a, b in rows]
        fn = dlg.multiselect if multi else dlg.select
        return fn(heading, items, useDetails=True, **kw)
    except (TypeError, AttributeError):
        labels = ["%s  [%s]" % (a, b) if b else a for a, b in rows]
        return (dlg.multiselect if multi else dlg.select)(heading, labels, **kw)


def quality_info(phone):
    """(current key, [[key, label], ...]) from the phone, or (None, []) with an older helper."""
    r = phone.call("/yt/settings", {})
    if not r.get("settings"):
        return None, []
    return r["settings"].get("quality"), r.get("qualities") or []


def quality_label(cur, qualities):
    return dict((k, v) for k, v in qualities).get(cur) or cur or "?"


def choose_quality(dlg, phone):
    cur, qs = quality_info(phone)
    if not qs:
        dlg.ok(HEADING, "The phone's YouTube helper is older than this option. On the phone: stop xbox-share "
                        "(Ctrl+C) and start it again, then try again.")
        return
    labels = [("%s  (now)" % v) if k == cur else v for k, v in qs]
    pick = dlg.select("Download quality - the best YouTube has, up to this", labels)
    if pick >= 0:
        phone.call("/yt/settings", {"quality": qs[pick][0]})
        xbmcgui.Dialog().notification(HEADING, "Download quality: %s" % qs[pick][1], xbmcgui.NOTIFICATION_INFO, 4000)


def import_cookies(dlg, phone):
    """Look for a cookies file in the phone's Download now and say plainly what happened."""
    c = phone.call("/yt/cookies", {}).get("cookies") or {}
    if c.get("imported"):
        msg = "Cookies imported from %s." % c["imported"]
        msg += ("\nThey're signed in to YouTube - downloads should work now." if c.get("signed_in") else
                "\nBut they aren't signed in to YouTube: sign in to youtube.com in the private tab first, then export again.")
    elif c.get("present"):
        msg = ("No new cookies file in Download, so the phone keeps the ones it has (%s)." % cookie_line({"cookies": c}) +
               "\nTo replace them: export cookies.txt into Download again, then choose this again.")
    else:
        msg = ("No cookies file found in the phone's Download folder.\nExport it with the Firefox extension first "
               "(see How to set up cookies). The file is usually called cookies.txt or youtube.com_cookies.txt.")
    dlg.ok(HEADING, msg)


def queue_line(jobs):
    waiting = sum(1 for j in jobs if j["state"] == "queued")
    now = [j for j in jobs if j["state"] in ("downloading", "copying")]
    done = sum(1 for j in jobs if j["state"] == "done")
    failed = sum(1 for j in jobs if j["state"] == "failed")
    bits = []
    if now:
        n = now[0]
        bits.append("%s %s" % (("%d%%" % n["pct"]) if n.get("pct") else ("%.0f MB" % n["mb"] if n.get("mb") else "starting"),
                               (n.get("title") or "")[:40]))
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
    cur, qs = quality_info(phone)
    q = ("\nQuality: %s (change it in the YouTube menu)" % quality_label(cur, qs)) if qs else ""
    if added and dlg.yesno(HEADING, "%d video%s queued on the phone.%s\nWatch the download progress?"
                           % (added, "" if added == 1 else "s", q), nolabel="Later", yeslabel="Watch"):
        watch(phone)


def search(dlg, phone, last):
    q = dlg.input("Search YouTube", last.get("q", ""))
    if not q:
        return
    last["q"] = q
    prog = xbmcgui.DialogProgress()
    prog.create(HEADING, "Searching YouTube for \"%s\" on the phone..." % q)
    try:
        # 20 = one page of YouTube results (25 needed a second, slow request)
        r = phone.call("/yt/search?n=20&q=" + quote(q), timeout=200)
    finally:
        prog.close()
    if r.get("error"):
        dlg.ok(HEADING, "Search failed: %s" % r["error"])
        return
    res = r.get("results") or []
    if not res:
        dlg.ok(HEADING, "Nothing found for \"%s\"." % q)
        return
    rows = [(_short(_plain(x["title"])), _short("%s%s" % (_mins(x["duration"]) if x.get("duration") else "playlist/live",
                                                          " - " + x["channel"] if x.get("channel") else ""), 70))
            for x in res]
    picks = select2(dlg, "Pick the videos to download (select several, then OK)", rows, multi=True)
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
            r = phone.call("/yt/search?n=1&q=" + quote(url), timeout=200)
        finally:
            prog.close()
        res = r.get("results") or []
        if r.get("error") or not res:
            dlg.ok(HEADING, "Couldn't read that playlist: %s" % (r.get("error") or "empty"))
            return
        picks = select2(dlg, "Playlist - pick the videos (all are selected)",
                        [(_short(_plain(x["title"])), _mins(x["duration"])) for x in res], multi=True,
                        preselect=list(range(len(res))))
        if picks:
            queue_videos(dlg, phone, [res[i] for i in picks])
        return
    queue_videos(dlg, phone, [{"url": url}])


def downloads(dlg, phone):
    while True:
        jobs = phone.call("/yt/jobs")["jobs"]
        opts = [("Watch progress", "live view of the current download"), ("Refresh", "")] + \
               [job_lines(j) for j in jobs] + \
               ([("Clear finished and failed from this list", "the videos stay on the phone")] if jobs else [])
        pick = select2(dlg, "Downloads on the phone - %s" % queue_line(jobs), opts)
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
                what = dlg.select(_short(job_lines(j)[1], 60), ["Try again", "Remove from the list",
                                                                "Show the whole error"])
                if what == 2:
                    dlg.ok(HEADING, "%s\n\n%s" % (_plain(j.get("title") or j["url"]), j.get("error")))
                elif what == 0:
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


def menu(dlg, find_ip, creds, log, dest_line=None):
    """Returns "sort" (sort the finished downloads now), "dest" (choose where they're sorted) or None."""
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
        qcur, qlist = quality_info(phone)
        c = st.get("cookies") or {}
        if c.get("imported"):
            xbmcgui.Dialog().notification(HEADING, "Cookies imported from %s" % c["imported"], xbmcgui.NOTIFICATION_INFO, 5000)
        opts = ["Search YouTube (pick videos from the results)...",
                "Type a YouTube link (video or playlist)...",
                "Downloads: %s" % queue_line(jobs),
                "Sort the finished downloads now (into %s)" % (dest_line() if dest_line else "your library"),
                "How to set up cookies (sign-in) - %s" % cookie_line(st),
                "Import cookies now (from the phone's Download folder)",
                "Download quality: %s" % (quality_label(qcur, qlist) if qlist
                                          else "restart xbox-share on the phone to choose"),
                "Where sorted videos go: %s (change)" % (dest_line() if dest_line else "?")]
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
            elif pick == 5:
                import_cookies(dlg, phone)
            elif pick == 6:
                choose_quality(dlg, phone)
            elif pick == 7:
                return "dest"
        except RuntimeError as e:
            dlg.ok(HEADING, str(e))

"""Real-Debrid: download what's in your Real-Debrid account straight to the library drive.

Sign-in uses Real-Debrid's TV-style device code: Kodi shows a short code, you
enter it at real-debrid.com/device on your phone. (Or type an API token from
real-debrid.com/apitoken.) The tokens are kept in Kodi Sorter's addon_data.
"""
import json
import time

API = "https://api.real-debrid.com/rest/1.0"
OAUTH = "https://api.real-debrid.com/oauth/v2"
CLIENT_ID = "X245A4XAIBGVM"  # Real-Debrid's public client id for open-source apps
VIDEO_EXTS = (".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".ts", ".webm")
STATUS = {
    "downloaded": "Ready",
    "downloading": "Real-Debrid is fetching it",
    "queued": "Waiting at Real-Debrid",
    "uploading": "Real-Debrid is finishing it",
    "compressing": "Real-Debrid is finishing it",
    "magnet_conversion": "Reading the magnet link",
    "waiting_files_selection": "Waiting for files to be picked",
    "magnet_error": "Bad magnet link",
    "error": "Failed at Real-Debrid",
    "virus": "Flagged as a virus",
    "dead": "Dead (no one sharing it)",
}


class RDError(Exception):
    pass


def _http(url, data=None, headers=None, timeout=30):
    """(status code, body bytes). data: dict -> form POST."""
    try:
        from urllib.request import Request, urlopen
        from urllib.parse import urlencode
        from urllib.error import HTTPError
    except ImportError:
        from urllib2 import Request, urlopen, HTTPError
        from urllib import urlencode
    body = urlencode(data).encode() if data is not None else None
    req = Request(url, data=body, headers=dict({"User-Agent": "KodiSorter"}, **(headers or {})))
    try:
        resp = urlopen(req, timeout=timeout)
        try:
            return resp.getcode(), resp.read()
        finally:
            resp.close()
    except HTTPError as e:
        return e.code, e.read() if hasattr(e, "read") else b""


def size_text(n):
    n = float(n or 0)
    return "%.1f GB" % (n / 1e9) if n >= 1e9 else "%d MB" % round(n / 1e6)


class RD(object):
    def __init__(self, load, save, http=_http, now=time.time):
        self.load, self.save, self.http, self.now = load, save, http, now
        self.state = load() or {}

    # ----- sign-in -----
    def signed_in(self):
        return bool(self.state.get("access_token"))

    def sign_out(self):
        self.state = {}
        self.save(self.state)

    def device_start(self):
        code, body = self.http("%s/device/code?client_id=%s&new_credentials=yes" % (OAUTH, CLIENT_ID))
        if code != 200:
            raise RDError("Real-Debrid didn't answer (%s)" % code)
        return json.loads(body.decode("utf-8"))

    def device_poll(self, dev):
        """True once the code was entered and the tokens are saved; False to keep waiting."""
        code, body = self.http("%s/device/credentials?client_id=%s&code=%s" % (OAUTH, CLIENT_ID, dev["device_code"]))
        if code != 200:
            return False
        cred = json.loads(body.decode("utf-8"))
        if not cred.get("client_secret"):
            return False
        self.state = {"client_id": cred["client_id"], "client_secret": cred["client_secret"],
                      "device_code": dev["device_code"]}
        self._token(dev["device_code"])
        return True

    def _token(self, code_or_refresh):
        code, body = self.http("%s/token" % OAUTH, {
            "client_id": self.state["client_id"], "client_secret": self.state["client_secret"],
            "code": code_or_refresh, "grant_type": "http://oauth.net/grant_type/device/1.0"})
        if code != 200:
            raise RDError("Real-Debrid sign-in failed (%s)" % code)
        tok = json.loads(body.decode("utf-8"))
        self.state.update(access_token=tok["access_token"], refresh_token=tok.get("refresh_token"),
                          expires=self.now() + int(tok.get("expires_in", 3600)) - 60)
        self.save(self.state)

    def use_api_token(self, token):
        self.state = {"access_token": token.strip(), "expires": self.now() + 10 * 365 * 86400}
        self.save(self.state)

    # ----- API -----
    def call(self, path, data=None, _again=True):
        if not self.signed_in():
            raise RDError("not signed in to Real-Debrid")
        if self.state.get("refresh_token") and self.now() > self.state.get("expires", 0):
            self._token(self.state["refresh_token"])
        code, body = self.http(API + path, data, {"Authorization": "Bearer " + self.state["access_token"]})
        if code == 401 and _again and self.state.get("refresh_token"):
            self._token(self.state["refresh_token"])
            return self.call(path, data, False)
        if code == 401:
            raise RDError("Real-Debrid signed you out - sign in again")
        if code >= 400:
            try:
                msg = json.loads(body.decode("utf-8")).get("error", "")
            except ValueError:
                msg = ""
            raise RDError("Real-Debrid said no (%s %s)" % (code, msg))
        return json.loads(body.decode("utf-8")) if body and body.strip() else {}

    def user(self):
        return self.call("/user")

    def torrents(self):
        return self.call("/torrents?limit=100")

    def torrent_files(self, tid):
        """[(name, size, restricted link)] for the files of a finished torrent."""
        info = self.call("/torrents/info/%s" % tid)
        files = [f for f in info.get("files", []) if f.get("selected")]
        links = info.get("links") or []
        return [(f["path"].strip("/").split("/")[-1], f.get("bytes", 0), links[i])
                for i, f in enumerate(files) if i < len(links)]

    def add_magnet(self, magnet):
        tid = self.call("/torrents/addMagnet", {"magnet": magnet.strip()}).get("id")
        if not tid:
            raise RDError("Real-Debrid didn't take that magnet link")
        for _ in range(10):  # the file list appears after a moment
            info = self.call("/torrents/info/%s" % tid)
            if info.get("status") == "waiting_files_selection":
                self.call("/torrents/selectFiles/%s" % tid, {"files": "all"})
                break
            if info.get("status") not in ("magnet_conversion", "queued"):
                break
            time.sleep(1)
        return tid

    def unrestrict(self, link):
        r = self.call("/unrestrict/link", {"link": link.strip()})
        if not r.get("download"):
            raise RDError("Real-Debrid couldn't unlock that link")
        return r["download"], r.get("filename") or "download", int(r.get("filesize") or 0)

    def history(self):
        return self.call("/downloads?limit=50")


def torrent_lines(t):
    st = STATUS.get(t.get("status"), t.get("status") or "?")
    if t.get("status") == "downloading" and t.get("progress") is not None:
        st += " - %d%%" % t["progress"]
    return t.get("filename") or "?", "%s - %s" % (st, size_text(t.get("bytes")))


def is_video(name):
    return name.lower().endswith(VIDEO_EXTS)

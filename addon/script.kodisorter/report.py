"""Problem reports: remove private details from a Kodi log before anyone sees it."""
import re

MAX_LINES = 12000  # Kodi's paste site holds about 15,000 lines
_RULES = [
    (re.compile(r"\b((?:dav|davs|ftp|ftps|smb|sftp|nfs|https?)://)[^/\s:@]+:[^/\s@]+@", re.I), r"\1***@"),
    (re.compile(r"([?&;](?:pass|passkey|password|key|apikey|api_key|token|authkey|auth|torrent_pass|secret|sid|uid)=)"
                r"[^&\s\"']+", re.I), r"\1***"),
    (re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+", re.I), r"\1 ***"),
    (re.compile(r"(\"?(?:access_token|refresh_token|client_secret|device_code|password|passcode|pass|api_key|apikey)\"?"
                r"\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|\S+)", re.I), r"\1***"),
    (re.compile(r"([\\/]Users[\\/])[^\\/\s]+", re.I), r"\1***"),
    (re.compile(r"(/home/|/storage/emulated/\d+/|/data/data/)[^/\s]+", re.I), r"\1***"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "x.x.x.x"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "***@***"),
]


def scrub(text):
    """The log's last lines, with passwords, keys, sign-ins, user names and addresses removed."""
    lines = text.splitlines()[-MAX_LINES:]
    out = "\n".join(lines)
    for pattern, repl in _RULES:
        out = pattern.sub(repl, out)
    return out

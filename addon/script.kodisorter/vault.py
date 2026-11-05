"""Optional passcode protection for saved passwords, keys and sign-ins.

The passcode is never stored. A key is derived from it with PBKDF2-HMAC-SHA256, and each
file is sealed with a keystream from HMAC-SHA256 and authenticated with a second key
(encrypt, then MAC). Only Python's standard library is used, because Kodi on an Xbox
can't load compiled crypto modules.
"""
import base64
import hashlib
import hmac
import json
import os

ROUNDS = 200000
CHECK = b"sortovia-passcode-check"


class BadPasscode(Exception):
    pass


def new_salt():
    return base64.b64encode(os.urandom(16)).decode()


def derive(passcode, salt):
    """The session key (text) for a passcode."""
    raw = hashlib.pbkdf2_hmac("sha256", passcode.encode("utf-8"), base64.b64decode(salt), ROUNDS, dklen=64)
    return base64.b64encode(raw).decode()


def _keys(key):
    raw = base64.b64decode(key)
    return raw[:32], raw[32:]


def _stream(enc_key, nonce, length):
    out, counter = [], 0
    while sum(len(b) for b in out) < length:
        out.append(hmac.new(enc_key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest())
        counter += 1
    return b"".join(out)[:length]


def seal(key, data):
    """bytes -> text: nonce + ciphertext + authentication tag."""
    enc_key, mac_key = _keys(key)
    nonce = os.urandom(16)
    body = bytes(a ^ b for a, b in zip(data, _stream(enc_key, nonce, len(data))))
    tag = hmac.new(mac_key, nonce + body, hashlib.sha256).digest()
    return base64.b64encode(nonce + body + tag).decode()


def unseal(key, text):
    """text -> bytes. Raises BadPasscode if the key is wrong or the data was changed."""
    enc_key, mac_key = _keys(key)
    try:
        raw = base64.b64decode(text)
    except ValueError:
        raise BadPasscode()
    nonce, body, tag = raw[:16], raw[16:-32], raw[-32:]
    if len(raw) < 48 or not hmac.compare_digest(tag, hmac.new(mac_key, nonce + body, hashlib.sha256).digest()):
        raise BadPasscode()
    return bytes(a ^ b for a, b in zip(body, _stream(enc_key, nonce, len(body))))


def seal_json(key, value):
    return {"_sealed": seal(key, json.dumps(value).encode("utf-8"))}


def unseal_json(key, value):
    return json.loads(unseal(key, value["_sealed"]).decode("utf-8"))


def is_sealed(value):
    return isinstance(value, dict) and "_sealed" in value


def setup(passcode):
    """What gets saved to recognise the right passcode later, and the session key."""
    salt = new_salt()
    key = derive(passcode, salt)
    return {"salt": salt, "check": seal(key, CHECK)}, key


def unlock(state, passcode):
    """The session key, or None for a wrong passcode."""
    key = derive(passcode, state["salt"])
    try:
        return key if unseal(key, state["check"]) == CHECK else None
    except BadPasscode:
        return None

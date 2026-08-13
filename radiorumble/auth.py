"""An admin password, and a cookie that remembers it.

What this replaces: one shared token, either set in ``RR_ADMIN_TOKEN`` or
generated at boot and printed to the log, sent as an ``X-Admin-Token`` header
and kept in ``sessionStorage``. That was the right weight for a two-hour event
with nothing to leave behind. It stopped being the right weight once the admin
page could change the schedule, because a generated token means a value
that changes every restart, and a fixed one means a secret in the environment
of every shell that starts the server.

A password set on first launch is the smaller thing to ask of somebody running
an event: one prompt, once, and thereafter a normal sign-in.

No new dependencies, and deliberately so -- this app's whole runtime is FastAPI,
uvicorn and a file watcher.

``hashlib.scrypt`` for the password. It is in the standard library, it is
memory-hard, and its parameters are explicit rather than implied by a version
number. n=2**14 costs about 60ms per attempt here, which nobody notices once a
session and which makes a stolen hash expensive to grind.

``hmac`` for the cookie. The cookie is not encrypted and does not need to be:
it says who you are and when it expires, and the signature says the server
wrote it. There is nothing secret in it, so there is nothing to hide -- only
something to make unforgeable.

The signing key lives in the database rather than the environment, generated
once on first use. Two consequences worth stating: sessions survive a restart,
which the old token did not, and resetting the password can invalidate every
existing session by rotating the key, which the old token could not.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import time

log = logging.getLogger(__name__)

PASSWORD_KEY = "admin_password"      # scrypt$n$r$p$salt$hash
SIGNING_KEY = "session_secret"
COOKIE_NAME = "rr_admin"

#: A fortnight. An event runs for an afternoon, but the person setting one up
#: should not be asked to sign in again between the rehearsal and the day.
SESSION_SECONDS = 14 * 24 * 60 * 60

#: scrypt cost. n is the memory-hard one; r and p are the standard pairing.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1

#: Short passwords are fine -- this guards a scoreboard for an afternoon, not a
#: bank -- but a one-character password is a mistake rather than a choice.
MIN_PASSWORD = 6


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# -- passwords --------------------------------------------------------------

def hash_password(raw: str) -> str:
    """scrypt, with the parameters recorded alongside the hash.

    Stored rather than assumed, so raising the cost later does not invalidate
    every existing password -- an old hash still says how to check itself.
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(raw.encode("utf-8"), salt=salt,
                            n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(raw: str, stored: str) -> bool:
    """Constant-time, and false rather than an exception on anything malformed."""
    try:
        scheme, n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(raw.encode("utf-8"), salt=_unb64(salt),
                                n=int(n), r=int(r), p=int(p), dklen=len(_unb64(expected)))
    except (ValueError, TypeError, KeyError):
        return False
    return hmac.compare_digest(digest, _unb64(expected))


# -- the signing key --------------------------------------------------------

def signing_key(db) -> bytes:
    """The key that signs session cookies, made once and kept.

    In the database rather than the environment so sessions survive a restart.
    """
    stored = db.get_setting(SIGNING_KEY)
    if stored:
        return _unb64(stored)
    key = secrets.token_bytes(32)
    db.set_setting(SIGNING_KEY, _b64(key))
    log.info("generated a new session signing key")
    return key


def rotate_signing_key(db) -> None:
    """Invalidate every existing session. Used when the password changes."""
    db.delete_setting(SIGNING_KEY)


# -- sessions ---------------------------------------------------------------

def issue_session(db, *, now: float | None = None) -> str:
    """A signed cookie value: when it expires, and proof the server said so."""
    expires = int((now if now is not None else time.time()) + SESSION_SECONDS)
    payload = f"admin.{expires}"
    signature = hmac.new(signing_key(db), payload.encode("ascii"), hashlib.sha256).digest()
    return f"{payload}.{_b64(signature)}"


def valid_session(db, cookie: str | None, *, now: float | None = None) -> bool:
    """Is this cookie one we wrote, and has it not expired?

    The signature is checked before the expiry is trusted -- the expiry is part
    of the signed payload, so reading it from an unverified cookie would be
    taking the attacker's word for when their access ends.
    """
    if not cookie:
        return False
    try:
        who, expires, signature = cookie.rsplit(".", 2)[-3:]
        payload = f"{who}.{expires}"
    except ValueError:
        return False

    expected = hmac.new(signing_key(db), payload.encode("ascii"), hashlib.sha256).digest()
    try:
        if not hmac.compare_digest(expected, _unb64(signature)):
            return False
    except (ValueError, TypeError):
        return False

    try:
        deadline = int(expires)
    except ValueError:
        return False
    return (now if now is not None else time.time()) < deadline


# -- the state the pages ask about ------------------------------------------

def needs_setup(db) -> bool:
    """True until somebody has chosen a password.

    Every admin endpoint is refused while this is true. An instance nobody has
    claimed is not an open one: it is one waiting to be claimed, and the only
    thing it will accept is the claim.
    """
    return not db.get_setting(PASSWORD_KEY)


def set_password(db, raw: str) -> None:
    """Set or replace the admin password, ending every existing session."""
    if len(raw) < MIN_PASSWORD:
        raise ValueError(f"Use at least {MIN_PASSWORD} characters.")
    db.set_setting(PASSWORD_KEY, hash_password(raw))
    rotate_signing_key(db)


def check_password(db, raw: str) -> bool:
    stored = db.get_setting(PASSWORD_KEY)
    return bool(stored) and verify_password(raw, stored)

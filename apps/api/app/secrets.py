"""App-level secret management (Fernet key for encrypting OAuth tokens).

Key source, in order:
1. ``CF_OAUTH_SECRET_KEY`` env var (RECOMMENDED - set on Render). A
   44-char urlsafe-base64 value is used as a Fernet key directly; any
   other string is hashed into a key.
2. A random key generated on first use and stored in the ``app_secrets``
   table. This keeps the app working zero-config; the trade-off is that
   anyone with database read access could decrypt tokens. Acceptable
   for this free single-tenant tool, set the env var if you care.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import threading

from cryptography.fernet import Fernet

_KEY_ROW = "oauth_encryption_key"
_lock = threading.Lock()
_fernet: Fernet | None = None

_FERNET_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{43}=$")


def _fernet_from_string(value: str) -> Fernet:
    if _FERNET_KEY_RE.match(value):
        return Fernet(value.encode())
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(value.encode()).digest()))


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet
    with _lock:
        if _fernet is not None:
            return _fernet
        env_key = os.environ.get("CF_OAUTH_SECRET_KEY", "").strip()
        if env_key:
            _fernet = _fernet_from_string(env_key)
            return _fernet
        from .db import SessionLocal
        from .models import AppSecret

        with SessionLocal() as db:
            row = db.get(AppSecret, _KEY_ROW)
            if row is None:
                row = AppSecret(key=_KEY_ROW, value=Fernet.generate_key().decode())
                db.add(row)
                db.commit()
            _fernet = Fernet(row.value.encode())
            return _fernet


def encrypt_secret(plain: str) -> str:
    return get_fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    return get_fernet().decrypt(token.encode()).decode()

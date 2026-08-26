"""Google OAuth 2.0 + Gmail API client (drafts only).

Compliance (agreed product rules):
- The ONLY scope requested is ``gmail.modify``: it lets the app create
  drafts inside the candidate's own Gmail account. It cannot read mail,
  send mail, or list contacts.
- The candidate reviews every draft in Gmail and clicks send themselves.
- The refresh token is encrypted at rest (see app/secrets.py).
- Candidate-supplied OAuth client (free Google Cloud project) - the app
  stores no Google credentials of its own.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

from .config import get_settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
DRAFTS_URL = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
SCOPE = "https://www.googleapis.com/auth/gmail.modify"
UA = "CareerForgePro/1.1 (user-authorized Gmail drafts only)"
TIMEOUT = 25


class GmailApiError(RuntimeError):
    pass


def configured() -> bool:
    s = get_settings()
    return bool(s.google_client_id and s.google_client_secret)


def redirect_uri() -> str:
    return get_settings().gmail_redirect_uri


def web_redirect_url(path: str = "/outreach") -> str:
    return get_settings().web_url.rstrip("/") + path


def _request(url: str, *, data: bytes | None = None, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read(2_000_000)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise GmailApiError(f"Google API error {exc.code}: {detail}") from exc
    except Exception as exc:  # network level
        raise GmailApiError(f"Could not reach Google: {str(exc)[:160]}") from exc


def build_auth_url(state: str) -> str:
    s = get_settings()
    q = urllib.parse.urlencode(
        {
            "client_id": s.google_client_id,
            "redirect_uri": redirect_uri(),
            "response_type": "code",
            "scope": SCOPE,
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
    )
    return f"{AUTH_URL}?{q}"


def exchange_code(code: str) -> dict:
    """authorization code -> refresh token + account email."""
    s = get_settings()
    body = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
            "redirect_uri": redirect_uri(),
            "grant_type": "authorization_code",
        }
    ).encode()
    tok = json.loads(
        _request(TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    )
    refresh = tok.get("refresh_token")
    if not refresh:
        raise GmailApiError(
            "Google did not return a refresh token. Disconnect in Settings and reconnect once."
        )
    profile = json.loads(_request(PROFILE_URL, headers={"Authorization": f"Bearer {tok['access_token']}"})
    )
    emails = profile.get("emails") or []
    email = emails[0].get("value") if emails else None
    return {"refresh_token": refresh, "email": email or "your gmail address"}


def refresh_access(refresh_token: str) -> str:
    s = get_settings()
    body = urllib.parse.urlencode(
        {
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode()
    tok = json.loads(
        _request(TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    )
    at = tok.get("access_token")
    if not at:
        raise GmailApiError("Could not refresh the Google token - reconnect Gmail in Settings.")
    return at


def create_draft(refresh_token: str, to: str, subject: str, body: str) -> str:
    """Create a draft in the candidate's Gmail. Returns the draft id."""
    access = refresh_access(refresh_token)
    message = (
        f"To: {to}\nSubject: {subject}\n"
        "Content-Type: text/plain; charset=UTF-8\nMIME-Version: 1.0\n\n"
        f"{body}\n"
    )
    raw = base64.urlsafe_b64encode(message.encode("utf-8")).decode().rstrip("=")
    out = json.loads(
        _request(
            DRAFTS_URL,
            data=json.dumps({"id": {"message": {"raw": raw}}}).encode(),
            headers={
                "Authorization": f"Bearer {access}",
                "Content-Type": "application/json",
            },
        )
    )
    draft_id = out.get("id")
    if not draft_id:
        raise GmailApiError("Gmail did not return a draft id.")
    return draft_id

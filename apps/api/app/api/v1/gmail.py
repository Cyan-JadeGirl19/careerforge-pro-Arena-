"""Gmail OAuth connection (candidate's own account, drafts-only scope).

The app can create drafts in the candidate's Gmail and nothing more
(scope ``gmail.modify``). Pending OAuth states are kept in memory with
a 10-minute TTL - the service is effectively single-instance on the
free tier, which matches this usage.
"""
from __future__ import annotations

import time
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import uuid4

from ... import gmailx, secrets
from ...config import get_settings
from ...consents import require_consent
from ...db import SessionLocal, get_db
from ...models import GmailAccount, OutreachDraft, Profile, RecruiterContact
from ...schemas import (
    GmailAuthorizeOut,
    GmailStatusOut,
    OutreachDraftOut,
)
from .profiles import get_profile_or_404

router = APIRouter(tags=["gmail"])

_PENDING: dict[str, tuple[str, float]] = {}  # state -> (profile_id, expires_at)
_STATE_TTL = 600


def _prune_states() -> None:
    now = time.time()
    for k in [k for k, (_, exp) in _PENDING.items() if exp < now]:
        _PENDING.pop(k, None)


def _get_account(db: Session, profile_id: str) -> GmailAccount | None:
    return db.scalars(
        select(GmailAccount).where(GmailAccount.profile_id == profile_id)
    ).first()


def _status_out(profile_id: str, db: Session) -> GmailStatusOut:
    acc = _get_account(db, profile_id)
    if acc is None:
        return GmailStatusOut(connected=False)
    return GmailStatusOut(
        connected=True,
        email=acc.email,
        scopes=acc.scopes or None,
        connected_at=acc.connected_at,
    )


def _callback_page(message: str, *, failed: bool, target: str) -> HTMLResponse:
    safe_msg = message.replace("<", "&lt;").replace(">", "&gt;")
    safe_target = urllib.parse.quote(target, safe="/?&=")
    kind = "error" if failed else "success"
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<meta http-equiv='refresh' content='3;url={safe_target}'>"
        f"<title>CareerForge Pro</title>"
        f"<style>body{{font-family:system-ui,sans-serif;max-width:480px;margin:80px auto;"
        f"color:#222;padding:0 20px}}.box{{border-radius:12px;padding:20px 22px;margin:18px 0}}"
        f".ok{{background:#e8f6ee;color:#1d7a46;border:1px solid #bfe5cf}}"
        f".err{{background:#fdecec;color:#b03030;border:1px solid #f3c1c1}}"
        f"a{{color:#1a56b0}}</style></head><body>"
        f"<h1 style='font-size:22px'>CareerForge Pro</h1>"
        f"<div class='box {kind}'>{safe_msg}</div>"
        f"<p>Taking you back in 3 seconds &mdash; or "
        f"<a href='{safe_target}'>continue now</a>.</p></body></html>"
    )


@router.get("/profiles/{profile_id}/gmail/status", response_model=GmailStatusOut)
def gmail_status(profile_id: str, db: Session = Depends(get_db)) -> GmailStatusOut:
    get_profile_or_404(db, profile_id)
    return _status_out(profile_id, db)


@router.post("/profiles/{profile_id}/gmail/authorize", response_model=GmailAuthorizeOut)
def gmail_authorize(profile_id: str, db: Session = Depends(get_db)) -> GmailAuthorizeOut:
    profile = get_profile_or_404(db, profile_id)
    require_consent(db, profile.id, "outreach_sending")
    if not gmailx.configured():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "GOOGLE_NOT_CONFIGURED",
                "message": (
                    "Gmail is not configured on this deployment yet. A free Google "
                    "Cloud OAuth client is needed - see docs/GOOGLE_SETUP.md."
                ),
            },
        )
    _prune_states()
    state = uuid4().hex
    _PENDING[state] = (profile.id, time.time() + _STATE_TTL)
    return GmailAuthorizeOut(auth_url=gmailx.build_auth_url(state))


@router.get("/gmail/oauth/callback")
def gmail_callback(
    state: str = "", code: str = "", error: str = ""
) -> HTMLResponse:
    _prune_states()
    target = gmailx.web_redirect_url("/outreach")
    if error:
        return _callback_page(
            f"Google returned an error ({error}). You can try again from Settings.",
            failed=True,
            target=target,
        )
    entry = _PENDING.pop(state, None) if state else None
    if entry is None:
        return _callback_page(
            "We could not verify that sign-in attempt (it may have expired). "
            "Try connecting again from Settings.",
            failed=True,
            target=target,
        )
    profile_id = entry[0]
    try:
        tok = gmailx.exchange_code(code)
    except gmailx.GmailApiError as exc:
        return _callback_page(str(exc), failed=True, target=target)
    db = SessionLocal()
    try:
        acc = _get_account(db, profile_id)
        if acc is None:
            acc = GmailAccount(
                id=str(uuid4()),
                profile_id=profile_id,
                email=tok["email"],
                refresh_token=secrets.encrypt_secret(tok["refresh_token"]),
                scopes=gmailx.SCOPE,
            )
            db.add(acc)
        else:
            acc.email = tok["email"]
            acc.refresh_token = secrets.encrypt_secret(tok["refresh_token"])
            acc.scopes = gmailx.SCOPE
        from datetime import datetime, timezone

        acc.connected_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()
    return _callback_page(
        f"Connected as {tok['email']}. You can now create outreach drafts "
        "in your own Gmail.",
        failed=False,
        target=target,
    )


@router.post("/profiles/{profile_id}/gmail/disconnect", status_code=204)
def gmail_disconnect(profile_id: str, db: Session = Depends(get_db)) -> None:
    get_profile_or_404(db, profile_id)
    acc = _get_account(db, profile_id)
    if acc is not None:
        db.delete(acc)
        db.commit()


@router.get("/profiles/{profile_id}/outreach/drafts", response_model=list[OutreachDraftOut])
def list_outreach_drafts(profile_id: str, db: Session = Depends(get_db)) -> list[OutreachDraftOut]:
    get_profile_or_404(db, profile_id)
    rows = db.scalars(
        select(OutreachDraft)
        .where(OutreachDraft.profile_id == profile_id)
        .order_by(OutreachDraft.created_at.desc())
    ).all()
    out: list[OutreachDraftOut] = []
    for r in rows:
        name = None
        if r.recruiter_id:
            rec = db.get(RecruiterContact, r.recruiter_id)
            name = rec.name if rec else None
        out.append(
            OutreachDraftOut(
                id=r.id,
                profile_id=r.profile_id,
                to_email=r.to_email,
                subject=r.subject,
                body=r.body,
                tone=r.tone,
                status=r.status,
                gmail_draft_id=r.gmail_draft_id,
                gmail_url=(
                    f"https://mail.google.com/mail/?view=compose&draftid={r.gmail_draft_id}"
                    if r.gmail_draft_id
                    else None
                ),
                recruiter_name=name,
                created_at=r.created_at,
            )
        )
    return out

"""Recruiter / job-poster discovery routes.

Public information only: publicly displayed names/titles/companies,
public profile URLs, and published emails. Pattern-suggested emails are
clearly labelled unverified. No SMTP probing, no hidden data, one page
per user request.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

import urllib.request
from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import gmailx, secrets
from ...config import get_settings
from ...consents import require_consent
from ...db import get_db
from ...models import CvRecord, GmailAccount, OutreachDraft, Profile, RecruiterContact
from ...parsing import ParsedCv, parse_cv_text
from ...recruiters import extract, outreach
from ...schemas import (
    GmailDraftOut,
    OutreachIn,
    OutreachOut,
    RecruiterCreate,
    RecruiterExtractIn,
    RecruiterOut,
    RecruiterUpdate,
)
from .profiles import get_profile_or_404

router = APIRouter(tags=["recruiters"])

MAX_PAGE = 2_000_000
UA = "CareerForgePro/1.0 (user-directed, single public page)"


def _out(c: RecruiterContact) -> RecruiterOut:
    return RecruiterOut(
        id=c.id,
        profile_id=c.profile_id,
        source=c.source,
        source_url=c.source_url,
        name=c.name,
        title=c.title,
        company=c.company,
        profile_url=c.profile_url,
        email=c.email,
        email_status=c.email_status,
        suggested_emails=json.loads(c.suggested_emails or "[]"),
        job_title=c.job_title,
        notes=c.notes,
        verified=c.verified,
        verified_at=c.verified_at,
        suppressed=c.suppressed,
        created_at=c.created_at,
    )


def get_contact_or_404(db: Session, contact_id: str) -> RecruiterContact:
    c = db.get(RecruiterContact, contact_id)
    if c is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "CONTACT_NOT_FOUND", "message": "No contact with that id."},
        )
    return c


def _fetch_page(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=422,
            detail={"code": "BAD_URL", "message": "Enter a full URL starting with https://"},
        )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.read(MAX_PAGE).decode("utf-8", errors="replace")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PAGE_FETCH_FAILED",
                "message": f"Could not read that page: {str(exc)[:120]}. "
                "If the site blocks it, add the contact manually.",
            },
        )


def _parsed_profile(db: Session, profile: Profile):
    cvs = db.scalars(select(CvRecord).where(CvRecord.profile_id == profile.id)).all()
    if not cvs:
        return None
    cv = cvs[-1]
    if not cv.parsed_json:
        cv.parsed_json = json.dumps(parse_cv_text(cv.text).to_dict())
        db.commit()
    d = json.loads(cv.parsed_json)
    return ParsedCv(**{
        k: d[k]
        for k in (
            "name", "email", "phone", "location", "links", "summary",
            "experience", "education", "skills", "certifications",
            "projects", "languages",
        )
    })


# --- extract & manual ---------------------------------------------------------


@router.post("/profiles/{profile_id}/recruiters/extract", response_model=list[RecruiterOut], status_code=201)
def extract_from_page(
    profile_id: str, payload: RecruiterExtractIn, db: Session = Depends(get_db)
) -> list[RecruiterOut]:
    """User-directed: read ONE public page the user provides."""
    profile = get_profile_or_404(db, profile_id)
    require_consent(db, profile.id, "recruiter_contact")
    html = _fetch_page(payload.url)
    result = extract.extract_from_url(payload.url, html, payload.company)
    out = []
    for c in result["contacts"]:
        row = RecruiterContact(
            id=str(uuid.uuid4()),
            profile_id=profile.id,
            **{k: c[k] for k in (
                "source", "source_url", "name", "title", "company",
                "profile_url", "email", "email_status", "suggested_emails",
                "job_title", "notes",
            )},
        )
        db.add(row)
        out.append(row)
    db.commit()
    for row in out:
        db.refresh(row)
    return [_out(r) for r in out]


@router.post("/profiles/{profile_id}/recruiters", response_model=RecruiterOut, status_code=201)
def create_contact(
    profile_id: str, payload: RecruiterCreate, db: Session = Depends(get_db)
) -> RecruiterOut:
    profile = get_profile_or_404(db, profile_id)
    require_consent(db, profile.id, "recruiter_contact")
    row = RecruiterContact(
        id=str(uuid.uuid4()),
        profile_id=profile.id,
        source=payload.source_url and "job_posting" or "manual",
        source_url=payload.source_url,
        name=payload.name,
        title=payload.title,
        company=payload.company,
        profile_url=payload.profile_url,
        email=payload.email,
        email_status=payload.email_status,
        suggested_emails="[]",
        job_title=payload.job_title,
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


@router.get("/profiles/{profile_id}/recruiters", response_model=list[RecruiterOut])
def list_contacts(
    profile_id: str,
    include_suppressed: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[RecruiterOut]:
    profile = get_profile_or_404(db, profile_id)
    stmt = select(RecruiterContact).where(RecruiterContact.profile_id == profile.id)
    if not include_suppressed:
        stmt = stmt.where(RecruiterContact.suppressed.is_(False))
    rows = db.scalars(stmt.order_by(RecruiterContact.created_at.desc())).all()
    return [_out(r) for r in rows]


@router.get("/recruiters/{contact_id}", response_model=RecruiterOut)
def get_contact(contact_id: str, db: Session = Depends(get_db)) -> RecruiterOut:
    return _out(get_contact_or_404(db, contact_id))


@router.patch("/recruiters/{contact_id}", response_model=RecruiterOut)
def update_contact(
    contact_id: str, payload: RecruiterUpdate, db: Session = Depends(get_db)
) -> RecruiterOut:
    c = get_contact_or_404(db, contact_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "verified" and value is True:
            c.verified_at = datetime.now(timezone.utc)
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return _out(c)


@router.delete("/recruiters/{contact_id}", status_code=204)
def delete_contact(contact_id: str, db: Session = Depends(get_db)) -> None:
    c = get_contact_or_404(db, contact_id)
    db.delete(c)
    db.commit()


# --- outreach drafts (drafts only - nothing is ever sent) -----------------------


def _outreach_parts(
    db: Session, c: RecruiterContact, profile: Profile, job_title: str | None, tone: str
) -> tuple[str, list[str], str]:
    """Build (draft_text, issues, subject) from real profile evidence."""
    parsed = _parsed_profile(db, profile)
    candidate_role = None
    evidence = None
    if parsed:
        for e in parsed.experience:
            if e.get("title"):
                candidate_role = e["title"]
                break
        for e in parsed.experience:
            for b in e.get("bullets", []):
                if any(ch.isdigit() for ch in b):
                    evidence = b
                    break
            if evidence:
                break

    first_name = (parsed.name.split()[0] if parsed and parsed.name else None) or (
        profile.first_name if profile else None
    )
    draft, issues = outreach.build_outreach_draft(
        candidate_first_name=first_name,
        candidate_role=candidate_role,
        candidate_evidence=evidence,
        contact_name=c.name,
        contact_title=c.title,
        company=c.company,
        job_title=job_title,
        tone=tone,
        email_status=c.email_status,
    )
    subject = f"About the {job_title} role" if job_title else "Quick introduction"
    return draft, issues, subject


@router.post("/recruiters/{contact_id}/outreach", response_model=OutreachOut)
def outreach_draft(
    contact_id: str, payload: OutreachIn, db: Session = Depends(get_db)
) -> OutreachOut:
    c = get_contact_or_404(db, contact_id)
    profile = db.get(Profile, c.profile_id)
    require_consent(db, c.profile_id, "outreach_sending")
    draft, issues, _ = _outreach_parts(
        db, c, profile, payload.job_title or c.job_title, payload.tone
    )
    return OutreachOut(draft=draft, issues=issues)


@router.post("/recruiters/{contact_id}/gmail-draft", response_model=GmailDraftOut, status_code=201)
def create_gmail_draft(
    contact_id: str, payload: OutreachIn, db: Session = Depends(get_db)
) -> GmailDraftOut:
    """Create the outreach email as a DRAFT in the candidate's own Gmail.

    Hard limits: outreach_sending consent, not suppressed, confirmed
    email, Gmail connected, 20 drafts/hour. The app never sends mail -
    the candidate opens the draft and clicks send themselves.
    """
    c = get_contact_or_404(db, contact_id)
    profile = db.get(Profile, c.profile_id)
    require_consent(db, c.profile_id, "outreach_sending")
    if c.suppressed:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SUPPRESSED",
                "message": "This contact is on your suppression list - do not email them.",
            },
        )
    if not c.email:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NO_EMAIL",
                "message": "No confirmed email address for this contact yet.",
            },
        )
    acc = db.scalars(
        select(GmailAccount).where(GmailAccount.profile_id == c.profile_id)
    ).first()
    if acc is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "GMAIL_NOT_CONNECTED",
                "message": "Connect your Gmail in Settings first. The app only "
                "creates drafts - you always click send yourself.",
            },
        )
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = db.scalars(
        select(OutreachDraft).where(
            OutreachDraft.profile_id == c.profile_id,
            OutreachDraft.created_at >= since,
        )
    ).all()
    if len(recent) >= 20:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "THROTTLED",
                "message": "You've reached the 20-drafts-per-hour limit. Give it a "
                "little time - it keeps you out of spam filters and respectful to recruiters.",
            },
        )
    draft, issues, subject = _outreach_parts(
        db, c, profile, payload.job_title or c.job_title, payload.tone
    )
    try:
        refresh = secrets.decrypt_secret(acc.refresh_token)
        gmail_draft_id = gmailx.create_draft(refresh, c.email, subject, draft)
    except InvalidToken:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "GMAIL_TOKEN_INVALID",
                "message": "Could not read the stored Google token - reconnect Gmail in Settings.",
            },
        )
    except gmailx.GmailApiError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "GMAIL_API_FAILED", "message": str(exc)[:300]},
        )
    row = OutreachDraft(
        id=str(uuid.uuid4()),
        profile_id=c.profile_id,
        recruiter_id=c.id,
        to_email=c.email,
        subject=subject,
        body=draft,
        tone=payload.tone,
        status="sent_to_gmail",
        gmail_draft_id=gmail_draft_id,
        issues_json=json.dumps(issues),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return GmailDraftOut(
        draft_id=row.id,
        to_email=c.email,
        subject=subject,
        gmail_draft_id=gmail_draft_id,
        gmail_url=f"https://mail.google.com/mail/?view=compose&draftid={gmail_draft_id}",
        created_at=row.created_at,
    )

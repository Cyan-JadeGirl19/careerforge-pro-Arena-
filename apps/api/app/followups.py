"""Follow-up scheduling and draft writing.

The program schedules follow-ups automatically when an application
moves to a new stage; the candidate marks them sent/skipped. Drafts are
plain and specific, and sending always happens in the candidate's own
mail client (the program never sends without the Gmail phase + consent).
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Application, FollowUp, Profile
from .parsing import ParsedCv, parse_cv_text
from .schemas import FollowUpOut


def _candidate_first_name(db: Session, profile_id: str) -> str:
    profile = db.get(Profile, profile_id)
    if profile and profile.first_name:
        return profile.first_name.split()[0]
    return ""


def _top_skill(db: Session, profile_id: str) -> str | None:
    from .models import CvRecord

    cvs = db.scalars(select(CvRecord).where(CvRecord.profile_id == profile_id)).all()
    if not cvs:
        return None
    cv = cvs[-1]
    if not cv.parsed_json:
        cv.parsed_json = json.dumps(parse_cv_text(cv.text).to_dict())
        db.commit()
    d = json.loads(cv.parsed_json)
    return d.get("skills")[0] if d.get("skills") else None


def _draft(kind: str, app: Application, candidate_first: str, top_skill: str | None) -> str:
    role = app.jd.title
    company = app.jd.company or "your team"
    sign = f"\n\nThanks,\n{candidate_first}" if candidate_first else ""

    if kind == "post_application":
        return (
            f"Hi {company} team,\n\n"
            f"I wanted to reiterate my interest in the {role} role. "
            + (
                f"My background in {top_skill} maps closely to what you described, "
                if top_skill
                else "My recent work maps closely to what you described, "
            )
            + "and I'd welcome any update on the process when convenient.\n"
            + sign
        )
    if kind == "post_interview":
        return (
            f"Hi {company} team,\n\n"
            f"Thank you for the conversation about the {role} role. "
            f"I enjoyed learning more about the team, and I remain very interested. "
            f"If it's useful, I'm happy to share anything further.\n"
            + sign
        )
    return f"Hi {company} team,\n\nFollow-up on the {role} role.\n" + sign


def follow_up_out(db: Session, f: FollowUp) -> FollowUpOut:
    app = db.get(Application, f.application_id) if f.application_id else None
    return FollowUpOut(
        id=f.id,
        profile_id=f.profile_id,
        application_id=f.application_id,
        kind=f.kind,
        due_at=f.due_at,
        status=f.status,
        draft_text=f.draft_text,
        notes=f.notes,
        touch_number=f.touch_number,
        gmail_draft_id=f.gmail_draft_id,
        gmail_url=(
            f"https://mail.google.com/mail/?view=compose&draftid={f.gmail_draft_id}"
            if f.gmail_draft_id
            else None
        ),
        application_title=app.jd.title if app else None,
        application_company=app.jd.company if app else None,
    )


def maybe_schedule(db: Session, app: Application, new_status: str) -> FollowUp | None:
    """Auto-schedule when an application advances. One per kind, ever."""
    rules = {
        "applied": ("post_application", 5),
        "interview": ("post_interview", 3),
    }
    if new_status not in rules:
        return None
    kind, days = rules[new_status]
    existing = db.scalar(
        select(FollowUp).where(
            FollowUp.application_id == app.id,
            FollowUp.kind == kind,
        )
    )
    if existing is not None:
        return None
    f = FollowUp(
        id=str(uuid.uuid4()),
        profile_id=app.profile_id,
        application_id=app.id,
        kind=kind,
        due_at=datetime.now(timezone.utc) + timedelta(days=days),
        status="scheduled",
        draft_text=_draft(kind, app, _candidate_first_name(db, app.profile_id), _top_skill(db, app.profile_id)),
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


def list_followups(db: Session, profile_id: str, only_active: bool = True) -> list[FollowUpOut]:
    stmt = select(FollowUp).where(FollowUp.profile_id == profile_id)
    if only_active:
        stmt = stmt.where(FollowUp.status == "scheduled")
    rows = db.scalars(stmt.order_by(FollowUp.due_at.asc())).all()
    return [follow_up_out(db, f) for f in rows]


def create_followup(
    db: Session,
    profile_id: str,
    application_id: str,
    kind: str,
    due_days: int,
    notes: str | None,
) -> FollowUp:
    app = db.get(Application, application_id)
    if app is None or app.profile_id != profile_id:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail={"code": "APPLICATION_NOT_FOUND", "message": "No application with that id."},
        )
    f = FollowUp(
        id=str(uuid.uuid4()),
        profile_id=profile_id,
        application_id=application_id,
        kind=kind,
        due_at=datetime.now(timezone.utc) + timedelta(days=due_days),
        status="scheduled",
        draft_text=_draft(kind, app, _candidate_first_name(db, profile_id), _top_skill(db, profile_id)),
        notes=notes,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


def get_followup(db: Session, followup_id: str) -> FollowUp:
    from fastapi import HTTPException

    f = db.get(FollowUp, followup_id)
    if f is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "FOLLOWUP_NOT_FOUND", "message": "No follow-up with that id."},
        )
    return f


# --- 3-touch follow-up sequences -------------------------------------------------

# Day offsets from today for each pattern. Spaced so there is never more
# than one outstanding touch: the next is only drafted after the previous
# is marked sent or skipped.
SEQUENCE_OFFSETS: dict[str, tuple[int, int, int]] = {
    "standard": (5, 10, 17),
    "quick": (3, 7, 12),
    "gentle": (7, 14, 21),
}

SEQUENCE_STATUS_OK = {"applied", "phone_screen"}


def _first_evidence(db: Session, profile_id: str) -> str | None:
    """First quantified bullet from the CV - real, never invented."""
    from .models import CvRecord

    cvs = db.scalars(select(CvRecord).where(CvRecord.profile_id == profile_id)).all()
    if not cvs:
        return None
    cv = cvs[-1]
    if not cv.parsed_json:
        cv.parsed_json = json.dumps(parse_cv_text(cv.text).to_dict())
        db.commit()
    d = json.loads(cv.parsed_json)
    for e in d.get("experience", []):
        for b in e.get("bullets", []):
            if any(ch.isdigit() for ch in b):
                return b.strip().lstrip("-• ").strip()
    return None


def _draft_touch(
    touch_number: int, app: Application, candidate_first: str, evidence: str | None
) -> str:
    """Plain, human copy per touch. No pressure, no AI filler words."""
    role = app.jd.title
    company = app.jd.company or "your team"
    sign = f"\n\nThanks,\n{candidate_first}" if candidate_first else ""

    if touch_number == 1:
        body = (
            f"I'm following up on my application for the {role} role. "
            + (
                f"Relevant to what you described, {evidence.lower()} - happy to go "
                "into more detail if useful. "
                if evidence
                else ""
            )
            + "Any update on the process would be welcome."
        )
    elif touch_number == 2:
        body = (
            f"I'm still very interested in the {role} role, so I wanted to check in "
            "once more. I know these things take time - no pressure at all. "
            "If it would help, I'm glad to share anything further or make time "
            "for a quick chat."
        )
    else:
        body = (
            f"This is my last note on the {role} application, so nothing further "
            "will follow. I remain interested should anything change, and I'm "
            "grateful for the time spent reviewing my application. I wish the "
            "team the best in finding the right person."
        )
    return f"Hi {company} team,\n\n{body}\n" + sign


def create_sequence(
    db: Session, app: Application, pattern: str
) -> list[FollowUp]:
    """Schedule a 3-touch follow-up sequence for an application.

    Guards: pattern valid, application in an active stage, and no
    post-application follow-ups already scheduled (an auto or manual one
    means the candidate has already started following up).
    """
    from fastapi import HTTPException

    if pattern not in SEQUENCE_OFFSETS:
        raise HTTPException(
            status_code=422,
            detail={"code": "BAD_PATTERN", "message": f"Unknown pattern '{pattern}'."},
        )
    if app.status not in SEQUENCE_STATUS_OK:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "BAD_STAGE",
                "message": "Follow-up sequences start once you've applied "
                "(status: applied or phone screen).",
            },
        )
    existing = db.scalars(
        select(FollowUp).where(
            FollowUp.application_id == app.id,
            FollowUp.kind == "post_application",
        )
    ).all()
    # A sequence already exists if any touch beyond the first is present.
    if any(e.touch_number >= 2 for e in existing):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ALREADY_SCHEDULED",
                "message": "A follow-up sequence is already running for this "
                "application - work through its touches first.",
            },
        )
    # Supersede the single auto-scheduled follow-up (touch 1) so the
    # sequence is the one source of post-application follow-ups.
    for e in existing:
        if e.status == "scheduled":
            db.delete(e)
    db.flush()
    offsets = SEQUENCE_OFFSETS[pattern]
    first = _candidate_first_name(db, app.profile_id)
    evidence = _first_evidence(db, app.profile_id)
    now = datetime.now(timezone.utc)
    rows = []
    for i, days in enumerate(offsets, start=1):
        f = FollowUp(
            id=str(uuid.uuid4()),
            profile_id=app.profile_id,
            application_id=app.id,
            kind="post_application",
            due_at=now + timedelta(days=days),
            status="scheduled",
            draft_text=_draft_touch(i, app, first, evidence),
            touch_number=i,
        )
        db.add(f)
        rows.append(f)
    db.commit()
    for f in rows:
        db.refresh(f)
    return rows


# --- follow-up -> Gmail draft (drafts only, one outstanding touch) ---------------

HOUR_THROTTLE = 20


def create_followup_gmail_draft(db: Session, f: FollowUp) -> FollowUp:
    """File a pending follow-up as a draft in the candidate's own Gmail.

    Etiquette + safety gates, enforced server-side:
    - application must still be in an active stage (no touching once it
      moves to interview/offer/rejected)
    - the touch must be pending, and must be the EARLIEST pending touch
      (never two outstanding follow-ups)
    - Gmail connected; 20-draft/hour throttle shared with recruiter
      outreach drafts
    """
    from fastapi import HTTPException

    from . import gmailx, secrets
    from .models import GmailAccount, OutreachDraft

    app = db.get(Application, f.application_id) if f.application_id else None
    if app is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "NO_APPLICATION", "message": "This follow-up has no application."},
        )
    if app.status not in SEQUENCE_STATUS_OK:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "PROCESS_MOVED_ON",
                "message": f"The application has moved to '{app.status}' - "
                "no need to follow up. Mark this one skipped.",
            },
        )
    if f.status != "scheduled":
        raise HTTPException(
            status_code=409,
            detail={"code": "NOT_PENDING", "message": "Only pending follow-ups can be drafted."},
        )
    pending = db.scalars(
        select(FollowUp)
        .where(
            FollowUp.application_id == app.id,
            FollowUp.kind == "post_application",
            FollowUp.status == "scheduled",
        )
        .order_by(FollowUp.touch_number.asc(), FollowUp.due_at.asc())
    ).all()
    if pending and pending[0].id != f.id:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "OUT_OF_ORDER",
                "message": f"Send or skip touch {pending[0].touch_number} first - "
                "keep at most one follow-up outstanding.",
            },
        )
    acc = db.scalars(
        select(GmailAccount).where(GmailAccount.profile_id == app.profile_id)
    ).first()
    if acc is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "GMAIL_NOT_CONNECTED",
                "message": "Connect your Gmail in Settings first - the app only "
                "creates drafts, you always click send.",
            },
        )
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    outreach_count = db.scalars(
        select(OutreachDraft).where(
            OutreachDraft.profile_id == app.profile_id,
            OutreachDraft.created_at >= since,
        )
    ).all()
    fu_count = db.scalars(
        select(FollowUp).where(
            FollowUp.profile_id == app.profile_id,
            FollowUp.gmail_draft_id.is_not(None),
            FollowUp.created_at >= since,
        )
    ).all()
    if len(outreach_count) + len(fu_count) >= HOUR_THROTTLE:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "THROTTLED",
                "message": "Hourly outreach limit (20) reached across drafts - "
                "wait a little to stay out of spam filters.",
            },
        )
    recipient = _contact_email(db, app)
    subject = f"Following up - {app.jd.title} application"
    try:
        refresh = secrets.decrypt_secret(acc.refresh_token)
        gmail_draft_id = gmailx.create_draft(refresh, recipient, subject, f.draft_text)
    except Exception as exc:  # noqa: BLE001 - surfaced as a clear API error
        from cryptography.fernet import InvalidToken

        if isinstance(exc, InvalidToken):
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "GMAIL_TOKEN_INVALID",
                    "message": "Could not read the stored Google token - reconnect Gmail in Settings.",
                },
            )
        raise HTTPException(
            status_code=502,
            detail={"code": "GMAIL_API_FAILED", "message": str(exc)[:300]},
        )
    f.gmail_draft_id = gmail_draft_id
    db.commit()
    db.refresh(f)
    return f


def _contact_email(db: Session, app: Application) -> str:
    """Follow-ups go to the employer, never to the candidate: the recipient
    is the best-matching NON-suppressed recruiter contact on file (job
    title first, then company), and must have a publicly displayed email.
    No guesswork - pattern-suggested emails are never used here."""
    from .models import RecruiterContact

    rows = db.scalars(
        select(RecruiterContact)
        .where(
            RecruiterContact.profile_id == app.profile_id,
            RecruiterContact.suppressed.is_(False),
        )
    ).all()
    # Only contacts that match THIS job (title, then company) - a follow-up
    # must never land with the wrong company.
    for r in rows:
        if (
            r.email
            and r.job_title
            and app.jd.title
            and r.job_title.lower() == app.jd.title.lower()
        ):
            return r.email
    for r in rows:
        if r.email and r.company and app.jd.company and r.company.lower() == app.jd.company.lower():
            return r.email
    raise NoContactEmail()


class NoContactEmail(Exception):
    """Raised when no publicly displayed recruiter email is on file."""

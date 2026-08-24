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

"""Follow-up routes: the program schedules, the candidate acts."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...consents import require_consent
from ...db import get_db
from ...followups import (
    NoContactEmail,
    create_followup,
    create_followup_gmail_draft,
    create_sequence,
    follow_up_out,
    get_followup,
    list_followups,
)
from ...schemas import (
    FollowUpCreate,
    FollowUpOut,
    FollowUpSequenceCreate,
    FollowUpSequenceOut,
    FollowUpStatusIn,
)
from .profiles import get_profile_or_404

router = APIRouter(tags=["followups"])


@router.get("/profiles/{profile_id}/followups", response_model=list[FollowUpOut])
def followups_list(
    profile_id: str,
    include_done: bool = False,
    db: Session = Depends(get_db),
) -> list[FollowUpOut]:
    get_profile_or_404(db, profile_id)
    return list_followups(db, profile_id, only_active=not include_done)


@router.post(
    "/applications/{app_id}/followups",
    response_model=FollowUpOut,
    status_code=201,
)
def followup_create(
    app_id: str, payload: FollowUpCreate, db: Session = Depends(get_db)
) -> FollowUpOut:
    from ...models import Application

    a = db.get(Application, app_id)
    if a is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail={"code": "APPLICATION_NOT_FOUND", "message": "No application with that id."},
        )
    require_consent(db, a.profile_id, "outreach_sending")
    f = create_followup(db, a.profile_id, app_id, payload.kind, payload.due_days, payload.notes)
    return follow_up_out(db, f)


@router.patch("/followups/{followup_id}", response_model=FollowUpOut)
def followup_update(
    followup_id: str, payload: FollowUpStatusIn, db: Session = Depends(get_db)
) -> FollowUpOut:
    # Bookkeeping on the candidate's own reminders - no consent needed.
    f = get_followup(db, followup_id)
    f.status = payload.status
    if payload.notes is not None:
        f.notes = payload.notes
    if payload.draft_text is not None:
        f.draft_text = payload.draft_text
    db.commit()
    db.refresh(f)
    return follow_up_out(db, f)


@router.delete("/followups/{followup_id}", status_code=204)
def followup_delete(followup_id: str, db: Session = Depends(get_db)) -> None:
    f = get_followup(db, followup_id)
    db.delete(f)
    db.commit()


@router.post(
    "/applications/{app_id}/followup-sequence",
    response_model=FollowUpSequenceOut,
    status_code=201,
)
def followup_sequence_create(
    app_id: str, payload: FollowUpSequenceCreate, db: Session = Depends(get_db)
) -> FollowUpSequenceOut:
    from fastapi import HTTPException

    from ...models import Application

    a = db.get(Application, app_id)
    if a is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "APPLICATION_NOT_FOUND", "message": "No application with that id."},
        )
    require_consent(db, a.profile_id, "outreach_sending")
    rows = create_sequence(db, a, payload.pattern)
    return FollowUpSequenceOut(
        pattern=payload.pattern,
        touches=[follow_up_out(db, r) for r in rows],
    )


@router.post(
    "/followups/{followup_id}/gmail-draft",
    response_model=FollowUpOut,
    status_code=201,
)
def followup_gmail_draft(
    followup_id: str, db: Session = Depends(get_db)
) -> FollowUpOut:
    from fastapi import HTTPException

    f = get_followup(db, followup_id)
    require_consent(db, f.profile_id, "outreach_sending")
    try:
        f = create_followup_gmail_draft(db, f)
    except NoContactEmail:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NO_CONTACT_EMAIL",
                "message": "No publicly displayed email for this role's poster is on file. "
                "Add the contact in Recruiter Finder (with its published email) first.",
            },
        )
    return follow_up_out(db, f)

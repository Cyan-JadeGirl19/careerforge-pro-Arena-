"""Follow-up routes: the program schedules, the candidate acts."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...consents import require_consent
from ...db import get_db
from ...followups import (
    create_followup,
    follow_up_out,
    get_followup,
    list_followups,
)
from ...schemas import FollowUpCreate, FollowUpOut, FollowUpStatusIn
from .profiles import get_profile_or_404

router = APIRouter(tags=["followups"])


@router.get("/profiles/{profile_id}/followups", response_model=list[FollowUpOut])
def followups_list(profile_id: str, db: Session = Depends(get_db)) -> list[FollowUpOut]:
    get_profile_or_404(db, profile_id)
    return list_followups(db, profile_id)


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

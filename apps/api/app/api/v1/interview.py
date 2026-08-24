"""Interview Coach routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...db import get_db
from ...interview.generate import generate_session
from ...models import Profile
from ...schemas import InterviewGenerateIn, InterviewSessionOut
from .profiles import get_profile_or_404

router = APIRouter(tags=["interview"])


@router.post("/interview/generate", response_model=InterviewSessionOut)
def interview_generate(
    profile_id: str, payload: InterviewGenerateIn, db: Session = Depends(get_db)
) -> InterviewSessionOut:
    get_profile_or_404(db, profile_id)
    return generate_session(db, profile_id, payload.role, payload.jd_id, payload.jd_text)

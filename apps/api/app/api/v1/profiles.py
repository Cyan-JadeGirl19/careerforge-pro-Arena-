"""Profile CRUD, including POPIA-aligned erasure."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models, schemas
from ...db import get_db

router = APIRouter(prefix="/profiles", tags=["profiles"])


def get_profile_or_404(db: Session, profile_id: str) -> models.Profile:
    profile = db.get(models.Profile, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PROFILE_NOT_FOUND",
                "message": "No profile with that id.",
            },
        )
    return profile


@router.post("", response_model=schemas.ProfileOut, status_code=201)
def create_profile(
    payload: schemas.ProfileCreate, db: Session = Depends(get_db)
) -> models.Profile:
    profile = models.Profile(id=str(uuid.uuid4()), **payload.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{profile_id}", response_model=schemas.ProfileOut)
def get_profile(profile_id: str, db: Session = Depends(get_db)) -> models.Profile:
    return get_profile_or_404(db, profile_id)


@router.patch("/{profile_id}", response_model=schemas.ProfileOut)
def update_profile(
    profile_id: str,
    payload: schemas.ProfileUpdate,
    db: Session = Depends(get_db),
) -> models.Profile:
    profile = get_profile_or_404(db, profile_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=204)
def delete_profile(profile_id: str, db: Session = Depends(get_db)) -> None:
    """Erase the profile and everything derived from it."""
    from ...models import (
        Application,
        CoverLetter,
        CvVersion,
        JobDescription,
        TailoredCv,
        VideoResponse,
    )

    profile = get_profile_or_404(db, profile_id)
    for model in (VideoResponse, CoverLetter, Application):
        for row in list(
            db.scalars(select(model).where(model.profile_id == profile.id)).all()
        ):
            db.delete(row)
    for row in list(
        db.scalars(select(TailoredCv).where(TailoredCv.profile_id == profile.id)).all()
    ):
        db.delete(row)
    for row in list(
        db.scalars(select(CvVersion).where(CvVersion.profile_id == profile.id)).all()
    ):
        db.delete(row)
    for row in list(
        db.scalars(select(JobDescription).where(JobDescription.profile_id == profile.id)).all()
    ):
        db.delete(row)
    for cv in list(profile.cvs):
        for analysis in list(cv.analyses):
            db.delete(analysis)
        db.delete(cv)
    for consent in list(profile.consents):
        db.delete(consent)
    for evidence in list(profile.evidence):
        db.delete(evidence)
    db.delete(profile)
    db.commit()

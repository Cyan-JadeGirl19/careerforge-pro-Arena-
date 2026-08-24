"""Consent grants, revocations, and listing."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import models, schemas
from ...db import get_db
from .profiles import get_profile_or_404

router = APIRouter(prefix="/profiles/{profile_id}/consents", tags=["consents"])


@router.post("", response_model=schemas.ConsentOut, status_code=201)
def grant_consent(
    profile_id: str,
    payload: schemas.ConsentGrant,
    db: Session = Depends(get_db),
) -> models.Consent:
    """Record an explicit consent decision (grant or re-grant)."""
    profile = get_profile_or_404(db, profile_id)
    existing = db.scalars(
        select(models.Consent).where(
            models.Consent.profile_id == profile.id,
            models.Consent.item == payload.item.value,
        )
    ).first()
    if existing is not None:
        existing.granted = payload.granted
        existing.notes = payload.notes
        existing.revoked_at = None if payload.granted else datetime.now(timezone.utc)
        consent = existing
    else:
        consent = models.Consent(
            id=str(uuid.uuid4()),
            profile_id=profile.id,
            item=payload.item.value,
            granted=payload.granted,
            notes=payload.notes,
        )
        db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent


@router.get("", response_model=list[schemas.ConsentOut])
def list_consents(
    profile_id: str, db: Session = Depends(get_db)
) -> list[models.Consent]:
    get_profile_or_404(db, profile_id)
    return list(
        db.scalars(
            select(models.Consent).where(models.Consent.profile_id == profile_id)
        ).all()
    )


@router.delete("/{item}", status_code=204)
def revoke_consent(
    profile_id: str,
    item: schemas.ConsentItem,
    db: Session = Depends(get_db),
) -> None:
    """Revoke a consent. Revocation takes effect immediately."""
    get_profile_or_404(db, profile_id)
    consent = db.scalars(
        select(models.Consent).where(
            models.Consent.profile_id == profile_id,
            models.Consent.item == item.value,
        )
    ).first()
    if consent is None:
        return
    consent.granted = False
    consent.revoked_at = datetime.now(timezone.utc)
    db.commit()

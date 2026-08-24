"""Consent enforcement helpers.

Sensitive actions must check for an *active* consent (granted and not
revoked) for the specific purpose before proceeding. This is the
single place that policy lives so routes stay small and consistent.
"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


def get_active_consent(
    db: Session, profile_id: str, item: str
) -> models.Consent | None:
    stmt = select(models.Consent).where(
        models.Consent.profile_id == profile_id,
        models.Consent.item == item,
        models.Consent.granted.is_(True),
        models.Consent.revoked_at.is_(None),
    )
    return db.scalars(stmt).first()


def require_consent(db: Session, profile_id: str, item: str) -> models.Consent:
    """Raise a 409 with a stable error code when consent is missing."""
    consent = get_active_consent(db, profile_id, item)
    if consent is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CONSENT_REQUIRED",
                "message": f"Explicit consent for '{item}' is required for this action.",
                "hint": "Grant the consent in the app (Settings -> Privacy) or call "
                "POST /api/v1/profiles/{id}/consents first.",
            },
        )
    return consent

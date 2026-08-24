"""CV records and transparent analysis."""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import analysis, models, schemas
from ...consents import require_consent
from ...db import get_db
from .profiles import get_profile_or_404

router = APIRouter(tags=["cvs"])


def get_cv_or_404(db: Session, cv_id: str) -> models.CvRecord:
    cv = db.get(models.CvRecord, cv_id)
    if cv is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "CV_NOT_FOUND", "message": "No CV with that id."},
        )
    return cv


@router.post(
    "/profiles/{profile_id}/cvs", response_model=schemas.CvOut, status_code=201
)
def create_cv(
    profile_id: str,
    payload: schemas.CvCreate,
    db: Session = Depends(get_db),
) -> models.CvRecord:
    """Store a CV version. Requires active profile_processing consent."""
    get_profile_or_404(db, profile_id)
    require_consent(db, profile_id, schemas.ConsentItem.PROFILE_PROCESSING.value)
    previous = db.scalars(
        select(models.CvRecord).where(
            models.CvRecord.profile_id == profile_id
        )
    ).all()
    cv = models.CvRecord(
        id=str(uuid.uuid4()),
        profile_id=profile_id,
        version=len(previous) + 1,
        title=payload.title,
        text=payload.text,
        source_type=payload.source_type,
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    return cv


@router.get("/profiles/{profile_id}/cvs", response_model=list[schemas.CvOut])
def list_cvs(profile_id: str, db: Session = Depends(get_db)) -> list[models.CvRecord]:
    get_profile_or_404(db, profile_id)
    return list(
        db.scalars(
            select(models.CvRecord).where(models.CvRecord.profile_id == profile_id)
        ).all()
    )


@router.get("/cvs/{cv_id}", response_model=schemas.CvOut)
def get_cv(cv_id: str, db: Session = Depends(get_db)) -> models.CvRecord:
    return get_cv_or_404(db, cv_id)


def _analysis_out(record: models.CvAnalysis) -> schemas.CvAnalysisOut:
    report = json.loads(record.report_json)
    return schemas.CvAnalysisOut(
        id=record.id,
        cv_id=record.cv_id,
        created_at=record.created_at,
        **report,
    )


@router.post("/cvs/{cv_id}/analyze", response_model=schemas.CvAnalysisOut)
def analyze_cv(cv_id: str, db: Session = Depends(get_db)) -> schemas.CvAnalysisOut:
    """Run the transparent checks and store the report."""
    cv = get_cv_or_404(db, cv_id)
    report = analysis.analyze_cv_text(cv.text)
    record = models.CvAnalysis(
        id=str(uuid.uuid4()),
        cv_id=cv.id,
        report_json=json.dumps(report),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _analysis_out(record)


@router.get("/cvs/{cv_id}/analysis/latest", response_model=schemas.CvAnalysisOut)
def latest_analysis(
    cv_id: str, db: Session = Depends(get_db)
) -> schemas.CvAnalysisOut:
    get_cv_or_404(db, cv_id)
    record = db.scalars(
        select(models.CvAnalysis)
        .where(models.CvAnalysis.cv_id == cv_id)
        .order_by(models.CvAnalysis.created_at.desc())
    ).first()
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ANALYSIS_NOT_FOUND",
                "message": "No analysis yet. Call POST /api/v1/cvs/{id}/analyze.",
            },
        )
    return _analysis_out(record)

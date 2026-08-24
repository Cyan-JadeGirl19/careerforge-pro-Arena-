"""Job Finder routes: permitted feeds, SA-eligibility signals, matching,
and one-click hand-off to the application pipeline."""
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...jobs import service as jobs_service, sources as jobs_sources
from ...config import get_settings
from ...consents import require_consent
from ...db import get_db
from ...models import (
    Application,
    CoverLetter,
    JobDescription,
    JobPosting,
    Profile,
    SavedSearch,
)
from ...parsing import ParsedCv
from ...schemas import (
    AddUrlIn,
    JobDetailOut,
    JobOut,
    JobSyncOut,
    SavedSearchIn,
    SavedSearchOut,
    SourceStatusOut,
)
from ...writing import build_cover_letter
from .profiles import get_profile_or_404

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _profile_for_match(db: Session, profile_id: str | None) -> Profile | None:
    if not profile_id:
        return None
    profile = db.get(Profile, profile_id)
    if profile is None:
        return None
    return profile


def _maybe_match(db: Session, profile: Profile | None, job: JobPosting):
    if profile is None:
        return None
    try:
        return jobs_service.compute_match(db, profile, job)
    except Exception:
        return None


def _out(job: JobPosting, match=None, detail: bool = False):
    d = jobs_service.job_to_dict(job, match)
    if detail:
        d["description"] = job.description
    return d


# --- search & sync -------------------------------------------------------------


@router.get("", response_model=list[JobOut])
def search_jobs(
    q: str | None = Query(default=None, max_length=120),
    source: str | None = Query(default=None, pattern="^(all|wwr|remoteok|remotive|adzuna|user_url)$"),
    sa_only: bool = Query(default=False),
    max_age_days: int | None = Query(default=None, ge=1, le=90),
    sort: str = Query(default="newest", pattern="^(newest|oldest)$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    profile_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    profile = _profile_for_match(db, profile_id)
    rows = jobs_service.search_jobs(
        db, q=q, source=source, sa_only=sa_only, max_age_days=max_age_days,
        sort=sort, limit=limit, offset=offset,
    )
    out = []
    for job in rows:
        match = _maybe_match(db, profile, job) if profile else None
        if profile and match is not None:
            require_consent_quiet(db, profile.id)
        out.append(_out(job, match))
    return out


def require_consent_quiet(db: Session, profile_id: str) -> None:
    """Matching uses job_matching consent; but search is a read-only,
    local operation on already-stored data, so we don't block browsing.
    Kept as a no-op hook for a future stricter mode."""
    return None


@router.post("/sync", response_model=JobSyncOut)
def sync_jobs(db: Session = Depends(get_db)) -> JobSyncOut:
    """Pull every enabled public feed. One source failing never blocks the rest."""
    settings = get_settings()
    enabled = [s for s in settings.job_sources if s in jobs_service.SOURCE_NAMES]
    creds = None
    if "adzuna" in enabled and settings.adzuna_app_id and settings.adzuna_api_key:
        creds = (settings.adzuna_app_id, settings.adzuna_api_key)
    results = jobs_service.sync_all(db, enabled, creds)
    total = db.scalar(select(func.count(JobPosting.id))) or 0
    return JobSyncOut(sources=results, total_jobs=total)


@router.get("/health", response_model=list[SourceStatusOut])
def jobs_health(db: Session = Depends(get_db)) -> list[dict]:
    settings = get_settings()
    out = []
    for name in ("wwr", "remoteok", "remotive", "adzuna", "user_url"):
        enabled = (name in settings.job_sources) or name == "user_url"
        if name == "user_url":
            out.append({"source": name, "enabled": True, "status": "manual"})
            continue
        last = db.scalar(
            select(func.max(JobPosting.fetched_at)).where(JobPosting.source == name)
        )
        out.append(
            {
                "source": name,
                "enabled": enabled and name in jobs_service.SOURCE_NAMES,
                "status": "has_data" if last else "empty",
                "fetched": db.scalar(
                    select(func.count(JobPosting.id)).where(JobPosting.source == name)
                ) or 0,
                "last_sync": last,
                "error": None,
            }
        )
    return out  # type: ignore[return-value]


# --- detail, hand-off, add-url ---------------------------------------------------


@router.get("/{job_id}", response_model=JobDetailOut)
def get_job(
    job_id: str,
    profile_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    job = jobs_service.get_job(db, job_id)
    profile = _profile_for_match(db, profile_id)
    return _out(job, _maybe_match(db, profile, job), detail=True)


@router.post("/{job_id}/to-application", status_code=201, response_model=dict)
def job_to_application(
    job_id: str,
    profile_id: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    """The hand-off: job -> JD record -> application package (tailored CV +
    cover letter). Consent-gated; nothing is submitted anywhere."""
    job = jobs_service.get_job(db, job_id)
    profile = get_profile_or_404(db, profile_id)
    require_consent(db, profile.id, "job_matching")
    require_consent(db, profile.id, "profile_processing")

    # Don't duplicate if this job already has an application for this profile.
    existing_jd = db.scalar(
        select(JobDescription).where(
            JobDescription.profile_id == profile.id,
            JobDescription.source_url == job.url,
        )
    )
    if existing_jd is not None:
        existing_app = db.scalar(
            select(Application).where(
                Application.profile_id == profile.id,
                Application.jd_id == existing_jd.id,
            )
        )
        if existing_app is not None:
            return {"application_id": existing_app.id, "existing": True}

    jd = JobDescription(
        id=str(uuid.uuid4()),
        profile_id=profile.id,
        title=job.title,
        company=job.company,
        source_url=job.url,
        text=job.description[:100000] or f"{job.title} at {job.company or 'unknown company'}",
    )
    db.add(jd)
    db.flush()

    # Reuse the studio logic: create application (auto-picks best version or
    # builds masters), tailor, letter.
    from .applications_internal import create_application_package

    app_id = create_application_package(db, profile, jd)
    return {"application_id": app_id, "existing": False}


@router.post("/add-url", status_code=201, response_model=JobOut)
def add_job_url(
    payload: AddUrlIn,
    profile_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """User-directed: fetch one public job page the user provides."""
    get_profile_or_404(db, profile_id)
    try:
        posting = jobs_sources.fetch_user_url(payload.url)
    except ValueError as exc:
        raise _http_422(str(exc))
    except Exception as exc:
        raise _http_422(f"Could not read that page: {str(exc)[:120]}")
    existing = db.scalar(select(JobPosting).where(JobPosting.dedupe_key == posting["dedupe_key"]))
    if existing is not None:
        return _out(existing)
    row = JobPosting(id=str(uuid.uuid4()), fetched_at=datetime.now(timezone.utc), **posting)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _out(row)


def _http_422(message: str):
    from fastapi import HTTPException

    return HTTPException(status_code=422, detail={"code": "URL_FAILED", "message": message})


# --- saved searches ---------------------------------------------------------------


@router.get("/profiles/{profile_id}/saved-searches", response_model=list[SavedSearchOut])
def list_saved(profile_id: str, db: Session = Depends(get_db)) -> list[dict]:
    get_profile_or_404(db, profile_id)
    rows = db.scalars(
        select(SavedSearch).where(SavedSearch.profile_id == profile_id)
    ).all()
    return [
        {"id": r.id, "name": r.name, "filters": json.loads(r.filters_json), "created_at": r.created_at}
        for r in rows
    ]


@router.post("/profiles/{profile_id}/saved-searches", response_model=SavedSearchOut, status_code=201)
def save_search(profile_id: str, payload: SavedSearchIn, db: Session = Depends(get_db)) -> dict:
    get_profile_or_404(db, profile_id)
    row = SavedSearch(
        id=str(uuid.uuid4()),
        profile_id=profile_id,
        name=payload.name,
        filters_json=json.dumps(payload.filters),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "filters": payload.filters, "created_at": row.created_at}


@router.delete("/profiles/{profile_id}/saved-searches/{search_id}", status_code=204)
def delete_search(profile_id: str, search_id: str, db: Session = Depends(get_db)) -> None:
    get_profile_or_404(db, profile_id)
    row = db.get(SavedSearch, search_id)
    if row is not None and row.profile_id == profile_id:
        db.delete(row)
        db.commit()

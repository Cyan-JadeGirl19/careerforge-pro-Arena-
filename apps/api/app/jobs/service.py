"""Jobs service: sync sources, dedupe, search, match, hand off to applications."""
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import JobPosting, Profile
from . import sources
from .matching import match_job

SOURCE_NAMES = ("wwr", "remoteok", "remotive", "adzuna")


def sync_all(db: Session, enabled: list[str], adzuna_creds: tuple[str, str] | None) -> list[dict]:
    """Fetch every enabled source; one broken source never fails the others."""
    results = []
    for name in enabled:
        entry = {
            "source": name,
            "enabled": True,
            "status": "ok",
            "fetched": 0,
            "added": 0,
            "error": None,
        }
        try:
            if name == "adzuna":
                if not adzuna_creds:
                    entry.update(enabled=False, status="disabled", error="No Adzuna API key configured.")
                    results.append(entry)
                    continue
                postings = sources.fetch_adzuna(*adzuna_creds)
            else:
                fn = sources.get_source(name)
                if fn is None:
                    entry.update(enabled=False, status="disabled", error="Unknown source.")
                    results.append(entry)
                    continue
                postings = fn()
            entry["fetched"] = len(postings)
            seen: set[str] = set()
            for p in postings:
                if p["dedupe_key"] in seen:
                    continue  # duplicate within this feed batch
                seen.add(p["dedupe_key"])
                existing = db.scalar(
                    select(JobPosting).where(JobPosting.dedupe_key == p["dedupe_key"])
                )
                if existing is None:
                    db.add(JobPosting(id=str(uuid.uuid4()), fetched_at=datetime.now(timezone.utc), **p))
                    entry["added"] += 1
                elif p.get("posted_at") and existing.posted_at is None:
                    existing.posted_at = p["posted_at"]
            db.commit()
        except Exception as exc:  # noqa: BLE001 - per-source isolation
            db.rollback()
            entry.update(status="error", error=str(exc)[:200])
        results.append(entry)
    return results


def search_jobs(
    db: Session,
    *,
    q: str | None = None,
    source: str | None = None,
    sa_only: bool = False,
    max_age_days: int | None = None,
    sort: str = "newest",
    limit: int = 50,
    offset: int = 0,
) -> list[JobPosting]:
    stmt = select(JobPosting)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                JobPosting.title.ilike(like),
                JobPosting.company.ilike(like),
                JobPosting.tags.ilike(like),
                JobPosting.description.ilike(like),
            )
        )
    if source and source != "all":
        stmt = stmt.where(JobPosting.source == source)
    if sa_only:
        stmt = stmt.where(JobPosting.open_to_sa == "yes")
    if max_age_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        stmt = stmt.where(JobPosting.posted_at >= cutoff)
    if sort == "newest":
        stmt = stmt.order_by(JobPosting.posted_at.desc().nulls_last())
    elif sort == "oldest":
        stmt = stmt.order_by(JobPosting.posted_at.asc().nulls_last())
    return list(db.scalars(stmt.limit(limit).offset(offset)).all())


def get_job(db: Session, job_id: str) -> JobPosting:
    job = db.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": "No job with that id."},
        )
    return job


def job_to_dict(job: JobPosting, match: dict | None = None) -> dict:
    return {
        "id": job.id,
        "source": job.source,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "url": job.url,
        "tags": job.tags,
        "salary_text": job.salary_text,
        "posted_at": job.posted_at,
        "fetched_at": job.fetched_at,
        "open_to_sa": job.open_to_sa,
        "sa_signals": json.loads(job.sa_signals_json) if job.sa_signals_json else [],
        "global_signals": json.loads(job.global_signals_json) if job.global_signals_json else [],
        "exclude_signals": json.loads(job.exclude_signals_json) if job.exclude_signals_json else [],
        "payment_signals": json.loads(job.payment_signals_json) if job.payment_signals_json else [],
        "timezone_signals": json.loads(job.timezone_signals_json) if job.timezone_signals_json else [],
        "remote_type": job.remote_type,
        "match": match,
    }


def profile_match_inputs(db: Session, profile: Profile) -> tuple[list[str], int | None, str]:
    """Skills, years, and full corpus from the profile's latest parsed CV."""
    from ..models import CvRecord
    from ..parsing import ParsedCv, parse_cv_text

    cvs = db.scalars(select(CvRecord).where(CvRecord.profile_id == profile.id)).all()
    if not cvs:
        return [], None, ""
    cv = cvs[-1]
    if not cv.parsed_json:
        cv.parsed_json = json.dumps(parse_cv_text(cv.text).to_dict())
        db.commit()
    d = json.loads(cv.parsed_json)
    parsed = ParsedCv(**{
        k: d[k]
        for k in (
            "name", "email", "phone", "location", "links", "summary",
            "experience", "education", "skills", "certifications",
            "projects", "languages",
        )
    })
    from ..video import _years

    corpus_parts = [parsed.summary, " ".join(parsed.skills)]
    for e in parsed.experience:
        corpus_parts.append(" ".join([e.get("title", ""), e.get("company", "")] + e.get("bullets", [])))
    return list(parsed.skills), _years(parsed), " \n ".join(p.lower() for p in corpus_parts if p)


def compute_match(db: Session, profile: Profile, job: JobPosting) -> dict:
    skills, years, corpus = profile_match_inputs(db, profile)
    return match_job(
        {
            "title": job.title,
            "description": job.description,
            "posted_at": job.posted_at,
        }
        | {"open_to_sa": job.open_to_sa, "remote_type": job.remote_type},
        skills,
        years,
        corpus,
    )

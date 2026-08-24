"""Shared application-package creation.

One place where a job becomes a reviewable package: best-version
selection, tailored CV, and cover letter. Used by the auto-pipeline and
the Job Finder hand-off so behaviour is identical.
"""
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import builders
from ...content import CvContent
from ...models import (
    Application,
    CoverLetter,
    CvRecord,
    CvVersion,
    JobDescription,
    Profile,
    TailoredCv,
)
from ...parsing import ParsedCv, parse_cv_text
from ...writing import build_cover_letter


def parsed_from_cv(cv: CvRecord, db: Session) -> ParsedCv:
    if not cv.parsed_json:
        cv.parsed_json = json.dumps(parse_cv_text(cv.text).to_dict())
        db.commit()
    d = json.loads(cv.parsed_json)
    return ParsedCv(**{
        k: d[k]
        for k in (
            "name", "email", "phone", "location", "links", "summary",
            "experience", "education", "skills", "certifications",
            "projects", "languages",
        )
    })


def tailor_version_for_jd(db: Session, version: CvVersion, jd: JobDescription) -> TailoredCv:
    """Tailor a CV version to a job; returns the stored tailored row."""
    cv = db.get(CvRecord, version.base_cv_id)
    if cv is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "BASE_CV_MISSING", "message": "The base CV for this version is gone."},
        )
    parsed = parsed_from_cv(cv, db)
    content = CvContent.from_dict(json.loads(version.content_json))
    tailored_content, report = builders.tailor(
        content, parsed, jd.title, jd.text, jd.id
    )
    row = TailoredCv(
        id=str(uuid.uuid4()),
        profile_id=version.profile_id,
        version_id=version.id,
        jd_id=jd.id,
        title=f"{jd.title} @ {jd.company}" if jd.company else f"Tailored — {jd.title}",
        content_json=json.dumps(tailored_content.to_dict()),
        report_json=json.dumps(report),
    )
    db.add(row)
    db.flush()
    return row


def ensure_versions(db: Session, profile: Profile, role_hint: str | None) -> list[CvVersion]:
    versions = db.scalars(
        select(CvVersion).where(CvVersion.profile_id == profile.id)
    ).all()
    if versions:
        return versions
    cvs = db.scalars(select(CvRecord).where(CvRecord.profile_id == profile.id)).all()
    if not cvs:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NO_CV",
                "message": "Upload a CV first - versions are built from it.",
            },
        )
    from .documents import _build_version

    base = cvs[-1]
    for kind, focus in (
        (builders.KIND_ATS, None),
        (builders.KIND_MODERN, None),
        (builders.KIND_ROLE, role_hint),
    ):
        _build_version(db, base, kind, focus, [], [])
    return list(
        db.scalars(select(CvVersion).where(CvVersion.profile_id == profile.id)).all()
    )


def select_best_version(versions: list[CvVersion], jd: JobDescription) -> CvVersion:
    keywords = builders.extract_jd_keywords(jd.text)
    best, best_score = versions[0], -1
    for v in versions:
        content = CvContent.from_dict(json.loads(v.content_json))
        corpus = content.all_text()
        score = sum(1 for k in keywords if k in corpus)
        if score > best_score:
            best, best_score = v, score
    return best


def create_application_package(db: Session, profile: Profile, jd: JobDescription) -> str:
    """Full package: application record + tailored CV + cover letter."""
    versions = ensure_versions(db, profile, jd.title)
    version = select_best_version(versions, jd)

    app = Application(
        id=str(uuid.uuid4()),
        profile_id=profile.id,
        jd_id=jd.id,
        cv_version_id=version.id,
    )
    db.add(app)
    db.flush()

    tailored = tailor_version_for_jd(db, version, jd)
    app.tailored_cv_id = tailored.id

    cv = db.get(CvRecord, version.base_cv_id)
    parsed = parsed_from_cv(cv, db)
    text, issues = build_cover_letter(parsed, jd.title, jd.company, jd.text, "direct")
    letter = CoverLetter(
        id=str(uuid.uuid4()),
        application_id=app.id,
        profile_id=profile.id,
        text=text,
        tone="direct",
        quality_issues=json.dumps(issues),
    )
    db.add(letter)
    db.commit()
    return app.id

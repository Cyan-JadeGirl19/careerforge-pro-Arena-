"""CV documents: upload/parse, master & custom versions, tailoring, export."""
import json
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import builders, export
from ...content import CvContent
from ...consents import require_consent
from ...db import get_db
from ...models import CvRecord, CvVersion, JobDescription, Profile, TailoredCv
from ...parsing import extract_file_text, parse_cv_text
from ...schemas import (
    BuildMastersRequest,
    CvVersionCreate,
    CvVersionOut,
    JobDescriptionCreate,
    JobDescriptionOut,
    ParsedCvOut,
    TailorRequest,
    TailoredCvOut,
)
from .cvs import get_cv_or_404
from .profiles import get_profile_or_404

router = APIRouter(tags=["documents"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


# --- parsing -----------------------------------------------------------------


def _parsed_or_compute(cv: CvRecord, db: Session) -> dict:
    if cv.parsed_json:
        return json.loads(cv.parsed_json)
    parsed = parse_cv_text(cv.text)
    cv.parsed_json = json.dumps(parsed.to_dict())
    db.commit()
    return parsed.to_dict()


@router.get("/cvs/{cv_id}/parsed", response_model=ParsedCvOut)
def get_parsed(cv_id: str, db: Session = Depends(get_db)) -> dict:
    cv = get_cv_or_404(db, cv_id)
    return _parsed_or_compute(cv, db)


# --- version building ----------------------------------------------------------


def _version_out(v: CvVersion) -> CvVersionOut:
    return CvVersionOut(
        id=v.id,
        profile_id=v.profile_id,
        base_cv_id=v.base_cv_id,
        kind=v.kind,
        title=v.title,
        role_focus=v.role_focus,
        content=json.loads(v.content_json),
        created_at=v.created_at,
    )


def _build_version(
    db: Session,
    cv: CvRecord,
    kind: str,
    role_focus: str | None,
    emphasize: list[str],
    exclude: list[str],
) -> CvVersion:
    parsed_dict = _parsed_or_compute(cv, db)
    from ...parsing import ParsedCv

    parsed = ParsedCv(**{
        k: parsed_dict[k]
        for k in (
            "name", "email", "phone", "location", "links", "summary",
            "experience", "education", "skills", "certifications",
            "projects", "languages",
        )
    })
    if kind in (builders.KIND_ROLE, builders.KIND_CUSTOM) and not role_focus:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "ROLE_FOCUS_REQUIRED",
                "message": "role_focus is required for role-specialist and custom versions.",
            },
        )
    if kind == builders.KIND_ATS:
        content = builders.build_master_ats(parsed)
        title = "ATS Enterprise"
    elif kind == builders.KIND_MODERN:
        content = builders.build_master_modern(parsed)
        title = "Modern Professional"
    elif kind == builders.KIND_ROLE:
        content = builders.build_master_role(parsed, role_focus)
        title = f"Master CV — {role_focus}"
    else:
        content = builders.build_custom(parsed, role_focus, emphasize, exclude)
        title = f"Custom — {role_focus}"

    content.source_profile_version = cv.id
    content.generation_timestamp = datetime.now(timezone.utc).isoformat()

    version = CvVersion(
        id=str(uuid.uuid4()),
        profile_id=cv.profile_id,
        base_cv_id=cv.id,
        kind=kind,
        title=title,
        role_focus=role_focus,
        content_json=json.dumps(content.to_dict()),
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


@router.post(
    "/cvs/{cv_id}/versions", response_model=CvVersionOut, status_code=201
)
def create_version(
    cv_id: str, payload: CvVersionCreate, db: Session = Depends(get_db)
) -> CvVersionOut:
    cv = get_cv_or_404(db, cv_id)
    require_consent(db, cv.profile_id, "profile_processing")
    return _version_out(_build_version(db, cv, payload.kind, payload.role_focus, payload.emphasize, payload.exclude))


@router.post(
    "/cvs/{cv_id}/versions/build-masters",
    response_model=list[CvVersionOut],
    status_code=201,
)
def build_masters(
    cv_id: str, payload: BuildMastersRequest, db: Session = Depends(get_db)
) -> list[CvVersionOut]:
    """One action builds a master CV per best-fit role (up to three).

    The roles come from the candidate's own profile (skill overlap with
    role keyword sets, see app/roles.py) - not from formatting styles.
    Every master is single-column and parser-safe; `role_focus` pins the
    first master to a chosen role.
    """
    cv = get_cv_or_404(db, cv_id)
    require_consent(db, cv.profile_id, "profile_processing")
    versions = build_all_masters(db, cv, pin_role=payload.role_focus)
    return [_version_out(v) for v in versions]


def build_all_masters(
    db: Session, cv: CvRecord, pin_role: str | None = None
) -> list[CvVersion]:
    """Build one role-focused master per top role from the CV's own data.

    Shared by the build-masters route and the autonomous application
    flow (studio), so both always build the same role-based set.
    """
    parsed_dict = _parsed_or_compute(cv, db)
    from ...parsing import ParsedCv

    parsed = ParsedCv(**{
        k: parsed_dict[k]
        for k in (
            "name", "email", "phone", "location", "links", "summary",
            "experience", "education", "skills", "certifications",
            "projects", "languages",
        )
    })
    roles = builders.top_roles_for_cv(parsed)
    if pin_role:
        roles = [pin_role] + [r for r in roles if r.lower() != pin_role.lower()]
        roles = roles[:3]
    out = []
    for role in roles:
        out.append(_build_version(db, cv, builders.KIND_ROLE, role, [], []))
    return out


def _guess_role_focus(cv: CvRecord, db: Session) -> str:
    """Best-effort target role from the parsed CV (candidate can override)."""
    parsed = _parsed_or_compute(cv, db)
    for entry in parsed["experience"]:
        if entry.get("title"):
            return entry["title"]
    return "Remote Professional"


@router.get("/cvs/{cv_id}/versions", response_model=list[CvVersionOut])
def list_versions(cv_id: str, db: Session = Depends(get_db)) -> list[CvVersionOut]:
    cv = get_cv_or_404(db, cv_id)
    rows = db.scalars(
        select(CvVersion).where(CvVersion.base_cv_id == cv.id)
    ).all()
    return [_version_out(v) for v in rows]


def get_version_or_404(db: Session, version_id: str) -> CvVersion:
    v = db.get(CvVersion, version_id)
    if v is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "CV_VERSION_NOT_FOUND", "message": "No CV version with that id."},
        )
    return v


@router.get("/cv-versions/{version_id}", response_model=CvVersionOut)
def get_version(version_id: str, db: Session = Depends(get_db)) -> CvVersionOut:
    return _version_out(get_version_or_404(db, version_id))


# --- job descriptions & tailoring ---------------------------------------------


@router.post(
    "/profiles/{profile_id}/job-descriptions",
    response_model=JobDescriptionOut,
    status_code=201,
)
def create_jd(
    profile_id: str, payload: JobDescriptionCreate, db: Session = Depends(get_db)
) -> JobDescription:
    get_profile_or_404(db, profile_id)
    require_consent(db, profile_id, "job_matching")
    jd = JobDescription(
        id=str(uuid.uuid4()),
        profile_id=profile_id,
        title=payload.title,
        company=payload.company,
        source_url=payload.source_url,
        text=payload.text,
    )
    db.add(jd)
    db.commit()
    db.refresh(jd)
    return jd


def get_jd_or_404(db: Session, jd_id: str) -> JobDescription:
    jd = db.get(JobDescription, jd_id)
    if jd is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "JD_NOT_FOUND", "message": "No job description with that id."},
        )
    return jd


@router.post(
    "/cv-versions/{version_id}/tailor", response_model=TailoredCvOut, status_code=201
)
def tailor_version(
    version_id: str, payload: TailorRequest, db: Session = Depends(get_db)
) -> TailoredCvOut:
    """Create a job-specific version of a CV version. Consent: job_matching."""
    version = get_version_or_404(db, version_id)
    jd = get_jd_or_404(db, payload.jd_id)
    require_consent(db, version.profile_id, "profile_processing")
    require_consent(db, version.profile_id, "job_matching")

    cv = get_cv_or_404(db, version.base_cv_id)
    parsed_dict = _parsed_or_compute(cv, db)
    from ...parsing import ParsedCv

    parsed = ParsedCv(**{
        k: parsed_dict[k]
        for k in (
            "name", "email", "phone", "location", "links", "summary",
            "experience", "education", "skills", "certifications",
            "projects", "languages",
        )
    })
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
    db.commit()
    db.refresh(row)
    return _tailored_out(row)


def _tailored_out(row: TailoredCv) -> TailoredCvOut:
    return TailoredCvOut(
        id=row.id,
        profile_id=row.profile_id,
        version_id=row.version_id,
        jd_id=row.jd_id,
        title=row.title,
        content=json.loads(row.content_json),
        report=json.loads(row.report_json),
        created_at=row.created_at,
    )


def get_tailored_or_404(db: Session, tailored_id: str) -> TailoredCv:
    row = db.get(TailoredCv, tailored_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "TAILORED_CV_NOT_FOUND", "message": "No tailored CV with that id."},
        )
    return row


@router.get("/tailored/{tailored_id}", response_model=TailoredCvOut)
def get_tailored(tailored_id: str, db: Session = Depends(get_db)) -> TailoredCvOut:
    return _tailored_out(get_tailored_or_404(db, tailored_id))


# --- upload & export -----------------------------------------------------------


@router.post(
    "/profiles/{profile_id}/cvs/upload",
    status_code=201,
    response_model=dict,
)
async def upload_cv(
    profile_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """Upload a PDF/DOCX/TXT CV; it is parsed immediately."""
    get_profile_or_404(db, profile_id)
    require_consent(db, profile_id, "profile_processing")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"code": "UPLOAD_TOO_LARGE", "message": "File exceeds 10 MB."},
        )
    try:
        text = extract_file_text(file.filename or "cv.txt", data)
    except ValueError as exc:
        raise HTTPException(
            status_code=415,
            detail={"code": "UNSUPPORTED_FILE", "message": str(exc)},
        )
    except Exception:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PARSE_FAILED",
                "message": "We could not read that file. Try exporting it as PDF/DOCX/text and upload again.",
            },
        )
    if len(text.strip()) < 40:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CV_EMPTY",
                "message": "No usable text found in the file. Try a text-based PDF or paste your CV instead.",
            },
        )
    previous = db.scalars(
        select(CvRecord).where(CvRecord.profile_id == profile_id)
    ).all()
    parsed = parse_cv_text(text)
    cv = CvRecord(
        id=str(uuid.uuid4()),
        profile_id=profile_id,
        version=len(previous) + 1,
        title="Uploaded CV",
        text=text,
        source_type="upload",
        parsed_json=json.dumps(parsed.to_dict()),
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    return {
        "id": cv.id,
        "profile_id": cv.profile_id,
        "version": cv.version,
        "title": cv.title,
        "text": cv.text,
        "source_type": cv.source_type,
        "created_at": cv.created_at,
        "parsed": parsed.to_dict(),
    }


def _slug(text: str, max_len: int = 60) -> str:
    """ASCII-safe filename slug (HTTP headers must be latin-1)."""
    s = re.sub(r"[^a-z0-9._-]+", "-", text.lower()).strip("-")
    return s[:max_len] or "document"


def _export_response(content: CvContent, filename: str, fmt: str) -> Response:
    data = export.EXPORTERS[fmt](content)
    return Response(
        content=data,
        media_type=export.MEDIA_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/cv-versions/{version_id}/export",
    response_class=Response,
)
def export_version(
    version_id: str,
    format: str = Query(default="docx", pattern="^(docx|pdf|txt|json)$"),
    db: Session = Depends(get_db),
) -> Response:
    v = get_version_or_404(db, version_id)
    content = CvContent.from_dict(json.loads(v.content_json))
    ext = "txt" if format == "txt" else format
    return _export_response(content, f"{_slug(v.title)}.{ext}", format)


@router.get("/tailored/{tailored_id}/export", response_class=Response)
def export_tailored(
    tailored_id: str,
    format: str = Query(default="docx", pattern="^(docx|pdf|txt|json)$"),
    db: Session = Depends(get_db),
) -> Response:
    row = get_tailored_or_404(db, tailored_id)
    content = CvContent.from_dict(json.loads(row.content_json))
    ext = "txt" if format == "txt" else format
    return _export_response(content, f"{_slug(row.title)}.{ext}", format)


@router.get("/cvs/{cv_id}/export", response_class=Response)
def export_cv(
    cv_id: str,
    format: str = Query(default="txt", pattern="^(docx|pdf|txt|json)$"),
    db: Session = Depends(get_db),
) -> Response:
    """Export the raw uploaded CV as plain text or JSON (source of truth)."""
    cv = get_cv_or_404(db, cv_id)
    parsed = _parsed_or_compute(cv, db)
    if format in ("txt", "json"):
        return Response(
            content=cv.text.encode("utf-8") if format == "txt" else json.dumps(parsed, indent=2).encode("utf-8"),
            media_type=export.MEDIA_TYPES[format],
            headers={"Content-Disposition": f'attachment; filename="cv-{cv.version}.{format}"'},
        )
    content = CvContent.from_dict(
        {
            "name": parsed["name"],
            "email": parsed["email"],
            "phone": parsed["phone"],
            "location": parsed["location"],
            "links": parsed["links"],
            "summary": parsed["summary"],
            "skills": parsed["skills"],
            "experience": [
                {"title": e["title"], "company": e["company"], "dates": e["dates"], "bullets": e["bullets"]}
                for e in parsed["experience"]
            ],
            "education": [
                {"degree": e["degree"], "institution": e["institution"], "year": e["year"]}
                for e in parsed["education"]
            ],
            "certifications": parsed["certifications"],
            "projects": parsed["projects"],
            "languages": parsed["languages"],
            "layout": "ats_single_column",
        }
    )
    return _export_response(content, f"cv-{cv.version}-{format}", format)

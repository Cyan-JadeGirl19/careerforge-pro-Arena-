"""The autonomous studio: roles, applications, letters, video responses.

This is where "upload your CV and the program does the rest" lives:
``auto-pipeline`` turns a CV + job descriptions into a complete,
reviewable application package in one call.
"""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import builders, roles, video, writing
from ...content import CvContent
from ...consents import get_active_consent, require_consent
from ...db import get_db
from ...models import (
    Application,
    CoverLetter,
    CvRecord,
    CvVersion,
    JobDescription,
    Profile,
    TailoredCv,
    VideoResponse,
)
from ...parsing import ParsedCv
from ...schemas import (
    ApplicationCreate,
    ApplicationOut,
    ApplicationStatusUpdate,
    AutoPipelineOut,
    AutoPipelineRequest,
    CoverLetterCreate,
    CoverLetterOut,
    RoleRecommendationOut,
    VideoCreate,
    VideoMediaUpdate,
    VideoOut,
)
from . import applications_internal
from .documents import get_cv_or_404, get_jd_or_404, get_version_or_404
from .profiles import get_profile_or_404

router = APIRouter(tags=["studio"])

VALID_STATUSES = (
    "saved", "ready", "applied", "phone_screen",
    "interview", "offer", "rejected", "archived",
)


def _parsed_from_cv(cv: CvRecord, db: Session) -> ParsedCv:
    if not cv.parsed_json:
        from ...parsing import parse_cv_text

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


# --- roles -------------------------------------------------------------------


@router.post(
    "/profiles/{profile_id}/roles/recommend",
    response_model=list[RoleRecommendationOut],
)
def recommend_roles(profile_id: str, db: Session = Depends(get_db)) -> list[dict]:
    profile = get_profile_or_404(db, profile_id)
    require_consent(db, profile.id, "job_matching")
    cvs = db.scalars(
        select(CvRecord).where(CvRecord.profile_id == profile.id)
    ).all()
    if not cvs:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NO_CV",
                "message": "Upload a CV first - role recommendations come from your real experience.",
            },
        )
    return roles.recommend_roles(_parsed_from_cv(cvs[-1], db))


# --- applications --------------------------------------------------------------


def _select_best_version(db: Session, profile: Profile, jd: JobDescription) -> CvVersion:
    """Pick the best-fitting CV version for this job.

    Autonomous behaviour: if no versions exist yet, build the three
    masters now (role-focused on this job's title), then pick the best.
    """
    versions = db.scalars(
        select(CvVersion).where(CvVersion.profile_id == profile.id)
    ).all()
    if not versions:
        cvs = db.scalars(
            select(CvRecord).where(CvRecord.profile_id == profile.id)
        ).all()
        if not cvs:
            raise HTTPException(
                status_code=409,
                detail={"code": "NO_CV", "message": "Upload a CV first - versions are built from it."},
            )
        from .documents import _build_version

        base_cv = cvs[-1]
        for kind, focus in (
            (builders.KIND_ATS, None),
            (builders.KIND_MODERN, None),
            (builders.KIND_ROLE, jd.title),
        ):
            _build_version(db, base_cv, kind, focus, [], [])
        versions = db.scalars(
            select(CvVersion).where(CvVersion.profile_id == profile.id)
        ).all()
    keywords = builders.extract_jd_keywords(jd.text)
    best, best_score = versions[0], -1
    for v in versions:
        content = CvContent.from_dict(json.loads(v.content_json))
        corpus = content.all_text()
        score = sum(1 for k in keywords if k in corpus)
        if score > best_score:
            best, best_score = v, score
    return best


def _video_out(v: VideoResponse) -> VideoOut:
    return VideoOut(
        id=v.id,
        application_id=v.application_id,
        question=v.question,
        key_points=v.key_points,
        exclusions=v.exclusions,
        tone=v.tone,
        target_seconds=v.target_seconds,
        mode=v.mode,
        script_text=v.script_text,
        script_version=v.script_version,
        media_status=v.media_status,
        ai_disclosed=v.ai_disclosed,
        delete_media_after_export=v.delete_media_after_export,
        created_at=v.created_at,
        updated_at=v.updated_at,
    )


def _letter_out(l: CoverLetter) -> CoverLetterOut:
    return CoverLetterOut(
        id=l.id,
        application_id=l.application_id,
        text=l.text,
        tone=l.tone,
        quality_issues=json.loads(l.quality_issues or "[]"),
        created_at=l.created_at,
    )


def _app_out(db: Session, a: Application) -> "ApplicationOut":
    return applications_internal.app_out(db, a)


def get_application_or_404(db: Session, app_id: str) -> Application:
    a = db.get(Application, app_id)
    if a is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "APPLICATION_NOT_FOUND", "message": "No application with that id."},
        )
    return a


def _ensure_tailored(db: Session, app: Application) -> None:
    """Create the tailored CV for this application if not already done."""
    if app.tailored_cv_id:
        return
    profile = db.get(Profile, app.profile_id)
    if not app.cv_version_id:
        versions = applications_internal.ensure_versions(db, profile, app.jd.title)
        app.cv_version_id = applications_internal.select_best_version(versions, app.jd).id
        db.commit()
    version = get_version_or_404(db, app.cv_version_id)
    row = applications_internal.tailor_version_for_jd(db, version, app.jd)
    app.tailored_cv_id = row.id
    db.commit()


@router.post("/profiles/{profile_id}/applications", response_model=ApplicationOut, status_code=201)
def create_application(
    profile_id: str, payload: ApplicationCreate, db: Session = Depends(get_db)
) -> ApplicationOut:
    profile = get_profile_or_404(db, profile_id)
    require_consent(db, profile.id, "profile_processing")
    require_consent(db, profile.id, "job_matching")
    jd = get_jd_or_404(db, payload.jd_id)
    version_id = payload.cv_version_id
    if version_id:
        version = get_version_or_404(db, version_id)
        if version.profile_id != profile.id:
            raise HTTPException(status_code=409, detail={"code": "OWNERSHIP_MISMATCH", "message": "CV version belongs to a different profile."})
    else:
        version_id = _select_best_version(db, profile, jd).id
    app = Application(
        id=str(uuid.uuid4()),
        profile_id=profile.id,
        jd_id=jd.id,
        cv_version_id=version_id,
        notes=payload.notes,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return _app_out(db, app)


@router.get("/profiles/{profile_id}/applications", response_model=list[ApplicationOut])
def list_applications(profile_id: str, db: Session = Depends(get_db)) -> list[ApplicationOut]:
    get_profile_or_404(db, profile_id)
    rows = db.scalars(
        select(Application).where(Application.profile_id == profile_id).order_by(Application.created_at.desc())
    ).all()
    return [_app_out(db, a) for a in rows]


@router.get("/applications/{app_id}", response_model=ApplicationOut)
def get_application(app_id: str, db: Session = Depends(get_db)) -> ApplicationOut:
    return _app_out(db, get_application_or_404(db, app_id))


@router.post("/applications/{app_id}/status", response_model=ApplicationOut)
def update_status(
    app_id: str, payload: ApplicationStatusUpdate, db: Session = Depends(get_db)
) -> ApplicationOut:
    app = get_application_or_404(db, app_id)
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail={"code": "BAD_STATUS", "message": "Unknown status."})
    old_status = app.status
    app.status = payload.status
    if payload.notes is not None:
        app.notes = payload.notes
    db.commit()
    db.refresh(app)
    # The program does the rest: schedule the right follow-up automatically.
    from ...followups import maybe_schedule

    maybe_schedule(db, app, payload.status)
    db.refresh(app)
    return _app_out(db, app)


@router.post("/applications/{app_id}/tailor")
def tailor_application(app_id: str, db: Session = Depends(get_db)) -> dict:
    app = get_application_or_404(db, app_id)
    require_consent(db, app.profile_id, "profile_processing")
    require_consent(db, app.profile_id, "job_matching")
    _ensure_tailored(db, app)
    db.refresh(app)
    row = db.get(TailoredCv, app.tailored_cv_id)
    return {"tailored_cv_id": row.id, "report": json.loads(row.report_json)}


# --- cover letters ---------------------------------------------------------------


@router.post("/applications/{app_id}/cover-letter", response_model=CoverLetterOut, status_code=201)
def create_cover_letter(
    app_id: str,
    payload: CoverLetterCreate | None = None,
    db: Session = Depends(get_db),
) -> CoverLetterOut:
    tone = (payload.tone if payload else "direct")
    app = get_application_or_404(db, app_id)
    require_consent(db, app.profile_id, "job_matching")
    _ensure_tailored(db, app)  # guarantees a CV version is selected
    existing = db.scalars(
        select(CoverLetter).where(CoverLetter.application_id == app.id)
    ).first()
    if existing is not None:
        # Regenerate: replace the letter for this application.
        db.delete(existing)
        db.flush()
    version = get_version_or_404(db, app.cv_version_id)
    cv = get_cv_or_404(db, version.base_cv_id)
    parsed = _parsed_from_cv(cv, db)
    text, issues = writing.build_cover_letter(
        parsed, app.jd.title, app.jd.company, app.jd.text, tone
    )
    letter = CoverLetter(
        id=str(uuid.uuid4()),
        application_id=app.id,
        profile_id=app.profile_id,
        text=text,
        tone=tone,
        quality_issues=json.dumps(issues),
    )
    db.add(letter)
    db.commit()
    db.refresh(letter)
    return _letter_out(letter)


# --- voice / video responses -------------------------------------------------------


def _make_video(
    db: Session, app: Application, payload: VideoCreate, parsed: ParsedCv
) -> VideoResponse:
    require_consent(db, app.profile_id, "video_recording")
    if payload.mode == "ai_assisted":
        require_consent(db, app.profile_id, "media_use")
    try:
        script, report = video.generate_script(
            parsed,
            app.jd.title,
            app.jd.company,
            app.jd.text,
            payload.question,
            payload.target_seconds,
            payload.key_points,
            payload.exclusions,
            payload.tone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "BAD_VIDEO_REQUEST", "message": str(exc)})
    row = VideoResponse(
        id=str(uuid.uuid4()),
        application_id=app.id,
        profile_id=app.profile_id,
        question=payload.question,
        key_points="; ".join(payload.key_points) or None,
        exclusions="; ".join(payload.exclusions) or None,
        tone=payload.tone,
        target_seconds=payload.target_seconds,
        mode=payload.mode,
        script_text=script,
        script_version=1,
        media_status="none",
        ai_disclosed=payload.ai_disclosed,
        delete_media_after_export=payload.delete_media_after_export,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/applications/{app_id}/videos", response_model=VideoOut, status_code=201)
def create_video_response(
    app_id: str, payload: VideoCreate, db: Session = Depends(get_db)
) -> VideoOut:
    app = get_application_or_404(db, app_id)
    _ensure_tailored(db, app)
    version = get_version_or_404(db, app.cv_version_id)
    cv = get_cv_or_404(db, version.base_cv_id)
    parsed = _parsed_from_cv(cv, db)
    return _video_out(_make_video(db, app, payload, parsed))


def get_video_or_404(db: Session, video_id: str) -> VideoResponse:
    v = db.get(VideoResponse, video_id)
    if v is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "VIDEO_NOT_FOUND", "message": "No video response with that id."},
        )
    return v


@router.post("/videos/{video_id}/regenerate", response_model=VideoOut)
def regenerate_script(
    video_id: str, payload: VideoCreate, db: Session = Depends(get_db)
) -> VideoOut:
    """Re-run the script with new instructions; keeps version history."""
    old = get_video_or_404(db, video_id)
    app = get_application_or_404(db, old.application_id)
    _ensure_tailored(db, app)
    version = get_version_or_404(db, app.cv_version_id)
    cv = get_cv_or_404(db, version.base_cv_id)
    parsed = _parsed_from_cv(cv, db)
    require_consent(db, app.profile_id, "video_recording")
    if payload.mode == "ai_assisted":
        require_consent(db, app.profile_id, "media_use")
    try:
        script, _ = video.generate_script(
            parsed, app.jd.title, app.jd.company, app.jd.text,
            payload.question, payload.target_seconds,
            payload.key_points, payload.exclusions, payload.tone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "BAD_VIDEO_REQUEST", "message": str(exc)})
    old.script_text = script
    old.question = payload.question
    old.key_points = "; ".join(payload.key_points) or None
    old.exclusions = "; ".join(payload.exclusions) or None
    old.tone = payload.tone
    old.target_seconds = payload.target_seconds
    old.mode = payload.mode
    old.script_version += 1
    db.commit()
    db.refresh(old)
    return _video_out(old)


@router.post("/videos/{video_id}/media", response_model=VideoOut)
def update_video_media(
    video_id: str, payload: VideoMediaUpdate, db: Session = Depends(get_db)
) -> VideoOut:
    """Client reports the recording state after upload (media storage lands with the studio UI)."""
    v = get_video_or_404(db, video_id)
    require_consent(db, v.profile_id, "media_use")
    v.media_status = payload.media_status
    db.commit()
    db.refresh(v)
    return _video_out(v)


# --- auto pipeline ---------------------------------------------------------------


@router.post("/profiles/{profile_id}/auto-pipeline", response_model=AutoPipelineOut)
def auto_pipeline(
    profile_id: str, payload: AutoPipelineRequest, db: Session = Depends(get_db)
) -> AutoPipelineOut:
    """'Upload your CV and the program does the rest.'

    For each job: pick the best master, tailor a job-specific CV, draft a
    human-sounding cover letter, and prepare a video-response script
    (when video consent exists). Everything lands as reviewable
    applications - nothing is sent or submitted.
    """
    profile = get_profile_or_404(db, profile_id)
    require_consent(db, profile.id, "profile_processing")
    require_consent(db, profile.id, "job_matching")
    cv = get_cv_or_404(db, payload.cv_id)
    if cv.profile_id != profile.id:
        raise HTTPException(status_code=409, detail={"code": "OWNERSHIP_MISMATCH", "message": "CV belongs to a different profile."})
    parsed = _parsed_from_cv(cv, db)

    have_video_consent = bool(get_active_consent(db, profile.id, "video_recording"))

    apps_out: list[ApplicationOut] = []
    skipped: list[dict] = []
    for jd_id in payload.jd_ids:
        jd = get_jd_or_404(db, jd_id)
        try:
            app_id = applications_internal.create_application_package(db, profile, jd)
        except HTTPException as exc:
            skipped.append({"jd_id": jd_id, "reason": exc.detail})
            continue
        app = db.get(Application, app_id)

        if have_video_consent:
            try:
                _make_video(
                    db,
                    app,
                    VideoCreate(
                        question="Tell us a bit about yourself and why you are a good fit for this role.",
                        target_seconds=60,
                    ),
                    parsed,
                )
            except HTTPException as exc:
                skipped.append({"jd_id": jd_id, "reason": f"video: {exc.detail}"})
        db.commit()
        db.refresh(app)
        apps_out.append(_app_out(db, app))
    return AutoPipelineOut(applications=apps_out, skipped=skipped)

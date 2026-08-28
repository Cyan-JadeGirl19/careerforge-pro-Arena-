"""The autonomous studio: roles, applications, letters, video responses.

This is where "upload your CV and the program does the rest" lives:
``auto-pipeline`` turns a CV + job descriptions into a complete,
reviewable application package in one call.

Video media (upload / enhance / quality / captions / export) lives here
too. Processing is real file-level work (ffmpeg): nothing is faked, and
every artefact is stored against the video response for download.
"""
import json
import logging
import re
import uuid
from contextlib import nullcontext
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ... import builders, ffmpegx, media_jobs as jobs, quality, roles, uploads, video, writing
from ...captions import transcript_to_cues, cues_to_vtt
from ...content import CvContent
from ...consents import get_active_consent, require_consent
from ...db import SessionLocal, get_db
from ...models import (
    Application,
    CoverLetter,
    CvRecord,
    CvVersion,
    JobDescription,
    JobPosting,
    Profile,
    ReferenceDocument,
    TailoredCv,
    VideoMedia,
    VideoResponse,
)
from ...jobs import service as jobs_service, sources as jobs_sources
from ...parsing import ParsedCv
from ...schemas import (
    ApplicationCreate,
    ApplicationOut,
    ApplicationStatusUpdate,
    AutoPipelineOut,
    AutoPipelineRequest,
    CaptionsRequest,
    CoverLetterCreate,
    CoverLetterOut,
    IntroCardRequest,
    RoleRecommendationOut,
    TailoredCvOut,
    TailorFromUrlIn,
    TailorFromUrlOut,
    TrimRequest,
    UploadChunkOut,
    UploadInitIn,
    UploadInitOut,
    VideoAnalyzeOut,
    VideoCreate,
    VideoEnhanceRequest,
    VideoJobOut,
    VideoMediaOut,
    VideoMediaUpdate,
    VideoOut,
)

HEADSHOT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_HEADSHOT_BYTES = 5 * 1024 * 1024
from . import applications_internal
from .documents import _tailored_out, get_cv_or_404, get_jd_or_404, get_version_or_404
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
        from .documents import build_all_masters

        base_cv = cvs[-1]
        # Role-based masters, pinned to this job's title so the best-fit
        # master for it is built first.
        build_all_masters(db, base_cv, pin_role=jd.title)
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
        likeness_consent=bool(v.likeness_consent),
        media=[_media_out(m) for m in v.media],
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


# --- paste a job URL -> tailored CV (one step) ---------------------------------


@router.post(
    "/profiles/{profile_id}/tailor-from-url",
    response_model=TailorFromUrlOut,
    status_code=201,
)
def tailor_from_url(
    profile_id: str, payload: TailorFromUrlIn, db: Session = Depends(get_db)
) -> TailorFromUrlOut:
    """Fetch a public job posting from a pasted URL and immediately build
    the tailored CV for it.

    One user-directed fetch of a page the user provides (no scraping
    behind logins). The job is stored (deduped) so it also appears in
    the Job Finder, and the tailored CV is the same rewrite engine used
    everywhere: real facts + the job's own keywords, gaps flagged.
    """
    from datetime import datetime, timezone

    profile = get_profile_or_404(db, profile_id)
    require_consent(db, profile.id, "profile_processing")
    require_consent(db, profile.id, "job_matching")

    try:
        posting = jobs_sources.fetch_user_url(payload.url)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "BAD_URL", "message": str(exc)},
        )
    except Exception as exc:  # noqa: BLE001 - network/parse failures
        raise HTTPException(
            status_code=422,
            detail={
                "code": "URL_FAILED",
                "message": f"Could not read that page: {str(exc)[:120]}. "
                "You can paste the job text manually instead.",
            },
        )
    if len(posting["description"]) < 80:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "THIN_PAGE",
                "message": "That page didn't contain enough job description text "
                "to tailor against. Paste the job text manually.",
            },
        )

    # Store the job (deduped) so it also shows in the Job Finder.
    existing_job = db.scalar(
        select(JobPosting).where(JobPosting.dedupe_key == posting["dedupe_key"])
    )
    if existing_job is None:
        job = JobPosting(
            id=str(uuid.uuid4()),
            fetched_at=datetime.now(timezone.utc),
            **posting,
        )
        db.add(job)
    else:
        job = existing_job

    # Job description record (deduped by URL) for tailoring + applications.
    jd = db.scalar(
        select(JobDescription).where(
            JobDescription.profile_id == profile.id,
            JobDescription.source_url == job.url,
        )
    )
    if jd is None:
        jd = JobDescription(
            id=str(uuid.uuid4()),
            profile_id=profile.id,
            title=job.title,
            company=job.company,
            source_url=job.url,
            text=(job.description or "")[:100000]
            or f"{job.title} at {job.company or 'unknown company'}",
        )
        db.add(jd)
    db.flush()

    # Pick the version to tailor: the one chosen, else the best fit.
    versions = db.scalars(
        select(CvVersion).where(CvVersion.profile_id == profile.id)
    ).all()
    if not versions:
        versions = applications_internal.ensure_versions(db, profile, job.title)
    if payload.version_id:
        version = get_version_or_404(db, payload.version_id)
        if version.profile_id != profile.id:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OWNERSHIP_MISMATCH",
                    "message": "That CV version belongs to a different profile.",
                },
            )
    else:
        version = applications_internal.select_best_version(versions, jd)

    row = applications_internal.tailor_version_for_jd(db, version, jd)
    db.commit()
    db.refresh(row)
    db.refresh(job)
    return TailorFromUrlOut(
        job=jobs_service.job_to_dict(job),
        jd_id=jd.id,
        version_id=version.id,
        version_title=version.title,
        tailored=_tailored_out(row),
    )
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


# --- video media: upload, enhance, quality, captions, exports ------------------


def _media_out(m: VideoMedia) -> VideoMediaOut:
    duration: float | None = None
    if m.probe_json:
        try:
            duration = json.loads(m.probe_json).get("duration")
        except json.JSONDecodeError:
            duration = None
    return VideoMediaOut(
        id=m.id,
        kind=m.kind,
        filename=m.filename,
        content_type=m.content_type,
        size=m.size,
        duration=duration,
        created_at=m.created_at,
    )


def get_media_or_404(db: Session, video: VideoResponse, media_id: str) -> VideoMedia:
    m = db.get(VideoMedia, media_id)
    if m is None or m.video_response_id != video.id:
        raise HTTPException(
            status_code=404,
            detail={"code": "MEDIA_NOT_FOUND", "message": "No media with that id."},
        )
    return m


def _suffix_for(m: VideoMedia) -> str:
    if m.kind == "captions":
        return ".vtt"
    if m.kind == "audio":
        return ".mp3"
    ct = m.content_type or ""
    if "webm" in ct:
        return ".webm"
    if "quicktime" in ct:
        return ".mov"
    return ".mp4"


def _safe_filename(name: str) -> str:
    return re.sub(r"[^\w.\- ]", "_", name)[:200] or "file"


def _run_quality(m: VideoMedia, target_seconds: int | None = None) -> dict:
    with ffmpegx.temp_media(m.data, suffix=_suffix_for(m)) as path:
        probe = ffmpegx.probe_path(path)
        if probe.audio_codec:
            audio = ffmpegx.analyze_audio(path)
            silences = ffmpegx.detect_silences(path)
        else:
            audio = {"mean_volume": None, "max_volume": None}
            silences = []
        lighting = ffmpegx.measure_lighting(path)
    return quality.build_report(probe, audio, silences, lighting, target_seconds)


@router.post("/videos/{video_id}/media-upload", response_model=VideoOut, status_code=201)
def upload_video_media(
    video_id: str,
    file: UploadFile = File(...),
    likeness_consent: bool = Form(False),
    db: Session = Depends(get_db),
) -> VideoOut:
    """Store a recording/upload against the video response (private).

    Requires the purpose-scoped ``media_use`` consent AND an explicit
    likeness confirmation for this upload (face/voice are yours or you
    have permission).
    """
    v = get_video_or_404(db, video_id)
    require_consent(db, v.profile_id, "media_use")
    if not likeness_consent:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "LIKENESS_CONSENT_REQUIRED",
                "message": "Confirm the face and voice in this video are yours "
                "(or you have permission to use them) before uploading.",
            },
        )
    ct = (file.content_type or "").lower()
    if ct not in ffmpegx.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail={
                "code": "UNSUPPORTED_MEDIA_TYPE",
                "message": f"Unsupported file type '{ct}'. Upload MP4, WebM, MOV or M4V.",
            },
        )
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > ffmpegx.MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"code": "MEDIA_TOO_LARGE", "message": "File exceeds the 150 MB limit."},
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if len(data) < 1024:
        raise HTTPException(
            status_code=422,
            detail={"code": "EMPTY_MEDIA", "message": "That file is too small to be a video."},
        )
    try:
        probe = ffmpegx.probe_media(data, suffix=_suffix_for_probe(ct))
    except RuntimeError:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "UNREADABLE_MEDIA",
                "message": "That file could not be read as a video. Try re-exporting it as MP4.",
            },
        )
    if not probe.duration or probe.duration < 2 or not probe.video_codec:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "UNREADABLE_MEDIA",
                "message": "No usable video stream found in that file.",
            },
        )
    m = VideoMedia(
        id=str(uuid.uuid4()),
        video_response_id=v.id,
        kind="original",
        filename=(file.filename or "recording")[:300],
        content_type=ct,
        size=size,
        data=data,
        probe_json=json.dumps(probe.to_dict()),
    )
    db.add(m)
    v.media_status = "uploaded"
    v.likeness_consent = True
    db.commit()
    db.refresh(v)
    return _video_out(v)


def _suffix_for_probe(ct: str) -> str:
    if "webm" in ct:
        return ".webm"
    if "quicktime" in ct:
        return ".mov"
    return ".mp4"


# --- chunked upload (free-tier friendly) ---------------------------------------
#
# Render's free tier kills a single HTTP request that runs ~100 s, so a
# 2-3 minute video on a slow uplink dies mid-request ("Upload failed
# (500)"). The client instead splits the file into ~5 MB chunks; each
# request is small and fast, bytes stream to a temp file (no giant
# in-memory buffer), and "complete" probes + stores the finished file.


@router.post(
    "/videos/{video_id}/upload-init",
    response_model=UploadInitOut,
    status_code=201,
)
def upload_init(
    video_id: str, payload: UploadInitIn, db: Session = Depends(get_db)
) -> UploadInitOut:
    v = get_video_or_404(db, video_id)
    require_consent(db, v.profile_id, "media_use")
    if not payload.likeness_consent:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "LIKENESS_CONSENT_REQUIRED",
                "message": "Confirm the face and voice in this video are yours "
                "(or you have permission to use them) before uploading.",
            },
        )
    try:
        upload_id, _ = uploads.init_session(
            v.id, v.profile_id, payload.filename, payload.content_type, payload.size
        )
    except uploads.UploadError as e:
        raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message})
    return UploadInitOut(upload_id=upload_id, chunk_size=uploads.CHUNK_SIZE)


@router.post("/uploads/{upload_id}/chunk", response_model=UploadChunkOut)
async def upload_chunk(
    request: Request, upload_id: str, index: int = Query(..., ge=0)
) -> UploadChunkOut:
    body = await request.body()
    try:
        session = uploads.write_chunk(upload_id, index, body)
    except uploads.UploadError as e:
        raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message})
    return UploadChunkOut(
        received_bytes=session.received_bytes,
        complete=session.received_bytes == session.expected_size,
    )


@router.post(
    "/uploads/{upload_id}/complete", response_model=VideoJobOut, status_code=202
)
def upload_complete(upload_id: str, db: Session = Depends(get_db)) -> VideoJobOut:
    """Finish the chunked upload: validates, then stores the file in a
    background job (large files are compressed first - free-tier Postgres
    is 1 GB total, so a 2-3 minute recording is re-encoded to H.264 720p
    before it is stored). Poll /jobs/video/{job_id}."""
    try:
        session = uploads.complete_session(upload_id)
    except uploads.UploadError as e:
        raise HTTPException(status_code=e.status, detail={"code": e.code, "message": e.message})
    v = get_video_or_404(db, session.video_id)
    require_consent(db, v.profile_id, "media_use")
    job = jobs.submit("store-upload", _store_upload_worker, session.video_id, upload_id)
    return VideoJobOut(**job.to_out())


COMPRESS_THRESHOLD = 20 * 1024 * 1024  # files bigger than this get re-encoded
_upload_logger = logging.getLogger("careerforge.upload")


def _store_upload_worker(job: jobs.Job, video_id: str, upload_id: str) -> None:
    db = SessionLocal()
    try:
        job.phase = "checking video"
        job.progress = 0.1
        try:
            session = uploads.get_session(upload_id)
        except uploads.UploadError:
            raise RuntimeError("Upload session expired - please upload again.")
        src = Path(session.temp_path)
        probe_src = ffmpegx.probe_path(src)
        if not probe_src.duration or probe_src.duration < 2 or not probe_src.video_codec:
            raise RuntimeError(
                "That file could not be read as a video. Try re-exporting it as MP4."
            )

        stored_ct = session.content_type
        stored_name = (session.filename or "recording")[:300]
        compressed = False
        data = b""
        if probe_src.size > COMPRESS_THRESHOLD:
            job.phase = "compressing for the web"
            job.progress = 0.3
            vfilter = None
            if (probe_src.height or 0) > 720 or (probe_src.width or 0) > 1280:
                vfilter = (
                    "scale=1280:720:force_original_aspect_ratio=decrease,"
                    "pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
                )
            with ffmpegx.temp_out(".mp4") as dst:
                ffmpegx.reencode_mp4(
                    src, dst, vfilter=vfilter, has_audio=bool(probe_src.audio_codec)
                )
                data = dst.read_bytes()
            if len(data) >= probe_src.size:
                # Re-encoding didn't make it smaller (already compact) -
                # keep the original bytes instead of storing a bigger file.
                with open(src, "rb") as fh:
                    data = fh.read()
                probe = probe_src
            else:
                with ffmpegx.temp_media(data) as p2:
                    probe = ffmpegx.probe_path(p2)
                stem = re.sub(r"\.[a-z0-9]+$", "", session.filename or "") or "recording"
                stored_name = f"{stem}.mp4"[:300]
                stored_ct = "video/mp4"
                compressed = True
        else:
            with open(src, "rb") as fh:
                data = fh.read()
            probe = probe_src

        job.phase = "saving privately"
        job.progress = 0.8
        m = VideoMedia(
            id=str(uuid.uuid4()),
            video_response_id=video_id,
            kind="original",
            filename=stored_name,
            content_type=stored_ct,
            size=len(data),
            data=data,
            probe_json=json.dumps(probe.to_dict()),
        )
        db.add(m)
        v = db.get(VideoResponse, video_id)
        if v is None:
            raise RuntimeError("This video response no longer exists.")
        v.media_status = "uploaded"
        v.likeness_consent = True
        try:
            db.commit()
        except Exception:
            db.rollback()
            _upload_logger.exception(
                "storing uploaded media failed (video %s) - possible storage quota",
                video_id,
            )
            raise RuntimeError(
                "Server storage is full - delete some old media in the Video "
                "Studio, then try the upload again."
            )
        db.refresh(m)
        job.progress = 1.0
        job.result = {"media_id": m.id, "compressed": compressed}
    finally:
        try:
            uploads.discard(upload_id)
        except Exception:
            pass
        db.close()


# --- storage usage --------------------------------------------------------------


@router.get("/profiles/{profile_id}/storage")
def storage_usage(profile_id: str, db: Session = Depends(get_db)) -> dict:
    """How much of the (limited, free) storage media is using."""
    get_profile_or_404(db, profile_id)
    out = {
        "database_size": "n/a",
        "video_media_count": 0,
        "video_media_bytes": 0,
        "reference_document_bytes": 0,
    }
    if db.bind.dialect.name == "postgresql":
        out["database_size"] = (
            db.scalar(text("SELECT pg_size_pretty(pg_database_size(current_database()))"))
            or "n/a"
        )
        out["video_media_count"] = db.scalar(text("SELECT COUNT(*) FROM video_media")) or 0
        out["video_media_bytes"] = (
            db.scalar(text("SELECT COALESCE(SUM(size),0) FROM video_media")) or 0
        )
        out["reference_document_bytes"] = (
            db.scalar(text("SELECT COALESCE(SUM(size),0) FROM reference_documents")) or 0
        )
    else:
        rows = db.scalars(select(VideoMedia)).all()
        out["video_media_count"] = len(rows)
        out["video_media_bytes"] = sum(r.size for r in rows)
        docs = db.scalars(select(ReferenceDocument)).all()
        out["reference_document_bytes"] = sum(r.size for r in docs)
    return out


@router.post("/videos/{video_id}/media/{media_id}/analyze", response_model=VideoAnalyzeOut)
def analyze_video_media(
    video_id: str, media_id: str, db: Session = Depends(get_db)
) -> VideoAnalyzeOut:
    """Run transparent quality checks (length, resolution, audio,
    pauses, lighting) and store the report with the media."""
    v = get_video_or_404(db, video_id)
    m = get_media_or_404(db, v, media_id)
    if m.kind not in ffmpegx.VIDEO_KINDS:
        raise HTTPException(
            status_code=409,
            detail={"code": "NOT_A_VIDEO", "message": "Quality checks apply to video files."},
        )
    try:
        report = _run_quality(m, v.target_seconds)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "ANALYSIS_FAILED", "message": str(exc)[:300]},
        )
    m.quality_json = json.dumps(report)
    db.commit()
    return VideoAnalyzeOut(media_id=m.id, report=report)


@router.post(
    "/videos/{video_id}/media/{media_id}/enhance",
    response_model=VideoJobOut,
    status_code=202,
)
def enhance_video_media(
    video_id: str,
    media_id: str,
    payload: VideoEnhanceRequest,
    db: Session = Depends(get_db),
) -> VideoJobOut:
    """Process the file: colour/lighting, loudness, framing, optional
    caption burn-in -> new H.264 MP4 artefact. Runs as a background job
    (free-tier HTTP responses time out); poll /jobs/video/{job_id}."""
    v = get_video_or_404(db, video_id)
    m = get_media_or_404(db, v, media_id)
    if m.kind not in ffmpegx.VIDEO_KINDS:
        raise HTTPException(
            status_code=409,
            detail={"code": "NOT_A_VIDEO", "message": "Enhance applies to video files."},
        )
    if not v.likeness_consent:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "LIKENESS_CONSENT_REQUIRED",
                "message": "Confirm the face and voice are yours before processing.",
            },
        )
    if payload.burn_captions:
        cap = db.scalars(
            select(VideoMedia)
            .where(
                VideoMedia.video_response_id == v.id,
                VideoMedia.kind == "captions",
            )
            .order_by(VideoMedia.created_at.desc())
        ).first()
        if cap is None:
            raise HTTPException(
                status_code=409,
                detail={"code": "NO_CAPTIONS", "message": "Generate captions first."},
            )
    job = jobs.submit(
        "enhance", _enhance_worker, v.id, m.id, payload.model_dump()
    )
    return VideoJobOut(**job.to_out())


def _enhance_worker(job: jobs.Job, video_id: str, media_id: str, params: dict) -> None:
    db = SessionLocal()
    try:
        job.phase = "reading media"
        job.progress = 0.05
        v = db.get(VideoResponse, video_id)
        m = db.get(VideoMedia, media_id)
        if v is None or m is None:
            raise RuntimeError("Video or media no longer exists.")
        b, c, s = int(params.get("brightness", 0)), int(params.get("contrast", 0)), int(params.get("saturation", 0))
        if params.get("auto_enhance") and not (b or c or s):
            b, c, s = 2, 4, 6  # mild, safe defaults
        vfilter = ffmpegx.build_video_filters(
            brightness=b, contrast=c, saturation=s, framing=params.get("framing", "none")
        )
        afilter = ffmpegx.build_audio_filters(bool(params.get("normalize_audio")))

        cap: VideoMedia | None = None
        if params.get("burn_captions"):
            cap = db.scalars(
                select(VideoMedia)
                .where(VideoMedia.video_response_id == v.id, VideoMedia.kind == "captions")
                .order_by(VideoMedia.created_at.desc())
            ).first()
            if cap is None:
                raise RuntimeError("No captions found. Generate captions first.")

        job.phase = "encoding"
        job.progress = 0.4
        with ffmpegx.temp_media(m.data, suffix=_suffix_for(m)) as src:
            probe = ffmpegx.probe_path(src)
            vtt_cm = (
                ffmpegx.temp_media(cap.data, suffix=".vtt") if cap is not None
                else nullcontext(None)
            )
            with vtt_cm as vtt_path, ffmpegx.temp_out(".mp4") as dst:
                ffmpegx.reencode_mp4(
                    src,
                    dst,
                    vfilter=vfilter,
                    afilter=afilter,
                    burn_vtt=vtt_path if cap is not None else None,
                    has_audio=bool(probe.audio_codec),
                )
                out = dst.read_bytes()

        job.phase = "analysing result"
        job.progress = 0.85
        stem = re.sub(r"\.[a-z0-9]+$", "", m.filename) or "response"
        new_m = VideoMedia(
            id=str(uuid.uuid4()),
            video_response_id=v.id,
            kind="enhanced",
            filename=f"{stem}-enhanced.mp4",
            content_type="video/mp4",
            size=len(out),
            data=out,
        )
        db.add(new_m)
        db.flush()
        with ffmpegx.temp_media(out) as p2:
            probe2 = ffmpegx.probe_path(p2)
            if probe2.audio_codec:
                audio2 = ffmpegx.analyze_audio(p2)
                sil2 = ffmpegx.detect_silences(p2)
            else:
                audio2 = {"mean_volume": None, "max_volume": None}
                sil2 = []
            light2 = ffmpegx.measure_lighting(p2)
        report = quality.build_report(probe2, audio2, sil2, light2, v.target_seconds)
        new_m.probe_json = json.dumps(probe2.to_dict())
        new_m.quality_json = json.dumps(report)
        v.media_status = "ready"
        db.commit()
        db.refresh(new_m)
        job.progress = 1.0
        job.result = {"media_id": new_m.id, "report": report}
    finally:
        db.close()


@router.post(
    "/videos/{video_id}/media/{media_id}/export-mp4",
    response_model=VideoJobOut,
    status_code=202,
)
def export_mp4(
    video_id: str, media_id: str, db: Session = Depends(get_db)
) -> VideoJobOut:
    """Re-encode an uploaded file to H.264 MP4 with no other changes
    (many application portals reject WebM/MOV). Background job."""
    v = get_video_or_404(db, video_id)
    m = get_media_or_404(db, v, media_id)
    if m.kind == "enhanced" and m.content_type == "video/mp4":
        raise HTTPException(
            status_code=409,
            detail={"code": "ALREADY_MP4", "message": "That file is already MP4 - just download it."},
        )
    if m.kind not in ffmpegx.VIDEO_KINDS:
        raise HTTPException(
            status_code=409,
            detail={"code": "NOT_A_VIDEO", "message": "MP4 export applies to video files."},
        )
    job = jobs.submit("export-mp4", _export_mp4_worker, v.id, m.id)
    return VideoJobOut(**job.to_out())


def _export_mp4_worker(job: jobs.Job, video_id: str, media_id: str) -> None:
    db = SessionLocal()
    try:
        job.phase = "reading media"
        job.progress = 0.05
        v = db.get(VideoResponse, video_id)
        m = db.get(VideoMedia, media_id)
        if v is None or m is None:
            raise RuntimeError("Video or media no longer exists.")
        job.phase = "encoding"
        job.progress = 0.4
        with ffmpegx.temp_media(m.data, suffix=_suffix_for(m)) as src:
            probe = ffmpegx.probe_path(src)
            with ffmpegx.temp_out(".mp4") as dst:
                ffmpegx.reencode_mp4(
                    src, dst, has_audio=bool(probe.audio_codec)
                )
                out = dst.read_bytes()
        job.phase = "analysing result"
        job.progress = 0.85
        stem = re.sub(r"\.[a-z0-9]+$", "", m.filename) or "response"
        new_m = VideoMedia(
            id=str(uuid.uuid4()),
            video_response_id=v.id,
            kind="enhanced",
            filename=f"{stem}-mp4.mp4",
            content_type="video/mp4",
            size=len(out),
            data=out,
        )
        db.add(new_m)
        db.flush()
        with ffmpegx.temp_media(out) as p2:
            probe2 = ffmpegx.probe_path(p2)
            if probe2.audio_codec:
                audio2 = ffmpegx.analyze_audio(p2)
                sil2 = ffmpegx.detect_silences(p2)
            else:
                audio2 = {"mean_volume": None, "max_volume": None}
                sil2 = []
            light2 = ffmpegx.measure_lighting(p2)
        report = quality.build_report(probe2, audio2, sil2, light2, v.target_seconds)
        new_m.probe_json = json.dumps(probe2.to_dict())
        new_m.quality_json = json.dumps(report)
        db.commit()
        db.refresh(new_m)
        job.progress = 1.0
        job.result = {"media_id": new_m.id, "report": report}
    finally:
        db.close()


@router.post(
    "/videos/{video_id}/media/{media_id}/export-audio",
    response_model=VideoOut,
    status_code=201,
)
def export_audio(
    video_id: str, media_id: str, db: Session = Depends(get_db)
) -> VideoOut:
    """Extract the voice as an MP3 (fast enough to run inline)."""
    v = get_video_or_404(db, video_id)
    m = get_media_or_404(db, v, media_id)
    if m.kind not in ffmpegx.VIDEO_KINDS:
        raise HTTPException(
            status_code=409,
            detail={"code": "NOT_A_VIDEO", "message": "Audio export applies to video files."},
        )
    stem = re.sub(r"\.[a-z0-9]+$", "", m.filename) or "response"
    with ffmpegx.temp_media(m.data, suffix=_suffix_for(m)) as src:
        probe = ffmpegx.probe_path(src)
        if not probe.audio_codec:
            raise HTTPException(
                status_code=409,
                detail={"code": "NO_AUDIO", "message": "That file has no audio track."},
            )
        with ffmpegx.temp_out(".mp3") as dst:
            ffmpegx.extract_mp3(src, dst)
            out = dst.read_bytes()
    new_m = VideoMedia(
        id=str(uuid.uuid4()),
        video_response_id=v.id,
        kind="audio",
        filename=f"{stem}-audio.mp3",
        content_type="audio/mpeg",
        size=len(out),
        data=out,
    )
    db.add(new_m)
    db.commit()
    db.refresh(v)
    return _video_out(v)


@router.post("/videos/{video_id}/captions", response_model=VideoOut, status_code=201)
def generate_captions(
    video_id: str, payload: CaptionsRequest, db: Session = Depends(get_db)
) -> VideoOut:
    """Build a WebVTT caption file from the candidate's own text.

    Timing is proportional across the measured video duration - the UI
    says so explicitly and the candidate reviews cues before export.
    This is not speech recognition and never claims to be.
    """
    v = get_video_or_404(db, video_id)
    text = (payload.transcript or "").strip()
    if not text and payload.use_script:
        text = (v.script_text or "").strip()
    if not text:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "NO_TRANSCRIPT",
                "message": "Paste what you say in the video, or generate a script "
                "and tick 'use my script'.",
            },
        )
    m: VideoMedia | None = None
    if payload.media_id:
        m = get_media_or_404(db, v, payload.media_id)
        if m.kind not in ffmpegx.VIDEO_KINDS:
            raise HTTPException(
                status_code=409,
                detail={"code": "NOT_A_VIDEO", "message": "media_id must be a video file."},
            )
    else:
        m = db.scalars(
            select(VideoMedia)
            .where(
                VideoMedia.video_response_id == v.id,
                VideoMedia.kind.in_(list(ffmpegx.VIDEO_KINDS)),
            )
            .order_by(VideoMedia.created_at.desc())
        ).first()
    duration: float | None = None
    if m is not None and m.probe_json:
        try:
            duration = json.loads(m.probe_json).get("duration")
        except json.JSONDecodeError:
            duration = None
    estimated = duration is None
    if estimated:
        duration = float(v.target_seconds or 60)
    try:
        cues = transcript_to_cues(text, duration)
        vtt = cues_to_vtt(cues)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "BAD_TRANSCRIPT", "message": str(exc)})
    cap = VideoMedia(
        id=str(uuid.uuid4()),
        video_response_id=v.id,
        kind="captions",
        filename="captions.vtt",
        content_type="text/vtt",
        size=len(vtt.encode("utf-8")),
        data=vtt.encode("utf-8"),
        probe_json=json.dumps(
            {"duration": duration, "cues": len(cues), "estimated_timing": estimated}
        ),
    )
    db.add(cap)
    db.commit()
    db.refresh(v)
    return _video_out(v)


@router.get("/videos/{video_id}/media/{media_id}/download")
def download_video_media(
    video_id: str, media_id: str, db: Session = Depends(get_db)
) -> Response:
    v = get_video_or_404(db, video_id)
    m = get_media_or_404(db, v, media_id)
    return Response(
        content=m.data,
        media_type=m.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{_safe_filename(m.filename)}"'
        },
    )


@router.delete("/videos/{video_id}/media/{media_id}", status_code=204)
def delete_video_media(
    video_id: str, media_id: str, db: Session = Depends(get_db)
) -> None:
    v = get_video_or_404(db, video_id)
    m = get_media_or_404(db, v, media_id)
    db.delete(m)
    db.commit()


@router.get("/jobs/video/{job_id}", response_model=VideoJobOut)
def video_job_status(job_id: str) -> VideoJobOut:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": "Job not found (it may have expired)."},
        )
    return VideoJobOut(**job.to_out())


# --- trim, headshot, intro card ----------------------------------------------------


def _latest_video_media(db: Session, video_id: str) -> VideoMedia | None:
    return db.scalars(
        select(VideoMedia)
        .where(
            VideoMedia.video_response_id == video_id,
            VideoMedia.kind.in_(list(ffmpegx.VIDEO_KINDS)),
        )
        .order_by(VideoMedia.created_at.desc())
    ).first()


def _read_probe(m: VideoMedia) -> dict:
    if m.probe_json:
        try:
            return json.loads(m.probe_json)
        except json.JSONDecodeError:
            pass
    return {}


def _probe_and_report(data: bytes, target_seconds: int | None) -> tuple[ffmpegx.MediaProbe, dict]:
    with ffmpegx.temp_media(data) as p2:
        probe2 = ffmpegx.probe_path(p2)
        if probe2.audio_codec:
            audio2 = ffmpegx.analyze_audio(p2)
            sil2 = ffmpegx.detect_silences(p2)
        else:
            audio2 = {"mean_volume": None, "max_volume": None}
            sil2 = []
        light2 = ffmpegx.measure_lighting(p2)
    return probe2, quality.build_report(probe2, audio2, sil2, light2, target_seconds)


def _latest_role_title(db: Session, profile_id: str) -> str | None:
    cvs = db.scalars(select(CvRecord).where(CvRecord.profile_id == profile_id)).all()
    if not cvs:
        return None
    try:
        parsed = _parsed_from_cv(cvs[-1], db)
    except Exception:
        return None
    for e in reversed(parsed.experience):
        t = (e.get("title") or "").strip()
        if t:
            return t[:80]
    return None


@router.post("/videos/{video_id}/media/{media_id}/trim", response_model=VideoJobOut, status_code=202)
def trim_video_media(
    video_id: str, media_id: str, payload: TrimRequest, db: Session = Depends(get_db)
) -> VideoJobOut:
    """Cut [start, end] out of a take -> new MP4 (background job)."""
    v = get_video_or_404(db, video_id)
    m = get_media_or_404(db, v, media_id)
    if m.kind not in ffmpegx.VIDEO_KINDS:
        raise HTTPException(
            status_code=409,
            detail={"code": "NOT_A_VIDEO", "message": "Trim applies to video files."},
        )
    duration = _read_probe(m).get("duration")
    if not duration:
        raise HTTPException(
            status_code=422,
            detail={"code": "UNKNOWN_DURATION", "message": "Could not read the video length."},
        )
    if not (0 <= payload.start < payload.end <= duration + 0.25):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "BAD_TRIM_RANGE",
                "message": f"Trim range must sit inside the {duration:.1f}s video (start < end).",
            },
        )
    if payload.end - payload.start < 2:
        raise HTTPException(
            status_code=422,
            detail={"code": "BAD_TRIM_RANGE", "message": "Trimmed clip must be at least 2 seconds."},
        )
    job = jobs.submit("trim", _trim_worker, v.id, m.id, payload.start, payload.end)
    return VideoJobOut(**job.to_out())


def _trim_worker(job: jobs.Job, video_id: str, media_id: str, start: float, end: float) -> None:
    db = SessionLocal()
    try:
        job.phase = "reading media"
        job.progress = 0.05
        v = db.get(VideoResponse, video_id)
        m = db.get(VideoMedia, media_id)
        if v is None or m is None:
            raise RuntimeError("Video or media no longer exists.")
        job.phase = "trimming"
        job.progress = 0.3
        with ffmpegx.temp_media(m.data, suffix=_suffix_for(m)) as src, ffmpegx.temp_out(".mp4") as dst:
            ffmpegx.trim_video(src, dst, start, end)
            out = dst.read_bytes()
        job.phase = "analysing result"
        job.progress = 0.8
        stem = re.sub(r"\.[a-z0-9]+$", "", m.filename) or "response"
        new_m = VideoMedia(
            id=str(uuid.uuid4()),
            video_response_id=v.id,
            kind="enhanced",
            filename=f"{stem}-trimmed.mp4",
            content_type="video/mp4",
            size=len(out),
            data=out,
        )
        db.add(new_m)
        db.flush()
        probe2, report = _probe_and_report(out, v.target_seconds)
        new_m.probe_json = json.dumps(probe2.to_dict())
        new_m.quality_json = json.dumps(report)
        db.commit()
        db.refresh(new_m)
        job.progress = 1.0
        job.result = {"media_id": new_m.id, "report": report}
    finally:
        db.close()


@router.post("/videos/{video_id}/media-headshot", response_model=VideoOut, status_code=201)
def upload_headshot(
    video_id: str,
    file: UploadFile = File(...),
    likeness_consent: bool = Form(False),
    db: Session = Depends(get_db),
) -> VideoOut:
    """Store an approved headshot for the intro card / thumbnail."""
    v = get_video_or_404(db, video_id)
    require_consent(db, v.profile_id, "media_use")
    if not likeness_consent:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "LIKENESS_CONSENT_REQUIRED",
                "message": "Confirm this photo is you (or you have permission to use it) first.",
            },
        )
    ct = (file.content_type or "").lower()
    if ct not in HEADSHOT_TYPES:
        raise HTTPException(
            status_code=415,
            detail={"code": "UNSUPPORTED_MEDIA_TYPE", "message": "Upload a JPG, PNG or WebP photo."},
        )
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_HEADSHOT_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"code": "MEDIA_TOO_LARGE", "message": "Headshot must be under 5 MB."},
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if len(data) < 1024:
        raise HTTPException(
            status_code=422,
            detail={"code": "EMPTY_MEDIA", "message": "That file is too small to be a photo."},
        )
    m = VideoMedia(
        id=str(uuid.uuid4()),
        video_response_id=v.id,
        kind="headshot",
        filename=(file.filename or "headshot")[:300],
        content_type=ct,
        size=size,
        data=data,
    )
    db.add(m)
    v.likeness_consent = True
    db.commit()
    db.refresh(v)
    return _video_out(v)


@router.post("/videos/{video_id}/intro-card", response_model=VideoJobOut, status_code=202)
def build_intro_card(
    video_id: str, payload: IntroCardRequest, db: Session = Depends(get_db)
) -> VideoJobOut:
    """Prepend a 2-10s intro card (name, role, approved headshot) to the
    latest video, and make a 1280x720 thumbnail PNG. Background job."""
    v = get_video_or_404(db, video_id)
    source = _latest_video_media(db, v.id)
    if source is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "NO_VIDEO", "message": "Upload or record a video first."},
        )
    headshot = db.scalars(
        select(VideoMedia)
        .where(VideoMedia.video_response_id == v.id, VideoMedia.kind == "headshot")
        .order_by(VideoMedia.created_at.desc())
    ).first()
    if headshot is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "NO_HEADSHOT", "message": "Upload an approved headshot first."},
        )
    profile = db.get(Profile, v.profile_id)
    name = (payload.name or "").strip()
    if not name and profile:
        name = f"{profile.first_name or ''} {profile.last_name or ''}".strip()
    role = (payload.role or "").strip()
    if not role:
        role = _latest_role_title(db, v.profile_id) or ""
    if not name:
        name = "Candidate"
    job = jobs.submit("intro-card", _intro_card_worker, v.id, payload.seconds, name, role)
    return VideoJobOut(**job.to_out())


def _intro_card_worker(job: jobs.Job, video_id: str, seconds: int, name: str, role: str) -> None:
    db = SessionLocal()
    try:
        job.phase = "reading media"
        job.progress = 0.05
        v = db.get(VideoResponse, video_id)
        source = _latest_video_media(db, video_id) if v else None
        headshot = (
            db.scalars(
                select(VideoMedia)
                .where(VideoMedia.video_response_id == video_id, VideoMedia.kind == "headshot")
                .order_by(VideoMedia.created_at.desc())
            ).first()
            if v
            else None
        )
        if v is None or source is None or headshot is None:
            raise RuntimeError("Video, media or headshot no longer exists.")
        # All temps stay open until the concat reads them (temp files are
        # removed when their context manager exits).
        with ffmpegx.temp_media(headshot.data, suffix=".png") as hs, \
             ffmpegx.temp_media(source.data, suffix=_suffix_for(source)) as src, \
             ffmpegx.temp_out(".png") as card, \
             ffmpegx.temp_out(".mp4") as intro, \
             ffmpegx.temp_out(".mp4") as norm, \
             ffmpegx.temp_out(".mp4") as out, \
             ffmpegx.temp_out(".png") as thumb:
            probe = ffmpegx.probe_path(src)
            job.phase = "building intro card"
            job.progress = 0.3
            ffmpegx.build_intro_image(card, hs, name, role)
            ffmpegx.build_intro_card(intro, card, seconds)
            job.phase = "preparing video"
            job.progress = 0.5
            ffmpegx.normalize_source(src, norm, has_audio=bool(probe.audio_codec))
            job.phase = "combining"
            job.progress = 0.75
            ffmpegx.concat_mp4([intro, norm], out)
            out_data = out.read_bytes()
            job.phase = "making thumbnail"
            job.progress = 0.9
            ffmpegx.make_thumbnail(
                src, thumb, at=min(2.0, (probe.duration or 6.0) * 0.25)
            )
            thumb_data = thumb.read_bytes()

        job.phase = "analysing result"
        job.progress = 0.95
        stem = re.sub(r"\.[a-z0-9]+$", "", source.filename) or "response"
        new_m = VideoMedia(
            id=str(uuid.uuid4()),
            video_response_id=v.id,
            kind="enhanced",
            filename=f"{stem}-with-intro.mp4",
            content_type="video/mp4",
            size=len(out_data),
            data=out_data,
        )
        thumb_m = VideoMedia(
            id=str(uuid.uuid4()),
            video_response_id=v.id,
            kind="thumbnail",
            filename=f"{stem}-thumbnail.png",
            content_type="image/png",
            size=len(thumb_data),
            data=thumb_data,
        )
        db.add(new_m)
        db.add(thumb_m)
        db.flush()
        probe2, report = _probe_and_report(out_data, v.target_seconds)
        new_m.probe_json = json.dumps(probe2.to_dict())
        new_m.quality_json = json.dumps(report)
        db.commit()
        db.refresh(new_m)
        job.progress = 1.0
        job.result = {"media_id": new_m.id, "thumbnail_id": thumb_m.id, "report": report}
    finally:
        db.close()


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

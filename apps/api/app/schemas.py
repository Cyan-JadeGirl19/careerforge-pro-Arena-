"""Pydantic API schemas - the typed v1 contract.

The machine-readable version of this contract is exported to
``docs/openapi/v1.json`` (see ``scripts/export_openapi.py``) and
mirrored in TypeScript at ``packages/contracts/types.ts``.
"""
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ConsentItem(str, Enum):
    """Purposes that require explicit, revocable candidate consent."""

    PROFILE_PROCESSING = "profile_processing"
    JOB_MATCHING = "job_matching"
    RECRUITER_CONTACT = "recruiter_contact"
    OUTREACH_SENDING = "outreach_sending"
    REFERENCE_SHARING = "reference_sharing"
    MEDIA_USE = "media_use"
    VIDEO_RECORDING = "video_recording"


class ProfileCreate(BaseModel):
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    timezone: str = Field(default="Africa/Johannesburg", max_length=64)
    work_authority: str = Field(default="sa_remote_eligible", max_length=64)
    summary: str | None = Field(default=None, max_length=4000)


class ProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    timezone: str | None = Field(default=None, max_length=64)
    work_authority: str | None = Field(default=None, max_length=64)
    summary: str | None = Field(default=None, max_length=4000)


class ProfileOut(BaseModel):
    id: str
    first_name: str | None
    last_name: str | None
    timezone: str
    work_authority: str
    summary: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ConsentGrant(BaseModel):
    item: ConsentItem
    granted: bool = True
    notes: str | None = Field(default=None, max_length=2000)


class ConsentOut(BaseModel):
    id: str
    item: ConsentItem
    granted: bool
    notes: str | None
    granted_at: datetime
    revoked_at: datetime | None
    created_at: datetime


class CvCreate(BaseModel):
    title: str = Field(default="Master CV", max_length=200)
    text: str = Field(
        min_length=40,
        max_length=100_000,
        description="The candidate's own CV text. Must be truthful; never invented.",
    )
    source_type: str = Field(default="paste", pattern="^(paste|upload)$")


class CvOut(BaseModel):
    id: str
    profile_id: str
    version: int
    title: str
    text: str
    source_type: str
    created_at: datetime


class ParsedCvOut(BaseModel):
    name: str
    email: str
    phone: str
    location: str
    links: list[str]
    summary: str
    experience: list[dict]
    education: list[dict]
    skills: list[str]
    certifications: list[str]
    projects: list[str]
    languages: list[str]
    other_sections: dict
    extraction_notes: list[str]


class CvVersionCreate(BaseModel):
    kind: str = Field(pattern="^(master_ats|master_modern|master_role|custom)$")
    role_focus: str | None = Field(
        default=None, max_length=120,
        description="Required for master_role and custom versions.",
    )
    emphasize: list[str] = Field(default_factory=list, max_length=20)
    exclude: list[str] = Field(default_factory=list, max_length=20)


class BuildMastersRequest(BaseModel):
    role_focus: str | None = Field(
        default=None, max_length=120,
        description="Target role for the Role-Specialist master.",
    )


class CvVersionOut(BaseModel):
    id: str
    profile_id: str
    base_cv_id: str
    kind: str
    title: str
    role_focus: str | None
    content: dict
    created_at: datetime


class JobDescriptionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=500)
    text: str = Field(min_length=40, max_length=100_000)


class JobDescriptionOut(BaseModel):
    id: str
    profile_id: str
    title: str
    company: str | None
    source_url: str | None
    text: str
    created_at: datetime


class TailorRequest(BaseModel):
    jd_id: str


class TailoredCvOut(BaseModel):
    id: str
    profile_id: str
    version_id: str
    jd_id: str
    title: str
    content: dict
    report: dict
    created_at: datetime


class CheckResult(BaseModel):
    check: str
    passed: bool
    detail: str


class KeywordStatus(BaseModel):
    keyword: str
    present: bool


class CvAnalysisOut(BaseModel):
    id: str
    cv_id: str
    checks: list[CheckResult]
    keywords: list[KeywordStatus]
    gaps: list[str]
    created_at: datetime
    note: str = (
        "Transparent checks only. This is not a vendor ATS pass-rate score."
    )


class RoleRecommendationOut(BaseModel):
    role: str
    match_pct: float
    matched: list[str]
    missing: list[str]
    reason: str


class ApplicationCreate(BaseModel):
    jd_id: str
    cv_version_id: str | None = None
    notes: str | None = Field(default=None, max_length=4000)


class CoverLetterCreate(BaseModel):
    tone: str = Field(default="direct", pattern="^(direct|warm|formal)$")


class CoverLetterOut(BaseModel):
    id: str
    application_id: str
    text: str
    tone: str
    quality_issues: list[str]
    created_at: datetime


class VideoCreate(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    key_points: list[str] = Field(default_factory=list, max_length=10)
    exclusions: list[str] = Field(default_factory=list, max_length=10)
    tone: str = Field(default="natural", pattern="^(natural|formal|warm|direct)$")
    target_seconds: Literal[30, 60, 90, 120, 180] = 60
    mode: str = Field(default="recording", pattern="^(recording|enhance|ai_assisted)$")
    ai_disclosed: bool = False
    delete_media_after_export: bool = True


class VideoMediaOut(BaseModel):
    id: str
    kind: str  # original | enhanced | captions | audio
    filename: str
    content_type: str
    size: int
    duration: float | None = None
    created_at: datetime


class VideoOut(BaseModel):
    id: str
    application_id: str
    question: str
    key_points: str | None
    exclusions: str | None
    tone: str
    target_seconds: int
    mode: str
    script_text: str
    script_version: int
    media_status: str
    ai_disclosed: bool
    delete_media_after_export: bool
    likeness_consent: bool = False
    media: list[VideoMediaOut] = []
    created_at: datetime
    updated_at: datetime


class VideoMediaUpdate(BaseModel):
    media_status: str = Field(pattern="^(uploaded|ready)$")


class VideoAnalyzeOut(BaseModel):
    media_id: str
    report: dict


class VideoEnhanceRequest(BaseModel):
    """Real, file-level processing: colour/lighting (eq), loudness
    (loudnorm), framing (crop/scale/pad) and optional caption burn-in.
    Sliders run -10..10; ``auto_enhance`` applies mild defaults when all
    sliders are at 0."""

    normalize_audio: bool = False
    auto_enhance: bool = True
    brightness: int = Field(default=0, ge=-10, le=10)
    contrast: int = Field(default=0, ge=-10, le=10)
    saturation: int = Field(default=0, ge=-10, le=10)
    framing: str = Field(default="none", pattern="^(none|16x9|9x16|1x1)$")
    burn_captions: bool = False


class CaptionsRequest(BaseModel):
    transcript: str | None = Field(default=None, max_length=20000)
    use_script: bool = False
    media_id: str | None = None


class VideoJobOut(BaseModel):
    job_id: str
    kind: str
    status: str  # running | done | failed
    phase: str
    progress: float
    result: dict | None = None
    error: str | None = None


class ApplicationStatusUpdate(BaseModel):
    status: str = Field(
        pattern="^(saved|ready|applied|phone_screen|interview|offer|rejected|archived)$"
    )
    notes: str | None = Field(default=None, max_length=4000)



class ApplicationReferenceOut(BaseModel):
    id: str
    name: str
    title: str | None
    company: str | None
    email: str | None
    phone: str | None
    type: str
    permission_confirmed: bool
    approved: bool
    missing: list[str]


class ApplicationOut(BaseModel):
    id: str
    profile_id: str
    jd_title: str
    jd_company: str | None
    cv_version_id: str | None
    tailored_cv_id: str | None
    status: str
    references_requested: str
    references: list[ApplicationReferenceOut] = []
    notes: str | None
    letter: CoverLetterOut | None
    videos: list[VideoOut]
    created_at: datetime
    updated_at: datetime


# ---- follow-ups ----

class FollowUpCreate(BaseModel):
    kind: str = Field(default="custom", pattern="^(post_application|post_interview|custom)$")
    due_days: int = Field(default=5, ge=0, le=90)
    notes: str | None = Field(default=None, max_length=4000)


class FollowUpOut(BaseModel):
    id: str
    profile_id: str
    application_id: str | None
    kind: str
    due_at: datetime
    status: str
    draft_text: str
    notes: str | None
    application_title: str | None = None
    application_company: str | None = None


class FollowUpStatusIn(BaseModel):
    status: str = Field(pattern="^(sent|skipped)$")
    notes: str | None = Field(default=None, max_length=4000)
    draft_text: str | None = Field(default=None, max_length=20000)


# ---- interview coach ----

class InterviewGenerateIn(BaseModel):
    role: str = Field(min_length=2, max_length=120)
    jd_id: str | None = None
    jd_text: str | None = Field(default=None, max_length=100000)


class InterviewQuestionOut(BaseModel):
    category: str
    question: str
    prepared_answer: str
    evidence_used: list[str]


class InterviewSessionOut(BaseModel):
    role: str
    questions: list[InterviewQuestionOut]
    note: str


class HealthOut(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    database: str


class AutoPipelineRequest(BaseModel):
    cv_id: str
    jd_ids: list[str] = Field(min_length=1, max_length=10)


class AutoPipelineOut(BaseModel):
    applications: list[ApplicationOut]
    skipped: list[dict]


# ---- jobs ----

class JobMatchOut(BaseModel):
    score: float
    components: dict
    skill_hits: list[str]
    keyword_hits: list[str]
    weights: dict


class JobOut(BaseModel):
    id: str
    source: str
    title: str
    company: str | None
    location: str | None
    url: str | None
    tags: str
    salary_text: str | None
    posted_at: datetime | None
    fetched_at: datetime
    open_to_sa: str
    sa_signals: list[str]
    global_signals: list[str]
    exclude_signals: list[str]
    payment_signals: list[str]
    timezone_signals: list[str]
    remote_type: str
    match: JobMatchOut | None = None


class JobDetailOut(JobOut):
    description: str


class SourceStatusOut(BaseModel):
    source: str
    enabled: bool
    status: str | None = None
    fetched: int | None = None
    added: int | None = None
    error: str | None = None


class JobSyncOut(BaseModel):
    sources: list[SourceStatusOut]
    total_jobs: int


class AddUrlIn(BaseModel):
    url: str = Field(min_length=10, max_length=500)


class SavedSearchIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    filters: dict = Field(default_factory=dict)


class SavedSearchOut(BaseModel):
    id: str
    name: str
    filters: dict
    created_at: datetime


# ---- recruiters ----

class RecruiterExtractIn(BaseModel):
    url: str = Field(min_length=10, max_length=500)
    company: str | None = Field(default=None, max_length=200)


class RecruiterCreate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=120)
    company: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    profile_url: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=500)
    job_title: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)
    email_status: str = Field(default="none", pattern="^(none|published|pattern_suggested)$")


class RecruiterUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=120)
    company: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    profile_url: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)
    verified: bool | None = None
    suppressed: bool | None = None
    email_status: str | None = Field(default=None, pattern="^(none|published|pattern_suggested)$")


class RecruiterOut(BaseModel):
    id: str
    profile_id: str
    source: str
    source_url: str | None
    name: str | None
    title: str | None
    company: str | None
    profile_url: str | None
    email: str | None
    email_status: str
    suggested_emails: list[str]
    job_title: str | None
    notes: str | None
    verified: bool
    verified_at: datetime | None
    suppressed: bool
    created_at: datetime


class OutreachIn(BaseModel):
    job_title: str | None = Field(default=None, max_length=200)
    tone: str = Field(default="direct", pattern="^(direct|warm)$")


class OutreachOut(BaseModel):
    draft: str
    issues: list[str]


# ---- references ----

class ReferenceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    title: str | None = Field(default=None, max_length=120)
    relationship: str | None = Field(default=None, max_length=120)
    company: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    type: str = Field(default="current", pattern="^(current|former|academic|personal)$")
    notes: str | None = Field(default=None, max_length=4000)
    permission_confirmed: bool = False
    include_by_default: bool = False


class ReferenceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    title: str | None = Field(default=None, max_length=120)
    relationship: str | None = Field(default=None, max_length=120)
    company: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    type: str | None = Field(default=None, pattern="^(current|former|academic|personal)$")
    notes: str | None = Field(default=None, max_length=4000)
    permission_confirmed: bool | None = None
    approved: bool | None = None
    include_by_default: bool | None = None
    suppressed: bool | None = None


class ReferenceDocumentOut(BaseModel):
    id: str
    reference_id: str | None
    filename: str
    content_type: str
    size: int
    created_at: datetime


class ReferenceOut(BaseModel):
    id: str
    profile_id: str
    name: str
    title: str | None
    relationship: str | None
    company: str | None
    email: str | None
    phone: str | None
    type: str
    notes: str | None
    permission_confirmed: bool
    permission_confirmed_at: datetime | None
    approved: bool
    include_by_default: bool
    suppressed: bool
    documents: list[ReferenceDocumentOut] = []
    created_at: datetime


class AttachReferencesIn(BaseModel):
    references_requested: str = Field(default="unspecified", pattern="^(yes|no|unspecified)$")
    reference_ids: list[str] = Field(default_factory=list, max_length=10)



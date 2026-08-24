"""Pydantic API schemas - the typed v1 contract.

The machine-readable version of this contract is exported to
``docs/openapi/v1.json`` (see ``scripts/export_openapi.py``) and
mirrored in TypeScript at ``packages/contracts/types.ts``.
"""
from datetime import datetime
from enum import Enum

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


class HealthOut(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    database: str

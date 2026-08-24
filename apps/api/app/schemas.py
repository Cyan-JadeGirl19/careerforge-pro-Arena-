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

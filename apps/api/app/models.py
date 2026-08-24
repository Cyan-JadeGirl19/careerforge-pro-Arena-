"""SQLAlchemy ORM models.

Design notes (see REVIEW.md "Important data model fields"):
- Evidence rows carry claim / source / verified / last_verified_at /
  candidate_approved so no metric is ever presented as fact without
  provenance and candidate approval.
- Consent rows are explicit, purpose-scoped and revocable (POPIA-aligned).
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Johannesburg")
    work_authority: Mapped[str] = mapped_column(
        String(64), default="sa_remote_eligible"
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    consents: Mapped[list["Consent"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    cvs: Mapped[list["CvRecord"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class Consent(Base):
    """Explicit, revocable consent for a specific purpose."""

    __tablename__ = "consents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    item: Mapped[str] = mapped_column(String(40), index=True)
    granted: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    profile: Mapped["Profile"] = relationship(back_populates="consents")


class CvRecord(Base):
    __tablename__ = "cv_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(200), default="Master CV")
    text: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(20), default="paste")
    parsed_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    profile: Mapped["Profile"] = relationship(back_populates="cvs")
    analyses: Mapped[list["CvAnalysis"]] = relationship(
        back_populates="cv", cascade="all, delete-orphan"
    )


class CvVersion(Base):
    """A built CV version: master (ats/modern/role), custom, or base."""

    __tablename__ = "cv_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    base_cv_id: Mapped[str] = mapped_column(
        ForeignKey("cv_records.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    role_focus: Mapped[str | None] = mapped_column(String(120), nullable=True)
    content_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    base_cv: Mapped["CvRecord"] = relationship()
    tailored: Mapped[list["TailoredCv"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class TailoredCv(Base):
    """Job-specific CV version + its transparent coverage report.

    Retains the per-application record agreed in the product spec:
    JD used, keywords surfaced, claims needing confirmation, date.
    """

    __tablename__ = "tailored_cvs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    version_id: Mapped[str] = mapped_column(
        ForeignKey("cv_versions.id", ondelete="CASCADE"), index=True
    )
    jd_id: Mapped[str] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(220))
    content_json: Mapped[str] = mapped_column(Text)
    report_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    version: Mapped["CvVersion"] = relationship(back_populates="tailored")
    jd: Mapped["JobDescription"] = relationship()


class CvAnalysis(Base):
    """Stored, transparent CV analysis report (no fabricated ATS %)."""

    __tablename__ = "cv_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    cv_id: Mapped[str] = mapped_column(
        ForeignKey("cv_records.id", ondelete="CASCADE"), index=True
    )
    report_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    cv: Mapped["CvRecord"] = relationship(back_populates="analyses")


class Evidence(Base):
    """Candidate-asserted claim with provenance and approval state."""

    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    claim: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    candidate_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    profile: Mapped["Profile"] = relationship(back_populates="evidence")

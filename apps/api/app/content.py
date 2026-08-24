"""CvContent — the shared in-memory CV document model.

Builders produce it, exporters render it, the API stores it as JSON.
Every generated document retains provenance per REVIEW.md:
``source_profile_version``, ``job_description_version``,
``generation_timestamp``.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ExperienceItem:
    title: str = ""
    company: str = ""
    dates: str = ""
    bullets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "company": self.company,
            "dates": self.dates,
            "bullets": self.bullets,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExperienceItem":
        return cls(
            title=d.get("title", ""),
            company=d.get("company", ""),
            dates=d.get("dates", ""),
            bullets=list(d.get("bullets", [])),
        )


@dataclass
class EducationItem:
    degree: str = ""
    institution: str = ""
    year: str = ""

    def to_dict(self) -> dict:
        return {
            "degree": self.degree,
            "institution": self.institution,
            "year": self.year,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EducationItem":
        return cls(
            degree=d.get("degree", ""),
            institution=d.get("institution", ""),
            year=d.get("year", ""),
        )


LAYOUT_ATS = "ats_single_column"
LAYOUT_MODERN = "modern"
LAYOUT_ROLE = "role_specialist"


@dataclass
class CvContent:
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: list[str] = field(default_factory=list)
    headline: str = ""
    summary: str = ""
    skills: list[str] = field(default_factory=list)
    experience: list[ExperienceItem] = field(default_factory=list)
    education: list[EducationItem] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    layout: str = LAYOUT_ATS
    role_focus: str | None = None
    source_profile_version: str | None = None
    job_description_version: str | None = None
    generation_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "links": self.links,
            "headline": self.headline,
            "summary": self.summary,
            "skills": self.skills,
            "experience": [e.to_dict() for e in self.experience],
            "education": [e.to_dict() for e in self.education],
            "certifications": self.certifications,
            "projects": self.projects,
            "languages": self.languages,
            "layout": self.layout,
            "role_focus": self.role_focus,
            "source_profile_version": self.source_profile_version,
            "job_description_version": self.job_description_version,
            "generation_timestamp": self.generation_timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CvContent":
        return cls(
            name=d.get("name", ""),
            email=d.get("email", ""),
            phone=d.get("phone", ""),
            location=d.get("location", ""),
            links=list(d.get("links", [])),
            headline=d.get("headline", ""),
            summary=d.get("summary", ""),
            skills=list(d.get("skills", [])),
            experience=[ExperienceItem.from_dict(e) for e in d.get("experience", [])],
            education=[EducationItem.from_dict(e) for e in d.get("education", [])],
            certifications=list(d.get("certifications", [])),
            projects=list(d.get("projects", [])),
            languages=list(d.get("languages", [])),
            layout=d.get("layout", LAYOUT_ATS),
            role_focus=d.get("role_focus"),
            source_profile_version=d.get("source_profile_version"),
            job_description_version=d.get("job_description_version"),
            generation_timestamp=d.get(
                "generation_timestamp",
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    # -- helpers ---------------------------------------------------------

    def all_text(self) -> str:
        """Everything a parser could match against (lowercased)."""
        parts: list[str] = [
            self.name,
            self.headline,
            self.summary,
            " ".join(self.skills),
            " ".join(self.certifications),
            " ".join(self.projects),
            " ".join(self.languages),
        ]
        for e in self.experience:
            parts.append(" ".join([e.title, e.company, e.dates, *e.bullets]))
        for e in self.education:
            parts.append(" ".join([e.degree, e.institution, e.year]))
        return " \n ".join(p.lower() for p in parts if p)

    def quantified_bullets(self) -> list[str]:
        import re

        return [
            b
            for e in self.experience
            for b in e.bullets
            if re.search(r"\d", b)
        ]

    def clone(self) -> "CvContent":
        return CvContent.from_dict(self.to_dict())

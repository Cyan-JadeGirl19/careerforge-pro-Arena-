"""Skills & Salary routes: gaps, 90-day plans, benchmarks, scripts."""
import json
import urllib.request

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_db
from ...models import CvRecord
from ...parsing import ParsedCv, parse_cv_text
from ...skills import catalog
from .profiles import get_profile_or_404

router = APIRouter(tags=["skills"])

FALLBACK_USD_ZAR = 18.20
FALLBACK_AS_OF = "2026-08 (static fallback)"


def _usd_zar() -> tuple[float, str]:
    """Live rate from a public API; falls back to a dated static rate."""
    try:
        req = urllib.request.Request(
            "https://open.er-api.com/v6/latest/USD",
            headers={"User-Agent": "CareerForgePro/1.0"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read(200_000).decode("utf-8", errors="replace"))
        rate = float(data["rates"]["ZAR"])
        return rate, "open.er-api.com (live)"
    except Exception:
        return FALLBACK_USD_ZAR, FALLBACK_AS_OF


def _parsed_for_profile(db: Session, profile_id: str) -> ParsedCv | None:
    cvs = db.scalars(select(CvRecord).where(CvRecord.profile_id == profile_id)).all()
    if not cvs:
        return None
    cv = cvs[-1]
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


def _course_for(skill: str) -> dict | None:
    low = skill.lower()
    for key, courses in catalog.FREE_COURSES.items():
        if low == key or low in key or key in low:
            return {**courses[0], "skill": skill}
    return None


@router.get("/skills/gaps")
def skills_gaps(
    profile_id: str,
    role: str = Query(min_length=2, max_length=120),
    db: Session = Depends(get_db),
) -> dict:
    get_profile_or_404(db, profile_id)
    parsed = _parsed_for_profile(db, profile_id)
    have = {s.lower() for s in (parsed.skills if parsed else [])}
    have.add(parsed.summary.lower() if parsed and parsed.summary else "")

    target = catalog.ROLE_SKILLS.get(
        role.lower(), [w for w in role.lower().split() if len(w) > 3]
    )
    present, missing = [], []
    for skill in target:
        if any(skill in h for h in have if h):
            present.append(skill)
        else:
            missing.append(skill)

    # high-ROI = missing skills that other target roles also need
    cross = set()
    for rk, sv in catalog.ROLE_SKILLS.items():
        if rk != role.lower():
            cross.update(sv)
    high_roi = [s for s in missing if s in cross]
    low_roi = [s for s in missing if s not in cross]

    courses = []
    for skill in (high_roi + low_roi)[:6]:
        c = _course_for(skill)
        if c:
            courses.append(c)

    return {
        "role": role,
        "catalog_as_of": catalog.CATALOG_AS_OF,
        "present": present,
        "missing": missing,
        "high_roi": high_roi,
        "low_roi": low_roi,
        "courses": courses,
        "note": (
            "Gap = a skill the role lists that your CV doesn't show. 'High ROI' means "
            "other common target roles need it too. Courses are free or free-to-audit; "
            "verify links before enrolling. Adding a skill to your CV is only valid once "
            "you've actually learned it."
        ),
    }


@router.get("/skills/plan-90d")
def plan_90d(
    profile_id: str,
    role: str = Query(min_length=2, max_length=120),
    db: Session = Depends(get_db),
) -> dict:
    gaps = skills_gaps(profile_id=profile_id, role=role, db=db)
    skills = (gaps["high_roi"] + gaps["low_roi"])[:3]
    weeks: list[dict] = []
    if not skills:
        weeks.append(
            {
                "weeks": "1-12",
                "focus": "No blocking gaps found",
                "detail": "Polish evidence instead: quantify more of what you already do, "
                "and strengthen your CV bullets with real numbers.",
            }
        )
    else:
        # split weeks 1-9 across the skills; 10-12 is for applying
        spans = {1: [(1, 9)], 2: [(1, 4), (5, 9)], 3: [(1, 3), (4, 6), (7, 9)]}[len(skills)]
        for (s, e), skill in zip(spans, skills):
            course = _course_for(skill) or {}
            weeks.append(
                {
                    "weeks": f"{s}-{e}",
                    "focus": f"Learn {skill}",
                    "detail": (
                        f"{course.get('title', 'Practice ' + skill)} "
                        f"({course.get('provider', 'free practice')}). "
                        f"5-7 hours/week: 3h course + 2-4h building one small "
                        f"real project you can put on your CV."
                    ),
                    "url": course.get("url"),
                }
            )
        weeks.append(
            {
                "weeks": "10-12",
                "focus": "Apply what you built",
                "detail": "Add the new skill (with your project) to your CV, update your "
                "target role, and apply to 5-10 matched jobs per week. Evidence first: "
                "only claim what you built.",
            }
        )
    return {"role": role, "weeks": weeks}


@router.get("/salary/benchmarks")
def salary_benchmarks(role: str = Query(min_length=2, max_length=120)) -> dict:
    low_key = role.lower()
    bench = catalog.SALARY_BENCHMARKS.get(low_key)
    if bench is None:
        for key, val in catalog.SALARY_BENCHMARKS.items():
            if key in low_key or low_key in key:
                bench, low_key = val, key
                break
    rate, rate_src = _usd_zar()
    if bench is None:
        return {
            "role": role,
            "found": False,
            "disclaimer": catalog.SALARY_DISCLAIMER,
            "rate": {"usd_zar": rate, "source": rate_src},
            "note": "No directional benchmark for this role yet. Check live job "
            "postings for the range, and compare 5-10 similar jobs before negotiating.",
        }
    usd_low, usd_high = bench["usd_month"]
    return {
        "role": role,
        "found": True,
        "benchmark_key": low_key,
        "note": bench["note"],
        "usd_month": [usd_low, usd_high],
        "zar_month": [round(usd_low * rate), round(usd_high * rate)],
        "rate": {"usd_zar": rate, "source": rate_src},
        "disclaimer": catalog.SALARY_DISCLAIMER,
    }


@router.get("/salary/negotiation-scripts")
def negotiation_scripts() -> dict:
    return {
        "scripts": catalog.NEGOTIATION_SCRIPTS,
        "disclaimer": catalog.SALARY_DISCLAIMER,
    }


@router.get("/salary/payment-guidance")
def payment_guidance() -> dict:
    return {
        "points": catalog.PAYMENT_GUIDANCE,
        "disclaimer": catalog.SALARY_DISCLAIMER,
    }

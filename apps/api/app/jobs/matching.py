"""Transparent match scoring for SA remote candidates.

Weights (agreed spec): skills overlap 40%, experience level 20%,
CV keyword match 20%, remote-SA feasibility 10%, freshness 10%.
Every component is returned so the UI can show *why*.
"""
from datetime import datetime, timezone

from ..builders import extract_jd_keywords

WEIGHTS = {
    "skills": 0.40,
    "experience": 0.20,
    "keywords": 0.20,
    "feasibility": 0.10,
    "freshness": 0.10,
}

_SENIOR_WORDS = ("senior", "principal", "lead", "head of", "manager", "staff", "architect")
_JUNIOR_WORDS = ("junior", "entry", "graduate", "intern", "apprentice")


def _seniority_score(title: str, years: int | None) -> float:
    t = (title or "").lower()
    if years is None:
        return 0.5
    senior = any(w in t for w in _SENIOR_WORDS)
    junior = any(w in t for w in _JUNIOR_WORDS)
    if senior:
        return 1.0 if years >= 5 else (0.6 if years >= 3 else 0.3)
    if junior:
        return 1.0 if years < 3 else (0.6 if years < 6 else 0.3)
    # mid-level default: reward mid-to-senior
    if years >= 2 and years <= 10:
        return 1.0
    return 0.5


def _freshness_score(posted_at: datetime | None, now: datetime) -> float:
    if not posted_at:
        return 0.5
    age_days = max(0.0, (now - posted_at).total_seconds() / 86400)
    # 7 days or less = full score (early applications), linear decay to 0 at 30 days
    if age_days <= 7:
        return 1.0
    if age_days >= 30:
        return 0.0
    return 1.0 - (age_days - 7) / 23


def _feasibility_score(signals: dict) -> float:
    base = {"yes": 1.0, "unknown": 0.5, "no": 0.0}.get(signals.get("open_to_sa"), 0.5)
    bonus = 0.0
    if signals.get("remote_type") == "remote":
        bonus += 0.0
    elif signals.get("remote_type") != "onsite":
        bonus -= 0.1
    return max(0.0, min(1.0, base + bonus))


def match_job(
    posting: dict,
    profile_skills: list[str],
    profile_years: int | None,
    profile_corpus: str,
    now: datetime | None = None,
) -> dict:
    """Return a 0-100 score with per-component breakdown (all transparent)."""
    now = now or datetime.now(timezone.utc)
    posted = posting.get("posted_at")
    if posted is not None and posted.tzinfo is None:
        # SQLite returns naive datetimes; treat stored times as UTC.
        posting = {**posting, "posted_at": posted.replace(tzinfo=timezone.utc)}
    text = " ".join(
        [posting.get("title", ""), posting.get("company") or "", posting.get("description", "")]
    ).lower()

    skills = [s.lower() for s in profile_skills if s]
    if skills:
        hits = [s for s in skills if s in text]
        skills_score = min(1.0, len(hits) / min(6, len(skills)))
    else:
        hits, skills_score = [], 0.5

    exp_score = _seniority_score(posting.get("title", ""), profile_years)

    keywords = extract_jd_keywords(posting.get("description", ""), top_n=20)
    kw_hits = [k for k in keywords if k in (profile_corpus or "").lower()]
    kw_score = (min(1.0, len(kw_hits) / min(8, len(keywords)))) if keywords else 0.5

    feas_score = _feasibility_score(posting)
    fresh_score = _freshness_score(posting.get("posted_at"), now)

    total = (
        WEIGHTS["skills"] * skills_score
        + WEIGHTS["experience"] * exp_score
        + WEIGHTS["keywords"] * kw_score
        + WEIGHTS["feasibility"] * feas_score
        + WEIGHTS["freshness"] * fresh_score
    )
    return {
        "score": round(total * 100, 1),
        "components": {
            "skills": round(skills_score * 100, 0),
            "experience": round(exp_score * 100, 0),
            "keywords": round(kw_score * 100, 0),
            "feasibility": round(feas_score * 100, 0),
            "freshness": round(fresh_score * 100, 0),
        },
        "skill_hits": hits[:8],
        "keyword_hits": kw_hits[:10],
        "weights": {k: round(v * 100) for k, v in WEIGHTS.items()},
    }

"""Evidence-backed CV analysis.

Deliberately transparent: every result is a named check with a human
explanation, plus a keyword map and gap list. We never emit a
fabricated "ATS pass rate" (see REVIEW.md).
"""
import re

#: Common signals for SA-eligible remote roles. Kept small and explicit
#: so candidates can see exactly what was searched for.
SA_REMOTE_KEYWORDS = [
    "remote",
    "stakeholder",
    "project management",
    "data analysis",
    "communication",
    "leadership",
    "agile",
    "customer success",
    "excel",
    "python",
]

_CONTACT_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d\s-]{8,}")
_BULLET_RE = re.compile(r"^\s*[-\u2022*]\s+")
_NUMBER_RE = re.compile(r"\d+")
_SECTIONS = ("experience", "education", "skills")


def analyze_cv_text(text: str) -> dict:
    """Return a structured, explainable report for the given CV text."""
    t = text.strip()
    lower = t.lower()
    checks: list[dict] = []
    gaps: list[str] = []

    has_contact = bool(_CONTACT_RE.search(t))
    checks.append(
        {
            "check": "contact_info",
            "passed": has_contact,
            "detail": "An email or phone number was found."
            if has_contact
            else "No email or phone number detected.",
        }
    )
    if not has_contact:
        gaps.append("Add an email address or phone number so recruiters can reach you.")

    found_sections = [s for s in _SECTIONS if s in lower]
    checks.append(
        {
            "check": "sections",
            "passed": len(found_sections) >= 2,
            "detail": f"Found {len(found_sections)}/3 standard sections: "
            + (", ".join(found_sections) or "none"),
        }
    )
    missing_sections = [s for s in _SECTIONS if s not in lower]
    if missing_sections:
        gaps.append("Add missing standard section(s): " + ", ".join(missing_sections) + ".")

    bullets = [line for line in t.splitlines() if _BULLET_RE.match(line)]
    checks.append(
        {
            "check": "achievement_bullets",
            "passed": len(bullets) >= 3,
            "detail": f"{len(bullets)} bulleted line(s) found; 3+ recommended.",
        }
    )
    if len(bullets) < 3:
        gaps.append("Use bullet points for achievements (at least 3 lines recommended).")

    quantified = [line for line in bullets if _NUMBER_RE.search(line)]
    checks.append(
        {
            "check": "quantified_results",
            "passed": len(quantified) >= 2,
            "detail": f"{len(quantified)} bullet(s) contain a number. "
            "Use only figures you can back up.",
        }
    )
    if len(quantified) < 2:
        gaps.append(
            "Add at least 2 quantified results you can substantiate (amounts, %, "
            "time saved, team size)."
        )

    length_ok = 400 <= len(t) <= 6000
    checks.append(
        {
            "check": "length",
            "passed": length_ok,
            "detail": f"{len(t)} characters; aim for roughly 400-6000 "
            "(about one focused page).",
        }
    )
    if len(t) < 400:
        gaps.append("The CV looks very short - add concrete details about your role.")
    elif len(t) > 6000:
        gaps.append("The CV looks long - trim to your strongest, most relevant items.")

    keywords = [
        {"keyword": kw, "present": kw in lower} for kw in SA_REMOTE_KEYWORDS
    ]

    return {"checks": checks, "keywords": keywords, "gaps": gaps}

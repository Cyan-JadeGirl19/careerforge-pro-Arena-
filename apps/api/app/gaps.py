"""Honest gap handling: never fabricate — turn every gap into an action.

The product rule (agreed and non-negotiable): requirements the candidate's
CV doesn't support are reported as gaps, never filled in with invented
metrics or experience. This module makes each gap *useful* instead:

- closest real skill from the candidate's own CV (to bridge honestly)
- a free, real course if the gap is a learnable skill
- an honest one-line interview answer
- (in the UI) a one-tap action to add GENUINE evidence, which then
  legitimately closes the gap on the next tailor run
"""
from .builders import KEYWORD_BRIDGES, _display_keyword
from .parsing import ParsedCv
from .skills.catalog import CATALOG_AS_OF, FREE_COURSES


def _closest_skill(keyword: str, skills: list[str]) -> str | None:
    """Best real skill that lets the candidate bridge honestly."""
    k = keyword.lower()
    for s in skills:
        sl = s.lower()
        if k in sl or sl in k:
            return s
    bridge = KEYWORD_BRIDGES.get(k, ())
    if bridge:
        for s in skills:
            sl = s.lower()
            if any(term in sl for term in bridge):
                return s
    return None


def _course_for(keyword: str) -> dict | None:
    k = keyword.lower()
    for key, courses in FREE_COURSES.items():
        if k == key or k in key or key in k:
            if courses:
                c = courses[0]
                return {
                    "title": c["title"],
                    "provider": c["provider"],
                    "url": c["url"],
                    "as_of": CATALOG_AS_OF,
                }
    return None


def _interview_line(keyword: str, closest: str | None, course: dict | None,
                    skills: list[str]) -> str:
    kw = _display_keyword(keyword)
    if closest:
        return (
            f"\"I haven't used {kw} directly, but I've used {closest} for the "
            "same kind of work - I'm confident I can get up to speed quickly.\""
        )
    parts = [f"I don't have direct {kw} experience yet."]
    if skills:
        parts.append(f"My closest work is {skills[0]}.")
    if course:
        parts.append(f"I'm building {kw} right now with a free course.")
    return '"' + " ".join(parts) + '"'


def gap_plan(gap_keywords: list[str], parsed: ParsedCv) -> list[dict]:
    """One honest action bundle per gap keyword (max 10, keeps it focused)."""
    out = []
    for kw in gap_keywords[:10]:
        closest = _closest_skill(kw, parsed.skills)
        course = _course_for(kw)
        out.append(
            {
                "keyword": kw,
                "closest_skill": closest,
                "course": course,
                "interview_line": _interview_line(
                    kw, closest, course, parsed.skills
                ),
            }
        )
    return out

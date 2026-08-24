"""Target-role recommendation.

Recommends the strongest roles from the candidate's *own* profile using
skill overlap with role keyword sets. Transparent: shows what matched and
what is missing. Never invents qualifications to make a role fit.
"""
from .builders import ROLE_KEYWORDS
from .parsing import ParsedCv


def _corpus(parsed: ParsedCv) -> str:
    parts = [
        parsed.summary,
        " ".join(parsed.skills),
        " ".join(parsed.certifications),
        " ".join(parsed.projects),
    ]
    for e in parsed.experience:
        parts.append(" ".join([e.get("title", ""), e.get("company", "")] + e.get("bullets", [])))
    for e in parsed.education:
        parts.append(" ".join([e.get("degree", ""), e.get("institution", "")]))
    return " \n ".join(p.lower() for p in parts if p)


def recommend_roles(parsed: ParsedCv, top_n: int = 3, min_match: float = 0.2) -> list[dict]:
    corpus = _corpus(parsed)
    results: list[dict] = []
    for role, keywords in ROLE_KEYWORDS.items():
        matched = [k for k in keywords if k in corpus]
        missing = [k for k in keywords if k not in corpus]
        score = len(matched) / max(1, len(keywords))
        if score < min_match:
            continue
        reasons = []
        if matched:
            reasons.append("Your profile already shows: " + ", ".join(matched[:4]) + ".")
        if missing:
            reasons.append(
                "Not yet visible in your CV (add evidence if true): "
                + ", ".join(missing[:3]) + "."
            )
        results.append(
            {
                "role": role,
                "match_pct": round(score * 100, 1),
                "matched": matched,
                "missing": missing,
                "reason": " ".join(reasons),
            }
        )
    results.sort(key=lambda r: r["match_pct"], reverse=True)
    return results[:top_n]

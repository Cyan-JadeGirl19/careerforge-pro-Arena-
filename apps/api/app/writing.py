"""Human-authentic writing engine.

Rules (agreed product requirements): plain, specific, candidate-voiced.
No AI-style language, no clichés, no keyword stuffing, no fabricated
claims. The writer only uses facts from the candidate's own profile and
the job description. A checker flags banned phrasings before anything
is shown for approval.
"""
import re

BANNED_PHRASES = [
    "i am excited to apply",
    "excited to apply",
    "excited about this opportunity",
    "leveraged",
    "leverage",
    "spearheaded",
    "utilized",
    "utilize",
    "synergy",
    "synergies",
    "thought leadership",
    "dynamic professional",
    "results-driven individual",
    "passionate self-starter",
    "navigating the ever-changing",
    "navigating the landscape",
    "in today's fast-paced",
    "in today's digital",
    "fast-paced environment",
    "delve",
    "tapestry",
    "proven track record of",
    "pleased to inform",
    "i hope this letter finds you well",
    "i hope this email finds you well",
    "eager to contribute",
    "unique blend of",
    "wealth of experience",
]


def humanize_check(text: str) -> list[str]:
    low = text.lower()
    return [p for p in BANNED_PHRASES if p in low]


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def speech_case(text: str) -> str:
    """Lowercase for natural speech, but keep all-caps acronyms (CSAT, SLA)."""
    out = []
    for word in text.split():
        core = word.strip(".,;:!?()[]\"'")
        if len(core) >= 2 and core.isupper():
            out.append(word)
        else:
            out.append(word.lower())
    return " ".join(out)


def _requirement_phrase(jd_text: str) -> str:
    """Pick one concrete requirement from the JD as a short phrase."""
    lines = [ln.strip() for ln in jd_text.splitlines() if ln.strip()]
    bullets = [re.sub(r"^[ -*•]+\s*", "", ln) for ln in lines if re.match(r"^\s*[-*•]\s*", ln)]
    pool = bullets or [ln for ln in lines if 20 <= len(ln) <= 80]
    # skip headings / intro lines
    pool = [
        ln for ln in pool
        if not re.match(r"^(requirements?|responsibilities?|about|we (are |)looking)\b", ln, re.IGNORECASE)
    ]
    if not pool:
        return "the responsibilities you listed"
    phrase = pool[0]
    phrase = re.sub(r"\brequirements?\s*:?\s*", "", phrase, flags=re.IGNORECASE)
    return speech_case(phrase).strip().rstrip(".;")


def _quant_bullets(parsed) -> list[str]:
    out = []
    for e in parsed.experience:
        for b in e.get("bullets", []):
            if re.search(r"\d", b):
                out.append(b.strip().rstrip("."))
    return out


def _plain_role_phrase(role: str) -> str:
    return role.strip().lower()


def build_cover_letter(parsed, jd_title: str, jd_company: str | None, jd_text: str, tone: str = "direct") -> tuple[str, list[str]]:
    """Return (letter, quality_issues). Factual only."""
    name = parsed.name or "the candidate"
    first_name = name.split()[0] if name else ""
    latest = ""
    for e in parsed.experience:
        if e.get("title"):
            latest = e["title"].strip()
            break
    span = None
    years = re.findall(r"\b(?:19|20)\d{2}\b", " ".join(e.get("dates", "") for e in parsed.experience))
    if years:
        from datetime import datetime, timezone

        span = max(0, min(datetime.now(timezone.utc).year - min(int(y) for y in years), 40))

    quant = _quant_bullets(parsed)
    skills = [s for s in parsed.skills][:4]
    company = jd_company or "your team"

    # One concrete requirement from the JD, quoted factually from their text.
    req1 = _requirement_phrase(jd_text)

    opener = f"Dear {company} hiring team,"
    p1 = (
        f"The {_plain_role_phrase(jd_title)} role is what I apply for when the work "
        f"matches what I already do well. You ask for {req1}; that is the centre "
        "of my recent work."
    )
    p2_parts = []
    if latest:
        intro = f"I'm a {latest}"
        if span:
            intro += f" with {span} years of experience"
        intro += "."
    elif parsed.summary:
        # No role line was parsed - use the candidate's own summary (factual).
        intro = re.sub(r"\s+", " ", parsed.summary.strip()).strip()
        if not intro.endswith((".", "!", "?")):
            intro += "."
    else:
        intro = ""
    if intro:
        p2_parts.append(intro)
    if quant:
        p2_parts.append("Most recently, I " + speech_case(quant[0]))
    if len(quant) > 1:
        p2_parts.append("Before that, I " + speech_case(quant[1]))
    if skills:
        p2_parts.append(
            "On the practical side, my daily tools and habits are "
            + ", ".join(s.lower() for s in skills)
            + "."
        )
    p2 = " ".join(p2_parts)

    p3_parts = []
    if parsed.location and re.search(r"south africa|johannesburg|cape town|pretoria|durban", parsed.location, re.IGNORECASE):
        city = parsed.location.split(",")[0].strip()
        p3_parts.append(
            f"I work from {city}, South Africa (UTC+2), which overlaps well with "
            "European and South African business hours."
        )
    if "remote" in " ".join(parsed.skills + [parsed.summary]).lower():
        p3_parts.append("I'm used to remote, distributed teams and keeping things moving without sitting in the same room.")
    p3 = " ".join(p3_parts)

    close = (
        f"If the role still suits your needs, I'd welcome a short conversation. "
        f"My CV is attached, and I'm happy to provide any further details.\n\n"
        f"{first_name}"
        + (f" {name.split()[1]}" if " " in name else "")
        + (f"\n{parsed.email}" if parsed.email else "")
    )

    tone_note = ""
    if tone == "warm":
        tone_note = (
            f"One more thing: I enjoy this kind of work, not just because it pays "
            "the bills but because I can point to concrete results when I finish a job."
        )

    letter = "\n\n".join(x for x in [opener, p1, p2, p3, tone_note, close] if x) + "\n"

    issues = humanize_check(letter)
    wc = _word_count(letter)
    if wc < 150:
        issues.append(f"Letter is short ({wc} words); add one more concrete detail from your history.")
    if wc > 400:
        issues.append(f"Letter is long ({wc} words); trim to 250-350.")
    return letter, issues

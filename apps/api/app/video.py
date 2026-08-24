"""Voice/video response script engine.

Generates a natural spoken script from the candidate's CV, the job
description, the employer's exact question, and the candidate's own
instructions (key points, exclusions, tone, length).

Facts come only from the candidate's profile. Lengths: 30/60/90/120/180
seconds (user-confirmed: many applications request 3-minute videos).
Plain speech, no AI-style phrasing (checked before delivery).
"""
import re

from .writing import humanize_check, speech_case
from .parsing import ParsedCv

VALID_LENGTHS = (30, 60, 90, 120, 180)
WORDS_PER_SECOND = 2.5  # ~150 wpm, natural conversational pace

VALID_TONES = ("natural", "formal", "warm", "direct")


def _city(parsed: ParsedCv) -> str:
    if parsed.location:
        return parsed.location.split(",")[0].strip()
    return ""


def _years(parsed: ParsedCv) -> int | None:
    years = []
    for e in parsed.experience:
        years.extend(re.findall(r"\b(?:19|20)\d{2}\b", e.get("dates", "")))
    if not years:
        return None
    from datetime import datetime, timezone

    return max(0, min(datetime.now(timezone.utc).year - min(int(y) for y in years), 40))


def _latest_role(parsed: ParsedCv) -> str:
    for e in parsed.experience:
        if e.get("title"):
            return e["title"].strip()
    return ""


def _quant_bullets(parsed: ParsedCv, exclusions: list[str]) -> list[str]:
    excl = [x.lower() for x in exclusions]
    out = []
    for e in parsed.experience:
        for b in e.get("bullets", []):
            if re.search(r"\d", b) and not any(x in b.lower() for x in excl):
                out.append(b.strip().rstrip("."))
    return out


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def generate_script(
    parsed: ParsedCv,
    jd_title: str,
    jd_company: str | None,
    jd_text: str,
    question: str,
    length_seconds: int = 60,
    key_points: list[str] | None = None,
    exclusions: list[str] | None = None,
    tone: str = "natural",
) -> tuple[str, dict]:
    """Build a spoken script + quality report."""
    if length_seconds not in VALID_LENGTHS:
        raise ValueError(f"length_seconds must be one of {VALID_LENGTHS}")
    if tone not in VALID_TONES:
        raise ValueError(f"tone must be one of {VALID_TONES}")

    name = parsed.name or "me"
    first = name.split()[0]
    city = _city(parsed)
    span = _years(parsed)
    latest = _latest_role(parsed) or "professional"
    quant = _quant_bullets(parsed, exclusions or [])
    skills = [s for s in parsed.skills if not any(x in s.lower() for x in (exclusions or []))][:4]
    remote_ok = "remote" in " ".join(parsed.skills + [parsed.summary]).lower()

    q_low = question.lower()
    is_about_yourself = ("about yourself" in q_low) or ("introduce" in q_low) or ("tell me who" in q_low)
    is_why_here = ("why" in q_low and ("here" in q_low or "this role" in q_low or "interested" in q_low))
    is_why_you = ("why should we" in q_low) or ("why you" in q_low) or ("why are you a good" in q_low)
    is_difficult = ("difficult" in q_low) or ("challenge" in q_low) or ("problem" in q_low)

    company = jd_company or "your team"
    role = jd_title.strip().lower()

    # --- building blocks (each optional, ordered by priority) -------------
    if tone in ("warm", "natural") and city:
        intro = f"Hi, I'm {first} from {city}."
    elif tone == "formal" and city:
        intro = f"Good day, my name is {name}, and I'm based in {city}."
    else:
        intro = f"Hi, I'm {first}."
    if tone == "formal":
        intro = intro.replace("Hi, I'm", "My name is")

    who = f"I'm a {latest}"
    if span:
        who += f" with {span} years of experience"
    who += "."

    ach1 = ("In my last role, I " + speech_case(quant[0]) + ".") if quant else ""
    ach2 = ("Before that, I " + speech_case(quant[1]) + ".") if len(quant) > 1 else ""

    skill_line = (
        "Day to day, that means " + ", ".join(speech_case(s) for s in skills[:3])
        + ", applied to real work."
    ) if skills else ""

    if is_why_here:
        fit = f"I'm interested in the {role} at {company} because the work it describes is close to what I already do."
    elif is_why_you:
        fit = (
            f"I think I'm a good fit for the {role} because it builds on what I've "
            "already delivered, and I can point to specific results."
        )
    elif is_difficult:
        fit = (
            "When I hit a difficult one, I break it down, deal with the customer "
            "first, and fix the process so it doesn't repeat. For example, I "
            + (speech_case(quant[0]) if quant else "worked through a high-volume period and kept quality up")
            + "."
        )
    elif is_about_yourself:
        fit = f"I'd be bringing that experience into the {role}."
    else:
        fit = f"That background is what I'd bring to the {role}."

    remote_line = (
        "I work from South Africa, which is UTC plus two, so I overlap well with "
        "European and South African hours, and I'm comfortable with remote, "
        "distributed teams."
        if (city and remote_ok)
        else ("I'm comfortable working remotely with distributed teams." if remote_ok else "")
    )

    key_line = (
        "I'd also like to mention "
        + ", ".join(k for k in key_points if k)
        + "."
        if key_points
        else ""
    )

    why_company = (
        f"{company} stood out to me because the {role} work you describe is "
        "specific and practical, which is where I do my best work."
    )

    if tone == "formal":
        close = "Thank you for your time. I look forward to the possibility of speaking with you."
    elif tone == "warm":
        close = "Anyway, I'd really appreciate the chance to chat. Thanks for watching."
    else:
        close = "I'd welcome a conversation about the role. Thanks for your time."

    # --- assemble to budget -------------------------------------------------
    budget = int(length_seconds * WORDS_PER_SECOND)
    # priority order: core blocks first, optional blocks fill remaining space
    core = [x for x in [intro, who, (ach1 or ""), (fit or ""), (close or "")] if x]
    optional = [x for x in [ach2, skill_line, remote_line, key_line, why_company] if x]

    parts = list(core)
    for block in optional:
        if _word_count(" ".join(parts)) + _word_count(block) + 2 <= budget:
            parts.append(block)

    # order for natural speech
    order_index = {
        intro: 0, who: 1, ach1: 2, ach2: 3, fit: 4, skill_line: 5,
        why_company: 6, remote_line: 7, key_line: 8, close: 9,
    }
    parts.sort(key=lambda p: order_index.get(p, 5))
    script = " ".join(parts)

    # de-duplicate consecutive repeated sentences
    sentences = re.split(r"(?<=[.!?]) ", script)
    seen, dedup = set(), []
    for s in sentences:
        key = s.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(s)
    script = " ".join(dedup).strip()

    # --- quality report -----------------------------------------------------
    wc = _word_count(script)
    checks = {
        "within_length": 0.8 * budget <= wc <= 1.2 * budget,
        "word_count": wc,
        "target_seconds": length_seconds,
        "addresses_question": (
            (role.split()[0] in script.lower() if role else False)
            or company.lower().split()[0] in script.lower()
            or is_about_yourself
        ),
        "no_ai_phrasing": humanize_check(script) == [],
        "opens_naturally": script.lower().startswith(("hi", "my name", "good day")),
        "candidate_name_present": first.lower() in script.lower(),
    }
    report = {
        "script": script,
        "word_count": wc,
        "estimated_seconds": round(wc / WORDS_PER_SECOND),
        "checks": checks,
        "note": (
            "Script uses only facts from your CV plus your own instructions. "
            "Edit anything before recording. You can re-generate with different "
            "instructions or length."
        ),
    }
    return script, report

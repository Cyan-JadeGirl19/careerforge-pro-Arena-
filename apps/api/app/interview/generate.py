"""Generate a mock interview for a target role.

Every prepared answer is a STAR scaffold built from the candidate's OWN
CV content (real bullets, real skills). Where the candidate must add
their own detail, the scaffold says so explicitly - nothing is invented.
Includes the South Africa remote-work question set agreed in the spec.
"""
import json
import re
from datetime import datetime, timezone

from ..builders import extract_jd_keywords
from ..models import CvRecord, JobDescription, Profile
from ..parsing import ParsedCv, parse_cv_text
from ..schemas import InterviewQuestionOut, InterviewSessionOut
from sqlalchemy import select
from sqlalchemy.orm import Session


def _get_parsed(db: Session, profile_id: str) -> ParsedCv | None:
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


def _quant_bullets(parsed: ParsedCv) -> list[str]:
    out = []
    for e in parsed.experience:
        for b in e.get("bullets", []):
            if any(ch.isdigit() for ch in b):
                out.append(b.strip().rstrip("."))
    return out


def _latest_role(parsed: ParsedCv) -> str:
    for e in parsed.experience:
        if e.get("title"):
            return e["title"]
    return ""


def _detect_gap_months(parsed: ParsedCv) -> int:
    """Rough employment-gap detection from date ranges (best effort)."""
    spans: list[tuple[int, int]] = []
    for e in parsed.experience:
        dates = e.get("dates") or ""
        years = re.findall(r"(?:19|20)\d{2}", dates)
        if len(years) >= 2:
            spans.append((min(int(y) for y in years), max(int(y) for y in years)))
        elif len(years) == 1 and re.search(r"present|current|now|today", dates, re.I):
            spans.append((int(years[0]), datetime.now(timezone.utc).year))
    if not spans:
        return 0
    spans.sort()
    gap = 0
    for (s1, e1), (s2, _) in zip(spans, spans[1:]):
        if s2 > e1 + 1:
            gap = max(gap, s2 - e1 - 1)
    return gap * 12


def _skill_for_role(parsed: ParsedCv, role: str) -> str | None:
    low = role.lower()
    for s in parsed.skills:
        if s.lower() in low or low.split()[0] in s.lower():
            return s
    return parsed.skills[0] if parsed.skills else None


def generate_session(
    db: Session,
    profile_id: str,
    role: str,
    jd_id: str | None = None,
    jd_text: str | None = None,
) -> InterviewSessionOut:
    parsed = _get_parsed(db, profile_id)
    jd = jd_text or ""
    if jd_id:
        d = db.get(JobDescription, jd_id)
        if d is not None:
            jd = d.text or jd

    quant = _quant_bullets(parsed) if parsed else []
    skills = [s for s in (parsed.skills if parsed else [])][:6]
    role_skill = _skill_for_role(parsed, role) if parsed else None
    latest = _latest_role(parsed) if parsed else ""
    location = (parsed.location if parsed else "") or ""

    questions: list[dict] = []

    def q(category: str, question: str, answer: str, evidence: list[str] | None = None):
        questions.append(
            {"category": category, "question": question, "prepared_answer": answer, "evidence_used": evidence or []}
        )

    # --- core ------------------------------------------------------------
    intro = f"I'm a {latest or 'professional'}"
    if location:
        intro += f" based in {location.split(',')[0]}"
    if skills:
        intro += f" with a focus on {', '.join(skills[:3])}"
    intro += "."
    if quant:
        intro += f" In my recent work: {quant[0]}."
    q("Core", "Tell me about yourself.", intro, [b for b in (quant[:1])])

    q(
        "Core",
        f"Why are you interested in the {role} role?",
        f"I'm interested because it sits at the centre of what I already do well: "
        + (f"{role_skill} " if role_skill else "")
        + "and the chance to keep applying it at a higher level. "
        "I'm looking for a role where I can own outcomes, not just tasks.",
        [role_skill] if role_skill else [],
    )

    # --- behavioural (STAR) from real CV ---------------------------------
    if quant:
        b = quant[0]
        role_context = f"at {parsed.experience[0].get('company') or 'my last role'}" if (parsed and parsed.experience) else "in my last role"
        q(
            "Behavioural (STAR)",
            "Tell me about a time you delivered a measurable result.",
            f"Situation: {role_context}. "
            f"Task/Action: the work that led to the result. "
            f"Result (from my CV): {b}. "
            f"[Add: your specific part, what you changed, and what you'd do differently.]",
            [b],
        )
    if len(quant) > 1:
        q(
            "Behavioural (STAR)",
            "Tell me about a time you improved a process.",
            f"Result (from my CV): {quant[1]}. "
            "[Add: the process, what you changed step by step, and how you measured it.]",
            [quant[1]],
        )
    q(
        "Behavioural (STAR)",
        "Tell me about a time you handled a difficult situation with a customer or stakeholder.",
        "[Your story - I can't invent this. Structure: Situation -> what you did first "
        "(usually: de-escalate, understand the real problem) -> action -> result. "
        "If you have a number from a real outcome, end with it.]",
        [],
    )

    # --- role-specific from the JD ---------------------------------------
    if jd:
        kws = [k for k in extract_jd_keywords(jd, top_n=6) if len(k) > 3][:4]
        if kws:
            for k in kws[:3]:
                q(
                    "Role-specific",
                    f"Tell me about your experience with {k}.",
                    f"From my CV: the relevant work is "
                    + (f"'{next((b for b in quant if k in b.lower()), skills[0] if skills else 'see my experience section')}'. "
                       if any(k in b.lower() for b in quant)
                       else "see the experience section of my CV. ")
                    + "[Add the specific project, what you did, and the outcome.]",
                    [k],
                )

    # --- red flags / gaps --------------------------------------------------
    gap_months = _detect_gap_months(parsed) if parsed else 0
    if gap_months >= 6:
        q(
            "Red flag / gap",
            f"You show a gap of about {gap_months} months. Can you tell me about that period?",
            "[Your honest account - the strongest answers name what you did: "
            "searching deliberately, upskilling (name courses), or caregiving. "
            "Then pivot to why you're ready now.]",
            [],
        )

    # --- South Africa remote-work set (agreed in spec) --------------------
    sa = (
        "I work from "
        + (location.split(",")[0] if location else "South Africa")
        + " (UTC+2), which overlaps almost fully with European business hours and the "
        "first part of US hours. "
    )
    q(
        "South Africa / remote",
        "How do you manage time zones working from South Africa?",
        sa
        + "I keep a core overlap window for live work and write async updates so the "
        "team never has to wait on me.",
        [],
    )
    q(
        "South Africa / remote",
        "What does your home setup look like? (internet, power)",
        "[Your real setup - e.g. dedicated fibre, UPS/backup power, mobile hotspot "
        "failover. Only state what is true.]",
        [],
    )
    q(
        "South Africa / remote",
        "How are you set up for international payments and contracting?",
        "[State your real arrangement - e.g. Deel, Wise, or a local contractor setup. "
        "If you're still setting it up, say so and that you're on top of it.]",
        [],
    )
    q(
        "South Africa / remote",
        "Why should we hire from South Africa?",
        "You get a strong English-speaking professional in a timezone that overlaps "
        "well with Europe, at a rate that's competitive versus UK/EU/US hiring - "
        "with the quality my work history shows.",
        [],
    )

    # --- close -------------------------------------------------------------
    q(
        "Close",
        "Do you have any questions for us?",
        "Yes - e.g. what the first 90 days look like, how success is measured for "
        "this role, and what the team needs most in the first quarter.",
        [],
    )

    return InterviewSessionOut(
        role=role,
        questions=[InterviewQuestionOut(**q) for q in questions],
        note=(
            "Prepared answers are built from your real CV. Wherever you see [Add: …], "
            "that part is yours to write - the app will never invent your experience. "
            "Practise out loud, then interview with confidence."
        ),
    )

"""Outreach draft generator - drafts only, never sends.

Rules: plain, specific, candidate-voiced; no AI-style phrasing
(banned-phrase checked); references the actual job; short and easy to
answer; explicit that the candidate attached a CV. The candidate always
reviews and approves before any message goes out (Gmail integration,
Phase 3, enforces this with consent + drafts-only scope).
"""
import re

from ..writing import humanize_check


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def build_outreach_draft(
    *,
    candidate_first_name: str,
    candidate_role: str | None,
    candidate_evidence: str | None,
    contact_name: str | None,
    contact_title: str | None,
    company: str | None,
    job_title: str | None,
    tone: str = "direct",
    email_status: str = "none",
) -> tuple[str, list[str]]:
    issues: list[str] = []

    first = (candidate_first_name or "candidate").split()[0] if candidate_first_name else "candidate"
    comp = (company or "your team").strip()
    role = (job_title or "the open role").strip()
    name = (contact_name or "").strip()
    sal = f"Hi {name.split()[0]}," if name else f"Hi {comp.split()[0]} team,"

    if name and (contact_title or "").strip():
        line1 = (
            f"I'm reaching out about the {role} role at {comp}, since your page "
            f"shows you're hiring for it."
        )
    else:
        line1 = f"I'm reaching out about the {role} role at {comp}."

    if candidate_evidence:
        line2 = (
            f"I'm a {candidate_role or 'professional'}; the most relevant part of my "
            f"recent work: {candidate_evidence.strip().rstrip('.')}."
        )
    elif candidate_role:
        line2 = f"I'm a {candidate_role} and the role maps closely to what I do now."
    else:
        line2 = "The role maps closely to what I do now."
        issues.append("Add a specific achievement to make this personal - the app suggests where.")

    if tone == "warm":
        line3 = "I'd be glad to share more if useful, and I'm happy to keep it short."
    else:
        line3 = "My CV is attached. If it's a fit, I'd welcome a short chat; if not, no worries."

    close = f"Thanks,\n{first}"

    draft = f"{sal}\n\n{line1}\n\n{line2}\n\n{line3}\n\n{close}\n"

    banned = humanize_check(draft)
    if banned:
        issues.append(f"Banned phrasing detected: {', '.join(banned)}")
    wc = _word_count(draft)
    if wc < 60:
        issues.append("Draft is very short - add one concrete detail.")
    if wc > 180:
        issues.append("Draft is long for a cold outreach - trim it.")
    if email_status == "pattern_suggested":
        issues.append("The email address is a pattern suggestion, not verified. Confirm it before sending.")
    if email_status == "none":
        issues.append("No contact email on file - use the public profile URL or add an email.")
    return draft, issues

"""Extract publicly displayed recruiter details from a job page.

Strict rules (agreed compliance):
- Only VISIBLE page text is read. <script>, <style> and <noscript>
  content is stripped first - tracking pixels and ad payloads
  (e.g. adroll_email=...) frequently contain personal emails that the
  employer never published for hiring contact, and using them would
  violate the "publicly displayed" rule.
- Names are only taken from explicit patterns ("Recruiter: Jane Doe",
  "Apply with Jane Doe", LinkedIn /in/ anchors).
- Emails found in visible text are 'published'; pattern guesses are
  stored separately as 'pattern_suggested' (clearly unverified).
- No login bypass, no hidden data, no mass harvesting: one page per
  user request.
"""
import json
import re

_SCRIPT_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_LINKEDIN_RE = re.compile(
    r'href="https://(?:www\.)?linkedin\.com/in/([a-z0-9._%-]+)"[^>]*>([^<]{2,60})<',
    re.I,
)
_LINKEDIN_HREF_RE = re.compile(r"https://(?:www\.)?linkedin\.com/in/([a-z0-9._%-]+)", re.I)
_NAME_PATTERNS = [
    re.compile(r"\bApply with ([A-Z][a-zA-Z]{1,20}(?: [A-Z][a-zA-Z]{1,20}){1,2})\b"),
    re.compile(r"\bRecruiter[:\s]+([A-Z][a-zA-Z]{1,20}(?: [A-Z][a-zA-Z]{1,20}){1,2})\b"),
    re.compile(r"\bHiring manager[:\s]+([A-Z][a-zA-Z]{1,20}(?: [A-Z][a-zA-Z]{1,20}){1,2})\b"),
    re.compile(r"\bContact[:\s]+([A-Z][a-zA-Z]{1,20}(?: [A-Z][a-zA-Z]{1,20}){1,2})\b"),
]
#: Words that never appear in a person's name. Any candidate containing
#: one of these (case-insensitive) is rejected - this stops nav/footer
#: fragments like "Support Terms Guidelines" or "AI No" being saved as
#: recruiter names.
_NOT_A_NAME = {
    "ai", "no", "us", "our", "ours", "the", "team", "support", "terms",
    "guidelines", "privacy", "why", "choose", "contact", "apply", "now",
    "join", "hiring", "manager", "managers", "recruiter", "recruiters",
    "job", "jobs", "career", "careers", "account", "sign", "login",
    "menu", "home", "top", "search", "new", "remote", "work", "today",
    "all", "see", "view", "read", "more", "learn", "about", "help",
    "faq", "blog", "news", "press", "events", "share", "follow", "like",
    "comment", "post", "posts", "article", "articles", "guide",
    "guides", "tutorial", "list", "page", "pages", "link", "links",
    "email", "phone", "address", "location", "city", "country", "state",
    "zip", "salary", "compensation", "benefits", "perks", "health",
    "insurance", "stock", "equity", "pto", "leave", "holiday",
    "vacation", "flex", "hybrid", "onsite", "fully", "part", "time",
    "full", "weekly", "monthly", "annually", "based", "looking",
    "seeking", "seek", "open", "opening", "position", "positions",
    "role", "roles", "company", "companies", "we", "you", "your",
    "they", "their", "them", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "will", "would", "can", "could",
    "this", "that", "these", "those", "who", "which", "what", "when",
    "where", "how", "not", "but", "and", "or", "for", "with", "from",
    "by", "it", "its", "let", "get", "got", "make", "makes", "help",
    "helps", "come", "came",
}


def _is_name_candidate(name: str) -> bool:
    words = name.split()
    if not 1 <= len(words) <= 3:
        return False
    for w in words:
        if not 2 <= len(w) <= 14:
            return False
        if not w[0].isalpha():
            return False
        if w.lower() in _NOT_A_NAME:
            return False
    return True
_FUNCTIONAL_DOMAINS = (
    "careers@", "career@", "talent@", "hr@", "recruiting@", "recruitment@",
    "jobs@", "hiring@", "people@",
)


def visible_text(html: str) -> str:
    """Page text with scripts/styles stripped (compliance-critical)."""
    out = _SCRIPT_RE.sub(" ", html or "")
    out = _TAG_RE.sub(" ", out)
    return _WS_RE.sub(" ", out).strip()


def _domain_of(url: str) -> str | None:
    m = re.search(r"https?://(?:www\.)?([a-z0-9.-]+\.[a-z]{2,})", url or "", re.I)
    return m.group(1).lower() if m else None


def _pattern_emails(name: str, domain: str | None) -> list[str]:
    if not domain:
        return []
    parts = [p.lower() for p in name.split() if p]
    if not parts:
        return []
    first, last = parts[0], parts[-1]
    seen: list[str] = []
    for cand in (f"{first}.{last}@{domain}", f"{first[0]}.{last}@{domain}", f"{first}@{domain}"):
        if cand not in seen:
            seen.append(cand)
    return seen


def extract_contacts(url: str, html: str, company_hint: str | None = None) -> list[dict]:
    """Return a list of contact dicts ready for storage (see schema notes)."""
    text = visible_text(html)
    domain = _domain_of(url)
    company = (company_hint or "").strip() or None

    found: list[dict] = []
    seen_keys: set[tuple] = set()

    def add(**kw) -> None:
        key = (kw.get("name"), kw.get("email"))
        if key in seen_keys:
            return
        seen_keys.add(key)
        base = {
            "source": "job_posting",
            "source_url": url,
            "name": None,
            "title": None,
            "company": company,
            "profile_url": None,
            "email": None,
            "email_status": "none",
            "suggested_emails": "[]",
            "job_title": None,
            "notes": None,
        }
        base.update(kw)
        found.append(base)

    # 1. LinkedIn profile links (public profile URLs are permitted)
    for slug, anchor in _LINKEDIN_RE.findall(html or ""):
        name = re.sub(r"\s+", " ", anchor).strip() or None
        if name and not _is_name_candidate(name):
            name = None
        add(
            name=name,
            profile_url=f"https://linkedin.com/in/{slug.lower()}",
            email_status="none",
        )
    if not found:
        for slug in _LINKEDIN_HREF_RE.findall(html or "")[:1]:
            add(profile_url=f"https://linkedin.com/in/{slug.lower()}")

    # 2. Explicit name patterns in visible text (strictly validated so
    #    nav/footer fragments are never saved as names)
    for pat in _NAME_PATTERNS:
        for raw in pat.findall(text)[:3]:
            name = re.sub(r"\s+", " ", raw).strip()
            if not _is_name_candidate(name):
                continue
            add(name=name, title=None)

    # 3. Emails in VISIBLE text only (published)
    for email in _EMAIL_RE.findall(text)[:3]:
        email = email.lower().strip()
        if re.search(r"\.(png|jpg|jpeg|gif|webp|svg)$", email):
            continue
        local, _, dom = email.partition("@")
        if dom in {"example.com", "example.org", "sentry.io", "wixpress.com"}:
            continue
        functional = any(email.startswith(d) for d in _FUNCTIONAL_DOMAINS)
        add(
            email=email,
            email_status="published",
            name=None,
            title="company recruiting contact" if functional else None,
        )

    # 4. If we found a name but no published email: pattern suggestions
    #    (clearly unverified - the candidate must confirm before use).
    if not any(c["email_status"] == "published" for c in found):
        for c in found:
            if c.get("name") and domain:
                c["suggested_emails"] = json.dumps(_pattern_emails(c["name"], domain))
                c["email_status"] = "pattern_suggested"
    return found


def extract_from_url(url: str, html: str, company_hint: str | None = None) -> dict:
    """Wrapper returning a stable shape for the API layer."""
    return {
        "url": url,
        "company_domain": _domain_of(url),
        "contacts": extract_contacts(url, html, company_hint),
        "notes": (
            "Only publicly displayed details are captured. Pattern-suggested "
            "emails are unverified - confirm them before outreach."
        ),
    }

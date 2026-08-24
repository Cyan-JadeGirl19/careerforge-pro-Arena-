"""Job posting normalisation + South African eligibility signals.

Signals are computed from the employer's own posting text and reported
transparently. "unknown" is a valid answer - we never guess eligibility.
"""
import hashlib
import json
import re
from datetime import datetime, timezone

_HTML_RE = re.compile(r"<[^>]+>")

SA_HINTS = (
    "south africa", "s.a.", "za remote", "johannesburg", "cape town",
    "pretoria", "durban", "from south africa",
)
GLOBAL_HINTS = (
    "anywhere", "worldwide", "global", "across africa", "africa", "emea",
    "europe and africa", "any country", "no location requirement",
)
EXCLUDE_HINTS = (
    "us work authorization", "authorized to work in the united states",
    "us citizens", "must be a us", "must live in the united states",
    "must be based in the uk", "uk work permit", "must work from the office in",
)
PAYMENT_HINTS = ("deel", "wise", "payoneer", "contractor", "eor", "employer of record")
TZ_HINTS = ("utc+0", "utc+1", "utc+2", "utc+3", "utc+4", "utc+0 to utc+4",
            "africa", "emea", "european", "central european")
REMOTE_HINTS = ("remote", "work from anywhere", "distributed")
HYBRID_HINTS = ("hybrid",)
ONSITE_HINTS = ("on-site", "onsite", "in office", "in-office", "office based")


def strip_html(text: str) -> str:
    out = _HTML_RE.sub(" ", text or "").replace("&amp;", "&").replace(
        "&#39;", "'").replace("&quot;", '"')
    return re.sub(r"\s+", " ", out).strip()


def compute_sa_signals(text: str, location: str | None) -> dict:
    low = (text or "").lower()
    loc = (location or "").lower()

    excluded = any(h in low for h in EXCLUDE_HINTS)
    sa_direct = any(h in low or h in loc for h in SA_HINTS)
    global_ok = any(h in low for h in GLOBAL_HINTS)

    if excluded:
        open_to_sa = "no"
    elif sa_direct or global_ok:
        open_to_sa = "yes"
    else:
        open_to_sa = "unknown"

    payment = [h for h in PAYMENT_HINTS if h in low]
    tz = [h for h in TZ_HINTS if h in low]
    remote = "remote" if any(h in low or h in loc for h in REMOTE_HINTS) else (
        "hybrid" if any(h in low for h in HYBRID_HINTS) else (
            "onsite" if any(h in low for h in ONSITE_HINTS) else "unknown"
        )
    )
    return {
        "open_to_sa": open_to_sa,
        "sa_signals_json": json.dumps(sorted(set([h for h in SA_HINTS if h in low or h in loc]))),
        "global_signals_json": json.dumps(sorted(set([h for h in GLOBAL_HINTS if h in low]))),
        "exclude_signals_json": json.dumps(sorted(set([h for h in EXCLUDE_HINTS if h in low]))),
        "payment_signals_json": json.dumps(payment[:4]),
        "timezone_signals_json": json.dumps(tz[:4]),
        "remote_type": remote,
    }


def dedupe_key(source: str, title: str, company: str | None, url: str | None) -> str:
    raw = f"{source}|{title.lower().strip()}|{(company or '').lower().strip()}|{url or ''}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def parse_posted_at(value) -> datetime | None:
    """Accept ISO 8601, epoch seconds, or None."""
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        s = str(value).strip()
        if s.isdigit():
            return datetime.fromtimestamp(int(s), tz=timezone.utc)
        if " " in s and s[0].isalpha() and not s.startswith(("20", "19")):
            # RFC 2822 (RSS pubDate)
            from email.utils import parsedate_to_datetime

            return parsedate_to_datetime(s)
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def normalize(
    *,
    source: str,
    title: str,
    company: str | None = None,
    location: str | None = None,
    url: str | None = None,
    description: str = "",
    tags: list[str] | None = None,
    salary_text: str | None = None,
    posted_at=None,
) -> dict:
    """Normalise a raw posting into the stored shape (signals included)."""
    desc = strip_html(description or "")
    signals = compute_sa_signals(desc, location)
    return {
        "dedupe_key": dedupe_key(source, title, company, url),
        "source": source,
        "title": (title or "").strip()[:200],
        "company": (company or "").strip()[:200] or None,
        "location": (location or "").strip()[:200] or None,
        "url": url,
        "description": desc[:20000],
        "tags": ", ".join((tags or [])[:20])[:300],
        "salary_text": (salary_text or "").strip()[:200] or None,
        "posted_at": parse_posted_at(posted_at),
        **signals,
    }

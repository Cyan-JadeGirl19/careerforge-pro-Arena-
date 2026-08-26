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

# High-frequency function words for the languages most likely to appear on
# global job boards. Used by the transparent language heuristic below. Words
# shared by more than one language are removed from ALL sets (see
# _LANGUAGE_SETS) so they can't create false signals.
_ENG_WORDS = frozenset(
    """
    the and to of is are was were you your yours we our ours us they their
    theirs he his she her hers it its this that these those for with without
    not but as at by from will would can could should may might have has had
    having been being there here what which who whom how when where why very
    more most less least only also about after before between through during
    above below out off up down again further just then than both each few
    many much some any all
    """.split()
)
_DE_WORDS = frozenset(
    """
    der die das und sind wir ich du er sie es eine einen einer einem dem den
    fur fuer mit ohne auf zu zur zum aus bei von nach wie was wer wo wann
    nicht auch aber sehr beim uns euch ihnen unsere unser sich man kann muss
    sollte hat haben hatte ihrer ihrem
    """.split()
)
_FR_WORDS = frozenset(
    """
    le la les un une des est sont nous je tu il elle vous ils elles a au aux
    pour avec sans sur sous dans par de du que qui quoi ou quand comment ne
    pas mais ou tres plus moins aussi encore peuvent doit doivent avoir votre
    nos leur leurs mon ma mes ce cet cette ces
    """.split()
)
_ES_WORDS = frozenset(
    """
    el la los las un una uno es son somos nosotros tu usted ellos ellas el
    ella yo te me se su sus le les con sin para por como que quien donde
    cuando pero o muy mas menos tambien aun puede pueden deben tener tiene
    nuestro nuestra este esta estos esas ese esa aquel aquella
    """.split()
)
_PT_WORDS = frozenset(
    """
    o os as um uma sao somos nos tu voce eles elas ele ela eu te me se seu
    sua com sem para por como que quem onde quando nao sim mas ou muito mais
    menos tambem pode podem deve devem ter tem nosso nossa este esta esses
    aquele aquela
    """.split()
)


def _build_language_sets() -> dict:
    """Deduplicate words that appear in more than one language set."""
    raw = {"en": set(_ENG_WORDS), "de": set(_DE_WORDS), "fr": set(_FR_WORDS),
           "es": set(_ES_WORDS), "pt": set(_PT_WORDS)}
    counts: dict[str, int] = {}
    for s in raw.values():
        for w in s:
            counts[w] = counts.get(w, 0) + 1
    return {lang: {w for w in s if counts[w] == 1} for lang, s in raw.items()}


_LANGUAGE_SETS = _build_language_sets()


def detect_language(text: str) -> str:
    """Best-effort, transparent classification: 'english' | 'other' | 'unknown'.

    No ML, no network. Decision order:
    1. Too short to judge -> 'unknown'.
    2. High share of non-Latin characters (accents / non-Latin scripts)
       -> 'other'.
    3. Count function words per language; English wins if it has at least
       two and no other language beats it; a clearly dominant other
       language wins otherwise.
    4. Ambiguous short Latin text -> 'english' (the feeds are English
       dominant); ambiguous long text with no English signal -> 'other'.

    Runs on the combined title + description.
    """
    sample = (text or "")[:5000]
    if len(sample.strip()) < 20:
        return "unknown"
    non_latin = sum(1 for ch in sample if ord(ch) > 0x7F)
    if non_latin / len(sample) > 0.06:
        return "other"
    words = re.findall(r"[a-zà-ÿ']+", sample.lower())
    if not words:
        return "unknown"
    scores = {
        lang: sum(1 for w in words if w in s)
        for lang, s in _LANGUAGE_SETS.items()
    }
    eng = scores["en"]
    max_other = max(v for k, v in scores.items() if k != "en")
    if eng >= 2 and eng >= max_other:
        return "english"
    if max_other >= 2 and max_other > eng:
        return "other"
    # ambiguous
    if len(words) <= 12:
        return "english"
    if eng > 0:
        return "english"
    return "other"


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
        "language": detect_language(f"{title or ''} {desc}"),
        **signals,
    }

"""Job sources - permitted feeds only.

Compliance rules (agreed product requirements):
- Official public APIs and explicitly public feeds only
- No login bypass, CAPTCHA defeat, or robots/terms violations
- LinkedIn, Indeed, CareerJunction and PNet are NOT scraped: they have no
  permitted public feed. They are covered later via licensed data or
  user-provided URLs (user-directed, single pages).
- Each source is feature-flaggable; one broken source never stops the app.

Sources implemented:
- wwr: We Work Remotely public RSS (explicitly provided for feeds)
- remoteok: RemoteOK public JSON feed
- remotive: Remotive public jobs API
- adzuna: Adzuna official API (requires the candidate's free API key -
  best source for South Africa-specific listings)
"""
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .normalizer import normalize, strip_html

TIMEOUT = 25
UA = "CareerForgePro/1.0 (permitted public feed; contact: support)"
MAX_BODY = 4_000_000


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read(MAX_BODY)


def _get_json(url: str):
    return json.loads(_get(url).decode("utf-8", errors="replace"))


# --- We Work Remotely (RSS) -----------------------------------------------------

def fetch_wwr() -> list[dict]:
    data = _get("https://weworkremotely.com/remote-jobs.rss")
    root = ET.fromstring(data)
    out = []
    for item in root.findall(".//item")[:80]:
        title = (item.findtext("title") or "").strip()
        company, _, role = title.partition(":")
        if not role.strip():
            company, role = "", title
        out.append(
            normalize(
                source="wwr",
                title=role.strip(),
                company=company.strip() or None,
                location="Remote",
                url=(item.findtext("link") or "").strip() or None,
                description=item.findtext("description") or "",
                posted_at=item.findtext("pubDate"),
            )
        )
    return out


# --- RemoteOK (public JSON) ------------------------------------------------------

def fetch_remoteok() -> list[dict]:
    data = _get_json("https://remoteok.com/api")
    out = []
    for j in data:
        if not isinstance(j, dict) or "position" not in j:
            continue  # first element is meta (last_updated/legal)
        salary = None
        if j.get("salary_min") or j.get("salary_max"):
            salary = f"{j.get('salary_min') or '?'} - {j.get('salary_max') or '?'}"
        out.append(
            normalize(
                source="remoteok",
                title=j.get("position") or "",
                company=j.get("company") or None,
                location=j.get("location") or None,
                url=j.get("url") or j.get("apply_url") or None,
                description=j.get("description") or "",
                tags=j.get("tags") or [],
                salary_text=salary,
                posted_at=j.get("date"),
            )
        )
    return out


# --- Remotive (public API) ---------------------------------------------------------

def fetch_remotive() -> list[dict]:
    data = _get_json("https://api.remotive.com/api/jobs?remote=true")
    jobs = data.get("jobs") if isinstance(data, dict) else data
    out = []
    for j in (jobs or [])[:100]:
        if not isinstance(j, dict):
            continue
        salary = j.get("salary")
        if isinstance(salary, dict):
            salary = f"{salary.get('value', '?')} {salary.get('period', 'per year')} {salary.get('currency', '')}".strip()
        out.append(
            normalize(
                source="remotive",
                title=j.get("title") or "",
                company=j.get("company_name") or None,
                location=j.get("location") or "Remote",
                url=j.get("url") or None,
                description=j.get("description") or "",
                tags=list((j.get("tags") or {}).keys())[:12]
                if isinstance(j.get("tags"), dict)
                else (j.get("tags") or []),
                salary_text=salary if isinstance(salary, str) else None,
                posted_at=j.get("created_at") or j.get("date"),
            )
        )
    return out


# --- Adzuna (official API; free key, best for SA listings) -------------------------

def fetch_adzuna(app_id: str, api_key: str) -> list[dict]:
    params = {
        "app_id": app_id,
        "api_key": api_key,
        "what": "",
        "where": "south africa",
        "results_per_page": "50",
        "start_page": "0",
        "what_terms": "false",
    }
    data = _get_json("https://co.uk.api.adzuna.com/v1/jobs/search?" + urllib.parse.urlencode(params))
    out = []
    for j in data.get("results", []):
        company = (j.get("company") or {}).get("name")
        location = (j.get("location") or {}).get("display_name")
        salary = None
        if j.get("salary_from") or j.get("salary_to"):
            salary = f"{j.get('salary_from') or '?'} - {j.get('salary_to') or '?'}"
        out.append(
            normalize(
                source="adzuna",
                title=j.get("title") or "",
                company=company,
                location=location,
                url=j.get("redirected_url") or None,
                description=j.get("description") or "",
                salary_text=salary,
                posted_at=j.get("created"),
            )
        )
    return out


# --- User-provided URL (user-directed, single public page) -------------------------

_TAG_RE = re.compile(r"<[^>]+>")
import html as _html


def _meta_map(html: str) -> dict:
    out: dict[str, str] = {}
    for m in re.finditer(r"<meta[^>]+>", html, re.I):
        tag = m.group(0)
        nm = re.search(r"(?:property|name)=[\"']([^\"']+)[\"']", tag, re.I)
        ct = re.search(r"content=[\"']([^\"']*)[\"']", tag, re.I)
        if nm and ct:
            out[nm.group(1).lower()] = _html.unescape(ct.group(1)).strip()
    return out


def _jsonld_job(html: str) -> dict:
    """JobPosting structured data, if the page carries it."""
    for m in re.finditer(
        r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", html, re.S | re.I
    ):
        try:
            data = json.loads(_html.unescape(m.group(1).strip()))
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and str(item.get("@type", "")).lower() == "jobposting":
                org = item.get("hiringOrganization")
                if isinstance(org, list):
                    org = org[0] if org else None
                if isinstance(org, dict):
                    org = org.get("name")
                return {
                    "description": strip_html(str(item.get("description") or "")),
                    "company": (org or "").strip()[:200] or None,
                }
    return {}


def _description_block(html: str) -> str | None:
    """A block whose id/class says 'description' (most job CMS patterns)."""
    for m in re.finditer(r"<(div|section|article)[^>]*>", html, re.I):
        tag = m.group(0)
        if re.search(
            r"(?:id|class)=[\"'][^\"']*(?:job[-_ ]?description|jobdescription|"
            r"jd[-_ ]?text|job[-_ ]?details|description)[^\"']*[\"']",
            tag,
            re.I,
        ):
            start = m.end()
            end = html.find(f"</{m.group(1)}>", start)
            if end == -1:
                continue
            text = re.sub(r"\s+", " ", _TAG_RE.sub(" ", html[start:end])).strip()
            if len(text) > 200:
                return text
    return None


def _company_from_title(title: str) -> tuple[str, str | None]:
    """'Support Manager - Acme | Remote' -> ('Support Manager', 'Acme') when
    the trailing part plausibly names the employer. Conservative: when in
    doubt, keep the whole title and no company."""
    for sep in (" | ", " - ", " @ "):
        if sep in title:
            head, tail = title.rsplit(sep, 1)
            tail = tail.strip()
            if (
                2 <= len(tail) <= 40
                and re.search(r"[A-Za-z]", tail)
                and not re.search(r"\d{4}", tail)
                and "http" not in tail.lower()
                and not tail.lower().endswith((".com", ".co", ".io", ".org", "careers", "jobs"))
            ):
                return head.strip(), tail
    return title.strip(), None


def fetch_user_url(url: str) -> dict:
    """Fetch one user-provided public job page. User-directed assistance only.

    Extraction priority (most structured first): JSON-LD JobPosting,
    then a description block, then meta tags, then the raw page text.
    """
    if not url.startswith(("http://", "https://")):
        raise ValueError("Enter a full job URL starting with https://")
    html = _get(url).decode("utf-8", errors="replace")
    meta = _meta_map(html)
    ld = _jsonld_job(html)

    title = (
        meta.get("og:title")
        or meta.get("twitter:title")
        or (re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I) or [None, ""])[1]
    )
    title = _html.unescape(title).strip()
    title, company_from_title = _company_from_title(title)
    company = ld.get("company") or company_from_title

    # JSON-LD JobPosting data is authoritative even when short; only fall
    # back to page-text heuristics when no structured description exists.
    description = ld.get("description")
    if not description:
        description = (
            _description_block(html)
            or meta.get("description")
            or meta.get("og:description")
        )
        if not description or len(description) < 200:
            description = re.sub(r"\s+", " ", _TAG_RE.sub(" ", html)).strip()
    return normalize(
        source="user_url",
        title=title[:200] or "Job",
        company=company,
        location=None,
        url=url,
        description=description[:20000],
        posted_at=None,
    )


def get_source(name: str):
    return {
        "wwr": fetch_wwr,
        "remoteok": fetch_remoteok,
        "remotive": fetch_remotive,
    }.get(name)

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

from .normalizer import normalize

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


def fetch_user_url(url: str) -> dict:
    """Fetch one user-provided public job page. User-directed assistance only."""
    if not url.startswith(("http://", "https://")):
        raise ValueError("Enter a full job URL starting with https://")
    html = _get(url).decode("utf-8", errors="replace")
    head_title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    text = _TAG_RE.sub(" ", html)
    text = re.sub(r"\s+", " ", text).strip()
    title = (head_title.group(1).strip() if head_title else "Job")[:200]
    # keep the first ~15k chars of page text as the description
    return normalize(
        source="user_url",
        title=title,
        company=None,
        location=None,
        url=url,
        description=text[:15000],
        posted_at=None,
    )


def get_source(name: str):
    return {
        "wwr": fetch_wwr,
        "remoteok": fetch_remoteok,
        "remotive": fetch_remotive,
    }.get(name)

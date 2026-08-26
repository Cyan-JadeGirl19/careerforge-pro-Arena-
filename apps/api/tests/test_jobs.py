"""Job engine tests: normalizer, matching, sources (fixtures), routes."""
import io
import json
import re
from datetime import datetime, timedelta, timezone

import pytest

API = "/api/v1"

# ---------------------------------------------------------------- normalizer

from app.jobs.normalizer import compute_sa_signals, normalize, strip_html  # noqa: E402


def test_signals_sa_direct():
    s = compute_sa_signals("We hire from South Africa. Work remotely.", "Johannesburg")
    assert s["open_to_sa"] == "yes"
    assert "south africa" in s["sa_signals_json"]


def test_signals_global():
    s = compute_sa_signals("Remote - anywhere in the world. We pay via Deel.", "Remote")
    assert s["open_to_sa"] == "yes"
    assert "deel" in s["payment_signals_json"]


def test_signals_excluded():
    s = compute_sa_signals("Remote worldwide, but you must have US work authorization.", "Remote")
    assert s["open_to_sa"] == "no"
    assert json.loads(s["exclude_signals_json"])


def test_signals_unknown():
    s = compute_sa_signals("We are a startup looking for engineers.", None)
    assert s["open_to_sa"] == "unknown"


def test_strip_html():
    assert "hello world" in strip_html("<p>hello <b>world</b></p>")


# ------------------------------------------------------------------ matching

from app.jobs.matching import match_job  # noqa: E402


def _posting(**kw):
    base = {
        "title": "Senior Customer Success Manager",
        "description": "5+ years customer success. Data analysis with Excel. "
        "Stakeholder management. CRM. Remote worldwide. We pay via Deel.",
        "posted_at": datetime.now(timezone.utc) - timedelta(days=2),
        "open_to_sa": "yes",
        "remote_type": "remote",
    }
    base.update(kw)
    return base


def test_match_components_sum_to_score():
    m = match_job(
        _posting(),
        ["customer success", "data analysis", "excel", "stakeholder management", "crm"],
        6,
        "customer success data analysis excel stakeholder management crm",
    )
    assert 0 <= m["score"] <= 100
    assert set(m["components"]) == {"skills", "experience", "keywords", "feasibility", "freshness"}
    assert m["skill_hits"]
    assert m["components"]["feasibility"] >= 80  # open_to_sa yes


def test_stale_job_scores_lower_freshness():
    fresh = match_job(_posting(), ["data analysis"], 5, "data analysis")
    stale = match_job(
        _posting(posted_at=datetime.now(timezone.utc) - timedelta(days=45)),
        ["data analysis"],
        5,
        "data analysis",
    )
    assert stale["components"]["freshness"] < fresh["components"]["freshness"]


def test_seniority_mismatch_penalised():
    senior_fit = match_job(_posting(), [], 8, "")
    junior_mismatch = match_job(_posting(title="Senior Lead Architect"), [], 1, "")
    assert senior_fit["components"]["experience"] > junior_mismatch["components"]["experience"]


# ------------------------------------------------------------------ sources

from app.jobs import sources  # noqa: E402

WWR_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss><channel>
<item><title>Acme: Customer Success Manager (Remote Africa)</title>
<link>https://weworkremotely.com/remote-jobs/acme-csm-1</link>
<pubDate>Mon, 24 Aug 2026 10:00:00 +0000</pubDate>
<description>Work from anywhere in Africa. We hire in South Africa. Pay via Deel or Wise.</description>
</item>
<item><title>Remote Support Agent - EMEA overlap</title>
<link>https://weworkremotely.com/remote-jobs/support-2</link>
<pubDate>Mon, 23 Aug 2026 09:00:00 +0000</pubDate>
<description>EMA overlap required. EMEA overlap required. Must be authorized to work in the United States.</description>
</item>
</channel></rss>"""


def test_wwr_parse(monkeypatch):
    import xml.etree.ElementTree as ET

    monkeypatch.setattr(sources, "_get", lambda url: WWR_RSS.encode())
    posts = sources.fetch_wwr()
    assert len(posts) == 2
    assert posts[0]["company"] == "Acme"
    assert posts[0]["title"] == "Customer Success Manager (Remote Africa)"
    assert posts[0]["open_to_sa"] == "yes"
    assert posts[1]["open_to_sa"] == "no"
    assert posts[0]["posted_at"] is not None


REMOTEOK_JSON = [
    {"last_updated": "x", "legal": "y"},
    {
        "id": 1,
        "position": "Operations Analyst",
        "company": "BuildCo",
        "location": "Remote - Africa",
        "tags": ["analytics", "sql"],
        "date": "2026-08-23T09:45:26+00:00",
        "url": "https://remoteok.com/job/1",
        "description": "Global remote team. We hire worldwide including South Africa.",
        "salary_min": "60000",
        "salary_max": "80000",
    },
]


def test_remoteok_parse(monkeypatch):
    monkeypatch.setattr(sources, "_get_json", lambda url: REMOTEOK_JSON)
    posts = sources.fetch_remoteok()
    assert len(posts) == 1
    assert posts[0]["title"] == "Operations Analyst"
    assert posts[0]["open_to_sa"] == "yes"
    assert posts[0]["salary_text"] == "60000 - 80000"


def test_user_url_rejects_bad_url():
    with pytest.raises(ValueError):
        sources.fetch_user_url("ftp://nope")


# ------------------------------------------------------------------- routes

FAKE_POSTINGS = [
    normalize(
        source="wwr",
        title="Customer Success Manager",
        company="Acme",
        location="Remote",
        url="https://example.com/job/csm",
        description="We hire from South Africa. Remote worldwide. Deel payments. "
        "Data analysis, stakeholder management, CRM, customer success, excel.",
        posted_at="2026-08-23T09:00:00+00:00",
    ),
    normalize(
        source="remoteok",
        title="Sandwich Artist",
        company="Subway",
        location="Grand Falls",
        url="https://example.com/job/sandwich",
        description="In-office only in Grand Falls.",
        posted_at="2026-08-20T09:00:00+00:00",
    ),
]


def _fake_sync(db, enabled, creds):
    """Mocked source sync: seeds the two FAKE_POSTINGS (dedup-safe)."""
    from sqlalchemy import select

    from app.models import JobPosting

    added = 0
    for p in FAKE_POSTINGS:
        if (
            db.scalar(select(JobPosting).where(JobPosting.dedupe_key == p["dedupe_key"]))
            is None
        ):
            db.add(
                JobPosting(
                    id=f"job-{p['dedupe_key']}",
                    fetched_at=datetime.now(timezone.utc),
                    **p,
                )
            )
            added += 1
    db.commit()
    return [
        {
            "source": "wwr",
            "enabled": True,
            "status": "ok",
            "fetched": len(FAKE_POSTINGS),
            "added": added,
            "error": None,
        }
    ]


@pytest.fixture()
def seeded_jobs(client, monkeypatch):
    """Patch the sync so tests never hit the network."""
    import app.jobs.service as svc

    monkeypatch.setattr(svc, "sync_all", _fake_sync)
    return _fake_sync


def test_jobs_search_and_filter(client, seeded_jobs):

    res = client.post(f"{API}/jobs/sync")
    assert res.status_code == 200
    assert res.json()["total_jobs"] == 2

    res = client.get(f"{API}/jobs")
    assert res.status_code == 200
    titles = [j["title"] for j in res.json()]
    assert "Customer Success Manager" in titles and "Sandwich Artist" in titles

    # SA-only filter drops the in-office US-style job
    res = client.get(f"{API}/jobs?sa_only=true")
    assert [j["title"] for j in res.json()] == ["Customer Success Manager"]

    # source filter
    res = client.get(f"{API}/jobs?source=remoteok")
    assert [j["title"] for j in res.json()] == ["Sandwich Artist"]

    # freshness filter: sandwich job is 4 days old in a 2-day window
    res = client.get(f"{API}/jobs?max_age_days=2")
    assert all("Sandwich" != j["title"] for j in res.json())


def test_job_sync_isolates_source_failures(client, monkeypatch):
    import app.jobs.service as svc

    def failing(db, enabled, creds):
        return [
            {"source": "wwr", "enabled": True, "status": "ok", "fetched": 1, "added": 1, "error": None},
            {"source": "remoteok", "enabled": True, "status": "error", "fetched": 0, "added": 0, "error": "boom"},
        ]

    monkeypatch.setattr(svc, "sync_all", failing)
    res = client.post(f"{API}/jobs/sync")
    assert res.status_code == 200
    statuses = {s["source"]: s["status"] for s in res.json()["sources"]}
    assert statuses["remoteok"] == "error" and statuses["wwr"] == "ok"


def test_job_to_application_builds_package(client, consented_profile, cv_id, seeded_jobs):
    client.post(f"{API}/jobs/sync")
    jobs = client.get(f"{API}/jobs").json()
    csm = next(j for j in jobs if j["title"] == "Customer Success Manager")

    res = client.post(f"{API}/jobs/{csm['id']}/to-application?profile_id={consented_profile}")
    assert res.status_code == 201
    app_id = res.json()["application_id"]

    app = client.get(f"{API}/applications/{app_id}").json()
    assert app["jd_title"] == "Customer Success Manager"
    assert app["tailored_cv_id"], "tailored CV created"
    assert app["letter"], "cover letter created"

    # idempotent: same job + profile returns the same application
    res2 = client.post(f"{API}/jobs/{csm['id']}/to-application?profile_id={consented_profile}")
    assert res2.json() == {"application_id": app_id, "existing": True}


def test_job_match_with_profile(client, consented_profile, cv_id, seeded_jobs):
    client.post(f"{API}/jobs/sync")
    jobs = client.get(f"{API}/jobs?profile_id={consented_profile}").json()
    csm = next(j for j in jobs if j["title"] == "Customer Success Manager")
    assert csm["match"] is not None
    assert 0 <= csm["match"]["score"] <= 100
    assert csm["match"]["components"]["feasibility"] >= 80


def test_saved_searches_roundtrip(client, consented_profile):
    res = client.post(
        f"{API}/jobs/profiles/{consented_profile}/saved-searches",
        json={"name": "CSM Africa", "filters": {"sa_only": True, "q": "customer success"}},
    )
    assert res.status_code == 201
    sid = res.json()["id"]
    listing = client.get(f"{API}/jobs/profiles/{consented_profile}/saved-searches").json()
    assert listing[0]["name"] == "CSM Africa"
    assert listing[0]["filters"]["sa_only"] is True
    assert client.delete(f"{API}/jobs/profiles/{consented_profile}/saved-searches/{sid}").status_code == 204
    assert client.get(f"{API}/jobs/profiles/{consented_profile}/saved-searches").json() == []


def test_erasure_covers_saved_searches(client, consented_profile):
    client.post(
        f"{API}/jobs/profiles/{consented_profile}/saved-searches",
        json={"name": "temp", "filters": {}},
    )
    assert client.delete(f"{API}/profiles/{consented_profile}").status_code == 204


# ---------------------------------------------------------- language filter
from app.jobs.normalizer import detect_language  # noqa: E402
from app.jobs import service as jobs_service  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import JobPosting  # noqa: E402


def test_detect_language_english():
    text = (
        "We are a remote company looking for a senior support team member. "
        "You will work with our customer success team to help customers every day. "
        "Experience with SaaS and strong communication skills are required."
    )
    assert detect_language(text) == "english"


def test_detect_language_german():
    text = (
        "Wir suchen einen erfahrenen Support-Mitarbeiter fuer unser Team. "
        "Sie arbeiten mit unseren Kunden zusammen und loesen ihre Probleme. "
        "Erfahrung im SaaS-Bereich und starke Kommunikation sind erforderlich."
    )
    assert detect_language(text) == "other"


def test_detect_language_french():
    text = (
        "Nous recherchons un développeur senior pour notre équipe à distance. "
        "Vous travaillerez avec nos clients et nos produits. Expérience en "
        "SaaS et bonnes compétences en communication requises."
    )
    assert detect_language(text) == "other"


def test_detect_language_cjk():
    assert detect_language("我们正在招聘一名高级客户成功经理，负责远程团队。") == "other"


def test_detect_language_short_is_unknown():
    assert detect_language("Job") == "unknown"


def test_normalize_sets_language():
    d = normalize(
        source="test",
        title="Senior Support Manager",
        description="We are looking for a remote team member to help customers. "
                    "Experience with SaaS and strong communication required.",
    )
    assert d["language"] == "english"
    d2 = normalize(
        source="test",
        title="Support",
        description="Wir suchen einen Mitarbeiter fuer unser Team. Sie helfen "
                    "unseren Kunden und loesen Probleme im SaaS-Bereich.",
    )
    assert d2["language"] == "other"


def _job_row(key, title, desc, language=None, open_to_sa="unknown"):
    return dict(
        id=key,
        dedupe_key=key,
        source="test",
        title=title,
        company=None,
        location="Remote",
        url=None,
        description=desc,
        tags="",
        salary_text=None,
        posted_at=None,
        fetched_at=datetime.now(timezone.utc),
        open_to_sa=open_to_sa,
        remote_type="remote",
        language=language,
    )


def test_search_english_only_filter(client):
    with SessionLocal() as db:
        eng = _job_row(
            "eng-key",
            "Senior Support Manager",
            "We are a remote company looking for a team member to help customers.",
            language="english",
        )
        ger = _job_row(
            "ger-key",
            "Support-Mitarbeiter",
            "Wir suchen einen Mitarbeiter fuer unser Team und loesen Probleme.",
            language="other",
        )
        unk = _job_row(
            "unk-key",
            "Manager",
            "We are a remote company looking for a team member to help customers.",
            language=None,  # unclassified
        )
        for r in (eng, ger, unk):
            db.add(JobPosting(**r))
        db.commit()

    try:
        # default (english_only=true) -> only the classified-english row
        res = client.get(f"{API}/jobs")
        assert res.status_code == 200
        titles = {j["title"] for j in res.json()}
        assert "Senior Support Manager" in titles
        assert "Support-Mitarbeiter" not in titles
        assert "Manager" not in titles  # unknown is hidden by default

        # english_only=false -> everything is visible
        res2 = client.get(f"{API}/jobs?english_only=false")
        titles2 = {j["title"] for j in res2.json()}
        assert "Senior Support Manager" in titles2
        assert "Support-Mitarbeiter" in titles2
        assert "Manager" in titles2

        # the language field is exposed
        eng_row = next(j for j in res2.json() if j["title"] == "Senior Support Manager")
        assert eng_row["language"] == "english"
    finally:
        with SessionLocal() as db:
            for key in ("eng-key", "ger-key", "unk-key"):
                row = db.get(JobPosting, key)
                if row:
                    db.delete(row)
            db.commit()


def test_backfill_languages_classifies_nulls(client):
    with SessionLocal() as db:
        row = _job_row(
            "backfill-key",
            "Senior Support Manager",
            "We are a remote company looking for a team member to help customers.",
            language=None,
        )
        db.add(JobPosting(**row))
        db.commit()
    try:
        with SessionLocal() as db:
            n = jobs_service.backfill_languages(db)
            assert n >= 1
            r = db.get(JobPosting, "backfill-key")
            assert r.language == "english"
    finally:
        with SessionLocal() as db:
            row = db.get(JobPosting, "backfill-key")
            if row:
                db.delete(row)
            db.commit()

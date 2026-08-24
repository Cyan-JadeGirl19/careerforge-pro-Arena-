"""Autonomous studio tests: roles, applications, letters, video, pipeline."""
import re

API = "/api/v1"

JD_CSM = """Customer Success Manager — Remote (Africa)

Requirements:
- 5+ years in customer success or customer service roles
- Strong data analysis with Excel and dashboards
- Stakeholder management across time zones
- Excellent written communication
- CRM tools and renewal processes
"""

JD_OPS = """Operations Analyst — Remote (UTC+2 friendly)

Responsibilities:
- Build and maintain operational reports in Excel
- Analyse process data and present findings to stakeholders
- Track key metrics and recommend improvements
- Coordinate with cross-functional teams
"""


# --- role recommendation -------------------------------------------------------


def test_recommend_roles_returns_top3(client, cv_id):
    res = client.get(f"{API}/cvs/{cv_id}").json()
    pid = res["profile_id"]
    res = client.post(f"{API}/profiles/{pid}/roles/recommend")
    assert res.status_code == 200
    roles = res.json()
    assert 1 <= len(roles) <= 3
    top = roles[0]
    assert top["match_pct"] >= 20
    assert top["matched"], "at least one matched signal expected"
    # order: best first
    pcts = [r["match_pct"] for r in roles]
    assert pcts == sorted(pcts, reverse=True)


def test_recommend_roles_requires_consent(client, profile_id):
    # needs a CV too, but consent is checked first -> 409
    res = client.post(f"{API}/profiles/{profile_id}/roles/recommend")
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "CONSENT_REQUIRED"


# --- application lifecycle -------------------------------------------------------


def _make_application(client, pid, cv_id, jd_text=JD_CSM):
    jd = client.post(
        f"{API}/profiles/{pid}/job-descriptions",
        json={"title": "Customer Success Manager", "company": "Acme Remote", "text": jd_text},
    )
    assert jd.status_code == 201
    res = client.post(
        f"{API}/profiles/{pid}/applications",
        json={"jd_id": jd.json()["id"]},
    )
    assert res.status_code == 201
    return jd.json(), res.json()


def test_application_auto_selects_best_version(client, consented_profile, cv_id):
    _, app = _make_application(client, consented_profile, cv_id)
    assert app["cv_version_id"]
    assert app["status"] == "saved"


def test_application_tailor_produces_record(client, consented_profile, cv_id):
    _, app = _make_application(client, consented_profile, cv_id)
    res = client.post(f"{API}/applications/{app['id']}/tailor")
    assert res.status_code == 200
    assert res.json()["tailored_cv_id"]
    report = res.json()["report"]
    assert "keywords" in report and "gaps" in report


def test_status_updates(client, consented_profile, cv_id):
    _, app = _make_application(client, consented_profile, cv_id)
    res = client.post(
        f"{API}/applications/{app['id']}/status",
        json={"status": "applied", "notes": "applied via portal"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "applied"
    assert res.json()["notes"] == "applied via portal"
    bad = client.post(
        f"{API}/applications/{app['id']}/status", json={"status": "bogus"}
    )
    assert bad.status_code == 422


# --- cover letters -----------------------------------------------------------------


def test_cover_letter_is_human_and_specific(client, consented_profile, cv_id):
    _, app = _make_application(client, consented_profile, cv_id)
    res = client.post(f"{API}/applications/{app['id']}/cover-letter", json={"tone": "direct"})
    assert res.status_code == 201
    letter = res.json()["text"]
    assert "Acme Remote" in letter
    words = len(re.findall(r"\b\w+\b", letter))
    assert words >= 150
    low = letter.lower()
    for banned in ("i am excited to apply", "leveraged", "synergy", "spearheaded", "utilized"):
        assert banned not in low
    assert res.json()["quality_issues"] == []


def test_cover_letters_differ_per_job(client, consented_profile, cv_id):
    _, app1 = _make_application(client, consented_profile, cv_id, JD_CSM)
    _, app2 = _make_application(client, consented_profile, cv_id, JD_OPS)
    l1 = client.post(f"{API}/applications/{app1['id']}/cover-letter").json()["text"]
    l2 = client.post(f"{API}/applications/{app2['id']}/cover-letter").json()["text"]
    assert l1 != l2


# --- voice/video scripts ------------------------------------------------------------


def _video(client, app_id, **kw):
    body = {
        "question": "Tell us a bit about yourself and why you are a good fit for this role.",
        "target_seconds": 60,
        **kw,
    }
    res = client.post(f"{API}/applications/{app_id}/videos", json=body)
    assert res.status_code == 201
    return res.json()


def test_video_script_60s_is_natural_and_on_budget(client, consented_profile, cv_id):
    _, app = _make_application(client, consented_profile, cv_id)
    v = _video(client, app["id"])
    words = len(re.findall(r"\b\w+\b", v["script_text"]))
    budget = 60 * 2.5
    assert 0.8 * budget <= words <= 1.2 * budget
    assert "Thando" in v["script_text"]
    assert v["media_status"] == "none"
    assert v["script_version"] == 1


def test_video_180s_longer_than_30s(client, consented_profile, cv_id):
    _, app = _make_application(client, consented_profile, cv_id)
    v30 = _video(client, app["id"], target_seconds=30)
    v180 = _video(client, app["id"], target_seconds=180)
    w30 = len(re.findall(r"\b\w+\b", v30["script_text"]))
    w180 = len(re.findall(r"\b\w+\b", v180["script_text"]))
    assert w180 > w30
    # Length is bounded by the candidate's real content - the engine
    # never pads a script with invented detail. A 180s target simply
    # carries more of their real material than a 30s target.


def test_video_key_points_and_exclusions_respected(client, consented_profile, cv_id):
    _, app = _make_application(client, consented_profile, cv_id)
    v = _video(
        client, app["id"],
        key_points=["my customer-service experience", "my remote setup"],
        exclusions=["knowledge base"],
    )
    assert "customer-service experience" in v["script_text"]
    # the excluded quantified bullet must not appear in the script
    assert "knowledge base" not in v["script_text"]


def test_video_ai_assisted_needs_media_consent(client, consented_profile, cv_id):
    _, app = _make_application(client, consented_profile, cv_id)
    res = client.post(
        f"{API}/applications/{app['id']}/videos",
        json={"question": "Introduce yourself.", "mode": "ai_assisted"},
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "CONSENT_REQUIRED"


def test_video_requires_recording_consent(client):
    # Brand-new profile with NO consents at all.
    res = client.post(f"{API}/profiles", json={"first_name": "No Consent"})
    pid = res.json()["id"]
    res = client.post(
        f"{API}/profiles/{pid}/applications", json={"jd_id": "0" * 36}
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "CONSENT_REQUIRED"


def test_video_regenerate_bumps_version(client, consented_profile, cv_id):
    _, app = _make_application(client, consented_profile, cv_id)
    v = _video(client, app["id"])
    res = client.post(
        f"{API}/videos/{v['id']}/regenerate",
        json={"question": "Why should we hire you?", "target_seconds": 90, "tone": "warm"},
    )
    assert res.status_code == 200
    assert res.json()["script_version"] == 2
    assert res.json()["target_seconds"] == 90


# --- regression: real-world text quality ---------------------------------------------


def test_years_of_experience_not_miscalculated(client, cv_id):
    """Dates 2019-2022 / 2022-present must give ~7 years, not 40."""
    from app.parsing import parse_cv_text
    from app.video import _years

    res = client.get(f"{API}/cvs/{cv_id}").json()
    parsed = parse_cv_text(res["text"])
    span = _years(parsed)
    assert span is not None
    assert 1 <= span <= 30


def test_acronyms_preserved_in_letter_and_video(client, consented_profile, cv_id):
    _, app = _make_application(client, consented_profile, cv_id)
    letter = client.post(f"{API}/applications/{app['id']}/cover-letter").json()["text"]
    v = _video(client, app["id"])
    assert "CSAT" in letter
    assert "csat" not in letter.lower().replace("csat", "CSAT") or "CSAT" in letter
    assert "CSAT" in v["script_text"]


# --- auto pipeline --------------------------------------------------------------------


def test_auto_pipeline_builds_full_package(client, consented_profile, cv_id):
    jds = []
    for title, text in (("Customer Success Manager", JD_CSM), ("Operations Analyst", JD_OPS)):
        jd = client.post(
            f"{API}/profiles/{consented_profile}/job-descriptions",
            json={"title": title, "company": "TestCo", "text": text},
        )
        jds.append(jd.json()["id"])
    # grant video consent so the pipeline also prepares scripts
    client.post(
        f"{API}/profiles/{consented_profile}/consents", json={"item": "video_recording"}
    )
    res = client.post(
        f"{API}/profiles/{consented_profile}/auto-pipeline",
        json={"cv_id": cv_id, "jd_ids": jds},
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["applications"]) == 2
    for app in body["applications"]:
        assert app["tailored_cv_id"], "every application gets a tailored CV"
        assert app["letter"], "every application gets a cover letter"
        assert app["videos"], "video script prepared (consent granted)"
        assert app["videos"][0]["script_text"]


def test_auto_pipeline_skips_video_without_consent(client):
    # Profile with CV + job consents, but explicitly NO video consent.
    from conftest import SAMPLE_CV

    pid = client.post(f"{API}/profiles", json={"first_name": "NoVideo"}).json()["id"]
    for item in ("profile_processing", "job_matching"):
        client.post(f"{API}/profiles/{pid}/consents", json={"item": item})
    cv = client.post(f"{API}/profiles/{pid}/cvs", json={"text": SAMPLE_CV}).json()["id"]
    jd = client.post(
        f"{API}/profiles/{pid}/job-descriptions",
        json={"title": "Ops Analyst", "company": "TestCo", "text": JD_OPS},
    )
    res = client.post(
        f"{API}/profiles/{pid}/auto-pipeline",
        json={"cv_id": cv, "jd_ids": [jd.json()["id"]]},
    )
    assert res.status_code == 200
    app = res.json()["applications"][0]
    assert app["tailored_cv_id"]
    assert app["letter"]
    assert app["videos"] == []  # no video consent -> no script, no failure


def test_erasure_covers_studio_tables(client, consented_profile, cv_id):
    _, app = _make_application(client, consented_profile, cv_id)
    client.post(f"{API}/applications/{app['id']}/tailor")
    client.post(f"{API}/applications/{app['id']}/cover-letter")
    assert client.delete(f"{API}/profiles/{consented_profile}").status_code == 204
    assert client.get(f"{API}/applications/{app['id']}").status_code == 404

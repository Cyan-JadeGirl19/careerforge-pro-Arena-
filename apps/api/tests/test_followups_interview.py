"""Follow-up scheduling and Interview Coach tests."""
import re

API = "/api/v1"

# ------------------------------------------------------------- follow-ups


def _application(client, pid):
    import conftest

    cv = client.post(f"{API}/profiles/{pid}/cvs", json={"text": conftest.SAMPLE_CV})
    jd = client.post(
        f"{API}/profiles/{pid}/job-descriptions",
        json={"title": "Customer Success Manager", "company": "Acme", "text": "A" * 60},
    )
    app = client.post(f"{API}/profiles/{pid}/applications", json={"jd_id": jd.json()["id"]})
    assert app.status_code == 201
    return app.json()


def test_status_change_auto_schedules_followup(client, consented_profile):
    app = _application(client, consented_profile)
    # no follow-up yet
    assert client.get(f"{API}/profiles/{consented_profile}/followups").json() == []

    res = client.post(f"{API}/applications/{app['id']}/status", json={"status": "applied"})
    assert res.status_code == 200

    fups = client.get(f"{API}/profiles/{consented_profile}/followups").json()
    assert len(fups) == 1
    f = fups[0]
    assert f["kind"] == "post_application"
    assert f["status"] == "scheduled"
    assert "Customer Success Manager" in f["draft_text"]
    assert f["application_title"] == "Customer Success Manager"


def test_no_duplicate_followup_per_kind(client, consented_profile):
    app = _application(client, consented_profile)
    client.post(f"{API}/applications/{app['id']}/status", json={"status": "applied"})
    client.post(f"{API}/applications/{app['id']}/status", json={"status": "applied"})
    assert len(client.get(f"{API}/profiles/{consented_profile}/followups").json()) == 1


def test_interview_schedules_post_interview(client, consented_profile):
    app = _application(client, consented_profile)
    client.post(f"{API}/applications/{app['id']}/status", json={"status": "applied"})
    client.post(f"{API}/applications/{app['id']}/status", json={"status": "interview"})
    fups = client.get(f"{API}/profiles/{consented_profile}/followups").json()
    kinds = sorted(f["kind"] for f in fups)
    assert kinds == ["post_application", "post_interview"]


def test_mark_sent_and_edit_draft(client, consented_profile):
    app = _application(client, consented_profile)
    client.post(f"{API}/applications/{app['id']}/status", json={"status": "applied"})
    fid = client.get(f"{API}/profiles/{consented_profile}/followups").json()[0]["id"]

    res = client.patch(
        f"{API}/followups/{fid}",
        json={"status": "sent", "draft_text": "Edited by candidate", "notes": "sent via Gmail"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "sent"
    assert res.json()["draft_text"] == "Edited by candidate"

    # only active (scheduled) ones listed by default
    assert client.get(f"{API}/profiles/{consented_profile}/followups").json() == []


def test_manual_followup_requires_outreach_consent(client, consented_profile):
    """consented_profile has job_matching but NOT outreach_sending, so a
    manual follow-up (draft generation) must be blocked."""
    app = _application(client, consented_profile)
    res = client.post(
        f"{API}/applications/{app['id']}/followups",
        json={"kind": "custom", "due_days": 7},
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "CONSENT_REQUIRED"


# -------------------------------------------------------- interview coach


def test_interview_session_from_cv(client, consented_profile, cv_id):
    res = client.post(
        f"{API}/interview/generate",
        json={"role": "Customer Success Manager"},
    )
    # role needs profile_id in URL
    assert res.status_code in (404, 422)


def test_interview_session_full(client, consented_profile, cv_id):
    res = client.post(
        f"{API}/interview/generate?profile_id={consented_profile}",
        json={"role": "Customer Success Manager"},
    )
    assert res.status_code == 200
    s = res.json()
    assert s["role"] == "Customer Success Manager"
    cats = {q["category"] for q in s["questions"]}
    assert "Core" in cats
    assert any(c.startswith("Behavioural") for c in cats)
    assert any(c == "South Africa / remote" for c in cats)
    assert any(c == "Close" for c in cats)

    # a behavioural answer is grounded in the real CV
    beh = next(q for q in s["questions"] if q["category"].startswith("Behavioural") and q["evidence_used"])
    assert "CSAT" in beh["prepared_answer"]

    # SA timezone question present
    sa = [q for q in s["questions"] if "time zone" in q["question"].lower()]
    assert sa and "UTC+2" in sa[0]["prepared_answer"]


def test_interview_with_jd_adds_role_specific(client, consented_profile, cv_id):
    jd = client.post(
        f"{API}/profiles/{consented_profile}/job-descriptions",
        json={
            "title": "Ops Analyst",
            "text": (
                "We need an operations analyst with data analysis, excel, "
                "stakeholder management and reporting skills. Daily reporting. "
                "Data analysis across teams."
            ),
        },
    )
    res = client.post(
        f"{API}/interview/generate?profile_id={consented_profile}",
        json={"role": "Operations Analyst", "jd_id": jd.json()["id"]},
    )
    assert res.status_code == 200
    role_q = [q for q in res.json()["questions"] if q["category"] == "Role-specific"]
    assert role_q, "JD keywords should generate role-specific questions"
    assert any("data analysis" in q["question"].lower() for q in role_q)


def test_interview_gap_question_when_gap_present(client, consented_profile):
    # CV with a clear 2-year gap
    gap_cv = """Jane Tester
jane@example.com
+27 82 000 0000

Experience
Ops Lead, Co One (2015 - 2018)
- Managed a team of 5
Ops Lead, Co Two (2021 - present)
- Improved reporting by 30%

Skills
data analysis, reporting
"""
    cv = client.post(f"{API}/profiles/{consented_profile}/cvs", json={"text": gap_cv})
    assert cv.status_code == 201
    res = client.post(
        f"{API}/interview/generate?profile_id={consented_profile}",
        json={"role": "Operations Lead"},
    )
    assert res.status_code == 200
    gap_qs = [q for q in res.json()["questions"] if q["category"] == "Red flag / gap"]
    assert gap_qs, "a 2-year gap should trigger a gap question"
    assert "24" in gap_qs[0]["question"]


def test_interview_requires_profile(client):
    res = client.post(
        f"{API}/interview/generate?profile_id={__import__('uuid').uuid4()}",
        json={"role": "Anything"},
    )
    assert res.status_code == 404

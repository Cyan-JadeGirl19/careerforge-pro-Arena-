"""3-touch follow-up sequences + follow-up -> Gmail draft (drafts only).

Google is never called: exchange_code / create_draft are monkeypatched,
so these tests cover the state machine, stage gates, ordering etiquette
and recipient matching - not Google itself.
"""
import pytest

from app import gmailx
from app.config import get_settings

API = "/api/v1"


def _outreach_profile(client, consented_profile) -> str:
    res = client.post(
        f"{API}/profiles/{consented_profile}/consents",
        json={"item": "outreach_sending", "granted": True},
    )
    assert res.status_code == 201
    return consented_profile


def _applied_application(client, pid) -> dict:
    import conftest

    cv = client.post(f"{API}/profiles/{pid}/cvs", json={"text": conftest.SAMPLE_CV})
    jd = client.post(
        f"{API}/profiles/{pid}/job-descriptions",
        json={
            "title": "Customer Success Manager",
            "company": "Acme",
            "text": "We need a remote CSM with SaaS experience. " * 2,
        },
    )
    app = client.post(f"{API}/profiles/{pid}/applications", json={"jd_id": jd.json()["id"]})
    assert app.status_code == 201, app.text
    res = client.post(f"{API}/applications/{app.json()['id']}/status", json={"status": "applied"})
    assert res.status_code == 200
    return app.json()


def _post_app_fups(client, pid) -> list:
    return [
        f
        for f in client.get(f"{API}/profiles/{pid}/followups").json()
        if f["kind"] == "post_application"
    ]


def test_sequence_requires_outreach_consent(client, consented_profile):
    app = _applied_application(client, consented_profile)
    # consented_profile lacks outreach_sending
    res = client.post(f"{API}/applications/{app['id']}/followup-sequence", json={})
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "CONSENT_REQUIRED"


def test_sequence_create_supersedes_auto(client, consented_profile):
    pid = _outreach_profile(client, consented_profile)
    app = _applied_application(client, pid)
    # auto single follow-up exists now
    assert len(_post_app_fups(client, pid)) == 1

    res = client.post(f"{API}/applications/{app['id']}/followup-sequence", json={"pattern": "standard"})
    assert res.status_code == 201, res.text
    touches = res.json()["touches"]
    assert [t["touch_number"] for t in touches] == [1, 2, 3]
    assert all(t["status"] == "scheduled" for t in touches)
    # the auto one was superseded: exactly 3 scheduled post-app follow-ups
    assert len(_post_app_fups(client, pid)) == 3

    # distinct, human-sounding copy per touch
    texts = [t["draft_text"] for t in touches]
    assert "still very interested" in texts[1]
    assert "last note" in texts[2]


def test_sequence_wrong_stage(client, consented_profile):
    pid = _outreach_profile(client, consented_profile)
    import conftest

    client.post(f"{API}/profiles/{pid}/cvs", json={"text": conftest.SAMPLE_CV})
    jd = client.post(
        f"{API}/profiles/{pid}/job-descriptions",
        json={"title": "Analyst", "text": "B" * 60},
    )
    app = client.post(f"{API}/profiles/{pid}/applications", json={"jd_id": jd.json()["id"]})
    # status is still 'saved' (never applied)
    res = client.post(f"{API}/applications/{app.json()['id']}/followup-sequence", json={})
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "BAD_STAGE"


def test_sequence_duplicate_blocked(client, consented_profile):
    pid = _outreach_profile(client, consented_profile)
    app = _applied_application(client, pid)
    assert client.post(f"{API}/applications/{app['id']}/followup-sequence", json={}).status_code == 201
    res = client.post(f"{API}/applications/{app['id']}/followup-sequence", json={})
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "ALREADY_SCHEDULED"


# --- follow-up -> Gmail draft -------------------------------------------------


@pytest.fixture()
def configured(monkeypatch):
    monkeypatch.setenv("CF_GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("CF_GOOGLE_CLIENT_SECRET", "test-client-secret")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _connect_gmail(client, pid, monkeypatch, email="thando@example.com"):
    monkeypatch.setattr(
        gmailx, "exchange_code", lambda code: {"refresh_token": "rt", "email": email}
    )
    auth_url = client.post(f"{API}/profiles/{pid}/gmail/authorize").json()["auth_url"]
    state = auth_url.split("state=")[1].split("&")[0]
    cb = client.get(f"{API}/gmail/oauth/callback?state={state}&code=x")
    assert cb.status_code == 200
    assert client.get(f"{API}/profiles/{pid}/gmail/status").json()["connected"] is True


def _recruiter(client, pid, job_title="Customer Success Manager", company="Acme",
               email="hiring@acme.example"):
    res = client.post(
        f"{API}/profiles/{pid}/recruiters",
        json={
            "name": "Hiring Manager",
            "company": company,
            "email": email,
            "email_status": "published",
            "job_title": job_title,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _touches(client, pid) -> list:
    return _post_app_fups(client, pid)


def test_gmail_draft_full_flow(client, consented_profile, configured, monkeypatch):
    pid = _outreach_profile(client, consented_profile)
    app = _applied_application(client, pid)
    client.post(f"{API}/applications/{app['id']}/followup-sequence", json={})
    _connect_gmail(client, pid, monkeypatch)
    monkeypatch.setattr(gmailx, "create_draft", lambda rt, to, subj, body: "fu-draft-1")
    _recruiter(client, pid)

    touches = {t["touch_number"]: t for t in _touches(client, pid)}

    # touch 1 (earliest pending) is allowed
    res = client.post(f"{API}/followups/{touches[1]['id']}/gmail-draft")
    assert res.status_code == 201, res.text
    assert res.json()["gmail_draft_id"] == "fu-draft-1"
    assert "draftid=fu-draft-1" in res.json()["gmail_url"]

    # touch 2 blocked until touch 1 is sent
    res = client.post(f"{API}/followups/{touches[2]['id']}/gmail-draft")
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "OUT_OF_ORDER"

    # mark touch 1 sent -> touch 2 becomes the earliest pending
    client.patch(f"{API}/followups/{touches[1]['id']}", json={"status": "sent"})
    monkeypatch.setattr(gmailx, "create_draft", lambda rt, to, subj, body: "fu-draft-2")
    res = client.post(f"{API}/followups/{touches[2]['id']}/gmail-draft")
    assert res.status_code == 201, res.text
    assert res.json()["gmail_draft_id"] == "fu-draft-2"


def test_gmail_draft_wrong_recipient_blocked(client, consented_profile, configured, monkeypatch):
    pid = _outreach_profile(client, consented_profile)
    app = _applied_application(client, pid)
    client.post(f"{API}/applications/{app['id']}/followup-sequence", json={})
    _connect_gmail(client, pid, monkeypatch)
    monkeypatch.setattr(gmailx, "create_draft", lambda rt, to, subj, body: "x")
    # contact matches neither the job title nor the company -> no recipient
    _recruiter(client, pid, job_title="Something Else", company="Other Co")
    fid = _touches(client, pid)[0]["id"]
    res = client.post(f"{API}/followups/{fid}/gmail-draft")
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "NO_CONTACT_EMAIL"


def test_gmail_draft_requires_gmail(client, consented_profile, configured, monkeypatch):
    pid = _outreach_profile(client, consented_profile)
    app = _applied_application(client, pid)
    client.post(f"{API}/applications/{app['id']}/followup-sequence", json={})
    _recruiter(client, pid)
    # no gmail connection
    fid = _touches(client, pid)[0]["id"]
    res = client.post(f"{API}/followups/{fid}/gmail-draft")
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "GMAIL_NOT_CONNECTED"


def test_gmail_draft_process_moved_on(client, consented_profile, configured, monkeypatch):
    pid = _outreach_profile(client, consented_profile)
    app = _applied_application(client, pid)
    client.post(f"{API}/applications/{app['id']}/followup-sequence", json={})
    _connect_gmail(client, pid, monkeypatch)
    monkeypatch.setattr(gmailx, "create_draft", lambda rt, to, subj, body: "x")
    _recruiter(client, pid)
    # application advances to interview -> no more follow-ups
    client.post(f"{API}/applications/{app['id']}/status", json={"status": "interview"})
    fid = _touches(client, pid)[0]["id"]
    res = client.post(f"{API}/followups/{fid}/gmail-draft")
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "PROCESS_MOVED_ON"

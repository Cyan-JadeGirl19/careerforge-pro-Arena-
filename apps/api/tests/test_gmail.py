"""Gmail outreach: OAuth connect flow + draft creation (drafts only).

Google is never called in tests: exchange_code / create_draft are
monkeypatched, so the tests cover the state machine, consent gates,
suppression, throttling and persistence - not Google itself.
"""
import pytest

from app import gmailx
from app.config import get_settings

API = "/api/v1"


@pytest.fixture()
def gmail_profile(client, consented_profile) -> str:
    res = client.post(
        f"{API}/profiles/{consented_profile}/consents",
        json={"item": "outreach_sending", "granted": True},
    )
    assert res.status_code == 201
    return consented_profile


@pytest.fixture()
def contact(client, gmail_profile) -> dict:
    res = client.post(
        f"{API}/profiles/{gmail_profile}/recruiters",
        json={
            "name": "Ayesha Khan",
            "title": "Talent Partner",
            "company": "RemoteCo",
            "email": "ayesha@remoteco.example",
            "email_status": "published",
            "job_title": "Support Specialist",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


@pytest.fixture()
def configured(monkeypatch):
    """Simulate a deployment with a Google OAuth client configured."""
    monkeypatch.setenv("CF_GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("CF_GOOGLE_CLIENT_SECRET", "test-client-secret")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _connect(client, profile_id: str, monkeypatch, email="thando@example.com"):
    monkeypatch.setattr(
        gmailx, "exchange_code", lambda code: {"refresh_token": "rt-test", "email": email}
    )
    auth_url = client.post(f"{API}/profiles/{profile_id}/gmail/authorize").json()["auth_url"]
    state = auth_url.split("state=")[1].split("&")[0]
    cb = client.get(f"{API}/gmail/oauth/callback?state={state}&code=fake-code")
    assert cb.status_code == 200
    assert cb.text.count("Connected as") == 1
    return auth_url


def test_status_not_connected(client, gmail_profile):
    res = client.get(f"{API}/profiles/{gmail_profile}/gmail/status")
    assert res.status_code == 200
    assert res.json()["connected"] is False


def test_authorize_requires_consent(client, profile_id):
    res = client.post(f"{API}/profiles/{profile_id}/gmail/authorize")
    assert res.status_code == 409  # outreach_sending not granted


def test_authorize_unconfigured(client, gmail_profile):
    res = client.post(f"{API}/profiles/{gmail_profile}/gmail/authorize")
    assert res.status_code == 503
    assert res.json()["detail"]["code"] == "GOOGLE_NOT_CONFIGURED"


def test_connect_flow(client, gmail_profile, configured, monkeypatch):
    auth_url = _connect(client, gmail_profile, monkeypatch)
    assert "test-client-id" in auth_url
    assert "gmail.modify" in auth_url
    st = client.get(f"{API}/profiles/{gmail_profile}/gmail/status").json()
    assert st["connected"] is True
    assert st["email"] == "thando@example.com"
    # refresh token is stored encrypted (not plaintext)
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import GmailAccount

    with SessionLocal() as db:
        acc = db.scalars(
            select(GmailAccount).where(GmailAccount.profile_id == gmail_profile)
        ).first()
        assert acc is not None
        assert "rt-test" not in acc.refresh_token

    # disconnect
    res = client.post(f"{API}/profiles/{gmail_profile}/gmail/disconnect")
    assert res.status_code == 204
    st = client.get(f"{API}/profiles/{gmail_profile}/gmail/status").json()
    assert st["connected"] is False


def test_callback_bad_state_is_friendly(client):
    cb = client.get(f"{API}/gmail/oauth/callback?state=nope&code=x")
    assert cb.status_code == 200
    assert "could not verify" in cb.text.lower()


def test_callback_google_error_is_friendly(client):
    cb = client.get(f"{API}/gmail/oauth/callback?state=x&error=access_denied")
    assert cb.status_code == 200
    assert "access_denied" in cb.text


def test_gmail_draft_flow(client, contact, gmail_profile, configured, monkeypatch):
    # not connected -> 409
    res = client.post(f"{API}/recruiters/{contact['id']}/gmail-draft", json={"tone": "direct"})
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "GMAIL_NOT_CONNECTED"

    _connect(client, gmail_profile, monkeypatch)
    monkeypatch.setattr(
        gmailx, "create_draft", lambda rt, to, subject, body: "draft-123"
    )
    res = client.post(
        f"{API}/recruiters/{contact['id']}/gmail-draft",
        json={"tone": "direct", "job_title": "Support Specialist"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["gmail_draft_id"] == "draft-123"
    assert body["to_email"] == contact["email"]
    assert "draftid=draft-123" in body["gmail_url"]
    assert "About the Support Specialist role" in body["subject"]

    # listed on the outreach page
    drafts = client.get(f"{API}/profiles/{gmail_profile}/outreach/drafts").json()
    assert len(drafts) == 1
    assert drafts[0]["to_email"] == contact["email"]
    assert drafts[0]["recruiter_name"] == "Ayesha Khan"
    assert drafts[0]["gmail_url"]


def test_gmail_draft_blocked_when_suppressed(client, gmail_profile, configured, monkeypatch):
    c = client.post(
        f"{API}/profiles/{gmail_profile}/recruiters",
        json={"name": "Noah", "email": "noah@x.example", "email_status": "published"},
    ).json()
    client.patch(f"{API}/recruiters/{c['id']}", json={"suppressed": True})
    _connect(client, gmail_profile, monkeypatch)
    res = client.post(f"{API}/recruiters/{c['id']}/gmail-draft", json={})
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "SUPPRESSED"


def test_gmail_draft_requires_email(client, gmail_profile, configured, monkeypatch):
    c = client.post(
        f"{API}/profiles/{gmail_profile}/recruiters",
        json={"name": "No Email", "email_status": "none"},
    ).json()
    _connect(client, gmail_profile, monkeypatch)
    res = client.post(f"{API}/recruiters/{c['id']}/gmail-draft", json={})
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "NO_EMAIL"


def test_gmail_draft_throttle(client, gmail_profile, configured, monkeypatch):
    _connect(client, gmail_profile, monkeypatch)
    monkeypatch.setattr(gmailx, "create_draft", lambda rt, to, subject, body: "d")
    for i in range(20):
        c = client.post(
            f"{API}/profiles/{gmail_profile}/recruiters",
            json={"name": f"P{i}", "email": f"p{i}@x.example", "email_status": "published"},
        ).json()
        res = client.post(f"{API}/recruiters/{c['id']}/gmail-draft", json={})
        assert res.status_code == 201, res.text
    c = client.post(
        f"{API}/profiles/{gmail_profile}/recruiters",
        json={"name": "P21", "email": "p21@x.example", "email_status": "published"},
    ).json()
    res = client.post(f"{API}/recruiters/{c['id']}/gmail-draft", json={})
    assert res.status_code == 429
    assert res.json()["detail"]["code"] == "THROTTLED"

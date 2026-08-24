"""Consent grant/revoke and enforcement tests."""
import uuid

API = "/api/v1"


def test_grant_and_list_consents(client, profile_id):
    res = client.post(
        f"{API}/profiles/{profile_id}/consents",
        json={"item": "job_matching", "granted": True, "notes": "matched roles"},
    )
    assert res.status_code == 201
    assert res.json()["item"] == "job_matching"
    assert res.json()["granted"] is True
    assert res.json()["revoked_at"] is None

    listing = client.get(f"{API}/profiles/{profile_id}/consents").json()
    assert [c["item"] for c in listing] == ["job_matching"]


def test_revoke_sets_revoked_state(client, profile_id):
    client.post(
        f"{API}/profiles/{profile_id}/consents", json={"item": "outreach_sending"}
    )
    res = client.delete(f"{API}/profiles/{profile_id}/consents/outreach_sending")
    assert res.status_code == 204
    listing = client.get(f"{API}/profiles/{profile_id}/consents").json()
    entry = next(c for c in listing if c["item"] == "outreach_sending")
    assert entry["granted"] is False
    assert entry["revoked_at"] is not None


def test_revoked_consent_is_not_active(client, profile_id):
    client.post(
        f"{API}/profiles/{profile_id}/consents", json={"item": "profile_processing"}
    )
    client.delete(f"{API}/profiles/{profile_id}/consents/profile_processing")
    res = client.post(
        f"{API}/profiles/{profile_id}/cvs",
        json={"text": "x" * 60},
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "CONSENT_REQUIRED"


def test_regrant_reactivates_consent(client, profile_id):
    client.post(
        f"{API}/profiles/{profile_id}/consents", json={"item": "profile_processing"}
    )
    client.delete(f"{API}/profiles/{profile_id}/consents/profile_processing")
    client.post(
        f"{API}/profiles/{profile_id}/consents", json={"item": "profile_processing"}
    )
    res = client.post(
        f"{API}/profiles/{profile_id}/cvs",
        json={"text": "A" * 60, "title": "Re-granted CV"},
    )
    assert res.status_code == 201


def test_unknown_profile_404(client):
    res = client.post(
        f"{API}/profiles/{uuid.uuid4()}/consents", json={"item": "media_use"}
    )
    assert res.status_code == 404

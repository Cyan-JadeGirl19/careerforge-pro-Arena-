"""Profile CRUD and erasure tests."""
import uuid

API = "/api/v1"


def test_create_profile_returns_full_shape(client):
    res = client.post(
        f"{API}/profiles",
        json={"first_name": "Zanele", "last_name": "Dube", "summary": "Ops lead"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["first_name"] == "Zanele"
    assert body["timezone"] == "Africa/Johannesburg"
    assert body["status"] == "active"
    uuid.UUID(body["id"])  # valid UUID


def test_get_missing_profile_404s(client):
    res = client.get(f"{API}/profiles/{uuid.uuid4()}")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "PROFILE_NOT_FOUND"


def test_patch_updates_only_sent_fields(client, profile_id):
    res = client.patch(f"{API}/profiles/{profile_id}", json={"summary": "New summary"})
    assert res.status_code == 200
    assert res.json()["summary"] == "New summary"
    assert res.json()["first_name"] == "Thando"  # untouched


def test_delete_erases_profile_and_dependents(client, consented_profile, cv_id):
    pid = consented_profile
    assert client.get(f"{API}/cvs/{cv_id}").status_code == 200
    res = client.delete(f"{API}/profiles/{pid}")
    assert res.status_code == 204
    assert client.get(f"{API}/profiles/{pid}").status_code == 404
    assert client.get(f"{API}/cvs/{cv_id}").status_code == 404
    assert client.get(f"{API}/profiles/{pid}/consents").status_code == 404

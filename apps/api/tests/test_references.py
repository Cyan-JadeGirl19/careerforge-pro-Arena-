"""Reference Manager tests: CRUD, permissions, documents, list parsing,
application integration, erasure."""
import io
import json

API = "/api/v1"

# ------------------------------------------------------------- list parsing

from app.references.parse_list import parse_reference_list  # noqa: E402

LIST_TEXT = """REFERENCES

Dr. Naledi Khumalo
Head of Customer Operations, Luno
naledi.khumalo@luno.com
+27 82 555 0101

Sam Patel
Former Manager, PayFast
sam.patel@payfast.co.za
082 444 2211

Professor J. Mokoena
University of Pretoria
jmokoena@up.ac.za
"""


def test_parse_reference_list():
    out = parse_reference_list(LIST_TEXT)
    assert len(out) == 3
    names = {o["name"] for o in out}
    assert "Dr. Naledi Khumalo" in names
    assert "Sam Patel" in names
    assert "Professor J. Mokoena" in names
    n = next(o for o in out if o["name"] == "Sam Patel")
    assert n["email"] == "sam.patel@payfast.co.za"
    assert n["phone"] == "082 444 2211"
    # permission is never assumed
    assert all(o["permission_confirmed"] is False for o in out)


def test_parse_reference_list_ignores_headers():
    out = parse_reference_list("Name: not a person\nEmail: x@y.com\n")
    names = [o["name"] for o in out if o["name"]]
    assert "not a person" not in [n for n in names if "not a person" in n.lower()]


# -------------------------------------------------------------------- routes


def _add_reference(client, pid, **kw) -> str:
    body = {
        "name": "Dr. Naledi Khumalo",
        "title": "Head of Customer Operations",
        "relationship": "former manager",
        "company": "Luno",
        "email": "naledi.khumalo@luno.com",
        "phone": "+27 82 555 0101",
        "type": "former",
        "permission_confirmed": kw.pop("permission_confirmed", True),
        **kw,
    }
    res = client.post(f"{API}/profiles/{pid}/references", json=body)
    assert res.status_code == 201
    return res.json()["id"]


def test_requires_consent(client, profile_id):
    res = client.post(
        f"{API}/profiles/{profile_id}/references",
        json={"name": "Someone Else"},
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "CONSENT_REQUIRED"


def test_crud_and_permission_flow(client, consented_profile):
    rid = _add_reference(client, consented_profile)
    got = client.get(f"{API}/references/{rid}").json()
    assert got["name"] == "Dr. Naledi Khumalo"
    assert got["permission_confirmed"] is True
    assert got["permission_confirmed_at"] is not None

    # revoke confirmation
    upd = client.patch(f"{API}/references/{rid}", json={"permission_confirmed": False})
    assert upd.status_code == 200
    assert upd.json()["permission_confirmed"] is False
    assert upd.json()["permission_confirmed_at"] is None  # reset when unconfirmed

    # suppress -> hidden from default list
    client.patch(f"{API}/references/{rid}", json={"suppressed": True})
    assert all(r["id"] != rid for r in client.get(
        f"{API}/profiles/{consented_profile}/references"
    ).json())


def test_parse_list_endpoint(client, consented_profile):
    res = client.post(
        f"{API}/profiles/{consented_profile}/references/parse-list",
        files={"file": ("refs.txt", LIST_TEXT.encode(), "text/plain")},
    )
    assert res.status_code == 201
    refs = res.json()
    assert len(refs) == 3
    assert all(r["permission_confirmed"] is False for r in refs)


def test_document_upload_download_delete(client, consented_profile):
    rid = _add_reference(client, consented_profile)
    res = client.post(
        f"{API}/references/{rid}/documents",
        files={"file": ("letter.txt", b"Reference letter body", "text/plain")},
    )
    assert res.status_code == 201
    doc_id = res.json()["id"]
    assert res.json()["filename"] == "letter.txt"

    listing = client.get(f"{API}/references/{rid}/documents").json()
    assert len(listing) == 1

    dl = client.get(f"{API}/documents/{doc_id}/download")
    assert dl.status_code == 200
    assert dl.content == b"Reference letter body"

    # bad type rejected
    bad = client.post(
        f"{API}/references/{rid}/documents",
        files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
    )
    assert bad.status_code == 415

    assert client.delete(f"{API}/documents/{doc_id}").status_code == 204
    assert client.get(f"{API}/documents/{doc_id}/download").status_code == 404


# ------------------------------------------------------- application flow


def _app_with_cv(client, pid):
    import re as _re

    sample = open(__file__).read()
    # reuse the shared sample CV from conftest
    import conftest

    cv = client.post(f"{API}/profiles/{pid}/cvs", json={"text": conftest.SAMPLE_CV})
    assert cv.status_code == 201
    jd = client.post(
        f"{API}/profiles/{pid}/job-descriptions",
        json={"title": "Customer Success Manager", "company": "Acme", "text": "A" * 60},
    )
    app = client.post(f"{API}/profiles/{pid}/applications", json={"jd_id": jd.json()["id"]})
    assert app.status_code == 201
    return app.json()


def test_attach_references_requires_permission(client, consented_profile):
    app = _app_with_cv(client, consented_profile)
    rid_unconfirmed = _add_reference(
        client, consented_profile, permission_confirmed=False, name="Unconfirmed Person"
    )
    res = client.post(
        f"{API}/applications/{app['id']}/references",
        json={"references_requested": "yes", "reference_ids": [rid_unconfirmed]},
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "PERMISSION_NOT_CONFIRMED"


def test_attach_approved_references_and_summary(client, consented_profile):
    app = _app_with_cv(client, consented_profile)
    rid = _add_reference(client, consented_profile)
    res = client.post(
        f"{API}/applications/{app['id']}/references",
        json={"references_requested": "yes", "reference_ids": [rid]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["references_requested"] == "yes"
    assert len(body["references"]) == 1
    assert body["references"][0]["name"] == "Dr. Naledi Khumalo"
    assert body["references"][0]["missing"] == []

    summary = client.get(f"{API}/applications/{app['id']}/references/summary")
    assert summary.status_code == 200
    assert "Dr. Naledi Khumalo" in summary.text
    assert "naledi.khumalo@luno.com" in summary.text


def test_missing_contact_flagged_in_applications(client, consented_profile):
    app = _app_with_cv(client, consented_profile)
    rid = _add_reference(
        client, consented_profile, name="No Contact Person", email=None, phone=None
    )
    res = client.post(
        f"{API}/applications/{app['id']}/references",
        json={"references_requested": "yes", "reference_ids": [rid]},
    )
    assert res.status_code == 200
    assert "no contact details" in res.json()["references"][0]["missing"]


# ------------------------------------------------------------------ erasure


def test_erasure_deletes_references_and_files(client, consented_profile):
    rid = _add_reference(client, consented_profile)
    doc = client.post(
        f"{API}/references/{rid}/documents",
        files={"file": ("letter.txt", b"body", "text/plain")},
    ).json()
    path = None
    # locate the stored file via the db to assert physical deletion
    from app.db import SessionLocal
    from app.models import ReferenceDocument
    from sqlalchemy import select

    db = SessionLocal()
    row = db.get(ReferenceDocument, doc["id"])
    path = row.storage_path
    db.close()
    assert path and __import__("os").path.exists(path)

    assert client.delete(f"{API}/profiles/{consented_profile}").status_code == 204
    assert client.get(f"{API}/references/{rid}").status_code == 404
    assert not __import__("os").path.exists(path)

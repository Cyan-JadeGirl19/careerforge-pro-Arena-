"""Recruiter discovery tests: extraction rules, routes, outreach, erasure."""
import pytest

API = "/api/v1"

# ------------------------------------------------------------- extraction

from app.recruiters.extract import extract_contacts, visible_text  # noqa: E402


def test_visible_text_strips_scripts_and_ad_pixels():
    html = (
        "<html><body><h1>Job</h1>"
        "<script>adroll_email=\"secret@adtracker.com\"; track('x');</script>"
        "<p>Reach us at real@example.com</p></body></html>"
    )
    text = visible_text(html)
    assert "secret@adtracker.com" not in text
    assert "real@example.com" in text


def test_extract_published_email_visible_only():
    html = (
        "<html><body>"
        "<script>var pixel='hidden@pixels.io';</script>"
        "<p>We are hiring a Customer Success Manager. Questions? email careers@acme.com</p>"
        "</body></html>"
    )
    out = extract_contacts("https://acme.com/jobs/csm", html, company_hint="Acme")
    emails = [c["email"] for c in out if c["email"]]
    assert "careers@acme.com" in emails
    assert "hidden@pixels.io" not in emails
    pub = next(c for c in out if c["email"] == "careers@acme.com")
    assert pub["email_status"] == "published"
    assert pub["company"] == "Acme"


def test_extract_linkedin_profile_url():
    html = (
        '<html><body><a href="https://www.linkedin.com/in/janedoe">Jane Doe</a></body></html>'
    )
    out = extract_contacts("https://acme.com/jobs/csm", html, company_hint="Acme")
    assert any(c["profile_url"] == "https://linkedin.com/in/janedoe" for c in out)


def test_extract_name_pattern_and_pattern_suggested_email():
    html = (
        "<html><body><p>Apply with Sarah Kim for the remote role. "
        "No direct email listed.</p></body></html>"
    )
    out = extract_contacts("https://acme.com/jobs/csm", html, company_hint="Acme")
    named = [c for c in out if c["name"] == "Sarah Kim"]
    assert named, "name pattern should be captured"
    c = named[0]
    # No published email -> pattern suggestions, clearly unverified.
    assert c["email"] is None
    assert c["email_status"] == "pattern_suggested"
    assert "sarah.kim@acme.com" in c["suggested_emails"]
    assert "s.kim@acme.com" in c["suggested_emails"]


def test_extract_ignores_nav_stopwords():
    html = "<html><body><p>Apply with AI. Contact Us. Recruiter The Team.</p></body></html>"
    out = extract_contacts("https://acme.com/jobs", html, company_hint="Acme")
    names = [c["name"] for c in out if c["name"]]
    assert not any(n in ("AI", "Us", "The Team") for n in names)


def test_extract_ignores_nav_fragments_from_real_pages():
    """Live WWR pages produce footer text like 'Apply with AI No account?
    ... Contact Support Terms Guidelines Privacy Why Choose ...' - none of
    these may be saved as recruiter names."""
    html = (
        "<html><body><p>Apply with AI No account? Sign up. "
        "Contact Support Terms Guidelines Privacy Why Choose Us Top 100 "
        "Remote Companies New! Search by Job Category</p></body></html>"
    )
    out = extract_contacts("https://wwr.example/remote-jobs/x", html, company_hint="X")
    assert out == [], f"nav fragments were saved as contacts: {out}"


def test_extract_nothing_clean():
    out = extract_contacts("https://acme.com/jobs", "<html><body><p>General job text.</p></body></html>")
    assert out == []


# ------------------------------------------------------------------ routes

def test_extract_route_mocks_fetch(client, consented_profile, monkeypatch):
    import app.api.v1.recruiters as r

    monkeypatch.setattr(
        r, "_fetch_page",
        lambda url: "<html><body><p>Apply with Sarah Kim. email careers@acme.com</p></body></html>",
    )
    res = client.post(
        f"{API}/profiles/{consented_profile}/recruiters/extract",
        json={"url": "https://acme.com/jobs/csm", "company": "Acme"},
    )
    assert res.status_code == 201
    contacts = res.json()
    assert len(contacts) >= 2
    assert any(c["name"] == "Sarah Kim" for c in contacts)
    assert any(c["email"] == "careers@acme.com" for c in contacts)


def test_extract_requires_consent(client, profile_id, monkeypatch):
    import app.api.v1.recruiters as r

    monkeypatch.setattr(r, "_fetch_page", lambda url: "<html><body>x</body></html>")
    res = client.post(
        f"{API}/profiles/{profile_id}/recruiters/extract",
        json={"url": "https://acme.com/jobs/csm"},
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "CONSENT_REQUIRED"


def test_manual_create_verify_suppress_delete(client, consented_profile):
    res = client.post(
        f"{API}/profiles/{consented_profile}/recruiters",
        json={
            "name": "John Mthembu",
            "title": "Talent Acquisition Lead",
            "company": "BuildCo",
            "email": "john@buildco.com",
            "email_status": "published",
            "profile_url": "https://linkedin.com/in/johnmthembu",
            "job_title": "Operations Analyst",
        },
    )
    assert res.status_code == 201
    cid = res.json()["id"]
    assert res.json()["company"] == "BuildCo"

    # list
    listing = client.get(f"{API}/profiles/{consented_profile}/recruiters").json()
    assert any(c["id"] == cid for c in listing)

    # verify
    upd = client.patch(f"{API}/recruiters/{cid}", json={"verified": True})
    assert upd.status_code == 200
    assert upd.json()["verified"] is True
    assert upd.json()["verified_at"] is not None

    # suppress -> hidden from default list
    client.patch(f"{API}/recruiters/{cid}", json={"suppressed": True})
    assert all(c["id"] != cid for c in client.get(f"{API}/profiles/{consented_profile}/recruiters").json())
    # still present with include_suppressed
    assert any(c["id"] == cid for c in client.get(
        f"{API}/profiles/{consented_profile}/recruiters?include_suppressed=true"
    ).json())

    # delete
    assert client.delete(f"{API}/recruiters/{cid}").status_code == 204
    assert client.get(f"{API}/recruiters/{cid}").status_code == 404


# --------------------------------------------------------------- outreach


def _make_contact(client, pid, **kw) -> str:
    res = client.post(f"{API}/profiles/{pid}/recruiters", json={
        "name": "Sarah Kim", "title": "Hiring Manager", "company": "Acme",
        "email": "careers@acme.com", "email_status": "published",
        "job_title": "Customer Success Manager",
        **kw,
    })
    assert res.status_code == 201
    return res.json()["id"]


def test_outreach_draft_personalised_and_clean(client, consented_profile, cv_id):
    client.post(
        f"{API}/profiles/{consented_profile}/consents", json={"item": "outreach_sending"}
    )
    cid = _make_contact(client, consented_profile)
    res = client.post(f"{API}/recruiters/{cid}/outreach", json={"job_title": "Customer Success Manager"})
    assert res.status_code == 200
    draft = res.json()["draft"]
    assert "Sarah" in draft
    assert "Acme" in draft
    assert "Customer Success Manager" in draft
    # uses the candidate's real role/evidence from the CV
    assert "Support Team Lead" in draft or "CSAT" in draft
    low = draft.lower()
    for banned in ("excited to apply", "leveraged", "synergy", "passionate self-starter"):
        assert banned not in low
    # published email -> no verification warning
    assert not any("pattern" in i.lower() for i in res.json()["issues"])


def test_outreach_draft_flags_unverified_email(client, consented_profile, cv_id):
    client.post(
        f"{API}/profiles/{consented_profile}/consents", json={"item": "outreach_sending"}
    )
    cid = _make_contact(
        client, consented_profile,
        email="sarah.kim@acme.com", email_status="pattern_suggested",
    )
    res = client.post(f"{API}/recruiters/{cid}/outreach", json={"job_title": "Customer Success Manager"})
    assert res.status_code == 200
    assert any("unverified" in i.lower() or "pattern" in i.lower() for i in res.json()["issues"])


def test_outreach_requires_consent(client):
    # Brand-new profile with NO consents (the cv_id fixture would grant some).
    pid = client.post(f"{API}/profiles", json={"first_name": "NoConsent"}).json()["id"]
    res = client.post(f"{API}/profiles/{pid}/recruiters", json={"name": "A B", "company": "X"})
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "CONSENT_REQUIRED"


def test_erasure_covers_contacts(client, consented_profile):
    cid = _make_contact(client, consented_profile)
    assert client.delete(f"{API}/profiles/{consented_profile}").status_code == 204
    assert client.get(f"{API}/recruiters/{cid}").status_code == 404

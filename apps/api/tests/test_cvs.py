"""CV creation and transparent analysis tests."""

API = "/api/v1"


def test_create_cv_requires_consent(client, profile_id):
    res = client.post(
        f"{API}/profiles/{profile_id}/cvs",
        json={"title": "No consent", "text": "A" * 60},
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "CONSENT_REQUIRED"


def test_cv_versions_increment(client, consented_profile):
    for _ in range(2):
        res = client.post(
            f"{API}/profiles/{consented_profile}/cvs",
            json={"text": "A" * 60},
        )
        assert res.status_code == 201
    listing = client.get(f"{API}/profiles/{consented_profile}/cvs").json()
    assert [cv["version"] for cv in listing] == [1, 2]


def test_analyze_reports_transparent_checks(client, cv_id):
    res = client.post(f"{API}/cvs/{cv_id}/analyze")
    assert res.status_code == 200
    body = res.json()
    check_names = [c["check"] for c in body["checks"]]
    assert check_names == [
        "contact_info",
        "sections",
        "achievement_bullets",
        "quantified_results",
        "length",
    ]
    assert all(c["passed"] for c in body["checks"])
    keywords = {k["keyword"]: k["present"] for k in body["keywords"]}
    assert keywords["remote"] is True
    assert keywords["python"] is False
    assert body["gaps"] == []
    assert "not a vendor ATS pass-rate score" in body["note"]


def test_analyze_flags_weak_cv(client, consented_profile):
    res = client.post(
        f"{API}/profiles/{consented_profile}/cvs",
        json={"text": "I do admin work and use a computer for my daily tasks at the office."},
    )
    assert res.status_code == 201
    cv_id = res.json()["id"]
    report = client.post(f"{API}/cvs/{cv_id}/analyze").json()
    by_name = {c["check"]: c for c in report["checks"]}
    assert by_name["contact_info"]["passed"] is False
    assert by_name["quantified_results"]["passed"] is False
    assert len(report["gaps"]) >= 2


def test_latest_analysis_404_before_analysis(client, consented_profile):
    res = client.post(
        f"{API}/profiles/{consented_profile}/cvs", json={"text": "B" * 60}
    )
    cv_id = res.json()["id"]
    res = client.get(f"{API}/cvs/{cv_id}/analysis/latest")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "ANALYSIS_NOT_FOUND"
    client.post(f"{API}/cvs/{cv_id}/analyze")
    assert client.get(f"{API}/cvs/{cv_id}/analysis/latest").status_code == 200


def test_min_length_enforced(client, consented_profile):
    res = client.post(
        f"{API}/profiles/{consented_profile}/cvs", json={"text": "too short"}
    )
    assert res.status_code == 422

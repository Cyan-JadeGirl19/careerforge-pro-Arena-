"""Skills & Salary and Portfolio Builder tests."""

API = "/api/v1"

# ------------------------------------------------------------------ skills


def test_skills_gaps_from_cv(client, consented_profile, cv_id):
    res = client.get(f"{API}/skills/gaps?profile_id={consented_profile}&role=Operations Analyst")
    assert res.status_code == 200
    body = res.json()
    # sample CV has data analysis + excel; sql/python likely missing
    assert "data analysis" in body["present"]
    assert "excel" in body["present"]
    assert "sql" in body["missing"]
    # courses offered for missing skills, all with URLs
    for c in body["courses"]:
        assert c["url"].startswith("http")
    assert "2026" in body["catalog_as_of"]
    assert "not valid once" not in body["note"]  # sanity: note present
    assert body["note"]


def test_plan_90d_covers_gaps(client, consented_profile, cv_id):
    res = client.get(f"{API}/skills/plan-90d?profile_id={consented_profile}&role=Operations Analyst")
    assert res.status_code == 200
    weeks = res.json()["weeks"]
    assert len(weeks) >= 2
    assert any("Learn" in w["focus"] for w in weeks)
    # plan spans exactly weeks 1-12
    assert weeks[0]["weeks"].startswith("1-")
    assert weeks[-1]["weeks"] == "10-12"


def test_salary_benchmarks_with_disclaimer(client):
    res = client.get(f"{API}/salary/benchmarks?role=Customer Success Manager")
    assert res.status_code == 200
    body = res.json()
    assert body["found"] is True
    assert body["usd_month"][0] < body["usd_month"][1]
    assert body["zar_month"][0] < body["zar_month"][1]
    assert body["rate"]["source"]
    assert "SARS" in body["disclaimer"]
    assert "tax" in body["disclaimer"].lower()


def test_salary_unknown_role_honest(client):
    res = client.get(f"{API}/salary/benchmarks?role=Underwater Basket Weaving")
    assert res.status_code == 200
    body = res.json()
    assert body["found"] is False
    assert body["disclaimer"]


def test_negotiation_scripts_and_payment(client):
    res = client.get(f"{API}/salary/negotiation-scripts")
    assert res.status_code == 200
    assert len(res.json()["scripts"]) >= 3
    res = client.get(f"{API}/salary/payment-guidance")
    assert res.status_code == 200
    assert any("SARS" in p for p in res.json()["points"])


# ---------------------------------------------------------------- portfolio


def _add_item(client, pid, **kw):
    body = {"title": "Test Project", "type": "project", **kw}
    res = client.post(f"{API}/profiles/{pid}/portfolio", json=body)
    assert res.status_code == 201
    return res.json()


def test_portfolio_crud_and_approval(client, consented_profile):
    item = _add_item(client, consented_profile, approved=False, url="https://example.com/x")
    assert item["approved"] is False

    # public page shows nothing until approved
    page = client.get(f"{API}/portfolio-page/{consented_profile}")
    assert page.status_code == 200
    assert "Test Project" not in page.text

    res = client.patch(f"{API}/portfolio/{item['id']}", json={"approved": True})
    assert res.status_code == 200
    assert res.json()["approved"] is True

    page = client.get(f"{API}/portfolio-page/{consented_profile}")
    assert "Test Project" in page.text
    assert 'href="https://example.com/x"' in page.text

    assert client.delete(f"{API}/portfolio/{item['id']}").status_code == 204
    assert client.get(f"{API}/profiles/{consented_profile}/portfolio").json() == []


def test_portfolio_bad_type_rejected(client, consented_profile):
    res = client.post(
        f"{API}/profiles/{consented_profile}/portfolio",
        json={"title": "X", "type": "hologram"},
    )
    assert res.status_code == 422


def test_portfolio_requires_profile(client):
    res = client.post(
        f"{API}/profiles/{__import__('uuid').uuid4()}/portfolio",
        json={"title": "X"},
    )
    assert res.status_code == 404


def test_portfolio_github_bad_format(client, consented_profile):
    res = client.post(
        f"{API}/profiles/{consented_profile}/portfolio/github",
        json={"repo": "not a valid repo"},
    )
    assert res.status_code == 422


def test_erasure_covers_portfolio(client, consented_profile):
    item = _add_item(client, consented_profile)
    assert client.delete(f"{API}/profiles/{consented_profile}").status_code == 204
    assert client.get(f"{API}/portfolio-page/{consented_profile}").status_code == 404

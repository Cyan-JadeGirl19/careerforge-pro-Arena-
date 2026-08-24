"""Shared test fixtures.

Environment is configured BEFORE the app is imported so the engine is
created against the throwaway test database.
"""
import os
import pathlib
import sys

_TEST_DIR = pathlib.Path(__file__).resolve().parent
_DB_FILE = _TEST_DIR / "test_careerforge.db"
if _DB_FILE.exists():
    _DB_FILE.unlink()

os.environ["CF_ENVIRONMENT"] = "test"
os.environ["CF_DATABASE_URL"] = f"sqlite:///{_DB_FILE}"
sys.path.insert(0, str(_TEST_DIR.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

API = "/api/v1"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def profile_id(client) -> str:
    res = client.post(f"{API}/profiles", json={"first_name": "Thando"})
    assert res.status_code == 201
    return res.json()["id"]


@pytest.fixture()
def consented_profile(client, profile_id) -> str:
    res = client.post(
        f"{API}/profiles/{profile_id}/consents",
        json={"item": "profile_processing", "granted": True},
    )
    assert res.status_code == 201
    return profile_id


SAMPLE_CV = """\
Thando Ndlovu
thando@example.com
+27 82 123 4567

Summary
Customer operations professional with 6 years in remote SaaS support.

Experience
- Led a remote team of 4 support agents; raised CSAT from 82% to 91%
- Handled 40+ tickets per day for SaaS customers across 3 time zones
- Built a knowledge base that cut repeat tickets by 22%

Education
BCom, University of Pretoria

Skills
Project management, data analysis, communication, stakeholder management,
Excel, agile delivery, remote collaboration, customer success
"""


@pytest.fixture()
def cv_id(client, consented_profile) -> str:
    res = client.post(
        f"{API}/profiles/{consented_profile}/cvs",
        json={"title": "Master CV", "text": SAMPLE_CV},
    )
    assert res.status_code == 201
    return res.json()["id"]

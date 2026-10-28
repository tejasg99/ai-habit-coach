import os

# Must be set BEFORE the app is imported: Settings() reads the environment at import time,
# and real environment variables override your .env file.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-only-secret-key-that-is-long-enough-123456"
# Make real LLM calls impossible in tests: fake key, and a reserved ".invalid" domain
# that never resolves. Tests that need LLM output mock it.
os.environ["LLM_API_KEY"] = "test-key-not-real"
os.environ["LLM_BASE_URL"] = "http://llm.invalid/v1"
os.environ["LLM_MODEL"] = "test-model"

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from tests.helpers import bearer, valid_plan_text

ONBOARDING = {
    "goal": "build_muscle",
    "fitness_level": "beginner",
    "dietary_pref": "vegetarian",
    "equipment": ["dumbbells"],
    "timezone": "Asia/Kolkata",
    "reminder_time": "19:30:00",
}


@pytest.fixture()
def engine():
    """A brand-new in-memory database for EVERY test."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session_factory(engine):
    """Tests can open sessions from this to inspect what was really saved."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def register(client):
    """Factory fixture: creates a user, logs in, returns the token pair."""

    def _register(email="tejas@example.com", password="correct-horse-battery"):
        res = client.post("/auth/signup", json={"email": email, "password": password})
        assert res.status_code == 201, res.text
        res = client.post("/auth/login", data={"username": email, "password": password})
        assert res.status_code == 200, res.text
        return res.json()

    return _register


class FakeLLM:
    """Stands in for chat_completion. Queue up replies (strings, or exceptions to raise)."""

    def __init__(self):
        self.queue = []
        self.calls = 0

    def __call__(self, messages, **kwargs):
        self.calls += 1
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture()
def fake_llm(monkeypatch):
    fake = FakeLLM()
    # Patch the name where it is USED (plan_generator), not where it is defined.
    monkeypatch.setattr("app.services.plan_generator.chat_completion", fake)
    return fake


@pytest.fixture()
def headers(client, register):
    """Auth headers for a user who has completed onboarding."""
    h = bearer(register())
    assert client.put("/onboarding/me", json=ONBOARDING, headers=h).status_code == 200
    return h


@pytest.fixture()
def set_today(monkeypatch):
    """Freeze 'today' for every feature at once, through the single place that decides it."""

    def _set(day: date):
        monkeypatch.setattr("app.services.plans.local_today", lambda tz, now=None: day)

    return _set


@pytest.fixture()
def plan(client, headers, fake_llm):
    """The user has a generated plan: 7 days x 2 items."""
    fake_llm.queue.append(valid_plan_text())
    assert client.post("/plan/generate", headers=headers).status_code == 201

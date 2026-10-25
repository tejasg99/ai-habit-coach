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

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def session_factory():
    """A brand-new in-memory database for EVERY test. Tests can open sessions from it
    to inspect what was really saved."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


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

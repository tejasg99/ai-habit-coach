import os

# Must be set BEFORE the app is imported: Settings() reads the environment at import time,
# and real environment variables override your .env file.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-only-secret-key-that-is-long-enough-123456"

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
def client():
    # A brand-new in-memory SQLite database for EVERY test, so tests can't affect each other.
    # StaticPool makes every connection share that one in-memory database.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)  # fine for a throwaway DB; real DBs use migrations
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    engine.dispose()


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

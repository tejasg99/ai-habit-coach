import pytest
from pydantic import ValidationError

from app.core.config import Settings


def make(**overrides):
    values = {"DATABASE_URL": "sqlite://", "SECRET_KEY": "k" * 40, **overrides}
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "given, expected",
    [
        (
            "postgres://u:p@host/db?sslmode=require",
            "postgresql+psycopg://u:p@host/db?sslmode=require",
        ),
        ("postgresql://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("sqlite://", "sqlite://"),
    ],
)
def test_database_url_always_uses_the_psycopg3_driver(given, expected):
    assert make(DATABASE_URL=given).DATABASE_URL == expected


def test_production_refuses_a_short_secret():
    with pytest.raises(ValidationError):
        make(ENVIRONMENT="production", SECRET_KEY="short")


def test_production_accepts_a_long_secret():
    assert make(ENVIRONMENT="production").ENVIRONMENT == "production"


def test_development_allows_a_short_secret():
    make(SECRET_KEY="short")


def test_a_misspelled_environment_is_rejected():
    with pytest.raises(ValidationError):
        make(ENVIRONMENT="prod")

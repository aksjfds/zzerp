"""Explicit application configuration; importing this module does not read .env."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL


def _database_url() -> str:
    if value := os.getenv("DATABASE_URL"):
        return value
    fields = {
        "POSTGRES_USER": os.getenv("POSTGRES_USER"),
        "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "POSTGRES_HOST": os.getenv("POSTGRES_HOST"),
        "POSTGRES_DB": os.getenv("POSTGRES_DB"),
    }
    missing = [name for name, value in fields.items() if not value]
    if missing:
        raise ValueError(f"Missing database configuration: {', '.join(missing)}")
    query = {
        key: value
        for key, value in {
            "sslmode": os.getenv("POSTGRES_SSLMODE"),
            "channel_binding": os.getenv("POSTGRES_CHANNEL_BINDING"),
        }.items()
        if value
    }
    return URL.create(
        "postgresql+psycopg2",
        username=fields["POSTGRES_USER"],
        password=fields["POSTGRES_PASSWORD"],
        host=fields["POSTGRES_HOST"],
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=fields["POSTGRES_DB"],
        query=query,
    ).render_as_string(hide_password=False)


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    allowed_origins: tuple[str, ...]
    allowed_origin_regex: str | None
    session_cookie_name: str
    session_expire_hours: int
    cookie_secure: bool
    cookie_samesite: str

    def allows_origin(self, origin: str) -> bool:
        return (
            origin in self.allowed_origins
            or "*" in self.allowed_origins
            or bool(self.allowed_origin_regex and re.fullmatch(self.allowed_origin_regex, origin))
        )


def load_settings() -> Settings:
    backend = Path(__file__).resolve().parents[2]
    environment = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "production"
    load_dotenv(os.getenv("ENV_FILE") or backend / f".env.{environment}")
    samesite = os.getenv("COOKIE_SAMESITE", "none").lower()
    if samesite not in {"lax", "strict", "none"}:
        raise ValueError("COOKIE_SAMESITE must be lax, strict, or none")
    hours = int(os.getenv("SESSION_EXPIRE_HOURS", "12"))
    if hours <= 0:
        raise ValueError("SESSION_EXPIRE_HOURS must be positive")
    pattern = os.getenv("ALLOWED_ORIGIN_REGEX") or None
    if pattern:
        re.compile(pattern)
    return Settings(
        database_url=_database_url(),
        allowed_origins=tuple(
            value.strip()
            for value in os.getenv(
                "ALLOWED_ORIGINS",
                "http://localhost:5173,https://zzerp.netlify.app",
            ).split(",")
            if value.strip()
        ),
        allowed_origin_regex=pattern,
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "zzerp_session"),
        session_expire_hours=hours,
        cookie_secure=os.getenv("COOKIE_SECURE", "true").lower() in {"1", "true", "yes"},
        cookie_samesite=samesite,
    )

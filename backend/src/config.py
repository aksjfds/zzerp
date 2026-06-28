from functools import lru_cache
import os
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]

env_file = os.getenv("ENV_FILE")
app_env = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "production"

if env_file:
    load_dotenv(env_file)
else:
    env_path = BACKEND_DIR / f".env.{app_env}"
    load_dotenv(env_path)


def _build_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB")
    sslmode = os.getenv("POSTGRES_SSLMODE")
    channel_binding = os.getenv("POSTGRES_CHANNEL_BINDING")

    missing = [
        name
        for name, value in {
            "POSTGRES_USER": user,
            "POSTGRES_PASSWORD": password,
            "POSTGRES_HOST": host,
            "POSTGRES_DB": database,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing database configuration: {', '.join(missing)}")

    query_params = {
        key: value
        for key, value in {
            "sslmode": sslmode,
            "channel_binding": channel_binding,
        }.items()
        if value
    }
    query = f"?{urlencode(query_params)}" if query_params else ""

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}{query}"


class Settings:
    database_url: str
    allowed_origins: list[str]
    session_cookie_name: str
    session_expire_hours: int
    cookie_secure: bool
    cookie_samesite: str

    def __init__(self) -> None:
        self.database_url = _build_database_url()
        self.allowed_origins = [
            origin.strip()
            for origin in os.getenv(
                "ALLOWED_ORIGINS",
                "http://localhost:5173,https://zzerp.netlify.app",
            ).split(",")
            if origin.strip()
        ]
        self.session_cookie_name = os.getenv("SESSION_COOKIE_NAME", "zzerp_session")
        self.session_expire_hours = int(os.getenv("SESSION_EXPIRE_HOURS", "12"))
        self.cookie_secure = os.getenv("COOKIE_SECURE", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        self.cookie_samesite = os.getenv("COOKIE_SAMESITE", "none").lower()

        if self.cookie_samesite not in {"lax", "strict", "none"}:
            raise RuntimeError("COOKIE_SAMESITE must be lax, strict, or none")


@lru_cache
def get_settings() -> Settings:
    return Settings()

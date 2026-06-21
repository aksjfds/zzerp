from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]

env_file = os.getenv("ENV_FILE")
app_env = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development"

if env_file:
    load_dotenv(env_file)
else:
    env_path = BACKEND_DIR / f".env.{app_env}"
    load_dotenv(env_path if env_path.exists() else BACKEND_DIR / ".env")

load_dotenv(BACKEND_DIR / ".env")


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _build_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB")

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

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


class Settings:
    database_url: str
    cors_origins: list[str]

    def __init__(self) -> None:
        self.database_url = _build_database_url()
        self.cors_origins = _split_csv(os.getenv("CORS_ORIGINS")) or [
            "http://localhost:5173",
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()

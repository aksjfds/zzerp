"""Explicitly rebuild the configured PostgreSQL database from zzerp.sql."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
SCHEMA_FILE = ROOT_DIR / "zzerp.sql"


def database_connection() -> dict | str:
    app_env = os.getenv("APP_ENV") or "development"
    load_dotenv(ROOT_DIR / "backend" / f".env.{app_env}")
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url.replace("postgresql+psycopg2://", "postgresql://", 1)
    required = {
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
        "dbname": os.getenv("POSTGRES_DB"),
        "host": os.getenv("POSTGRES_HOST"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing database configuration: {', '.join(missing)}")
    return required


def main() -> None:
    if os.getenv("ALLOW_DATABASE_RESET") != "yes":
        raise RuntimeError(
            "Database reset refused. Set ALLOW_DATABASE_RESET=yes explicitly."
        )
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    connection_config = database_connection()
    connection = (
        psycopg2.connect(connection_config)
        if isinstance(connection_config, str)
        else psycopg2.connect(**connection_config)
    )
    with connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)

    print("Database schema and test seed data were rebuilt successfully.")


if __name__ == "__main__":
    main()

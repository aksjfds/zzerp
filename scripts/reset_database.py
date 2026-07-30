"""Explicitly rebuild the configured PostgreSQL database from zzerp.sql."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2


ROOT_DIR = Path(__file__).resolve().parents[1]
SCHEMA_FILE = ROOT_DIR / "zzerp.sql"


def main() -> None:
    if os.getenv("ALLOW_DATABASE_RESET") != "yes":
        raise RuntimeError(
            "Database reset refused. Set ALLOW_DATABASE_RESET=yes explicitly."
        )
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)

    print("Database schema and test seed data were rebuilt successfully.")


if __name__ == "__main__":
    main()

import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 to verify the PostgreSQL schema",
)


def test_postgresql_schema_matches_module_ownership():
    from sqlalchemy import inspect

    from database import engine
    from modules.ownership import TABLE_OWNERS

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert set(TABLE_OWNERS) <= tables
    for table_name in TABLE_OWNERS:
        assert inspector.get_pk_constraint(table_name)["constrained_columns"]

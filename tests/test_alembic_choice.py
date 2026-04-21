# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2026 CESNET z.s.p.o.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

import time
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic.script import Script
from mocks import MockEntryPoint
from sqlalchemy import text

from invenio_db.utils import drop_alembic_version_table


def _mock_entry_points(group=None):
    data = {
        "invenio_db.models": [
            MockEntryPoint(
                name="demo.with_choice", value="demo.with_choice", group="test"
            ),
        ],
        "invenio_db.alembic": [
            MockEntryPoint(name="demo", value="demo:alembic", group="test"),
        ],
    }
    if group:
        return data.get(group, [])
    return data


def drop_transaction_table(db):
    connection = db.engine.connect()
    connection.execute(text("DROP TABLE IF EXISTS transaction;"))
    connection.execute(text("DROP SEQUENCE IF EXISTS transaction_id_seq;"))
    connection.commit()
    connection.close()


@patch("importlib.metadata.entry_points", _mock_entry_points)
def test_alembic(app, db):
    """Test alembic recipes."""
    from invenio_db.ext import InvenioDB

    ext = InvenioDB(app, db=db)

    if db.engine.name == "sqlite":
        raise pytest.skip("Upgrades are not supported on SQLite.")

    generated_paths = []
    try:
        db.drop_all()
        drop_alembic_version_table()
        drop_transaction_table(db)

        with app.app_context():
            # drop transaction table and sequence
            ext.alembic.upgrade()

            # generate a migration
            result = ext.alembic.revision(
                "Initial branch",
                branch="demo",
                parent="dbdbc1b19cf2",
                empty=True,
                splice=True,
            )[0]
            generated_paths.append(result.path)
            # need to sleep to avoid timestamp collision (hash is computed from timestamp)
            time.sleep(2)
            ext.alembic.upgrade()
            result = ext.alembic.revision("Choice test", branch="demo")[0]
            generated_paths.append(result.path)

            content = Path(result.path).read_text()

            # check that imports have been added
            assert "import sqlalchemy_utils" in content
            assert "import invenio_db.shared" in content
            assert "from demo.with_choice import Severity" in content
            assert (
                "sa.Column('enum_choice', sqlalchemy_utils.types.choice.ChoiceType(Severity, impl=sa.Unicode(length=255))"
                in content
            )
            assert "sa.Column('tuple_choice', sa.Unicode(length=255)" in content

            # upgrade to the new migration to check it works
            ext.alembic.upgrade()

        # Cleanup
        db.drop_all()
        drop_alembic_version_table()
        drop_transaction_table(db)
    finally:
        for path in generated_paths:
            Path(path).unlink()

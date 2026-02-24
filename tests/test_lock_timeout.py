# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2024 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Test migration lock_timeout support."""

import threading
import time

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from utils import requires_postgresql

from invenio_db import InvenioDB


@requires_postgresql
def test_alembic_lock_timeout(db, app):
    """Test that lock_timeout is set on migration connections."""
    ext = InvenioDB(app, entry_point_group=False, db=db)

    with app.app_context():
        ext.alembic.upgrade()
        ctx = ext.alembic.migration_context
        result = ctx.connection.execute(sa.text("SHOW lock_timeout")).scalar()
        assert result == "1s"


@requires_postgresql
def test_alembic_lock_timeout_custom(db, app):
    """Test that lock_timeout is configurable."""
    app.config["DB_MIGRATION_LOCK_TIMEOUT"] = "10s"
    ext = InvenioDB(app, entry_point_group=False, db=db)

    with app.app_context():
        ext.alembic.upgrade()
        ctx = ext.alembic.migration_context
        result = ctx.connection.execute(sa.text("SHOW lock_timeout")).scalar()
        assert result == "10s"


@requires_postgresql
def test_alembic_lock_timeout_prevents_long_waits(db, app):
    """Test that DDL fails fast when a table is locked by another transaction.

    Simulates a real scenario: a long-running query holds ACCESS SHARE on a
    table, and an ALTER TABLE (needing ACCESS EXCLUSIVE) hits lock_timeout
    instead of blocking indefinitely.
    """
    app.config["DB_MIGRATION_LOCK_TIMEOUT"] = "1s"
    ext = InvenioDB(app, entry_point_group=False, db=db)

    with app.app_context():
        ext.alembic.upgrade()
        engine = db.engine

        with engine.connect() as conn:
            conn.execute(
                sa.text("CREATE TABLE IF NOT EXISTS _lock_timeout_test (id int)")
            )
            conn.commit()

        try:
            lock_held = threading.Event()
            ddl_done = threading.Event()

            def hold_lock():
                """Simulate a long-running transaction holding ACCESS SHARE."""
                with engine.connect() as conn:
                    with conn.begin():
                        conn.execute(sa.text("SELECT * FROM _lock_timeout_test"))
                        lock_held.set()
                        ddl_done.wait(timeout=10)

            t = threading.Thread(target=hold_lock)
            t.start()
            lock_held.wait(timeout=5)

            # The migration connection has lock_timeout set — ALTER TABLE
            # needs ACCESS EXCLUSIVE which conflicts with ACCESS SHARE,
            # so this must fail within ~1s instead of blocking.
            ctx = ext.alembic.migration_context
            with pytest.raises(OperationalError, match="lock timeout"):
                ctx.connection.execute(
                    sa.text("ALTER TABLE _lock_timeout_test ADD COLUMN x int")
                )

            ddl_done.set()
            t.join(timeout=5)
        finally:
            with engine.connect() as conn:
                conn.execute(sa.text("DROP TABLE IF EXISTS _lock_timeout_test"))
                conn.commit()


@requires_postgresql
def test_alembic_lock_timeout_retry(db, app, caplog):
    """Test that migrations retry on lock timeout and eventually succeed.

    Strategy: apply all migrations, downgrade to base, lock alembic_version
    (which every migration step must write to), then upgrade with retries.
    The first attempts fail at the version stamp, but once the lock is
    released (~2s) a retry succeeds. PostgreSQL transactional DDL ensures
    rolled-back steps leave no artifacts.
    """
    app.config["DB_MIGRATION_LOCK_TIMEOUT"] = "500ms"
    app.config["DB_MIGRATION_LOCK_TIMEOUT_RETRIES"] = 10
    ext = InvenioDB(app, entry_point_group=False, db=db)

    with app.app_context():
        # Apply all, then roll back to base so upgrade has real work to do.
        ext.alembic.upgrade()
        ext.alembic.downgrade(target="96e796392533")

        engine = db.engine
        lock_held = threading.Event()

        def hold_lock_briefly():
            """Lock alembic_version exclusively for ~2s."""
            with engine.connect() as conn:
                with conn.begin():
                    conn.execute(
                        sa.text("LOCK TABLE alembic_version IN ACCESS EXCLUSIVE MODE")
                    )
                    lock_held.set()
                    time.sleep(2)

        t = threading.Thread(target=hold_lock_briefly)
        t.start()
        lock_held.wait(timeout=5)

        # upgrade() goes through run_migrations → lock_timeout on
        # alembic_version INSERT → retry → eventually succeeds.
        with caplog.at_level("WARNING", logger="invenio_db.ext"):
            ext.alembic.upgrade()

        t.join(timeout=10)

        # Verify retries actually happened.
        retry_msgs = [r for r in caplog.records if "lock timeout" in r.message]
        assert len(retry_msgs) >= 1

        # Verify migrations actually applied.
        heads = {s.revision for s in ext.alembic.current()}
        expected = set(ext.alembic.script_directory.get_heads())
        assert heads == expected

# SPDX-FileCopyrightText: 2017-2018 CERN.
# SPDX-FileCopyrightText: 2023 Graz University of Technology.
# SPDX-License-Identifier: MIT

"""Test DB utilities."""

import pytest
import sqlalchemy as sa
from sqlalchemy_continuum import remove_versioning
from sqlalchemy_utils.types import StringEncryptedType
from utils import requires_postgresql

from invenio_db import InvenioDB
from invenio_db.utils import (
    read_only_session,
    rebuild_encrypted_properties,
    versioning_model_classname,
    versioning_models_registered,
)


def test_rebuild_encrypted_properties(db, app):
    old_secret_key = "SECRET_KEY_1"
    new_secret_key = "SECRET_KEY_2"
    app.secret_key = old_secret_key

    def _secret_key():
        return app.config.get("SECRET_KEY").encode("utf-8")

    class Demo(db.Model):
        __tablename__ = "demo"
        pk = db.Column(sa.Integer, primary_key=True)
        et = db.Column(
            StringEncryptedType(length=255, type_in=db.Unicode, key=_secret_key),
            nullable=False,
        )

    InvenioDB(app, entry_point_group=False, db=db)

    with app.app_context():
        db.create_all()
        d1 = Demo(et="something")
        db.session.add(d1)
        db.session.commit()

    app.secret_key = new_secret_key

    with app.app_context():
        with pytest.raises(ValueError):
            db.session.query(Demo).all()
        with pytest.raises(AttributeError):
            rebuild_encrypted_properties(old_secret_key, Demo, ["nonexistent"], db)
        assert app.secret_key == new_secret_key

    with app.app_context():
        with pytest.raises(ValueError):
            db.session.query(Demo).all()
        rebuild_encrypted_properties(old_secret_key, Demo, ["et"], db)
        d1_after = db.session.query(Demo).first()
        assert d1_after.et == "something"

    with app.app_context():
        db.drop_all()


def test_versioning_model_classname(db, app):
    """Test the versioning model utilities."""

    class FooClass(db.Model):
        __versioned__ = {}
        pk = db.Column(db.Integer, primary_key=True)

    app.config["DB_VERSIONING"] = True
    idb = InvenioDB(app)
    manager = idb.versioning_manager
    manager.options["use_module_name"] = True
    assert versioning_model_classname(manager, FooClass) == "Test_UtilsFooClassVersion"
    manager.options["use_module_name"] = False
    assert versioning_model_classname(manager, FooClass) == "FooClassVersion"
    assert versioning_models_registered(manager, db.Model)
    remove_versioning(manager=manager)


def _backend(db, pid):
    """Return the state and demo table lock modes of a backend, seen from another connection."""
    with db.engine.connect() as conn:
        state = conn.execute(
            sa.text("SELECT state FROM pg_stat_activity WHERE pid = :pid"),
            {"pid": pid},
        ).scalar()
        locks = conn.execute(
            sa.text(
                "SELECT mode FROM pg_locks "
                "WHERE pid = :pid AND relation = 'read_only_demo'::regclass"
            ),
            {"pid": pid},
        ).scalars()
    return state, set(locks)


@requires_postgresql
def test_read_only_session(db, app):
    """Run queries without keeping a transaction open."""

    class ReadOnlyDemo(db.Model):
        __tablename__ = "read_only_demo"
        pk = db.Column(sa.Integer, primary_key=True)

    InvenioDB(app, entry_point_group=False, db=db)

    with app.app_context():
        db.create_all()
        demo = ReadOnlyDemo(pk=1)
        db.session.add(demo)
        db.session.commit()
        try:
            with read_only_session(db) as session:
                pid = session.execute(sa.text("SELECT pg_backend_pid()")).scalar()
                assert session.query(ReadOnlyDemo).count() == 1
                assert _backend(db, pid) == ("idle", set())

                # Writes commit immediately, visible to other connections
                session.execute(sa.text("INSERT INTO read_only_demo VALUES (2)"))
                with db.engine.connect() as conn:
                    count = conn.execute(sa.text("SELECT count(*) FROM read_only_demo"))
                    assert count.scalar() == 2

            # Objects loaded before the block stay attached and usable
            assert demo in db.session
            assert demo.pk == 1

            # A normal transaction afterwards holds its locks again
            pid = db.session.execute(sa.text("SELECT pg_backend_pid()")).scalar()
            db.session.add(ReadOnlyDemo(pk=3))
            db.session.flush()
            assert "RowExclusiveLock" in _backend(db, pid)[1]
            db.session.commit()
            assert db.session.query(ReadOnlyDemo).count() == 3
        finally:
            db.session.rollback()
            db.drop_all()


@requires_postgresql
def test_read_only_session_open_transaction(db, app):
    """End an open transaction that has only read; refuse one with writes."""

    class ReadOnlyDemo(db.Model):
        __tablename__ = "read_only_demo"
        pk = db.Column(sa.Integer, primary_key=True)

    InvenioDB(app, entry_point_group=False, db=db)

    with app.app_context():
        db.create_all()
        try:
            db.session.execute(sa.text("SELECT 1"))
            with read_only_session(db) as session:
                pid = session.execute(sa.text("SELECT pg_backend_pid()")).scalar()
                assert _backend(db, pid) == ("idle", set())

            db.session.add(ReadOnlyDemo(pk=1))
            with pytest.raises(RuntimeError):
                with read_only_session(db):
                    pass

            db.session.flush()
            with pytest.raises(RuntimeError):
                with read_only_session(db):
                    pass
            db.session.rollback()
            assert db.session.query(ReadOnlyDemo).count() == 0
        finally:
            db.session.rollback()
            db.drop_all()

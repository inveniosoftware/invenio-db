# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015-2018 CERN.
# Copyright (C) 2022 RERO.
# Copyright (C) 2024 Graz University of Technology.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Test database integration layer."""

import importlib.metadata
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from flask import Flask
from mocks import _mock_entry_points
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy_continuum import VersioningManager, remove_versioning
from sqlalchemy_utils.functions import create_database, drop_database

from invenio_db import InvenioDB
from invenio_db.cli import db as db_cmd
from invenio_db.shared import NAMING_CONVENTION, MetaData, SQLAlchemy
from invenio_db.utils import drop_alembic_version_table, has_table


def test_init(db, app):
    """Test extension initialization."""

    class Demo(db.Model):
        __tablename__ = "demo"
        pk = sa.Column(sa.Integer, primary_key=True)

    class Demo2(db.Model):
        __tablename__ = "demo2"
        pk = sa.Column(sa.Integer, primary_key=True)
        fk = sa.Column(sa.Integer, sa.ForeignKey(Demo.pk))

    app.config["DB_VERSIONING"] = False
    InvenioDB(app, entry_point_group=False, db=db)
    with app.app_context():
        db.create_all()
        assert len(db.metadata.tables) == 2

        # Test foreign key constraint checking
        d1 = Demo()
        db.session.add(d1)
        db.session.flush()

        d2 = Demo2(fk=d1.pk)
        db.session.add(d2)
        db.session.commit()

    with app.app_context():
        # Fails fk check
        d3 = Demo2(fk=10)
        db.session.add(d3)
        pytest.raises(IntegrityError, db.session.commit)
        db.session.rollback()

    with app.app_context():
        db.session.query(Demo2).delete()
        db.session.query(Demo).delete()
        db.session.commit()

        db.drop_all()


def test_alembic(db, app):
    """Test alembic recipes."""
    ext = InvenioDB(app, entry_point_group=False, db=db)

    with app.app_context():
        if db.engine.name == "sqlite":
            raise pytest.skip("Upgrades are not supported on SQLite.")

        ext.alembic.upgrade()
        ext.alembic.downgrade(target="96e796392533")


def test_naming_convention(db, app):
    """Test naming convention."""

    InvenioDB(app, entry_point_group=False, db=db)
    cfg = dict(
        DB_VERSIONING=True,
        DB_VERSIONING_USER_MODEL=None,
        SQLALCHEMY_DATABASE_URI=app.config["SQLALCHEMY_DATABASE_URI"],
    )

    with app.app_context():
        if db.engine.name == "sqlite":
            raise pytest.skip("Upgrades are not supported on SQLite.")

    def model_factory(base):
        """Create test models."""

        class Master(base):
            __tablename__ = "master"
            pk = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String(100), unique=True)
            city = sa.Column(sa.String(100), index=True)
            active = sa.Column(sa.Boolean(name="active"), server_default="1")

        class Slave(base):
            __tablename__ = "slave"
            pk = sa.Column(sa.Integer, primary_key=True)
            fk = sa.Column(sa.Integer, sa.ForeignKey(Master.pk))
            code = sa.Column(sa.Integer, index=True, unique=True)
            source = sa.Column(sa.String(100))

            __table_args__ = (
                sa.Index(None, source),
                # do not add anything after
                getattr(base, "__table_args__", {}),
            )

        return Master, Slave

    source_db = SQLAlchemy(
        metadata=MetaData(
            naming_convention={
                "ix": "source_ix_%(table_name)s_%(column_0_label)s",
                "uq": "source_uq_%(table_name)s_%(column_0_name)s",
                "ck": "source_ck_%(table_name)s_%(constraint_name)s",
                "fk": "source_fk_%(table_name)s_%(column_0_name)s_"
                "%(referred_table_name)s",
                "pk": "source_pk_%(table_name)s",
            }
        ),
    )
    source_app = Flask("source_app")
    source_app.config.update(**cfg)

    source_models = model_factory(source_db.Model)
    source_ext = InvenioDB(
        source_app,
        entry_point_group=False,
        db=source_db,
        versioning_manager=VersioningManager(),
    )

    with source_app.app_context():
        source_db.metadata.bind = source_db.engine
        source_db.create_all()
        source_ext.alembic.stamp("dbdbc1b19cf2")
        assert not source_ext.alembic.compare_metadata()
        source_constraints = set(
            [
                cns
                for model in source_models
                for cns in list(model.__table__.constraints)
                + list(model.__table__.indexes)
            ]
        )

    remove_versioning(manager=source_ext.versioning_manager)

    target_db = SQLAlchemy(metadata=MetaData(naming_convention=NAMING_CONVENTION))
    target_app = Flask("target_app")
    target_app.config.update(**cfg)

    target_models = model_factory(target_db.Model)
    target_ext = InvenioDB(
        target_app,
        entry_point_group=False,
        db=target_db,
        versioning_manager=VersioningManager(),
    )

    with target_app.app_context():
        target_db.metadata.bind = target_db.engine
        assert target_ext.alembic.compare_metadata()
        target_ext.alembic.upgrade("35c1075e6360")
        assert not target_ext.alembic.compare_metadata()
        target_db.drop_all()
        target_constraints = set(
            [
                cns.name
                for model in target_models
                for cns in list(model.__table__.constraints)
                + list(model.__table__.indexes)
            ]
        )

    remove_versioning(manager=target_ext.versioning_manager)

    assert source_constraints ^ target_constraints


def test_transaction(db, app):
    """Test transcation commit and rollback.

    This is necessary to make sure that pysqlite hacks are properly working.
    """

    class Demo(db.Model):
        __tablename__ = "demo"
        pk = sa.Column(sa.Integer, primary_key=True)

    app.config["DB_VERSIONING"] = False
    InvenioDB(app, entry_point_group=False, db=db)

    with app.app_context():
        db.drop_all()
        db.create_all()
        assert len(db.metadata.tables) == 1

    # Test rollback
    with app.app_context():
        d1 = Demo()
        d1.pk = 1
        db.session.add(d1)
        db.session.rollback()
    with app.app_context():
        res = Demo.query.all()
        assert len(res) == 0
        db.session.rollback()

    # Test nested session rollback
    with app.app_context():
        with db.session.begin_nested():
            d1 = Demo()
            d1.pk = 1
            db.session.add(d1)
        db.session.rollback()
    with app.app_context():
        res = Demo.query.all()
        assert len(res) == 0
        db.session.rollback()

    # Test commit
    with app.app_context():
        d1 = Demo()
        d1.pk = 1
        db.session.add(d1)
        db.session.commit()
    with app.app_context():
        res = Demo.query.all()
        assert len(res) == 1
        assert res[0].pk == 1
        db.session.commit()

    with app.app_context():
        db.drop_all()


@patch("importlib.metadata.entry_points", _mock_entry_points("invenio_db.models"))
def test_entry_points(db, app):
    """Test entrypoints loading."""
    InvenioDB(app, db=db)

    runner = app.test_cli_runner()

    assert len(db.metadata.tables) == 2

    # Test merging a base another file.
    with runner.isolated_filesystem():

        # show help
        result = runner.invoke(db_cmd, [])
        click_help_result_code = (
            0 if importlib.metadata.version("click") < "8.2.0" else 2
        )
        assert result.exit_code == click_help_result_code

        result = runner.invoke(db_cmd, ["init"])
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ["destroy", "--yes-i-know"])
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ["init"])
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ["create", "-v"])
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ["destroy", "--yes-i-know"])
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ["init"])
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ["create", "-v"])
        assert result.exit_code == 1

        result = runner.invoke(db_cmd, ["create", "-v"])
        assert result.exit_code == 1

        result = runner.invoke(db_cmd, ["drop", "-v", "--yes-i-know"])
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ["drop"])
        assert result.exit_code == 1

        result = runner.invoke(db_cmd, ["drop", "-v", "--yes-i-know"])
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ["drop", "create"])
        assert result.exit_code == 1

        result = runner.invoke(db_cmd, ["drop", "--yes-i-know", "create"])
        assert result.exit_code == 1

        result = runner.invoke(db_cmd, ["destroy", "--yes-i-know"])
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ["init"])
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ["destroy", "--yes-i-know"])
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ["init"])
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ["destroy", "--yes-i-know"])
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ["init"])
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ["drop", "-v", "--yes-i-know"])
        assert result.exit_code == 1

        result = runner.invoke(db_cmd, ["create", "-v"])
        assert result.exit_code == 1

        result = runner.invoke(db_cmd, ["drop", "-v", "--yes-i-know"])
        assert result.exit_code == 0


def test_local_proxy(app, db):
    """Test local proxy filter."""
    InvenioDB(app, db=db)

    with app.app_context():
        query = db.select(
            *[
                db.literal("hello") != db.bindparam("a"),
                db.literal(0) <= db.bindparam("x"),
                db.literal("2") == db.bindparam("y"),
                db.literal(None).is_(db.bindparam("z")),
            ]
        )
        result = db.session.execute(
            query,
            {
                "a": "world",
                "x": 1,
                "y": "2",
                "z": None,
            },
        ).fetchone()
        assert result == (True, True, True, True)


def test_db_create_alembic_upgrade(app, db):
    """Test that 'db create/drop' and 'alembic create' are compatible.

    It also checks that "alembic_version" table is processed properly
    as it is normally created by alembic and not by sqlalchemy.
    """
    app.config["DB_VERSIONING"] = True
    ext = InvenioDB(
        app, entry_point_group=None, db=db, versioning_manager=VersioningManager()
    )
    with app.app_context():
        try:
            if db.engine.name == "sqlite":
                raise pytest.skip("Upgrades are not supported on SQLite.")

            db.drop_all()
            runner = app.test_cli_runner()
            # Check that 'db create' creates the same schema as
            # 'alembic upgrade'.
            result = runner.invoke(db_cmd, ["create", "-v"])
            assert result.exit_code == 0
            assert has_table(db.engine, "transaction")
            assert ext.alembic.migration_context._has_version_table()

            # Note that compare_metadata does not detect additional sequences
            # and constraints.
            # TODO fix failing test on mysql
            if db.engine.name != "mysql":
                assert not ext.alembic.compare_metadata()

            ext.alembic.upgrade()
            assert has_table(db.engine, "transaction")

            ext.alembic.downgrade(target="96e796392533")
            assert inspect(db.engine).get_table_names() == ["alembic_version"]

            # Check that 'db drop' removes all tables, including
            # 'alembic_version'.
            ext.alembic.upgrade()
            result = runner.invoke(db_cmd, ["drop", "-v", "--yes-i-know"])
            assert result.exit_code == 0
            assert len(inspect(db.engine).get_table_names()) == 0

            ext.alembic.upgrade()
            db.drop_all()
            drop_alembic_version_table()
            assert len(inspect(db.engine).get_table_names()) == 0

        finally:
            drop_database(str(db.engine.url.render_as_string(hide_password=False)))
            remove_versioning(manager=ext.versioning_manager)
            create_database(str(db.engine.url.render_as_string(hide_password=False)))

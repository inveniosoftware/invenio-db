# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015-2018 CERN.
# Copyright (C) 2022 RERO.
# Copyright (C) 2022-2026 Graz University of Technology.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Database management for Invenio."""

import logging
import os
import random
import time
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from importlib.resources import files

import sqlalchemy as sa
from flask import current_app
from flask_alembic import Alembic
from invenio_base.utils import entry_points
from sqlalchemy.exc import OperationalError
from sqlalchemy_utils.functions import get_class_by_table

from .cli import db as db_cmd
from .shared import db
from .utils import versioning_models_registered

logger = logging.getLogger(__name__)


class InvenioAlembic(Alembic):
    """Alembic with PostgreSQL lock_timeout and retry for safe migrations.

    Sets lock_timeout on migration connections so DDL statements fail fast
    instead of blocking reads indefinitely while waiting for exclusive locks.
    On lock timeout, retries with exponential backoff. Already-applied
    migrations are skipped on retry (transaction_per_migration stamps each
    step).

    See https://postgres.ai/blog/20210923-zero-downtime-postgres-schema-migrations-lock-timeout-and-retries

    Configuration:

    - ``DB_MIGRATION_LOCK_TIMEOUT``: PostgreSQL lock_timeout value
      (default ``"1s"``). Set to ``"0"`` to disable.
    - ``DB_MIGRATION_LOCK_TIMEOUT_RETRIES``: number of retries on lock
      timeout (default ``5``).
    """

    def __init__(self, *args, **kwargs):
        """Initialize InvenioAlembic."""
        super().__init__(*args, **kwargs)

    def _set_lock_timeout(self):
        """Set lock_timeout on all PostgreSQL migration connections."""
        for ctx in self.migration_contexts.values():
            if (
                ctx.connection is not None
                and ctx.connection.dialect.name == "postgresql"
            ):
                timeout = current_app.config.get("DB_MIGRATION_LOCK_TIMEOUT", "1s")
                ctx.connection.execute(
                    sa.text("SELECT set_config('lock_timeout', :val, false)"),
                    {"val": timeout},
                )

    def run_migrations(self, fn, **kwargs):
        """Run migrations with lock_timeout and retry on lock failure."""
        max_retries = current_app.config.get("DB_MIGRATION_LOCK_TIMEOUT_RETRIES", 5)

        for attempt in range(max_retries + 1):
            self._set_lock_timeout()
            try:
                super().run_migrations(fn, **kwargs)
                return
            except OperationalError as e:
                is_lock_timeout = hasattr(e.orig, "pgcode") and e.orig.pgcode == "55P03"
                if not is_lock_timeout or attempt >= max_retries:
                    raise
                # Exponential backoff with jitter
                delay = min(30, 0.5 * 2**attempt) * (0.5 + random.random() * 0.5)
                logger.warning(
                    "Migration lock timeout, retrying in %.1fs (%d/%d)",
                    delay,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(delay)
                # Clear cached contexts — connection is dead after the error.
                # Next access to migration_contexts creates fresh connections.
                self._get_cache().clear()


class InvenioDB(object):
    """Invenio database extension."""

    def __init__(self, app=None, **kwargs):
        """Extension initialization."""
        self.alembic = InvenioAlembic(run_mkdir=False, command_name="alembic")
        if app:
            self.init_app(app, **kwargs)

    def init_app(self, app, **kwargs):
        """Initialize application object."""
        self.init_db(app, **kwargs)

        def pathify(base_entry):
            return str(files(base_entry.module) / os.path.join(base_entry.attr))

        alembic_entry_points = entry_points(group="invenio_db.alembic")
        version_locations = [
            (base_entry.name, pathify(base_entry))
            for base_entry in alembic_entry_points
        ]
        script_location = str(files("invenio_db") / "alembic")
        app.config.setdefault(
            "ALEMBIC",
            {
                "script_location": script_location,
                "version_locations": version_locations,
            },
        )
        app.config.setdefault(
            "ALEMBIC_CONTEXT",
            {
                "transaction_per_migration": True,
                "compare_type": True,  # Allows to detect change of column type, accuracy depends on backend
            },
        )

        self.alembic.init_app(app)
        app.extensions["invenio-db"] = self
        app.cli.add_command(db_cmd)

    def init_db(self, app, entry_point_group="invenio_db.models", **kwargs):
        """Initialize Flask-SQLAlchemy extension."""
        # Setup SQLAlchemy
        app.config.setdefault(
            "SQLALCHEMY_DATABASE_URI",
            "sqlite:///" + os.path.join(app.instance_path, app.name + ".db"),
        )
        app.config.setdefault("SQLALCHEMY_ECHO", False)
        # Needed for before/after_flush/commit/rollback events
        app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", True)
        app.config.setdefault(
            "SQLALCHEMY_ENGINE_OPTIONS",
            # Ensure the database is using the UTC timezone for interpreting timestamps (Postgres only).
            # This overrides any default setting (e.g. in postgresql.conf). Invenio expects the DB to receive
            # and provide UTC timestamps in all cases, so it's important that this doesn't get changed.
            {"connect_args": {"options": "-c timezone=UTC"}},
        )

        # Initialize Flask-SQLAlchemy extension.
        database = kwargs.get("db", db)
        database.init_app(app)

        # Initialize versioning support.
        self.init_versioning(app, database, kwargs.get("versioning_manager"))

        # Initialize model bases
        if entry_point_group:
            for base_entry in entry_points(group=entry_point_group):
                base_entry.load()

        # All models should be loaded by now.
        sa.orm.configure_mappers()
        # Ensure that versioning classes have been built.
        if app.config["DB_VERSIONING"]:
            manager = self.versioning_manager
            if manager.pending_classes:
                if not versioning_models_registered(manager, database.Model):
                    manager.builder.configure_versioned_classes()
            elif "transaction" not in database.metadata.tables:
                manager.declarative_base = database.Model
                manager.create_transaction_model()
                manager.plugins.after_build_tx_class(manager)

    def init_versioning(self, app, database, versioning_manager=None):
        """Initialize the versioning support using SQLAlchemy-Continuum."""
        try:
            package_version("sqlalchemy_continuum")
        except PackageNotFoundError:  # pragma: no cover
            default_versioning = False
        else:
            default_versioning = True

        app.config.setdefault("DB_VERSIONING", default_versioning)

        if not app.config["DB_VERSIONING"]:
            return

        if not default_versioning:  # pragma: no cover
            raise RuntimeError(
                "Please install extra versioning support first by running "
                "pip install invenio-db[versioning]."
            )

        # Now we can import SQLAlchemy-Continuum.
        from sqlalchemy_continuum import make_versioned
        from sqlalchemy_continuum import versioning_manager as default_vm
        from sqlalchemy_continuum.plugins import FlaskPlugin

        # Try to guess user model class:
        if "DB_VERSIONING_USER_MODEL" not in app.config:  # pragma: no cover
            try:
                package_version("invenio_accounts")
            except PackageNotFoundError:
                user_cls = None
            else:
                user_cls = "User"
        else:
            user_cls = app.config.get("DB_VERSIONING_USER_MODEL")

        plugins = [FlaskPlugin()] if user_cls else []

        # Call make_versioned() before your models are defined.
        self.versioning_manager = versioning_manager or default_vm
        make_versioned(
            user_cls=user_cls,
            manager=self.versioning_manager,
            plugins=plugins,
        )

        # Register models that have been loaded beforehand.
        builder = self.versioning_manager.builder

        for tbl in database.metadata.tables.values():
            builder.instrument_versioned_classes(
                database.mapper, get_class_by_table(database.Model, tbl)
            )

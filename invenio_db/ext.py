# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015-2018 CERN.
# Copyright (C) 2022 RERO.
# Copyright (C) 2022 Graz University of Technology.
# Copyright (C) 2025 TU Wien.
# Copyright (C) 2025 KTH Royal Institute of Technology.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Database management for Invenio."""

import os

import importlib_metadata
import importlib_resources
import sqlalchemy as sa
from flask_alembic import Alembic
from sqlalchemy_utils.functions import get_class_by_table

from .cli import db as db_cmd
from .shared import db
from .utils import versioning_models_registered


class InvenioDB(object):
    """Invenio database extension."""

    def __init__(self, app=None, **kwargs):
        """Extension initialization."""
        self.alembic = Alembic(run_mkdir=False, command_name="alembic")
        if app:
            self.init_app(app, **kwargs)

    def init_app(self, app, **kwargs):
        """Initialize application object."""
        self.init_db(app, **kwargs)

        def pathify(base_entry):
            return str(
                importlib_resources.files(base_entry.module)
                / os.path.join(base_entry.attr)
            )

        entry_points = importlib_metadata.entry_points(group="invenio_db.alembic")
        version_locations = [
            (base_entry.name, pathify(base_entry)) for base_entry in entry_points
        ]
        script_location = str(importlib_resources.files("invenio_db") / "alembic")
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

    def build_db_uri(self, app):
        """Return the connection string if configured or build it from its parts.

        If set, then ``SQLALCHEMY_DATABASE_URI`` will be returned.
        Otherwise, the URI will be pieced together by the configuration items
        ``DB_{USER,PASSWORD,HOST,PORT,NAME,PROTOCOL}``, where ``DB_PORT`` is
        optional.
        If that cannot be done (e.g. because required values are missing), then
        ``None`` will be returned.
        """
        if uri := app.config.get("SQLALCHEMY_DATABASE_URI", None):
            return uri

        params = {}
        for config_name in ["USER", "PASSWORD", "HOST", "PORT", "NAME", "PROTOCOL"]:
            params[config_name] = app.config.get(f"DB_{config_name}", None)

        # The port is expected to be an int, and optional
        if port := params.pop("PORT", None):
            params["PORT"] = int(port)

        if all(params.values()):
            uri = sa.URL.create(
                params["PROTOCOL"],
                username=params["USER"],
                password=params["PASSWORD"],
                host=params["HOST"],
                port=params["PORT"],
                database=params["NAME"],
            )
            return uri
        elif any(params.values()):
            app.logger.warn(
                'Ignoring "DB_*" config values as they are only partially set.'
            )

        return None

    def init_db(self, app, entry_point_group="invenio_db.models", **kwargs):
        """Initialize Flask-SQLAlchemy extension."""
        if uri := self.build_db_uri(app):
            app.config["SQLALCHEMY_DATABASE_URI"] = uri

        # Setup SQLAlchemy
        app.config.setdefault(
            "SQLALCHEMY_DATABASE_URI",
            "sqlite:///" + os.path.join(app.instance_path, app.name + ".db"),
        )
        app.config.setdefault("SQLALCHEMY_ECHO", False)
        # Needed for before/after_flush/commit/rollback events
        app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", True)

        # Initialize Flask-SQLAlchemy extension.
        database = kwargs.get("db", db)
        database.init_app(app)

        # Initialize versioning support.
        self.init_versioning(app, database, kwargs.get("versioning_manager"))

        # Initialize model bases
        if entry_point_group:
            for base_entry in importlib_metadata.entry_points(group=entry_point_group):
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
            importlib_metadata.version("sqlalchemy_continuum")
        except importlib_metadata.PackageNotFoundError:  # pragma: no cover
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
                importlib_metadata.version("invenio_accounts")
            except importlib_metadata.PackageNotFoundError:
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

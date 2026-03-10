# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015-2018 CERN.
# Copyright (C) 2024-2026 Graz University of Technology.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Shared database object for Invenio."""

import warnings
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy as FlaskSQLAlchemy
from sqlalchemy import Column, MetaData, event, util
from sqlalchemy.types import DateTime, TypeDecorator

NAMING_CONVENTION = util.immutabledict(
    {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)
"""Configuration for constraint naming conventions."""

metadata = MetaData(naming_convention=NAMING_CONVENTION)
"""Default database metadata object holding associated schema constructs."""


class UTCDateTime(TypeDecorator):
    """Custom UTC datetime type."""

    impl = DateTime(timezone=True)

    # todo: should be discussed, but has to be set explicitly to remove warning
    cache_ok = False

    def process_bind_param(self, value, dialect):
        """Process value storing into database."""
        if value is None:
            return value

        if isinstance(value, str):
            warnings.warn(
                "UTCDateTime: string values are deprecated, please pass a datetime object. "
                "String values will be removed in the next major release (3.0.0).",
                DeprecationWarning,
            )
            if " " in value:
                value = value.replace(" ", "T")
            value = datetime.strptime(value[0:19], "%Y-%m-%dT%H:%M:%S")

        if not isinstance(value, datetime):
            msg = f"ERROR: value: {value} is not of type datetime, instead of type: {type(value)}"
            raise ValueError(msg)

        if value.tzinfo not in (None, timezone.utc):
            msg = f"Error: value: {value}, tzinfo: {value.tzinfo} doesn't have a tzinfo of None or timezone.utc."
            raise ValueError(msg)

        return value.replace(tzinfo=timezone.utc)

    def process_result_value(self, value, dialect):
        """Process value retrieving from database."""
        if value is None:
            return None

        if not isinstance(value, datetime):
            msg = f"ERROR: value: {value} is not of type datetime."
            raise ValueError(msg)

        if value.tzinfo not in (None, timezone.utc):
            msg = (
                f"Error: value: {value} doesn't have a tzinfo of None or timezone.utc."
            )
            raise ValueError(msg)

        return value.replace(tzinfo=timezone.utc)


class Timestamp:
    """Adds `created` and `updated` columns to a derived declarative model.

    The `created` column is handled through a default and the `updated`
    column is handled through a `before_update` event that propagates
    for all derived declarative models.

    ::

        from invenio_db import db
        class SomeModel(Base, db.Timestamp):
            __tablename__ = "somemodel"
            id = sa.Column(sa.Integer, primary_key=True)
    """

    created = Column(
        UTCDateTime,
        default=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )
    updated = Column(
        UTCDateTime,
        default=lambda: datetime.now(tz=timezone.utc),
        nullable=False,
    )


@event.listens_for(Timestamp, "before_update", propagate=True)
def timestamp_before_update(mapper, connection, target):
    """Update timestamp on before_update event.

    When a model with a timestamp is updated; force update the updated
    timestamp.
    """
    target.updated = datetime.now(tz=timezone.utc)


class SQLAlchemy(FlaskSQLAlchemy):
    """Implement or overide extension methods."""

    def __getattr__(self, name):
        """Get attr."""
        if name == "UTCDateTime":
            return UTCDateTime

        if name == "Timestamp":
            return Timestamp

        return super().__getattr__(name)


db = SQLAlchemy(metadata=metadata)
"""Shared database instance using Flask-SQLAlchemy extension.

This object is initialized during initialization of ``InvenioDB``
extenstion that takes care about loading all entrypoints from key
``invenio_db.models``.
"""

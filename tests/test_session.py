# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2026 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Test session bind routing."""

import pytest

from invenio_db import InvenioDB
from invenio_db.shared import NAMING_CONVENTION, MetaData, Session, SQLAlchemy


def replica_bind(session, *args, **kwargs):
    """Route everything to the replica bind."""
    return session._db.engines["replica"]


@pytest.fixture()
def routed_db():
    """Database using the routing session class."""
    return SQLAlchemy(
        metadata=MetaData(naming_convention=NAMING_CONVENTION),
        session_options={"class_": Session},
    )


@pytest.mark.parametrize("bind_func", [replica_bind, "test_session:replica_bind"])
def test_bind_func_routes_session(app, routed_db, bind_func):
    """The configured function (or its import string) picks the session bind."""
    app.config.update(
        SQLALCHEMY_BINDS={"replica": app.config["SQLALCHEMY_DATABASE_URI"]},
        DB_SESSION_BIND_FUNC=bind_func,
    )
    InvenioDB(app, db=routed_db)

    with app.app_context():
        assert routed_db.session.get_bind() is routed_db.engines["replica"]


@pytest.mark.parametrize("bind_func", [None, lambda session, *args, **kwargs: None])
def test_bind_func_falls_back_to_default(app, routed_db, bind_func):
    """No function, or a function returning ``None``, uses the default bind."""
    app.config.update(
        SQLALCHEMY_BINDS={"replica": app.config["SQLALCHEMY_DATABASE_URI"]},
        DB_SESSION_BIND_FUNC=bind_func,
    )
    InvenioDB(app, db=routed_db)

    with app.app_context():
        assert routed_db.session.get_bind() is routed_db.engine

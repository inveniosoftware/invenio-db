# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015 CERN.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Database management for Invenio."""

from __future__ import absolute_import, print_function

import os

import pkg_resources
import sqlalchemy as sa
from sqlalchemy_utils.functions import get_class_by_table

from .cli import db as db_cmd
from .shared import db


class InvenioDB(object):
    """Invenio database extension."""

    def __init__(self, app=None, **kwargs):
        """Extension initialization."""
        if app:
            self.init_app(app, **kwargs)

    def init_app(self, app, **kwargs):
        """Initialize application object."""
        self.init_db(app, **kwargs)
        app.extensions['invenio-db'] = self
        app.cli.add_command(db_cmd)

    def init_db(self, app, entry_point_group='invenio_db.models', **kwargs):
        """Initialize Flask-SQLAlchemy extension."""
        # Setup SQLAlchemy
        app.config.setdefault(
            'SQLALCHEMY_DATABASE_URI',
            'sqlite:///' + os.path.join(app.instance_path, app.name + '.db')
        )
        app.config.setdefault('SQLALCHEMY_ECHO', app.debug)

        # Initialize Flask-SQLAlchemy extension.
        database = kwargs.get('db', db)
        database.init_app(app)

        # Initialize versioning support.
        self.init_versioning(app, database, kwargs.get('versioning_manager'))

        # Initialize model bases
        if entry_point_group:
            for base_entry in pkg_resources.iter_entry_points(
                    entry_point_group):
                base_entry.load()

        # All models should be loaded by now.
        sa.orm.configure_mappers()

    def init_versioning(self, app, database, versioning_manager=None):
        """Initialize the versioning support using SQLAlchemy-Continuum."""
        try:
            pkg_resources.get_distribution('sqlalchemy_continuum')
        except pkg_resources.DistributionNotFound:  # pragma: no cover
            default_versioning = False
        else:
            default_versioning = True

        app.config.setdefault('DB_VERSIONING', default_versioning)

        if not app.config['DB_VERSIONING']:
            return

        if not default_versioning:  # pragma: no cover
            raise RuntimeError(
                'Please install extra versioning support first by running '
                'pip install invenio-db[versioning].'
            )

        # Now we can import SQLAlchemy-Continuum.
        from sqlalchemy_continuum import make_versioned
        from sqlalchemy_continuum import versioning_manager as default_vm

        # Try to guess user model class:
        if 'DB_VERSIONING_USER_MODEL' not in app.config:  # pragma: no cover
            try:
                pkg_resources.get_distribution('invenio_accounts')
            except pkg_resources.DistributionNotFound:
                user_cls = None
            else:
                user_cls = 'User'
        else:
            user_cls = app.config.get('DB_VERSIONING_USER_MODEL')

        # Call make_versioned() before your models are defined.
        self.versioning_manager = versioning_manager or default_vm
        make_versioned(user_cls=user_cls, manager=self.versioning_manager)

        # Register models that have been loaded beforehand.
        builder = self.versioning_manager.builder

        for tbl in database.metadata.tables.values():
            builder.instrument_versioned_classes(
                database.mapper, get_class_by_table(database.Model, tbl)
            )

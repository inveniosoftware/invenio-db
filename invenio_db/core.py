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

from .cli import db as db_cmd
from .shared import db


class InvenioDB(object):
    """Invenio database extension."""

    def __init__(self, app=None, **kwargs):
        """Extension initialization."""
        self.kwargs = kwargs
        if app:
            self.init_app(app, **kwargs)

    def init_app(self, app, **kwargs):
        """Initialize application object."""
        self.kwargs.update(kwargs)
        self.init_db(app, **self.kwargs)
        app.extensions['invenio-db'] = self
        app.cli.add_command(db_cmd)

    def init_db(self, app, entrypoint_name='invenio_db.models', **kwargs):
        """Initialize Flask-SQLAlchemy extension."""
        # Setup SQLAlchemy
        app.config.setdefault(
            'SQLALCHEMY_DATABASE_URI',
            'sqlite:///' + os.path.join(app.instance_path, app.name + '.db')
        )
        app.config.setdefault('SQLALCHEMY_ECHO', app.debug)

        # Initialize Flask-SQLAlchemy extension.
        db.init_app(app)

        # Initialize model bases
        if entrypoint_name:
            for base_entry in pkg_resources.iter_entry_points(entrypoint_name):
                base_entry.load()

        sa.orm.configure_mappers()

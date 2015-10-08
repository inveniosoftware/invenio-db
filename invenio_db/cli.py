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

"""Click command-line interface for database management."""

from __future__ import absolute_import, print_function

import json
import logging
import pkg_resources

import click
from flask import current_app
from flask_cli import with_appcontext

from .shared import db as _db


def abort_if_false(ctx, param, value):
    """Abort command is value is False."""
    if not value:
        ctx.abort()

#
# Database commands
#

@click.group(chain=True)
def db():
    """Database commands."""


@db.command()
@with_appcontext
def create():
    """Create tables."""
    click.secho('Creating all tables!', bg='yellow', bold=True)
    with click.progressbar(reversed(_db.metadata.sorted_tables)) as bar:
        for table in bar:
            table.drop(bind=_db.engine, checkfirst=True)
    click.secho('Dropped all tables!', bg='green')


@db.command()
@click.option('--yes-i-know', is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Do you know that you are going to drop the db?')
@with_appcontext
def drop():
    click.secho('Dropping all tables!', bg='red', bold=True)
    with click.progressbar(reversed(_db.metadata.sorted_tables)) as bar:
        for table in bar:
            table.drop(bind=_db.engine, checkfirst=True)
    click.secho('Dropped all tables!', bg='green')

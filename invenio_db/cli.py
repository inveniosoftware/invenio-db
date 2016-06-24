# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015, 2016 CERN.
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

import sys

import click
from click import _termui_impl
from flask import current_app
from sqlalchemy_utils.functions import create_database, database_exists, \
    drop_database
from werkzeug.local import LocalProxy

try:
    from flask.cli import with_appcontext
except ImportError:  # pragma: no cover
    from flask_cli import with_appcontext

_db = LocalProxy(lambda: current_app.extensions['sqlalchemy'].db)

# Fix Python 3 compatibility issue in click
if sys.version_info > (3,):
    _termui_impl.long = int  # pragma: no cover


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
@click.option('-v', '--verbose', is_flag=True, default=False)
@with_appcontext
def create(verbose):
    """Create tables."""
    click.secho('Creating all tables!', fg='yellow', bold=True)
    with click.progressbar(_db.metadata.sorted_tables) as bar:
        for table in bar:
            if verbose:
                click.echo(' Creating table {0}'.format(table))
            table.create(bind=_db.engine, checkfirst=True)
    click.secho('Created all tables!', fg='green')


@db.command()
@click.option('-v', '--verbose', is_flag=True, default=False)
@click.option('--yes-i-know', is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Do you know that you are going to drop the db?')
@with_appcontext
def drop(verbose):
    """Drop tables."""
    click.secho('Dropping all tables!', fg='red', bold=True)
    with click.progressbar(reversed(_db.metadata.sorted_tables)) as bar:
        for table in bar:
            if verbose:
                click.echo(' Dropping table {0}'.format(table))
            table.drop(bind=_db.engine, checkfirst=True)
    click.secho('Dropped all tables!', fg='green')


@db.command()
@with_appcontext
def init():
    """Create database."""
    click.secho('Creating database {0}'.format(_db.engine.url),
                fg='green')
    if not database_exists(str(_db.engine.url)):
        create_database(str(_db.engine.url))


@db.command()
@click.option('--yes-i-know', is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Do you know that you are going to destroy the db?')
@with_appcontext
def destroy():
    """Drop database."""
    click.secho('Destroying database {0}'.format(_db.engine.url),
                fg='red', bold=True)
    drop_database(_db.engine.url)

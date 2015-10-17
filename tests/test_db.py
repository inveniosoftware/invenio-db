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

"""Test database integration layer."""

from __future__ import absolute_import, print_function

import importlib
import os

import sqlalchemy as sa
from click.testing import CliRunner
from flask import Flask
from flask_cli import FlaskCLI, ScriptInfo
from mock import patch
from pkg_resources import EntryPoint
from sqlalchemy_utils.functions import create_database, drop_database

from invenio_db import InvenioDB, db
from invenio_db.cli import db as db_cmd


class MockEntryPoint(EntryPoint):
    """Mocking of entrypoint."""

    def load(self):
        """Mock load entry point."""
        if self.name == 'importfail':
            raise ImportError()
        else:
            return importlib.import_module(self.name)


def _mock_entry_points(name):
    data = {
        'invenio_db.models': [MockEntryPoint('demo.child', 'demo.child'),
                              MockEntryPoint('demo.parent', 'demo.parent')],
    }
    names = data.keys() if name is None else [name]
    for key in names:
        for entry_point in data[key]:
            yield entry_point


def test_init():
    """Test extension initialization."""
    app = Flask('demo')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'SQLALCHEMY_DATABASE_URI', 'sqlite:///test.db'
    )
    FlaskCLI(app)
    InvenioDB(app, entrypoint_name=False)

    class Demo(db.Model):
        __tablename__ = 'demo'
        pk = sa.Column(sa.Integer, primary_key=True)

    class Demo2(db.Model):
        __tablename__ = 'demo2'
        pk = sa.Column(sa.Integer, primary_key=True)
        fk = sa.Column(sa.Integer, sa.ForeignKey(Demo.pk))

    with app.app_context():
        create_database(db.engine.url)
        db.create_all()
        assert len(db.metadata.tables) == 2
        db.drop_all()
        drop_database(db.engine.url)


@patch('pkg_resources.iter_entry_points', _mock_entry_points)
def test_entry_points(script_info):
    """Test entrypoints loading."""
    import invenio_db
    from invenio_db import shared
    from flask_sqlalchemy import SQLAlchemy
    db = invenio_db.db = shared.db = SQLAlchemy()

    app = Flask('demo')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'SQLALCHEMY_DATABASE_URI', 'sqlite:///test.db'
    )
    FlaskCLI(app)
    InvenioDB(app)

    runner = CliRunner()
    script_info = ScriptInfo(create_app=lambda info: app)

    assert len(db.metadata.tables) == 2

    # Test merging a base another file.
    with runner.isolated_filesystem():
        result = runner.invoke(db_cmd, [], obj=script_info)
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ['init'], obj=script_info)
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ['create'], obj=script_info)
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ['drop', '-v'],
                               obj=script_info)
        assert result.exit_code == 1

        result = runner.invoke(db_cmd, ['drop', '--yes-i-know'],
                               obj=script_info)
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ['drop', 'create', '-v'],
                               obj=script_info)
        assert result.exit_code == 1

        result = runner.invoke(db_cmd, ['drop', '--yes-i-know', 'create'],
                               obj=script_info)
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ['destroy'],
                               obj=script_info)
        assert result.exit_code == 1

        result = runner.invoke(db_cmd, ['destroy', '--yes-i-know'],
                               obj=script_info)
        assert result.exit_code == 0

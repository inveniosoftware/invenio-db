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

"""Test database integration layer."""

from __future__ import absolute_import, print_function

import pytest
import sqlalchemy as sa
from click.testing import CliRunner
from conftest import ScriptInfo
from mock import patch
from pkg_resources import EntryPoint
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import import_string

from invenio_db import InvenioDB
from invenio_db.cli import db as db_cmd


class MockEntryPoint(EntryPoint):
    """Mocking of entrypoint."""

    def load(self):
        """Mock load entry point."""
        if self.name == 'importfail':
            raise ImportError()
        else:
            return import_string(self.name)


def _mock_entry_points(name):
    data = {
        'invenio_db.models': [MockEntryPoint('demo.child', 'demo.child'),
                              MockEntryPoint('demo.parent', 'demo.parent')],
        'invenio_db.models_a': [
            MockEntryPoint('demo.versioned_a', 'demo.versioned_a'),
        ],
        'invenio_db.models_b': [
            MockEntryPoint('demo.versioned_b', 'demo.versioned_b'),
        ],
    }
    names = data.keys() if name is None else [name]
    for key in names:
        for entry_point in data[key]:
            yield entry_point


def test_init(db, app):
    """Test extension initialization."""
    class Demo(db.Model):
        __tablename__ = 'demo'
        pk = sa.Column(sa.Integer, primary_key=True)

    class Demo2(db.Model):
        __tablename__ = 'demo2'
        pk = sa.Column(sa.Integer, primary_key=True)
        fk = sa.Column(sa.Integer, sa.ForeignKey(Demo.pk))

    app.config['DB_VERSIONING'] = False
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
        Demo2.query.delete()
        Demo.query.delete()
        db.session.commit()

        db.drop_all()


def test_transaction(db, app):
    """Test transcation commit and rollback.

    This is necessary to make sure that pysqlite hacks are properly working.
    """
    class Demo(db.Model):
        __tablename__ = 'demo'
        pk = sa.Column(sa.Integer, primary_key=True)

    app.config['DB_VERSIONING'] = False
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


@patch('pkg_resources.iter_entry_points', _mock_entry_points)
def test_entry_points(db, app):
    """Test entrypoints loading."""
    InvenioDB(app, db=db)

    runner = CliRunner()
    script_info = ScriptInfo(create_app=lambda info: app)

    assert len(db.metadata.tables) == 2

    # Test merging a base another file.
    with runner.isolated_filesystem():
        result = runner.invoke(db_cmd, [], obj=script_info)
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ['destroy', '--yes-i-know'],
                               obj=script_info)
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ['init'], obj=script_info)
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ['create', '-v'], obj=script_info)
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ['drop'],
                               obj=script_info)
        assert result.exit_code == 1

        result = runner.invoke(db_cmd, ['drop', '-v', '--yes-i-know'],
                               obj=script_info)
        assert result.exit_code == 0

        result = runner.invoke(db_cmd, ['drop', 'create'],
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

        result = runner.invoke(db_cmd, ['init'], obj=script_info)
        assert result.exit_code == 0


def test_local_proxy(app, db):
    """Test local proxy filter."""
    from werkzeug.local import LocalProxy

    InvenioDB(app, db=db)

    with app.app_context():
        query = db.select([
            db.literal('hello') != db.bindparam('a'),
            db.literal(0) <= db.bindparam('x'),
            db.literal('2') == db.bindparam('y'),
            db.literal(None).is_(db.bindparam('z')),
        ])
        result = db.engine.execute(
            query,
            a=LocalProxy(lambda: 'world'),
            x=LocalProxy(lambda: 1),
            y=LocalProxy(lambda: '2'),
            z=LocalProxy(lambda: None),
        ).fetchone()
        assert result == (True, True, True, True)

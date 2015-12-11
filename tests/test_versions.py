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

"""Versioning tests for Invenio-DB"""

import pytest

from flask import Flask
from flask_cli import FlaskCLI

from mock import patch

from sqlalchemy_continuum import versioning_manager

from invenio_db import InvenioDB, db

from test_db import _mock_entry_points


class VersioningUser(db.Model):
    """User model to be used with versioning."""

    id = db.Column(db.Integer, primary_key=True)


class UnversionedArticle(db.Model):
    """Unversioned test model."""

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String)


class VersionedArticle(db.Model):
    """Versioned test model."""

    __versioned__ = {}

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String)


@patch('pkg_resources.iter_entry_points', _mock_entry_points)
def test_versioning_can_be_disabled(app):
    """Test that the versioning can be disabled."""
    app.config['DB_VERSIONING_ENABLED'] = False
    InvenioDB(app)
    with app.app_context():
        db.create_all()

        versioned = VersionedArticle()
        versioned.name = 'original_name'
        db.session.add(versioned)
        db.session.commit()

        versioned.name = 'modified_name'
        db.session.commit()

        assert not hasattr(versioned, 'versions')


@patch('pkg_resources.iter_entry_points', _mock_entry_points)
def test_versioning_user_model(app):
    """Test versioning user model loads."""
    app.config.update(DB_VERSIONING_USER_FROM_MODULE='test_versions')
    InvenioDB(app)
    with app.app_context():
        db.create_all()


@patch('pkg_resources.iter_entry_points', _mock_entry_points)
def test_versioning_invalid_user_model(app):
    """Test invalid versioning user model errors."""
    app.config.update(DB_VERSIONING_USER_FROM_MODULE='invalid_module')
    with pytest.raises(RuntimeError):
        InvenioDB(app)


@patch('pkg_resources.iter_entry_points', _mock_entry_points)
def test_versioning(app):
    """Test SQLAlchemy-Continuum versioning."""
    InvenioDB(app)
    with app.app_context():
        db.create_all()

        versioned = VersionedArticle()
        unversioned = UnversionedArticle()

        original_name = 'original_name'

        versioned.name = original_name
        unversioned.name = original_name

        db.session.add(versioned)
        db.session.add(unversioned)
        db.session.commit()

        assert unversioned.name == versioned.name

        modified_name = 'modified_name'

        versioned.name = modified_name
        unversioned.name = modified_name
        db.session.commit()

        assert unversioned.name == modified_name
        assert versioned.name == modified_name
        assert versioned.versions[0].name == original_name
        assert versioned.versions[1].name == versioned.name

        versioned.versions[0].revert()
        db.session.commit()

        assert unversioned.name == modified_name
        assert versioned.name == original_name

        versioned.versions[1].revert()
        db.session.commit()
        assert unversioned.name == versioned.name

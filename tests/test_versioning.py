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

from invenio_db import InvenioDB, db

from sqlalchemy_continuum import make_versioned


def test_versioning(app):
    """Test SQLAlchemy-Continuum versioning."""
    class UnversionedArticle(db.Model):
        """Unversioned test model."""

        id = db.Column(db.Integer, primary_key=True)

        name = db.Column(db.String)

    class VersionedArticle(db.Model):
        """Versioned test model."""

        __versioned__ = {}

        id = db.Column(db.Integer, primary_key=True)

        name = db.Column(db.String)

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

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
from mock import patch
from sqlalchemy_continuum import make_versioned
from test_db import _mock_entry_points

from invenio_db import InvenioDB


@patch('pkg_resources.iter_entry_points', _mock_entry_points)
def test_disabled_versioning(db, app):
    """Test SQLAlchemy-Continuum with disabled versioning."""
    InvenioDB(app, entry_point_group='invenio_db.models_a')

    with app.app_context():
        assert 2 == len(db.metadata.tables)


@pytest.mark.parametrize("versioning,tables", [
    (False, 1),  (True, 3)
])
def test_disabled_versioning_with_custom_table(db, app, versioning, tables):
    """Test SQLAlchemy-Continuum table loading."""
    app.config['DB_VERSIONING'] = versioning

    class EarlyClass(db.Model):

        __versioned__ = {}

        pk = db.Column(db.Integer, primary_key=True)

    idb = InvenioDB(app, entry_point_group=None, db=db)

    with app.app_context():
        db.drop_all()
        db.create_all()

        before = len(db.metadata.tables)
        ec = EarlyClass()
        ec.pk = 1
        db.session.add(ec)
        db.session.commit()

        assert tables == len(db.metadata.tables)

        db.drop_all()

    if versioning:
        from sqlalchemy_continuum import remove_versioning
        remove_versioning(manager=idb.versioning_manager)


@patch('pkg_resources.iter_entry_points', _mock_entry_points)
def test_versioning(db, app):
    """Test SQLAlchemy-Continuum enabled versioning."""
    from sqlalchemy_continuum import VersioningManager

    app.config['DB_VERSIONING'] = True

    idb = InvenioDB(app, entry_point_group='invenio_db.models_b', db=db,
                    versioning_manager=VersioningManager())

    with app.app_context():
        assert 4 == len(db.metadata.tables)

        db.create_all()

        from demo.versioned_b import UnversionedArticle, VersionedArticle
        original_name = 'original_name'

        versioned = VersionedArticle()
        unversioned = UnversionedArticle()

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

    with app.app_context():
        db.drop_all()

    from sqlalchemy_continuum import remove_versioning
    remove_versioning(manager=idb.versioning_manager)

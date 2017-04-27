# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2017 CERN.
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

"""Test DB utilities."""

import pytest
import sqlalchemy as sa
from sqlalchemy_utils.types.encrypted import EncryptedType

from invenio_db import InvenioDB
from invenio_db.utils import rebuild_encrypted_properties


def test_rebuild_encrypted_properties(db, app):
    old_secret_key = "SECRET_KEY_1"
    new_secret_key = "SECRET_KEY_2"
    app.secret_key = old_secret_key

    def _secret_key():
        return app.config.get('SECRET_KEY').encode('utf-8')

    class Demo(db.Model):
        __tablename__ = 'demo'
        pk = db.Column(sa.Integer, primary_key=True)
        et = db.Column(
            EncryptedType(type_in=db.Unicode, key=_secret_key), nullable=False
        )

    InvenioDB(app, entry_point_group=False, db=db)

    with app.app_context():
        db.create_all()
        d1 = Demo(et="something")
        db.session.add(d1)
        db.session.commit()

    app.secret_key = new_secret_key

    with app.app_context():
        with pytest.raises(UnicodeDecodeError):
            db.session.query(Demo).all()
        with pytest.raises(AttributeError):
            rebuild_encrypted_properties(old_secret_key, Demo, ['nonexistent'])
        assert app.secret_key == new_secret_key

    with app.app_context():
        with pytest.raises(UnicodeDecodeError):
            db.session.query(Demo).all()
        rebuild_encrypted_properties(old_secret_key, Demo, ['et'])
        d1_after = db.session.query(Demo).first()
        assert d1_after.et == "something"

    with app.app_context():
        db.drop_all()

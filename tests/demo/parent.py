# SPDX-FileCopyrightText: 2015-2018 CERN.
# SPDX-License-Identifier: MIT

"""Parent model."""

from invenio_db import db


class Parent(db.Model):
    """Parent demo model."""

    __tablename__ = "parent"
    pk = db.Column(db.Integer, primary_key=True)

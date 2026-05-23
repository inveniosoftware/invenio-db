# SPDX-FileCopyrightText: 2015-2018 CERN.
# SPDX-License-Identifier: MIT

"""Child model."""

from invenio_db import db

from .parent import Parent


class Child(db.Model):
    """Child demo model."""

    __tablename__ = "child"
    pk = db.Column(db.Integer, primary_key=True)
    fk = db.Column(db.Integer, db.ForeignKey(Parent.pk))

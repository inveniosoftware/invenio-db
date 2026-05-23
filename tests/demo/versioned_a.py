# SPDX-FileCopyrightText: 2015-2018 CERN.
# SPDX-License-Identifier: MIT

"""Normal and versioned models."""

from invenio_db import db


class UnversionedArticle(db.Model):
    """Unversioned test model."""

    __tablename__ = "unversioned_article_a"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(length=50))


class VersionedArticle(db.Model):
    """Versioned test model."""

    __tablename__ = "versioned_article_a"
    __versioned__ = {}

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(length=50))

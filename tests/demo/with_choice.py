# SPDX-FileCopyrightText: 2026 CESNET z.s.p..
# SPDX-License-Identifier: MIT

"""Model with ChoiceType."""

from enum import Enum

from sqlalchemy_utils.types.choice import ChoiceType

from invenio_db import db


class Severity(Enum):
    """Severity enum."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


USER_TYPES = [("admin", "Admin"), ("regular-user", "Regular user")]


class ModelWithChoices(db.Model):
    """A simple model with a ChoiceType column."""

    __tablename__ = "with_choices"
    pk = db.Column(db.Integer, primary_key=True)

    enum_choice = db.Column(ChoiceType(Severity))
    tuple_choice = db.Column(ChoiceType(USER_TYPES))

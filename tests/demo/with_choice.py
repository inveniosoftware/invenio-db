# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2026 CESNET z.s.p.o.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
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

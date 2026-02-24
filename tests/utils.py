# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2026 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Utility methods for tests."""

import os

import pytest

requires_postgresql = pytest.mark.skipif(
    not os.environ.get("SQLALCHEMY_DATABASE_URI", "").startswith("postgresql"),
    reason="PostgreSQL required",
)

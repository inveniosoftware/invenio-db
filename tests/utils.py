# SPDX-FileCopyrightText: 2026 CERN.
# SPDX-License-Identifier: MIT

"""Utility methods for tests."""

import os

import pytest

requires_postgresql = pytest.mark.skipif(
    not os.environ.get("SQLALCHEMY_DATABASE_URI", "").startswith("postgresql"),
    reason="PostgreSQL required",
)

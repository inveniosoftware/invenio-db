# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2023 Graz University of Technology.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Test database integration layer."""


from importlib_metadata import EntryPoint
from werkzeug.utils import import_string


class MockEntryPoint(EntryPoint):
    """Mocking of entrypoint."""

    def load(self):
        """Mock load entry point."""
        if self.name == "importfail":
            raise ImportError()
        else:
            return import_string(self.name)


def _mock_entry_points(name):
    def fn(group):
        data = {
            "invenio_db.models": [
                MockEntryPoint(name="demo.child", value="demo.child", group="test"),
                MockEntryPoint(name="demo.parent", value="demo.parent", group="test"),
            ],
            "invenio_db.models_a": [
                MockEntryPoint(
                    name="demo.versioned_a", value="demo.versioned_a", group="test"
                ),
            ],
            "invenio_db.models_b": [
                MockEntryPoint(
                    name="demo.versioned_b", value="demo.versioned_b", group="test"
                ),
            ],
        }
        if group:
            return data.get(group, [])
        if name:
            return {name: data.get(name)}
        return data

    return fn

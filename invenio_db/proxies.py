# SPDX-FileCopyrightText: 2022-2026 Graz University of Technology.
# SPDX-License-Identifier: MIT

"""Helper proxy to the state object."""

from flask import current_app
from werkzeug.local import LocalProxy

current_db = LocalProxy(lambda: current_app.extensions["sqlalchemy"])

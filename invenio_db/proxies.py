# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2022 Graz University of Technology.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Helper proxy to the state object."""


from flask import current_app
from werkzeug.local import LocalProxy

current_db = LocalProxy(lambda: current_app.extensions["sqlalchemy"])

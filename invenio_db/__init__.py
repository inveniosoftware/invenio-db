# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015 CERN.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Database management for Invenio.

First make sure you have Flask application with Click support (meaning
Flask 1.0+ or alternatively use the Flask-CLI extension):

    >>> from flask import Flask
    >>> app = Flask('myapp')
    >>> if not hasattr(app, 'cli'):
    ...     from flask_cli import FlaskCLI
    ...     cli = FlaskCLI(app)

Next, initialize your extension:

    >>> from invenio_db import InvenioDB
    >>> db = InvenioDB(app)


Command-line interface
~~~~~~~~~~~~~~~~~~~~~~
Invenio-DB installs the ``db`` command group on your application with the
following commands:

 * ``create`` - Create database tables.
 * ``drop`` - Drop database tables.
 * ``init`` - Initialize database.
 * ``destroy`` - Destroy database.

Models
~~~~~~

Database models are created by inheriting from the declarative base
``db.Model``:

.. code-block:: python

   # models.py
   from invenio_db import db

   class User(db.Model):
       id = db.Column(db.Integer, primary_key=True)
       username = db.Column(db.String(80), unique=True)
       email = db.Column(db.String(120), unique=True)

Setuptools integration
~~~~~~~~~~~~~~~~~~~~~~
In order for the CLI commands to be aware of your models, you must either
import your models in the application factory, or better simply specify the
entry point ``invenio_db.models``. Invenio-DB then takes care of loading the
models automatically:

.. code-block:: python

   # setup.py
   # ...
   setup(
       entry_points={
           'invenio_db.models': [
               'mymodule = mymodule.models',
           ],
       },
   )

"""

from __future__ import absolute_import, print_function

from .ext import InvenioDB
from .shared import db
from .version import __version__

__all__ = (
    '__version__',
    'db',
    'InvenioDB',
)

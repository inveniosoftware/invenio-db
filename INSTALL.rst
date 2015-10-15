Installation
============

The Invenio-DB package is on PyPI so all you need is:

.. code-block:: console

    $ pip install invenio-db

Invenio-DB depends on
`Flask-SQLAlchemy <https://pythonhosted.org/Flask-SQLAlchemy/>`_.


Configuration
=============

* ``SQLALCHEMY_DATABASE_URI`` - The database URI that should be used for the
  connection. Defaults to ``sqlite://<instane path>/<app name>.db``.
* ``SQLALCHEMY_ECHO`` - Log all statements to stderr.
  Defaults to ``app.debug``.

See https://pythonhosted.org/Flask-SQLAlchemy/config.html for further
configuration options.

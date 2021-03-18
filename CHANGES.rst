..
    This file is part of Invenio.
    Copyright (C) 2015-2020 CERN.

    Invenio is free software; you can redistribute it and/or modify it
    under the terms of the MIT License; see LICENSE file for more details.

Changes
=======

Version 1.0.9 (released 2021-03-18)

- Pins Flask-SQLAlchemy below 2.5 due to breaking changes. Perhaps to revisit when fixed.

Version 1.0.8 (released 2020-11-16)

- Pins SQLAlchemy to >=1.2.18 and <1.4 due to incompatibility between
  SQLAlchemy and SQLAlchemy-Utils.

Version 1.0.7 (released 2020-11-08)

- Hides password from output when running db init or db create.
- Disables MySQL 8 tests due to issue with Alembic

Version 1.0.6 (released 2020-10-02)

- Bump SQLAlchemy version to ``>=1.2.18`` to add support for PostgreSQL 12
- Integrate ``pytest-invenio`` and ``docker-services-cli`` for testing
- Support Python 3.8

Version 1.0.5 (released 2020-05-11)

- Deprecated Python versions lower than 3.6.0. Now supporting 3.6.0 and 3.7.0
- Use centrally managed Flask version (through Invenio-Base)
- Bumped SQLAlchemy version to ``>=1.1.0``
- SQLAlchemy-Utils set to ``<0.36`` due to breaking changes with MySQL
  (``VARCHAR`` length)
- Enriched documentation on DB session management
- Stop using example app

Version 1.0.4 (released 2019-07-29)

- Unpin sqlalchemy-continuum
- Added tests for postgresql 10

Version 1.0.3 (released 2019-02-22)

- Added handling in case of missing Sqlite db file.

Version 1.0.2 (released 2018-06-22)

- Pin SQLAlchemy-Continuum.

Version 1.0.1 (released 2018-05-16)

- Minor fixes in documenation links and the license file.

Version 1.0.0 (released 2018-03-23)

- Initial public release.

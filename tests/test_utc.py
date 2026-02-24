# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2026 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Test UTC and datetime column support for migrations.

The aim is that UTCDateTime should work regardless of whether the corresponding
`timestamp` -> `timestamptz` migrations have been run, **as long as the database
is using UTC**. The `SQLALCHEMY_ENGINE_OPTIONS` config specified in this module
is supposed to force PostgreSQL to always use UTC, so these tests should check
behaviour for both UTC and non-UTC zones.
"""

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from utils import requires_postgresql

from invenio_db.ext import InvenioDB
from invenio_db.shared import SQLAlchemy, UTCDateTime


@requires_postgresql
def test_timestamp_no_tz(app, db: SQLAlchemy):
    InvenioDB(app, entry_point_group=False, db=db)

    class TestTimestampNoTZ(db.Model):
        __tablename__ = "_test_timestamp_no_tz"
        id = sa.Column(sa.Integer, primary_key=True)
        t = sa.Column(UTCDateTime)

    with app.app_context():
        # Create the table manually so we can override the `t` column type to what it would be pre-migration.
        db.session.execute(
            sa.text(
                "CREATE TABLE IF NOT EXISTS _test_timestamp_no_tz (id int PRIMARY KEY, t TIMESTAMP WITHOUT TIME ZONE)"
            )
        )
        db.session.execute(sa.text("SET TIMEZONE TO 'UTC'"))
        db.session.commit()

    expected_datetime = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    with app.app_context():
        t = TestTimestampNoTZ()
        t.id = 1
        t.t = expected_datetime
        db.session.add(t)
        db.session.commit()

    with app.app_context():
        res = TestTimestampNoTZ.query.all()
        assert len(res) == 1
        assert res[0].id == 1
        assert res[0].t == expected_datetime
        assert res[0].t.tzinfo == expected_datetime.tzinfo
        db.session.delete(res[0])
        db.session.commit()

    with app.app_context():
        # Change to a non-UTC timezone to show the unexpected behaviour. Production Invenio databases
        # must always use UTC. Invenio-DB always initialises the connection with UTC so this will be
        # the case unless the instance overrides it.
        # This test shows the unexpected behaviour that occurs on a non-UTC DB.
        # We are changing the timezone to UTC+1 (depicted as UTC-1 in PostgreSQL). We are not using an
        # IANA named time zone to ensure the test is consistent at all times of year.
        # See https://www.postgresql.org/docs/current/datetime-posix-timezone-specs.html
        db.session.execute(sa.text("SET TIMEZONE TO 'UTC-1'"))
        db.session.commit()

    with app.app_context():
        t = TestTimestampNoTZ()
        t.id = 1
        # All Invenio modules always write UTC values to the DB without any knowledge of what the DB's
        # zone is set to. We therefore continue writing the UTC `expected_datetime` to show this behaviour.
        t.t = expected_datetime
        db.session.add(t)
        db.session.commit()

    with app.app_context():
        res = TestTimestampNoTZ.query.all()
        assert len(res) == 1
        assert res[0].id == 1
        # PostgreSQL received the timestamp as '2026-01-01T12:00+00:00'::timestamptz
        # Since the column type was `timestamp` and not `timestamptz`, it had to convert it
        # from UTC to the DB's default zone which is now UTC+1.
        # But when this value is read back, no timezone info is actually returned since the
        # column is no `timestamptz`. UTCDateTime assumes the zone to be UTC.
        # Therefore, the interpreted hour is shifted by one while the timezone is still
        # believed to be UTC.
        # This is unwanted behaviour and is why it's important that the DB is set to UTC.
        assert res[0].t != expected_datetime
        assert res[0].t.hour == expected_datetime.hour + 1
        assert res[0].t.tzinfo == expected_datetime.tzinfo
        db.session.delete(res[0])
        db.session.commit()

    with app.app_context():
        db.session.execute(sa.text("DROP TABLE _test_timestamp_no_tz"))
        db.session.execute(sa.text("SET TIMEZONE TO 'UTC'"))
        db.session.commit()


@requires_postgresql
def test_timestamp_with_tz(app, db: SQLAlchemy):
    InvenioDB(app, entry_point_group=False, db=db)

    class TestTimestampWithTZ(db.Model):
        __tablename__ = "_test_timestamp_with_tz"
        id = sa.Column(sa.Integer, primary_key=True)
        t = sa.Column(UTCDateTime)

    with app.app_context():
        # Create the table manually so we can override the `t` column type to what it would be post-migration.
        db.session.execute(
            sa.text(
                "CREATE TABLE IF NOT EXISTS _test_timestamp_with_tz (id int PRIMARY KEY, t TIMESTAMP WITH TIME ZONE)"
            )
        )
        db.session.execute(sa.text("SET TIMEZONE TO 'UTC'"))
        db.session.commit()

    expected_datetime = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    with app.app_context():
        t = TestTimestampWithTZ()
        t.id = 1
        t.t = expected_datetime
        db.session.add(t)
        db.session.commit()

    with app.app_context():
        res = TestTimestampWithTZ.query.all()
        assert len(res) == 1
        assert res[0].id == 1
        assert res[0].t == expected_datetime
        assert res[0].t.tzinfo == expected_datetime.tzinfo
        db.session.delete(res[0])
        db.session.commit()

    with app.app_context():
        db.session.execute(sa.text("SET TIMEZONE TO 'UTC-1'"))
        db.session.commit()

    with app.app_context():
        t = TestTimestampWithTZ()
        t.id = 1
        t.t = expected_datetime
        db.session.add(t)
        db.session.commit()

    with app.app_context():
        # In this case, PostgreSQL also shifts the inserted timestamp to UTC+1.
        # However, it now also returns the timezone with the column correctly as UTC+1.
        # To ensure we avoid unexpected behaviour as much as possible, UTCDateTime only
        # accepts timestamps from PostgreSQL that are in UTC, and raises an exception for
        # all other zones.
        # So in this case correctness is preserved but as an added safety mechanism we still
        # reject the value.
        with pytest.raises(ValueError) as excinfo:
            TestTimestampWithTZ.query.all()

        expected_shifted_datetime = expected_datetime.astimezone(
            timezone(timedelta(hours=1))
        )
        assert str(expected_shifted_datetime) in str(excinfo.value)

        db.session.commit()

    with app.app_context():
        db.session.execute(sa.text("DROP TABLE _test_timestamp_with_tz"))
        db.session.execute(sa.text("SET TIMEZONE TO 'UTC'"))
        db.session.commit()

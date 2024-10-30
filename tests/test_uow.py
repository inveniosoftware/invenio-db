# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Unit of work tests."""

from unittest.mock import MagicMock

from invenio_db import InvenioDB
from invenio_db.uow import ModelCommitOp, Operation, UnitOfWork


def test_uow_lifecycle(db, app):
    InvenioDB(app, entry_point_group=False, db=db)

    with app.app_context():
        mock_op = MagicMock()

        # Test normal lifecycle
        with UnitOfWork(db.session) as uow:
            uow.register(mock_op)
            uow.commit()

        mock_op.on_register.assert_called_once()
        mock_op.on_commit.assert_called_once()
        mock_op.on_post_commit.assert_called_once()

        mock_op.on_exception.assert_not_called()
        mock_op.on_rollback.assert_not_called()
        mock_op.on_post_rollback.assert_not_called()

        # Test rollback lifecycle
        mock_op.reset_mock()
        with UnitOfWork(db.session) as uow:
            uow.register(mock_op)
            uow.rollback()

        mock_op.on_register.assert_called_once()
        mock_op.on_commit.assert_not_called()
        mock_op.on_post_commit.assert_not_called()

        # on_exception is not called (since there was no exception)
        mock_op.on_exception.assert_not_called()

        # rest of the rollback lifecycle is called
        mock_op.on_rollback.assert_called_once()
        mock_op.on_post_rollback.assert_called_once()

        # Test exception lifecycle
        mock_op.reset_mock()
        try:
            with UnitOfWork(db.session) as uow:
                uow.register(mock_op)
                raise Exception()
        except Exception:
            pass

        mock_op.on_register.assert_called_once()
        mock_op.on_commit.assert_not_called()
        mock_op.on_post_commit.assert_not_called()

        # both exception and rollback lifecycle are called
        mock_op.on_exception.assert_called_once()
        mock_op.on_rollback.assert_called_once()
        mock_op.on_post_rollback.assert_called_once()


def test_uow_transactions(db, app):
    """Test transaction behavior with the Unit of Work."""

    class Data(db.Model):
        value = db.Column(db.String(100), primary_key=True)

    InvenioDB(app, entry_point_group=False, db=db)

    rollback_side_effect = MagicMock()
    post_rollback_side_effect = MagicMock()

    class CleanUpOp(Operation):
        def on_exception(self, uow, exception):
            uow.session.add(Data(value="clean-up"))

        on_rollback = rollback_side_effect
        on_post_rollback = post_rollback_side_effect

    with app.app_context():
        db.create_all()

        # Test normal lifecycle
        with UnitOfWork(db.session) as uow:
            uow.register(ModelCommitOp(Data(value="persisted")))
            uow.commit()

        data = db.session.query(Data).all()
        assert len(data) == 1
        assert data[0].value == "persisted"

        # Test rollback lifecycle
        with UnitOfWork(db.session) as uow:
            uow.register(ModelCommitOp(Data(value="not-persisted")))
            uow.register(CleanUpOp())
            uow.rollback()

        data = db.session.query(Data).all()
        assert len(data) == 1
        assert data[0].value == "persisted"

        rollback_side_effect.assert_called_once()
        post_rollback_side_effect.assert_called_once()

        # Test exception lifecycle
        rollback_side_effect.reset_mock()
        post_rollback_side_effect.reset_mock()
        try:
            with UnitOfWork(db.session) as uow:
                uow.register(ModelCommitOp(Data(value="not-persisted")))
                uow.register(CleanUpOp())
                raise Exception()
        except Exception:
            pass

        data = db.session.query(Data).all()
        assert len(data) == 2
        assert set([d.value for d in data]) == {"persisted", "clean-up"}

        rollback_side_effect.assert_called_once()
        post_rollback_side_effect.assert_called_once()

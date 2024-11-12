# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 CERN.
# Copyright (C) 2024 Graz University of Technology.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Unit of work.

Moved from invenio-records-resources.

Used to group multiple service operations into a single atomic unit. The Unit
of Work maintains a list of operations and coordinates the commit, indexing and
task execution.

Note, this is NOT a clean implementation of the UoW design pattern. The
main purpose of the Unit of Work in Invenio is to coordinate when the database
transaction commit is called, and ensure tasks that have to run after the
transaction are executed (such as indexing and running celery tasks).

This ensures that we can group multiple service calls into a single database
transaction and perform the necessary indexing/task execution afterwards.

**When to use?**

You should use the unit of work instead of running an explicit
``db.session.commit()`` or ``db.session.rollback()`` in the code. Basically
any function where you would normally have called a ``db.session.commit()``
should be changed to something like:

.. code-block:: python

    from invenio_db.uow import \
        ModelCommit, unit_of_work,

    @unit_of_work()
    def create(self, ... , uow=None):
        # ...
        uow.register(ModelCommit(model))
        # ...
        # Do not use `db.session.commit()` in service.

**When not to use?**

If you're not changing the database state there's no need to use the unit of
work. Examples include:

- Reading a model
- Search for models

**How to group multiple service calls?**

In order to group multiple service calls into one atomic operation you can use
the following pattern:

.. code-block:: python

    from invenio_db.uow import UnitOfWork

    with UnitOfWork() as uow:
        # Be careful to always inject "uow" to the service. If not, the
        # service will create its own unit of work and commit.
        service.communities.add(..., uow=uow)
        service.publish(... , uow=uow)
        uow.commit()

If you're not grouping multiple service calls, then simply just call the
service method (and it will commit automatically):

.. code-block:: python

    service.publish(...)

**Writing your own operation?**

You can write your own unit of work operation by subclassing the operation
class and implementing the desired methods:

.. code-block:: python

    from invenio_db.uow import Operation

    class BulkIndexOp(Operation):
        def on_commit(self, uow):
            # ... executed after the database transaction commit ...
"""

from functools import wraps

from .shared import db


#
# Unit of work operations
#
class Operation:
    """Base class for unit of work operations."""

    def on_register(self, uow):
        """Called upon operation registration."""
        pass

    def on_commit(self, uow):
        """Called in the commit phase (after the transaction is committed)."""
        pass

    def on_post_commit(self, uow):
        """Called right after the commit phase."""
        pass

    def on_exception(self, uow, exception):
        """Called in case of an exception."""
        pass

    def on_rollback(self, uow):
        """Called in the rollback phase (after the transaction rollback)."""
        pass

    def on_post_rollback(self, uow):
        """Called right after the rollback phase."""
        pass


class ModelCommitOp(Operation):
    """SQLAlchemy model add/update operation."""

    def __init__(self, model):
        """Initialize the commit operation."""
        super().__init__()
        self._model = model

    def on_register(self, uow):
        """Add model to db session."""
        uow.session.add(self._model)


class ModelDeleteOp(Operation):
    """SQLAlchemy model delete operation."""

    def __init__(self, model):
        """Initialize the set delete operation."""
        super().__init__()
        self._model = model

    def on_register(self, uow):
        """Delete model."""
        uow.session.delete(self._model)


#
# Unit of work context manager
#
class UnitOfWork:
    """Unit of work context manager.

    Note, the unit of work does not currently take duplication of work into
    account. Thus, you can e.g. add two record commit operations of the same
    record which will then index the record twice, even though only one time
    is needed.
    """

    def __init__(self, session=None):
        """Initialize unit of work context."""
        self._session = session or db.session
        self._operations = []
        self._dirty = False

    def __enter__(self):
        """Entering the context."""
        self.session.begin_nested()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Rollback on exception."""
        if exc_type is not None:
            self.rollback(exception=exc_value)
            self._mark_dirty()

    @property
    def session(self):
        """The SQLAlchemy database session associated with this UoW."""
        return self._session

    def _mark_dirty(self):
        """Mark the unit of work as dirty."""
        if self._dirty:
            raise RuntimeError("The unit of work is already committed or rolledback.")
        self._dirty = True

    def commit(self):
        """Commit the unit of work."""
        self.session.commit()
        # Run commit operations
        for op in self._operations:
            op.on_commit(self)
        # Run post commit operations
        for op in self._operations:
            op.on_post_commit(self)
        self._mark_dirty()

    def rollback(self, exception=None):
        """Rollback the database session."""
        self.session.rollback()

        # Run exception operations
        if exception:
            for op in self._operations:
                op.on_exception(self, exception)

            # Commit exception operations
            self.session.commit()

        # Run rollback operations
        for op in self._operations:
            op.on_rollback(self)
        # Run post rollback operations
        for op in self._operations:
            op.on_post_rollback(self)

    def register(self, op):
        """Register an operation."""
        # Run on register
        op.on_register(self)
        # Append to list of operations.
        self._operations.append(op)


def unit_of_work(**kwargs):
    """Decorator to auto-inject a unit of work if not provided.

    If no unit of work is provided, this decorator will create a new unit of
    work and commit it after the function has been executed.

    .. code-block:: python

        @unit_of_work()
        def aservice_method(self, ...., uow=None):
            # ...
            uow.register(...)

    """

    def decorator(f):
        @wraps(f)
        def inner(self, *args, **kwargs):
            if "uow" not in kwargs or kwargs["uow"] is None:
                # Migration path - start a UoW and commit
                with UnitOfWork(db.session) as uow:
                    kwargs["uow"] = uow
                    res = f(self, *args, **kwargs)
                    uow.commit()
                    return res
            else:
                return f(self, *args, **kwargs)

        return inner

    return decorator

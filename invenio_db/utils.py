# SPDX-FileCopyrightText: 2017-2018 CERN.
# SPDX-FileCopyrightText: 2022-2026 Graz University of Technology.
# SPDX-FileCopyrightText: 2026 University of Münster.
# SPDX-License-Identifier: MIT
# from .signals import secret_key_changed

"""Invenio-DB utility functions."""

from contextlib import contextmanager
from functools import partial

from alembic import op
from alembic.migration import MigrationContext
from flask import current_app
from sqlalchemy import inspect, text

from .proxies import current_db
from .shared import db as _db


def rebuild_encrypted_properties(old_key, model, properties, db=_db):
    """Rebuild model's EncryptedType properties when the SECRET_KEY is changed.

    :param old_key: old SECRET_KEY.
    :param model: the affected db model.
    :param properties: list of properties to rebuild.
    """
    inspector = inspect(db.engine)
    primary_key_names = inspector.get_pk_constraint(model.__tablename__)[
        "constrained_columns"
    ]

    new_secret_key = current_app.secret_key
    db.session.expunge_all()
    try:
        with db.session.begin_nested():
            current_app.secret_key = old_key
            db_columns = []
            for primary_key in primary_key_names:
                db_columns.append(getattr(model, primary_key))
            for prop in properties:
                db_columns.append(getattr(model, prop))
            old_rows = db.session.query(*db_columns).all()
    except Exception as e:
        current_app.logger.error(
            "Exception occurred while reading encrypted properties. "
            "Try again before starting the server with the new secret key."
        )
        raise e
    finally:
        current_app.secret_key = new_secret_key
        db.session.expunge_all()

    for old_row in old_rows:
        primary_keys, old_entries = (
            old_row[: len(primary_key_names)],
            old_row[len(primary_key_names) :],
        )
        primary_key_fields = dict(zip(primary_key_names, primary_keys))
        update_values = dict(zip(properties, old_entries))
        model.query.filter_by(**primary_key_fields).update(update_values)
    db.session.commit()


@contextmanager
def read_only_session(db=_db):
    """Run the session's queries in autocommit mode inside the block.

    Meant for read-only work: each statement runs in its own transaction, so a
    long read loop does not keep a transaction open (holding table locks and a
    pinned connection) between queries. Writes in the block commit
    immediately. The mode ends with the block, or earlier if anything in it
    commits or rolls back. An open transaction that has only read is ended
    first; one with writes raises. Streaming queries (``yield_per``) need a
    transaction and fail inside it.
    """
    session = db.session()
    if session.in_transaction():
        # A transaction that has only read can end without losing anything
        if _has_writes(session):
            raise RuntimeError(
                "read_only_session() can't end a transaction that has writes."
            )
        session.rollback()

    session.connection(execution_options={"isolation_level": "AUTOCOMMIT"})
    try:
        yield session
    finally:
        # Rollback, not close, so objects the caller loaded stay attached.
        # The pool resets the isolation level when the connection is returned.
        session.rollback()


def _has_writes(session):
    """Whether the session's transaction has pending or executed writes."""
    if session.new or session.dirty or session.deleted:
        return True
    if session.in_nested_transaction():
        return True
    connection = session.connection()
    if connection.dialect.name != "postgresql":
        return True
    # PostgreSQL assigns a transaction ID only once the transaction writes
    query = text("SELECT txid_current_if_assigned()")
    return connection.execute(query).scalar() is not None


def create_alembic_version_table():
    """Create alembic_version table."""
    alembic = current_app.extensions["invenio-db"].alembic
    db = current_app.extensions["sqlalchemy"]
    with db.engine.begin() as connection:
        context = MigrationContext.configure(connection)
        if not context._has_version_table():
            context._ensure_version_table()
            all_heads = alembic.script_directory.revision_map._real_heads
            context.stamp(alembic.script_directory, tuple(all_heads))


def drop_alembic_version_table():
    """Drop alembic_version table."""
    if has_table(current_db.engine, "alembic_version"):
        alembic_version = current_db.Table(
            "alembic_version", current_db.metadata, autoload_with=current_db.engine
        )
        alembic_version.drop(bind=current_db.engine)


def versioning_model_classname(manager, model):
    """Get the name of the versioned model class."""
    if manager.options.get("use_module_name", True):
        return "%s%sVersion" % (
            model.__module__.title().replace(".", ""),
            model.__name__,
        )
    else:
        return "%sVersion" % (model.__name__,)


def versioning_models_registered(manager, base):
    """Return True if all versioning models have been registered."""
    try:
        registry = base.registry._class_registry
    except AttributeError:  # SQLAlchemy <1.4
        registry = base._decl_class_registry
    declared_models = registry.keys()
    return all(
        versioning_model_classname(manager, c) in declared_models
        for c in manager.pending_classes
    )


def alembic_test_context():
    """Alembic test context.

    # skip index from alembic migrations until sqlalchemy 2.0
    # https://github.com/sqlalchemy/sqlalchemy/discussions/7597
    """

    def include_object(object, name, type_, reflected, compare_to):
        if name == "ix_uq_partial_files_object_is_head":
            return False
        return True

    return {
        "transaction_per_migration": True,
        "include_object": include_object,
        "compare_server_default": True,
        "autogenerate_plugins": [
            # Alembic v1.19.0 introduced the a new CHECK constraint plugin which causes
            # a few hiccups in our setup, so we disable it for now
            # cf. https://alembic.sqlalchemy.org/en/latest/changelog.html#change-1.19.0
            "alembic.autogenerate.*",
            "~alembic.autogenerate.checkconstraint_byname",
        ],
    }


def has_table(engine, table):
    """Determine if table exists."""
    try:
        return inspect(engine).has_table(table)
    except AttributeError:
        # SQLAlchemy <1.4
        return engine.has_table(table)


def update_table_columns_column_type(
    table_name, column_name, to_type=None, existing_type=None, existing_nullable=None
):
    """Update column type."""
    op.alter_column(
        table_name,
        column_name,
        type_=to_type(),
        existing_type=existing_type(),
        existing_nullable=existing_nullable,
    )


update_table_columns_column_type_to_utc_datetime = partial(
    update_table_columns_column_type,
    to_type=_db.UTCDateTime,
    existing_type=_db.DateTime,
    existing_nullable=True,
)

update_table_columns_column_type_to_datetime = partial(
    update_table_columns_column_type,
    to_type=_db.DateTime,
    existing_type=_db.UTCDateTime,
    existing_nullable=True,
)

# SPDX-FileCopyrightText: 2017-2018 CERN.
# SPDX-FileCopyrightText: 2022-2026 Graz University of Technology.
# SPDX-FileCopyrightText: 2026 University of Münster.
# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT
# from .signals import secret_key_changed

"""Invenio-DB utility functions."""

from functools import partial

from alembic import op
from alembic.migration import MigrationContext
from flask import current_app
from sqlalchemy import inspect

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


def alembic_render_item(type_, obj, autogen_context):
    """Fix import generation and broken reprs for known types.

    Alembic uses ``x.__repr__`` to generate the migration code. For ChoiceType,
    it is broken - the generated repr does not include the ``choices`` argument.

    This render function fixes it by emitting the ``choices`` argument explicitly.
    """
    if type_ == "type":
        # --- ChoiceType fix ---------------------------------------------------
        try:
            from sqlalchemy_utils.types.choice import ChoiceType
        except ImportError:
            pass
        else:
            if isinstance(obj, ChoiceType):
                from enum import Enum

                from alembic.autogenerate.render import _repr_type

                impl_repr = _repr_type(obj.impl_instance, autogen_context)

                choices = obj.choices
                if isinstance(choices, type) and issubclass(choices, Enum):
                    # The enum class itself is omitted, since referencing it would break if the
                    # class is later renamed, moved, or removed.
                    # Instead, all enum values are emitted as a list of (value, name) tuples.
                    # Note: this is for documentation purposes only; the choices list does not
                    # affect the generated SQL.
                    choices_list = [
                        (member.value, member.name)
                        for member in sorted(choices, key=lambda m: m.value)
                    ]
                    return (
                        f"sqlalchemy_utils.types.choice.ChoiceType("
                        f"{choices_list!r}, impl={impl_repr})"
                    )
                else:
                    # List-of-tuples: values may not be serialisable; render
                    # only the impl type, which is all the migration needs.
                    return impl_repr

    return False  # let Alembic render the type normally

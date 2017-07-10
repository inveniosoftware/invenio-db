Alembic
=======
Alembic is a database migration library used with SQLAlchemy ORM. Invenio works with the Flask-Alembic library, its documentation can be found here: http://flask-alembic.readthedocs.io/en/latest/
Invenio-DB fully supports alembic and each Invenio module having a database model is also expected to provide the corresponding alembic revisions.
Alembic migrations do not work with SQLite.


Adding alembic support to existing modules
------------------------------------------

The following procedures use invenio-unicorn for demonstration purposes.

We can create the alembic directory with:

.. code-block:: console

   $ invenio alembic mkdir

and then add the invenio_db.alembic entrypoint in setup.py:

.. code-block:: python
    
    setup(
        ...
        entry_points={
            ...
            'invenio_db.alembic': [
                'invenio_unicorn = invenio_unicorn:alembic',
            ]
    })

This will register the ``invenio_unicorn/alembic`` directory in alembic's ``version_locations``
Each module creates a branch for its revisions. To create a new branch:

.. code-block:: console
   
   $ invenio alembic revision "Create unicorn branch." -b invenio_unicorn -p <parent-revision> -d <dependencies> --empty

| -b  sets the branch label
| -p  sets the parent revision, as default all branches should root from ``dbdbc1b19cf2`` in invenio-db
| -d  sets the dependencies if they exist. For example when there is a foreign key pointing to the table of another invenio module, we need to make sure that table exists before applying this revision so we add it as a dependency.

The second revision typically has the message "Create unicorn tables." and will create the tables defined in the models. This can be created as a normal revision following the procedure below.

Creating a new revision
-----------------------

After making changes to the models of a module, we need to create a new alembic revision to apply these changes in the DB with a migration.
After making sure that the module creates its own branch and the alembic entrypoint is present as described above, we can create the new revision.

First to make sure that the DB is up to date we apply any pending revisions by

.. code-block:: console 

    $ invenio alembic upgrade heads

and now we can create the revision by:

.. code-block:: console

    $ invenio alembic revision "Revision message." --path <alembic-directory-path>

A short message describing the changes is required and the path parameter should point to the alembic directory of the module. If the path is not given the new revision will be placed in the invenio_db/alembic directory and should be moved.

The directories accepted are registered by the ``invenio_db.alembic`` entrypoints.

Show current state
------------------

To see the list of revisions in the order they will run:

.. code-block:: console

    $ invenio alembic log


The list of heads for all branches is given by:

.. code-block:: console

    $ invenio alembic heads

in this list revisions will be shown as ``(head)`` or ``(effective head)``, the difference being that effective heads are not shown in the ``alembic_version`` table as they are dependencies of other branches and they are overwritten.

The list of the revisions that have been applied is given by:

.. code-block:: console

    $ invenio alembic current

Enabling alembic migrations in existing invenio instances
---------------------------------------------------------

When there is a DB in place but there is no ``alembic_version`` table, meaning that the DB wasn't created through alembic upgrade, in order to start using alembic the table has to be inserted and stamped with the revisions matching the current state of the DB:

.. code-block:: console

    $ invenio alembic stamp

Given that there have been no changes in the DB, and the models match the alembic revisions, alembic upgrades and downgrades will be working now.
A thing to note is that the any constraints that were created without names, will have the default names from the DB which can be different from the ones in the alembic revisions, leading to errors in the future.

Naming Constraints
------------------

In http://alembic.zzzcomputing.com/en/latest/naming.html, the need for naming constraints in the models is explained. In invenio-db the '35c1075e6360' revision applies the naming convention. If models contain constraints that are unnamed an ``"InvalidRequestError: Naming convention including %(constraint_name)s token requires that constraint is explicitly named."`` will be raised.

The naming convention rules are:

+---------------+----------------------------------------------------------------+
| index         |  'ix_%(column_0_label)s'                                       |
+---------------+----------------------------------------------------------------+
| unique        |  'uq_%(table_name)s_%(column_0_name)s'                         |
+---------------+----------------------------------------------------------------+
| check         |  'ck_%(table_name)s_%(constraint_name)s'                       |
+---------------+----------------------------------------------------------------+
| foreign key   |  'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s' |
+---------------+----------------------------------------------------------------+
| primary key   |  'pk_%(table_name)s'                                           |
+---------------+----------------------------------------------------------------+

In the alembic revisions the constraints that will produce a name longer that 64 characters have to be named explicitly to a truncated form.

Testing revisions
-----------------
When initially creating alembic revisions one has to provide a test case for them.
The test for the created revisions starts from an empty DB, upgrades to the last branch revision and then downgrades to the base. We can check that there are no discrepancies in the state of the DB between the revisions and the models, by asserting that alembic.compare_metadata() returns an empty list. An example can be found here: https://github.com/inveniosoftware/invenio-oauthclient/blob/master/tests/test_app.py#L141

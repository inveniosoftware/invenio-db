# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015-2020 CERN.
# Copyright (C) 2021 Northwestern University.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Database management for Invenio."""

import os

from setuptools import find_packages, setup

readme = open('README.rst').read()
history = open('CHANGES.rst').read()

tests_require = [
    "pytest-invenio>=1.4.0",
    "cryptography>=2.1.4",
    "mock>=4.0.0"
]

extras_require = {
    'docs': [
        'Sphinx>=3.0.0',
    ],
    'mysql': [
        'pymysql>=0.10.1',
    ],
    'postgresql': [
        'psycopg2-binary>=2.8.6',
    ],
    'versioning': [
        'SQLAlchemy-Continuum>=1.3.11',
    ],
    'tests': tests_require,
}

extras_require['all'] = []
for reqs in extras_require.values():
    extras_require['all'].extend(reqs)

install_requires = [
    'invenio-base>=1.2.3',
    'Flask-Alembic>=2.0.1',
    'Flask-SQLAlchemy>=2.1,<2.5.0',
    'SQLAlchemy>=1.2.18,<1.4.0',
    'SQLAlchemy-Utils>=0.33.1,<0.36',
]

packages = find_packages()


# Get the version string. Cannot be done with import!
g = {}
with open(os.path.join('invenio_db', 'version.py'), 'rt') as fp:
    exec(fp.read(), g)
    version = g['__version__']
setup(
    name='invenio-db',
    version=version,
    description=__doc__,
    long_description=readme + '\n\n' + history,
    keywords='invenio database',
    license='MIT',
    author='Invenio Collaboration',
    author_email='info@inveniosoftware.org',
    url='https://github.com/inveniosoftware/invenio-db',
    packages=packages,
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    entry_points={
        'invenio_base.api_apps': [
            'invenio_db = invenio_db:InvenioDB',
        ],
        'invenio_base.apps': [
            'invenio_db = invenio_db:InvenioDB',
        ],
    },
    extras_require=extras_require,
    install_requires=install_requires,
    tests_require=tests_require,
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: Implementation :: CPython',
        'Development Status :: 5 - Production/Stable',
    ],
)

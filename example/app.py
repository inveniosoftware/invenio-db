import os

from flask import Flask
from flask_cli import FlaskCLI
from flask_sqlalchemy import SQLAlchemy

from invenio_db import InvenioDB

app = Flask('demo')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'SQLALCHEMY_DATABASE_URI', 'sqlite:///test.db'
)
FlaskCLI(app)
InvenioDB(app)

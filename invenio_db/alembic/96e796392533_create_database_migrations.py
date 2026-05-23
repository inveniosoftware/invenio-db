# SPDX-FileCopyrightText: 2016-2018 CERN.
# SPDX-License-Identifier: MIT

"""Create database migrations."""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "96e796392533"
down_revision = None
branch_labels = ("default",)
depends_on = None


def upgrade():
    """Update database."""


def downgrade():
    """Downgrade database."""

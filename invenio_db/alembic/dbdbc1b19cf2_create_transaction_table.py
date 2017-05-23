#
# This file is part of Invenio.
# Copyright (C) 2016 CERN.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Create transaction table."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.schema import Sequence, CreateSequence, \
    DropSequence

# revision identifiers, used by Alembic.
revision = 'dbdbc1b19cf2'
down_revision = '96e796392533'
branch_labels = ()
depends_on = None


def upgrade():
    """Update database."""
    op.create_table(
        'transaction',
        sa.Column('issued_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('remote_addr', sa.String(length=50), nullable=True),
    )
    op.create_primary_key('pk_transaction', 'transaction', ['id'])
    if op._proxy.migration_context.dialect.supports_sequences:
        op.execute(CreateSequence(Sequence('transaction_id_seq')))


def downgrade():
    """Downgrade database."""
    op.drop_table('transaction')
    if op._proxy.migration_context.dialect.supports_sequences:
        op.execute(DropSequence(Sequence('transaction_id_seq')))

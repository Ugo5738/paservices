"""create_app_clients_table

Revision ID: c4054d04812f
Revises: d86fc473c3fa
Create Date: 2025-05-27 12:10:08.872839

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4054d04812f'
down_revision: Union[str, None] = 'd86fc473c3fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

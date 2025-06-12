"""create_user_roles_table

Revision ID: 6aaf665c02c6
Revises: e8c2ee1b8bed
Create Date: 2025-05-27 12:13:08.622102

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6aaf665c02c6'
down_revision: Union[str, None] = 'e8c2ee1b8bed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

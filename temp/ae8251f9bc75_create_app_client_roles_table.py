"""create_app_client_roles_table

Revision ID: ae8251f9bc75
Revises: 6aaf665c02c6
Create Date: 2025-05-27 12:14:02.800497

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae8251f9bc75'
down_revision: Union[str, None] = '6aaf665c02c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

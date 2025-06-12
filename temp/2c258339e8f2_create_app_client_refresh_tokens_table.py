"""create_app_client_refresh_tokens_table

Revision ID: 2c258339e8f2
Revises: 81a5f5a67e29
Create Date: 2025-05-27 12:30:40.717355

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c258339e8f2'
down_revision: Union[str, None] = '81a5f5a67e29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

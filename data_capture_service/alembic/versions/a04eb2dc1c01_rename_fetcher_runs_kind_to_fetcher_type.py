"""Rename fetcher_runs.kind → fetcher_type.

Revision ID: a04eb2dc1c01
Revises: a28735a085a7
Create Date: 2026-05-15

Chunk 6 of the V2 SuperID rollout. Renames the discriminator column
on `data_capture.fetcher_runs` from the opaque `kind` to the
self-explanatory `fetcher_type`, per Rolf's naming feedback (May 13):
"Kind is terrible. It makes no sense on its own... Type or Fetcher
Type makes more sense."

The check constraint is renamed in lockstep so the constraint name
matches its column.

Data is preserved — this is a column rename, not a drop+add. The
acceptable values (`coded`, `ai`, `build_benchmark`) are unchanged.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a04eb2dc1c01"
down_revision: Union[str, None] = "a28735a085a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the old check constraint before renaming the column it referenced.
    op.drop_constraint(
        "ck_fetcher_runs_kind",
        "fetcher_runs",
        schema="data_capture",
        type_="check",
    )
    # Rename the column.
    op.alter_column(
        "fetcher_runs",
        "kind",
        new_column_name="fetcher_type",
        schema="data_capture",
    )
    # Re-create the check constraint with the new name + column reference.
    op.create_check_constraint(
        "ck_fetcher_runs_fetcher_type",
        "fetcher_runs",
        "fetcher_type IN ('coded', 'ai', 'build_benchmark')",
        schema="data_capture",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_fetcher_runs_fetcher_type",
        "fetcher_runs",
        schema="data_capture",
        type_="check",
    )
    op.alter_column(
        "fetcher_runs",
        "fetcher_type",
        new_column_name="kind",
        schema="data_capture",
    )
    op.create_check_constraint(
        "ck_fetcher_runs_kind",
        "fetcher_runs",
        "kind IN ('coded', 'ai', 'build_benchmark')",
        schema="data_capture",
    )

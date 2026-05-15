"""Add UNIQUE(super_id) to canonical_property_snapshots.

Revision ID: b75647262ca4
Revises: a04eb2dc1c01
Create Date: 2026-05-15

Chunk 8 of the V2 SuperID implementation. The V2 gate-promote primitive
(POST /fetchers/promote-to-canonical) writes one canonical snapshot row
per gate-passing SuperID. That makes `canonical_property_snapshots` a
SuperID-consuming datastore, and per docs/superid_principles.md section 4
each SuperID-consuming datastore must enforce single-use locally so a
second promote of the same SuperID is rejected rather than silently
duplicating a "canonical" answer.

PostgreSQL treats multiple NULLs as distinct in UNIQUE constraints by
default. Existing V1 rows that wrote canonical_property_snapshots may
have NULL super_id values; those continue to coexist after the
constraint is added.

Defensive duplicate check: if any non-NULL super_id appears on more than
one row, the migration raises a clear error before the constraint
creation would fail with an opaque one. Resolve the duplicates manually
before re-running.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b75647262ca4"
down_revision: Union[str, None] = "a04eb2dc1c01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    duplicate_count = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM (
                SELECT super_id
                FROM data_capture.canonical_property_snapshots
                WHERE super_id IS NOT NULL
                GROUP BY super_id
                HAVING COUNT(*) > 1
            ) AS dupes
            """
        )
    ).scalar()
    if duplicate_count and duplicate_count > 0:
        raise RuntimeError(
            f"Cannot add UNIQUE(super_id) to "
            f"data_capture.canonical_property_snapshots: {duplicate_count} "
            "super_id value(s) appear on more than one row. Resolve the "
            "duplicates manually (typically: keep the latest, archive the "
            "others) and re-run."
        )

    op.create_unique_constraint(
        "uq_canonical_property_snapshots_super_id",
        "canonical_property_snapshots",
        ["super_id"],
        schema="data_capture",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_canonical_property_snapshots_super_id",
        "canonical_property_snapshots",
        schema="data_capture",
        type_="unique",
    )

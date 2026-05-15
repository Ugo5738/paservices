"""Add UNIQUE(super_id) to fetcher_runs.

Revision ID: 961cbac71cd5
Revises: k3c8d6e1f4g5
Create Date: 2026-05-15

Chunk 4 of the V2 SuperID implementation. Implements the per-service
single-use check at the schema level for the V2 fetcher audit table
(see docs/superid_principles.md section 4: "Each service receives a
SuperID, it checks its own datastore. If the SuperID is already present
in that datastore, the service rejects the call.").

PostgreSQL UNIQUE allows multiple NULLs by default (NULL != NULL for
constraint purposes), so existing rows where super_id IS NULL continue
to coexist. Backfilling those NULLs and tightening the column to NOT
NULL is deferred to a later chunk along with the broader fetcher_runs
schema rework (chunk 5 — drop parent_run_id, attempt_number, status
lifecycle).

If the migration finds any pre-existing duplicate non-NULL super_ids,
it raises a clear error before creating the constraint so the operator
can resolve the duplicates by hand. Pre-existing duplicates indicate
that the same SuperID was used twice by this service under the old
non-enforcing schema; correct resolution is application-specific
(typically: keep the latest, archive the older rows).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "961cbac71cd5"
down_revision: Union[str, None] = "k3c8d6e1f4g5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Defensive check: surface any pre-existing duplicate super_ids before
    # the constraint creation would fail with an opaque message.
    bind = op.get_bind()
    duplicate_count = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM (
                SELECT super_id
                FROM data_capture.fetcher_runs
                WHERE super_id IS NOT NULL
                GROUP BY super_id
                HAVING COUNT(*) > 1
            ) AS dupes
            """
        )
    ).scalar()
    if duplicate_count and duplicate_count > 0:
        raise RuntimeError(
            f"Cannot add UNIQUE(super_id) to data_capture.fetcher_runs: "
            f"{duplicate_count} super_id value(s) appear on more than one "
            "row. Each service must use each SuperID at most once "
            "(docs/superid_principles.md section 4). Resolve the duplicates "
            "manually (typically: keep the latest, archive the others) and "
            "then re-run this migration."
        )

    op.create_unique_constraint(
        "uq_fetcher_runs_super_id",
        "fetcher_runs",
        ["super_id"],
        schema="data_capture",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_fetcher_runs_super_id",
        "fetcher_runs",
        schema="data_capture",
        type_="unique",
    )

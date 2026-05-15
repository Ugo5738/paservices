"""Drop fetcher_runs lifecycle columns: parent_run_id, attempt_number, status.

Revision ID: a28735a085a7
Revises: 961cbac71cd5
Create Date: 2026-05-15

Chunk 5 of the V2 SuperID implementation. The previous V2 fetcher audit
table carried a draft / final / superseded / failed status lifecycle that
was mutated via UPDATE (most notably by /ai-fetchers/promote-winner) to
mark one attempt as the winner among a parent_run_id-grouped set of
draft siblings. The principles forbid all of this:

  - status mutation violates the "no UPDATE on rows expressing run state"
    hygiene the data_capture_v2 architecture commits to
    (docs/data_capture_v2_architecture.md section 2);
  - parent_run_id is a structural relationship between SuperIDs that
    principles require to live in link records, not as a column on the
    audit table (docs/superid_principles.md section 5);
  - attempt_number encodes ordering / supersession that the principles
    require to live in link record metadata (docs/superid_principles.md
    section 9, "Mistake: encoding ordering or sequence in a field on the
    SuperID").

Under chunk 5, iteration / supersession / fallback chains live entirely
in the SuperID Metadata store (activity records + link records). Every
fetcher_runs row is therefore a single-shot, immutable record of one
service's use of one SuperID. Success / failure is signalled at insert
time by `error_message IS NULL` — a derived predicate, never a mutated
field.

This migration drops:

  - column `parent_run_id` (and its FK + index)
  - column `attempt_number`
  - column `status` (and its CHECK + composite index)

It does NOT modify any other column. The UNIQUE(super_id) added in chunk
4 (migration 961cbac71cd5) remains in place.

Reversibility: down() re-creates the columns but cannot reconstruct the
data they contained. Existing rows lose status / parent_run_id /
attempt_number after upgrade and get NULL / default values on downgrade.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a28735a085a7"
down_revision: Union[str, None] = "961cbac71cd5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the composite (status, started_at) index that referenced status.
    op.drop_index(
        "ix_fetcher_runs_status_started",
        table_name="fetcher_runs",
        schema="data_capture",
    )
    # Drop the status check constraint that whitelisted the four enum values.
    op.drop_constraint(
        "ck_fetcher_runs_status",
        "fetcher_runs",
        schema="data_capture",
        type_="check",
    )
    # Drop the parent_run_id index + foreign key.
    op.drop_index(
        "ix_fetcher_runs_parent_run_id",
        table_name="fetcher_runs",
        schema="data_capture",
    )
    op.drop_constraint(
        "fk_fetcher_runs_parent_run_id",
        "fetcher_runs",
        schema="data_capture",
        type_="foreignkey",
    )

    # Drop the three columns.
    op.drop_column("fetcher_runs", "parent_run_id", schema="data_capture")
    op.drop_column("fetcher_runs", "attempt_number", schema="data_capture")
    op.drop_column("fetcher_runs", "status", schema="data_capture")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "fetcher_runs",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="draft",
        ),
        schema="data_capture",
    )
    op.add_column(
        "fetcher_runs",
        sa.Column(
            "attempt_number",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        schema="data_capture",
    )
    op.add_column(
        "fetcher_runs",
        sa.Column(
            "parent_run_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        schema="data_capture",
    )
    op.create_foreign_key(
        "fk_fetcher_runs_parent_run_id",
        "fetcher_runs",
        "fetcher_runs",
        ["parent_run_id"],
        ["id"],
        source_schema="data_capture",
        referent_schema="data_capture",
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_fetcher_runs_parent_run_id",
        "fetcher_runs",
        ["parent_run_id"],
        schema="data_capture",
    )
    op.create_check_constraint(
        "ck_fetcher_runs_status",
        "fetcher_runs",
        "status IN ('draft', 'final', 'superseded', 'failed')",
        schema="data_capture",
    )
    op.create_index(
        "ix_fetcher_runs_status_started",
        "fetcher_runs",
        ["status", "started_at"],
        schema="data_capture",
    )

"""Add super_id to build_flags so Fetcher Build can run under the originating capture's SuperID.

Revision ID: l4d9e7f2g5h6
Revises: k3c8d6e1f4g5
Create Date: 2026-05-21

Why
---
`docs/superid_data_capture_design.md` §3.1 and `docs/data_capture_v2_id_and_data_flow.md`
Step 8 both prescribe: *the Fetcher Build workflow uses the same SuperID as the
originating Data Capture run (`S-001`). The asynchronous trigger does not require a
new SuperID; Fetcher Build is simply another consumer of `S-001`.*

But `build_flags` had no column to thread that originating SuperID through —
so when chunk 9 made `Auth + Super ID Sub-Workflow` stop minting and start
*requiring* a SuperID, the build pipeline silently broke. The Trigger workflow
fired on every flag insert, called Auth + Super ID with no super_id input, and
errored immediately at the second node (`super_id is required and must be a
valid UUID. The Auth + Super ID Sub-Workflow no longer mints SuperIDs;
SuperIDs must be minted at scope entry and passed through`).

What this migration does
------------------------
Adds `super_id UUID NULL` to `data_capture.build_flags`. Nullable so legacy
rows aren't broken at the DB level (those rows will be retired separately —
they were architecturally orphaned anyway, no live capture flow to attach to).
New flags written by `WF DC 1 Main` will carry the orchestrator's super_id;
the Motie Build Trigger workflow reads it from `Pick Flag` and passes it to
Auth + Super ID, restoring the documented "build under S-001" behaviour.

Idempotent: uses IF NOT EXISTS so re-running is safe.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "l4d9e7f2g5h6"
down_revision: Union[str, None] = "k3c8d6e1f4g5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE data_capture.build_flags
        ADD COLUMN IF NOT EXISTS super_id UUID NULL;
        """
    )
    # Index for occasional reverse-lookups (find the build associated with a
    # given capture's SuperID). Not strictly required but cheap.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_build_flags_super_id
            ON data_capture.build_flags (super_id);
        """
    )

    # Update the notify_build_flag_created trigger function from migration
    # g8e4d2f5h6c7 to include super_id in the NOTIFY payload. The Trigger
    # workflow's `Auth + Super ID` node runs BEFORE `Pick Flag`, so it must
    # read the super_id from the LISTEN payload directly (the picked-flag
    # row isn't available at that point in the workflow).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION data_capture.notify_build_flag_created()
        RETURNS TRIGGER AS $$
        BEGIN
          IF NEW.status = 'pending' THEN
            PERFORM pg_notify(
              'build_flag_created',
              json_build_object(
                'id', NEW.id,
                'url', NEW.url,
                'domain', NEW.domain,
                'super_id', NEW.super_id,
                'created_at', NEW.created_at
              )::text
            );
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    # Restore the previous payload shape (no super_id) before dropping the column.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION data_capture.notify_build_flag_created()
        RETURNS TRIGGER AS $$
        BEGIN
          IF NEW.status = 'pending' THEN
            PERFORM pg_notify(
              'build_flag_created',
              json_build_object(
                'id', NEW.id,
                'url', NEW.url,
                'domain', NEW.domain,
                'created_at', NEW.created_at
              )::text
            );
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute("DROP INDEX IF EXISTS data_capture.ix_build_flags_super_id;")
    op.execute(
        """
        ALTER TABLE data_capture.build_flags
        DROP COLUMN IF EXISTS super_id;
        """
    )

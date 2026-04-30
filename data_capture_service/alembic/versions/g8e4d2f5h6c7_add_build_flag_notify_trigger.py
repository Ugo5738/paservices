"""Add PostgreSQL NOTIFY trigger for new pending build_flags.

Revision ID: g8e4d2f5h6c7
Revises: f3d9c7a2b8e1
Create Date: 2026-04-30

Per the V2 spec, WF C is meant to be a database-trigger-driven workflow
("Db flag (to build a Fetcher) exists = Trigger Workflow 3"), not a cron poll.

This migration adds a Postgres trigger function and trigger that emits a
NOTIFY on the 'build_flag_created' channel whenever a build_flag row is
inserted with status='pending'. n8n's Postgres Trigger node listens on this
channel and fires WF C immediately, eliminating the up-to-5-min cron poll
latency.

Channel name: build_flag_created
Payload: JSON with {id, url, domain}
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g8e4d2f5h6c7"
down_revision: Union[str, None] = "f3d9c7a2b8e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_build_flag_created ON data_capture.build_flags;
        CREATE TRIGGER trg_build_flag_created
        AFTER INSERT ON data_capture.build_flags
        FOR EACH ROW
        EXECUTE FUNCTION data_capture.notify_build_flag_created();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_build_flag_created ON data_capture.build_flags;")
    op.execute("DROP FUNCTION IF EXISTS data_capture.notify_build_flag_created();")

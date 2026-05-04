"""Seed parser_name='rightmove' onto the Rightmove proxy fetcher's metadata.

Revision ID: k3c8d6e1f4g5
Revises: j2b7c5d0e3f4
Create Date: 2026-05-04

The /fetchers/validate endpoint resolves a parser by looking at the
fetcher row's metadata_json["parser_name"] when no explicit adapter_name
is given by the caller. This migration adds that hint to the existing
Rightmove proxy fetcher row so WF1's Validate call (which only knows the
fetcher_id, not which parser to use) automatically picks the new
"rightmove" parser registered in services.parser_registry.

Idempotent — uses jsonb_set with create_missing=true and only touches
rows whose source_type='proxy' AND metadata_json doesn't already carry
parser_name. Safe on environments that don't yet have a rightmove fetcher
registered (matches zero rows, no-op).
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k3c8d6e1f4g5"
down_revision: Union[str, None] = "j2b7c5d0e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE data_capture.fetchers
        SET metadata_json = jsonb_set(
            COALESCE(metadata_json, '{}'::jsonb),
            '{parser_name}',
            '"rightmove"'::jsonb,
            true
        )
        WHERE domain = 'rightmove.co.uk'
          AND source_type = 'proxy'
          AND (
              metadata_json IS NULL
              OR NOT metadata_json ? 'parser_name'
              OR metadata_json->>'parser_name' IS DISTINCT FROM 'rightmove'
          );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE data_capture.fetchers
        SET metadata_json = metadata_json - 'parser_name'
        WHERE domain = 'rightmove.co.uk'
          AND source_type = 'proxy'
          AND metadata_json ? 'parser_name';
        """
    )

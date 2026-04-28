"""Seed Rightmove as a proxy fetcher in the V2 registry.

Revision ID: e7c2b1f9a4d5
Revises: d5a4e8f1c2b3
Create Date: 2026-04-28

Inserts one row into data_capture.fetchers so /fetchers/lookup with a
rightmove.co.uk URL returns the data_capture_rightmove_service proxy. No
changes to the rightmove service itself.
"""

import json
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7c2b1f9a4d5"
down_revision: Union[str, None] = "d5a4e8f1c2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PARAM_SCHEMA = {"url_param": "property_url", "url_location": "body"}
METADATA = {"description": "Proxies to data_capture_rightmove_service /fetch/combined"}


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO data_capture.fetchers (
            id, domain, source_type, motie_project_uuid, route_path, http_method,
            param_schema, api_url_override, is_metered, status, metadata_json
        )
        SELECT
            gen_random_uuid(),
            'rightmove.co.uk',
            'proxy',
            NULL,
            '/api/v1/properties/fetch/combined',
            'POST',
            '{json.dumps(PARAM_SCHEMA)}'::jsonb,
            'https://data-capture-rightmove.supersami.com',
            false,
            'active',
            '{json.dumps(METADATA)}'::jsonb
        WHERE NOT EXISTS (
            SELECT 1 FROM data_capture.fetchers
            WHERE domain = 'rightmove.co.uk' AND source_type = 'proxy'
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM data_capture.fetchers
        WHERE domain = 'rightmove.co.uk' AND source_type = 'proxy';
        """
    )

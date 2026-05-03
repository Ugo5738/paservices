"""Replace full unique constraint on motie_scraper_projects.domain with a
partial unique index (one ACTIVE project per domain).

Revision ID: j2b7c5d0e3f4
Revises: i1a6b4c9d2e3
Create Date: 2026-05-03

Preserves Rolf's "one project per domain" rule at the schema level (only
one is_active=true row per domain is allowed) while permitting historical
inactive rows to coexist. Operational benefit: when a Motie session
becomes orphaned, an operator can mark the project inactive
(POST /fetcher-builds/motie/projects/{uuid}/deactivate) and the next
build creates a fresh project for the domain — without dropping the
schema-level guarantee that production sees only one active project per
domain at a time.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "j2b7c5d0e3f4"
down_revision: Union[str, None] = "i1a6b4c9d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop the full unique constraint on domain.
    op.execute(
        """
        ALTER TABLE data_capture.motie_scraper_projects
        DROP CONSTRAINT IF EXISTS uq_motie_scraper_projects_domain;
        """
    )
    # 2. Add a partial unique index that only enforces uniqueness across
    #    is_active=true rows. Inactive rows keep their domain values for
    #    audit but no longer participate in uniqueness — so once a stuck
    #    project is deactivated, a fresh active project can be created.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_motie_scraper_projects_active_domain
        ON data_capture.motie_scraper_projects (domain)
        WHERE is_active = true;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS data_capture.uq_motie_scraper_projects_active_domain;
        """
    )
    # Restore full uniqueness. If duplicate-domain rows exist (from inactive
    # historicals), this will fail; deactivate-then-keep-only-one would be
    # required first. We don't auto-clean to preserve audit history.
    op.execute(
        """
        ALTER TABLE data_capture.motie_scraper_projects
        ADD CONSTRAINT uq_motie_scraper_projects_domain UNIQUE (domain);
        """
    )

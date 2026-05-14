"""add SuperID metadata store: activity_records, link_records

Revision ID: 674e901b2bd1
Revises: f6ea09fd8d27
Create Date: 2026-05-14

Chunk 2 of the V2 SuperID implementation. Adds the SuperID Metadata store
(see docs/superid_principles.md §5, docs/superid_data_capture_design.md §3.2)
on the existing super_id_service database (per decision 2026-05-14: extend the
service, do not create a new one).

Tables:
  - activity_records: one row per use of a SuperID by a service or workflow.
  - link_records:     one row per claimed relationship between two SuperIDs.

Both are append-only and immutable. Immutability is enforced at the database
level by a BEFORE UPDATE OR DELETE trigger that raises an exception, in
addition to the application-layer contract.

No uniqueness constraints beyond the primary keys: idempotent insertion is
acceptable but not required (principles §5; data_capture_design §3.2
verification #5). Interpretation happens at read time.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '674e901b2bd1'
down_revision: Union[str, None] = 'f6ea09fd8d27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # activity_records: one row per use of a SuperID by a service or workflow.
    op.create_table(
        'activity_records',
        sa.Column(
            'activity_id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('uuid_generate_v4()'),
        ),
        sa.Column('super_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('used_by', sa.String(length=128), nullable=False),
        sa.Column(
            'used_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column(
            'activity_metadata',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index(
        'idx_activity_records_super_id',
        'activity_records',
        ['super_id'],
    )
    op.create_index(
        'idx_activity_records_used_at',
        'activity_records',
        ['used_at'],
    )

    # link_records: one row per claimed relationship between two SuperIDs.
    # super_id_a / super_id_b order is NOT semantically meaningful.
    op.create_table(
        'link_records',
        sa.Column(
            'link_id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('uuid_generate_v4()'),
        ),
        sa.Column('super_id_a', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('super_id_b', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column(
            'link_metadata',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    # Index BOTH columns separately so queries from either side are fast.
    op.create_index(
        'idx_link_records_super_id_a',
        'link_records',
        ['super_id_a'],
    )
    op.create_index(
        'idx_link_records_super_id_b',
        'link_records',
        ['super_id_b'],
    )

    # Immutability trigger: BEFORE UPDATE OR DELETE on either table → raise.
    # Belt-and-braces with the application-layer contract.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_mutation_on_superid_metadata_store()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'SuperID Metadata store records are immutable: % on % is forbidden (see docs/superid_principles.md section 3)', TG_OP, TG_TABLE_NAME
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER activity_records_immutable
        BEFORE UPDATE OR DELETE ON activity_records
        FOR EACH ROW EXECUTE FUNCTION prevent_mutation_on_superid_metadata_store();
        """
    )
    op.execute(
        """
        CREATE TRIGGER link_records_immutable
        BEFORE UPDATE OR DELETE ON link_records
        FOR EACH ROW EXECUTE FUNCTION prevent_mutation_on_superid_metadata_store();
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS link_records_immutable ON link_records;")
    op.execute("DROP TRIGGER IF EXISTS activity_records_immutable ON activity_records;")
    op.execute("DROP FUNCTION IF EXISTS prevent_mutation_on_superid_metadata_store();")
    op.drop_index('idx_link_records_super_id_b', table_name='link_records')
    op.drop_index('idx_link_records_super_id_a', table_name='link_records')
    op.drop_table('link_records')
    op.drop_index('idx_activity_records_used_at', table_name='activity_records')
    op.drop_index('idx_activity_records_super_id', table_name='activity_records')
    op.drop_table('activity_records')

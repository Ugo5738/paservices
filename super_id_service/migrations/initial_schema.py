"""Initial schema for Super ID Service

Revision ID: 0001_initial_schema
Create Date: 2025-06-11 11:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create the initial schema by executing the SQL directly
    # This is more maintainable than recreating the entire schema in SQLAlchemy syntax
    
    # First create the extension if it doesn't exist
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # Create super_ids table
    op.create_table(
        'super_ids',
        sa.Column('id', UUID(), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('tenant_id', UUID(), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', UUID(), nullable=True),
        sa.Column('external_ref', sa.String(255), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('created_by', UUID(), nullable=False),
        sa.Column('metadata', JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE')),
    )
    
    # Create indexes on commonly queried columns
    op.create_index('idx_super_ids_tenant_id', 'super_ids', ['tenant_id'])
    op.create_index('idx_super_ids_entity_type', 'super_ids', ['entity_type'])
    op.create_index('idx_super_ids_created_by', 'super_ids', ['created_by'])
    op.create_index('idx_super_ids_created_at', 'super_ids', ['created_at'])
    
    # Create audit logs table
    op.create_table(
        'super_id_audit_logs',
        sa.Column('id', UUID(), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('super_id', UUID(), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('performed_by', UUID(), nullable=False),
        sa.Column('performed_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('details', JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(['super_id'], ['super_ids.id']),
    )
    
    # Create indexes for audit logs
    op.create_index('idx_super_id_audit_logs_super_id', 'super_id_audit_logs', ['super_id'])
    op.create_index('idx_super_id_audit_logs_performed_at', 'super_id_audit_logs', ['performed_at'])
    
    # Create function for audit logging
    op.execute('''
        CREATE OR REPLACE FUNCTION log_super_id_changes()
        RETURNS TRIGGER AS $$
        BEGIN
            IF (TG_OP = 'UPDATE') THEN
                INSERT INTO super_id_audit_logs (super_id, action, performed_by, details)
                VALUES (
                    NEW.id,
                    'UPDATE',
                    NEW.created_by,
                    jsonb_build_object(
                        'old_value', row_to_json(OLD)::jsonb,
                        'new_value', row_to_json(NEW)::jsonb
                    )
                );
            ELSIF (TG_OP = 'DELETE') THEN
                INSERT INTO super_id_audit_logs (super_id, action, performed_by, details)
                VALUES (
                    OLD.id,
                    'DELETE',
                    OLD.created_by,
                    jsonb_build_object('old_value', row_to_json(OLD)::jsonb)
                );
            END IF;
            
            RETURN NULL; -- result is ignored since this is an AFTER trigger
        END;
        $$ LANGUAGE plpgsql;
    ''')
    
    # Create trigger for audit logging
    op.execute('''
        CREATE TRIGGER super_id_audit_trigger
        AFTER UPDATE OR DELETE ON super_ids
        FOR EACH ROW EXECUTE FUNCTION log_super_id_changes();
    ''')
    
    # Create statistics view
    op.execute('''
        CREATE OR REPLACE VIEW super_id_stats AS
        SELECT 
            tenant_id,
            entity_type,
            COUNT(*) AS total_ids,
            COUNT(*) FILTER (WHERE is_active = TRUE) AS active_ids,
            MIN(created_at) AS first_created_at,
            MAX(created_at) AS last_created_at
        FROM super_ids
        GROUP BY tenant_id, entity_type;
    ''')
    
    # Add comments for documentation
    op.execute("COMMENT ON TABLE super_ids IS 'Stores all generated Super IDs for tracking workflows across services'")
    op.execute("COMMENT ON TABLE super_id_audit_logs IS 'Audit trail for all changes to Super IDs'")
    op.execute("COMMENT ON VIEW super_id_stats IS 'Statistics on Super ID generation by tenant and entity type'")


def downgrade():
    # Drop objects in reverse order to avoid dependency issues
    op.execute('DROP VIEW IF EXISTS super_id_stats')
    op.execute('DROP TRIGGER IF EXISTS super_id_audit_trigger ON super_ids')
    op.execute('DROP FUNCTION IF EXISTS log_super_id_changes()')
    op.drop_table('super_id_audit_logs')
    op.drop_table('super_ids')
    # We don't drop the uuid-ossp extension as it might be used by other schemas

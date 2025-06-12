-- Super ID Service Database Schema
-- This schema defines the tables needed for the Super ID service
-- Note: Super ID service uses its own dedicated database for proper service isolation

-- Create extension for UUID generation if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table for storing generated Super IDs
CREATE TABLE IF NOT EXISTS super_ids (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID,
    external_ref VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID NOT NULL,
    metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE
);

-- Add indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_super_ids_tenant_id ON super_ids(tenant_id);
CREATE INDEX IF NOT EXISTS idx_super_ids_entity_type ON super_ids(entity_type);
CREATE INDEX IF NOT EXISTS idx_super_ids_created_by ON super_ids(created_by);
CREATE INDEX IF NOT EXISTS idx_super_ids_created_at ON super_ids(created_at);

-- Table for audit logging
CREATE TABLE IF NOT EXISTS super_id_audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    super_id UUID NOT NULL REFERENCES super_ids(id),
    action VARCHAR(50) NOT NULL,
    performed_by UUID NOT NULL,
    performed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    details JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_super_id_audit_logs_super_id ON super_id_audit_logs(super_id);
CREATE INDEX IF NOT EXISTS idx_super_id_audit_logs_performed_at ON super_id_audit_logs(performed_at);

-- Create a function to automatically log changes to super_ids
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

-- Create trigger for audit logging
CREATE TRIGGER super_id_audit_trigger
AFTER UPDATE OR DELETE ON super_ids
FOR EACH ROW EXECUTE FUNCTION log_super_id_changes();

-- Create statistics view
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

-- Add comments for documentation
COMMENT ON TABLE super_ids IS 'Stores all generated Super IDs for tracking workflows across services';
COMMENT ON TABLE super_id_audit_logs IS 'Audit trail for all changes to Super IDs';
COMMENT ON VIEW super_id_stats IS 'Statistics on Super ID generation by tenant and entity type';

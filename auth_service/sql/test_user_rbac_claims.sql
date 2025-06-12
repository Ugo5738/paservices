-- Test script for get_user_rbac_claims function
-- First, ensure the function exists or create it
\i get_user_rbac_claims.sql

-- Create a temporary table for test data
BEGIN;

-- Sample data for testing
-- 1. Create test roles
DO $$ 
DECLARE
    role1_id UUID := gen_random_uuid();
    role2_id UUID := gen_random_uuid();
    perm1_id UUID := gen_random_uuid();
    perm2_id UUID := gen_random_uuid();
    perm3_id UUID := gen_random_uuid();
    test_user_id UUID := '00000000-0000-0000-0000-000000000001';
BEGIN
    -- Insert test roles
    INSERT INTO auth_service_data.roles (id, name, description) VALUES 
    (role1_id, 'test_admin', 'Test Admin Role'),
    (role2_id, 'test_user', 'Test User Role');
    
    -- Insert test permissions
    INSERT INTO auth_service_data.permissions (id, name, description) VALUES
    (perm1_id, 'users:read', 'Can read user data'),
    (perm2_id, 'users:write', 'Can write user data'),
    (perm3_id, 'settings:admin', 'Can manage admin settings');
    
    -- Assign permissions to roles
    INSERT INTO auth_service_data.role_permissions (role_id, permission_id) VALUES
    (role1_id, perm1_id), -- admin can read users
    (role1_id, perm2_id), -- admin can write users
    (role1_id, perm3_id), -- admin can manage settings
    (role2_id, perm1_id); -- regular user can only read users
    
    -- Assign roles to test user
    INSERT INTO auth_service_data.user_roles (user_id, role_id) VALUES
    (test_user_id, role1_id), -- user has admin role
    (test_user_id, role2_id); -- user also has regular user role
    
    -- Test the function
    RAISE NOTICE 'Test User RBAC Claims: %', auth_service_data.get_user_rbac_claims(test_user_id);
    
    -- Expected result should be something like:
    -- {"roles": ["test_admin", "test_user"], "permissions": ["users:read", "users:write", "settings:admin"]}
    
    -- Test with a user that has no roles
    RAISE NOTICE 'Empty User RBAC Claims: %', auth_service_data.get_user_rbac_claims('00000000-0000-0000-0000-000000000002');
    -- Expected result: {"roles": [], "permissions": []}
    
END $$;

-- Rollback the test data
ROLLBACK;

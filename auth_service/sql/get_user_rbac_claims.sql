-- Function: get_user_rbac_claims(user_id UUID)
-- Description: This function queries the user roles and associated permissions
-- to generate a JWT claims object containing roles and permissions for a given user.
-- Returns: JSON with format {"roles": ["role_name_1"], "permissions": ["perm_slug_1"]}

CREATE OR REPLACE FUNCTION auth_service_data.get_user_rbac_claims(p_user_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSONB;
    roles_array TEXT[] := '{}';
    permissions_array TEXT[] := '{}';
BEGIN
    -- Get all roles assigned to the user
    SELECT ARRAY_AGG(DISTINCT r.name)
    INTO roles_array
    FROM auth_service_data.user_roles ur
    JOIN auth_service_data.roles r ON ur.role_id = r.id
    WHERE ur.user_id = p_user_id;
    
    -- Get all permissions for those roles
    SELECT ARRAY_AGG(DISTINCT p.name)
    INTO permissions_array
    FROM auth_service_data.user_roles ur
    JOIN auth_service_data.role_permissions rp ON ur.role_id = rp.role_id
    JOIN auth_service_data.permissions p ON rp.permission_id = p.id
    WHERE ur.user_id = p_user_id;
    
    -- Handle NULL arrays (user has no roles or permissions)
    IF roles_array IS NULL THEN
        roles_array := '{}';
    END IF;
    
    IF permissions_array IS NULL THEN
        permissions_array := '{}';
    END IF;
    
    -- Construct the result JSON
    result := jsonb_build_object(
        'roles', to_jsonb(roles_array),
        'permissions', to_jsonb(permissions_array)
    );
    
    RETURN result;
END;
$$;

# Supabase Custom Claims Setup

## Overview

This document describes how to configure Supabase to include custom RBAC (Role-Based Access Control) claims in JWT tokens. These claims are essential for implementing fine-grained authorization in your application.

## SQL Function Implementation

The core of the custom claims functionality is a PostgreSQL function named `get_user_rbac_claims` that queries the user's roles and associated permissions from our RBAC tables.

### Function Definition

```sql
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
```

## Function Purpose

This function serves to:

1. Query all roles assigned to a user from the `user_roles` table
2. Query all permissions associated with those roles from the `role_permissions` and `permissions` tables
3. Return a JSON object containing arrays of role names and permission names

The resulting JSON has this structure:

```json
{
  "roles": ["admin", "user"],
  "permissions": ["users:read", "users:write", "role:admin_manage"]
}
```

## Supabase JWT Configuration Steps

### 1. Create the SQL Function

Execute the SQL function definition in your Supabase database using the SQL editor.

### 2. Configure JWT Generation

To include custom claims in JWTs, you need to configure the JWT generation process in Supabase. This is done by updating the JWT template in your project settings.

1. Go to your Supabase dashboard
2. Navigate to Authentication > Settings
3. Find the JWT Template section
4. Update the template to include the custom claims

```json
{
  "role": "authenticated",
  "iss": "{{ .Issuer }}",
  "aud": "{{ .Audience }}",
  "sub": "{{ .Subject }}",
  "email": "{{ .Email }}",
  "phone": "{{ .Phone }}",
  "app_metadata": {
    "provider": "{{ .Provider }}",
    "providers": "{{ .Providers }}",
    "roles": "{{ (auth_service_data.get_user_rbac_claims(.Subject)).roles }}",
    "permissions": "{{ (auth_service_data.get_user_rbac_claims(.Subject)).permissions }}"
  },
  "user_metadata": {
    "{{ .UserMetadata }}"
  },
  "exp": "{{ .Expiry }}"
}
```

### 3. Set Function Permissions

Ensure the PostgreSQL function has the proper permissions:

```sql
GRANT EXECUTE ON FUNCTION auth_service_data.get_user_rbac_claims TO authenticated;
GRANT EXECUTE ON FUNCTION auth_service_data.get_user_rbac_claims TO service_role;
```

### 4. Create Schema and Tables (If Not Exists)

Make sure the auth_service_data schema and required tables exist:

```sql
CREATE SCHEMA IF NOT EXISTS auth_service_data;

CREATE TABLE IF NOT EXISTS auth_service_data.roles (
    id UUID PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth_service_data.permissions (
    id UUID PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth_service_data.role_permissions (
    role_id UUID REFERENCES auth_service_data.roles(id) ON DELETE CASCADE,
    permission_id UUID REFERENCES auth_service_data.permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS auth_service_data.user_roles (
    user_id UUID NOT NULL,
    role_id UUID REFERENCES auth_service_data.roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);
```

## Testing the Setup

To verify the custom claims are working correctly, follow these steps:

1. Create a test user in your Supabase auth system
2. Assign one or more roles to this user in the `user_roles` table
3. Generate a JWT token by logging in as this user
4. Decode the JWT token (e.g., using [jwt.io](https://jwt.io))
5. Verify that the `app_metadata` section contains the correct `roles` and `permissions` arrays

## Important Considerations

1. **Performance**: The function is called during JWT generation. Keep it efficient to avoid slow token generation.
2. **Security**: The function uses `SECURITY DEFINER` to run with elevated privileges. Ensure it's properly secured.
3. **Caching**: Consider implementing caching for frequently accessed roles and permissions.
4. **Updates**: When user roles change, the new permissions will only be reflected in newly issued tokens.
5. **Token Size**: Be mindful of the JWT token size if users can have many roles and permissions.

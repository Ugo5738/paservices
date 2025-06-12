# Admin User and RBAC Bootstrapping Guide

## Overview

This document explains how the initial admin user and RBAC (Role-Based Access Control) components are bootstrapped when the authentication service is first deployed. The process creates the necessary admin user, roles, permissions, and their relationships.

## Initial Admin User Creation

The system creates an initial admin user during the first startup, based on environment variables:

```bash
INITIAL_ADMIN_EMAIL=admin@example.com
INITIAL_ADMIN_PASSWORD=strong-password
```

## Bootstrapping Process

### 1. Service Startup

During service initialization, the application checks if the initial setup has been performed. This is typically executed as part of a FastAPI lifespan event or startup handler.

### 2. Admin User Creation

If no admin user exists, the system:

1. Creates a new user in Supabase using the provided admin email and password
2. Sets the appropriate admin metadata and claims in the user's profile
3. Creates a corresponding entry in the local profiles table

### 3. RBAC Components Initialization

The system also bootstraps the initial RBAC components:

#### Core Roles

- **admin**: Full system access
- **user**: Basic authenticated user access
- **service**: For machine-to-machine communication

#### Core Permissions

- **users:read**: View user information
- **users:write**: Create/update user information
- **roles:read**: View roles
- **roles:write**: Create/update roles
- **permissions:read**: View permissions
- **permissions:write**: Create/update permissions
- **role:admin_manage**: Special permission for admin operations

#### Initial Role-Permission Mappings

- **admin role**: All permissions
- **user role**: users:read (own profile only)
- **service role**: Configured based on the application's needs

## Implementation Details

The bootstrapping logic is typically implemented in a module like `bootstrap.py` or similar, which is called during application startup.

```python
async def bootstrap_admin_and_rbac(db, supabase_client, settings):
    # Check if bootstrapping has already been performed
    has_admin = await check_admin_exists(db, supabase_client)
    
    if not has_admin:
        # Create admin user in Supabase
        admin_user = await create_supabase_admin_user(
            supabase_client, 
            settings.INITIAL_ADMIN_EMAIL, 
            settings.INITIAL_ADMIN_PASSWORD
        )
        
        # Create admin profile locally
        await create_admin_profile(db, admin_user)
        
        # Create core roles
        role_ids = await create_core_roles(db)
        
        # Create core permissions
        permission_ids = await create_core_permissions(db)
        
        # Assign permissions to roles
        await assign_permissions_to_roles(db, role_ids, permission_ids)
        
        # Assign admin role to admin user
        await assign_admin_role_to_user(db, admin_user.id, role_ids['admin'])
        
        logger.info("Successfully bootstrapped admin user and RBAC components")
    else:
        logger.info("Bootstrapping skipped: Admin user already exists")
```

## Manual Bootstrapping

If you need to manually trigger the bootstrapping process (for example, during development or testing), you can execute:

```bash
# Inside the auth_service container
python -m auth_service.bootstrap
```

## Additional Admin Users

After the initial setup, additional admin users can be created through the admin API endpoints:

1. Create a new user through Supabase or the registration endpoint
2. Use the admin user role assignment endpoint to grant the admin role to the new user

```bash
POST /auth/admin/users/{user_id}/roles
Content-Type: application/json
Authorization: Bearer <admin_token>

{
  "roles": ["admin"]
}
```

## Resetting the Admin Password

If you need to reset the admin password:

1. Use Supabase's password reset functionality by sending a reset email
2. For development/testing environments, you can update the password directly in Supabase

## Security Considerations

- Change the initial admin password immediately after first login
- In production, use a strong, unique password for the initial admin user
- Consider implementing audit logging for admin actions
- Regularly review the list of users with admin privileges

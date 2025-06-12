# RBAC JWT Claims Configuration for Supabase

This directory contains SQL functions for implementing Role-Based Access Control (RBAC) in Supabase JWT tokens.

## Overview

The main function `get_user_rbac_claims` queries a user's assigned roles and their associated permissions to generate a JSON object that can be included in Supabase JWT tokens.

## Files

- `get_user_rbac_claims.sql`: The PostgreSQL function that generates RBAC claims
- `test_user_rbac_claims.sql`: Test script to verify the function with sample data

## Applying to Supabase

### Step 1: Apply the SQL Function

Connect to your Supabase PostgreSQL database using psql or the SQL editor in the Supabase dashboard and execute the `get_user_rbac_claims.sql` script.

```bash
# Using psql
psql -h <host> -d <database> -U <username> -f get_user_rbac_claims.sql

# Or copy-paste the function definition into the Supabase SQL editor
```

### Step 2: Configure Supabase JWT Claims

To include the RBAC claims in Supabase JWTs, you need to modify the JWT configuration in Supabase:

1. Edit the `supabase/config.toml` file in your Supabase project
2. Add or modify the JWT configuration to include custom claims:

```toml
[auth.jwt]
# Add custom claims from the database
auto_claims = [
  { claim = "roles", reference = "auth_service_data.get_user_rbac_claims(sub)::jsonb->>'roles'", cast = "jsonb" },
  { claim = "permissions", reference = "auth_service_data.get_user_rbac_claims(sub)::jsonb->>'permissions'", cast = "jsonb" }
]
```

3. Restart the Supabase Auth service to apply the changes

### Step 3: Test the Custom Claims

1. After configuring the JWT claims, log in with a user that has roles assigned
2. Examine the JWT token contents (you can use [jwt.io](https://jwt.io/)) to verify that roles and permissions are included

## Expected JWT Claims Format

```json
{
  "sub": "user-uuid",
  "roles": ["admin", "user"],
  "permissions": ["users:read", "users:write", "settings:admin"],
  ... (standard JWT claims)
}
```

## Troubleshooting

- If claims are not appearing in the JWT, verify the function is properly installed in the database
- Check that the function schema matches your Supabase configuration
- Test the function directly in SQL to ensure it returns the expected results
```

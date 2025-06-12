# JWT Claims Structure Documentation

This document describes the JWT (JSON Web Token) claims structure used in the Authentication Service for both human users (via Supabase) and machine-to-machine (M2M) application clients.

## 1. Human User JWT Claims (Supabase)

These tokens are issued by Supabase Auth (GoTrue) when a user logs in using email/password, magic link, or OAuth providers.

### Standard Claims

| Claim | Description | Example |
|-------|-------------|--------|
| `iss` | Issuer - URL of the Supabase project | `https://<project-ref>.supabase.co/auth/v1` |
| `sub` | Subject - User's UUID | `d9aa5120-a370-4305-9946-1fa5eb2a0845` |
| `aud` | Audience - Target service | `authenticated` |
| `exp` | Expiration time (Unix timestamp) | `1717027200` |
| `iat` | Issued at time (Unix timestamp) | `1716940800` |

### Custom Claims (in `app_metadata`)

| Claim | Description | Example |
|-------|-------------|--------|
| `app_metadata.provider` | Authentication provider | `email`, `google`, `github` |
| `app_metadata.providers` | List of linked providers | `["email", "google"]` |
| `app_metadata.roles` | User's assigned roles | `["admin", "user"]` |
| `app_metadata.permissions` | User's permissions (derived from roles) | `["users:read", "users:write", "role:admin_manage"]` |

### User Metadata (in `user_metadata`)

This section contains user-specific information that may have been collected during registration or updated later.

| Field | Description | Example |
|-------|-------------|--------|
| `user_metadata.name` | User's full name (optional) | `John Doe` |
| `user_metadata.avatar_url` | User's profile picture URL (optional) | `https://example.com/avatar.jpg` |

### Example Supabase JWT Payload

```json
{
  "aud": "authenticated",
  "exp": 1717027200,
  "iat": 1716940800,
  "iss": "https://your-project-ref.supabase.co/auth/v1",
  "sub": "d9aa5120-a370-4305-9946-1fa5eb2a0845",
  "email": "user@example.com",
  "phone": "",
  "app_metadata": {
    "provider": "email",
    "providers": ["email"],
    "roles": ["admin", "user"],
    "permissions": ["users:read", "users:write", "role:admin_manage"]
  },
  "user_metadata": {
    "name": "John Doe",
    "avatar_url": "https://example.com/avatar.jpg"
  },
  "role": "authenticated"
}
```

## 2. Machine-to-Machine (M2M) JWT Claims

These tokens are issued by the Authentication Service for application clients using the OAuth2 client credentials flow.

### Standard Claims

| Claim | Description | Example |
|-------|-------------|--------|
| `iss` | Issuer - Authentication Service | `auth-service` |
| `sub` | Subject - Client ID | `8a4d500f-b09c-4c88-8ab5-a9ee0d7e4c92` |
| `aud` | Audience - Target service | `api` |
| `exp` | Expiration time (Unix timestamp) | `1717027200` |
| `iat` | Issued at time (Unix timestamp) | `1716940800` |
| `jti` | JWT ID - Unique identifier for the token | `5f484300-c44b-47c9-9b28-3c71a6a2d1e5` |

### Custom Claims

| Claim | Description | Example |
|-------|-------------|--------|
| `client_name` | Name of the application client | `backend-service` |
| `client_type` | Type of client | `m2m` (machine-to-machine) |
| `roles` | Client's assigned roles | `["service", "data-processor"]` |
| `permissions` | Client's permissions (derived from roles) | `["users:read", "data:process"]` |

### Example M2M JWT Payload

```json
{
  "iss": "auth-service",
  "sub": "8a4d500f-b09c-4c88-8ab5-a9ee0d7e4c92",
  "aud": "api",
  "exp": 1717027200,
  "iat": 1716940800,
  "jti": "5f484300-c44b-47c9-9b28-3c71a6a2d1e5",
  "client_name": "backend-service",
  "client_type": "m2m",
  "roles": ["service", "data-processor"],
  "permissions": ["users:read", "data:process"]
}
```

## JWT Validation Rules

### Supabase JWT Validation

1. Verify token signature using Supabase public keys
2. Check `exp` to ensure token is not expired
3. Verify `iss` matches your Supabase project
4. Verify `aud` is "authenticated"

### M2M JWT Validation

1. Verify token signature using Authentication Service signing key
2. Check `exp` to ensure token is not expired
3. Verify `iss` is "auth-service"
4. Verify `aud` is appropriate for the receiving service
5. Validate that the client has the necessary permissions for the requested action

## Security Considerations

1. **Token Storage**: Store tokens securely, preferably in memory for SPA clients or in HTTP-only cookies for web applications
2. **Token Expiry**: Supabase access tokens expire by default after 1 hour, M2M tokens typically after 15 minutes
3. **Minimal Permissions**: Always assign the minimal required permissions to both users and application clients
4. **Refresh Tokens**: For Supabase users, refresh tokens can be used to obtain new access tokens without reauthentication
5. **Revocation**: M2M client access can be revoked by deactivating the client or resetting the client secret

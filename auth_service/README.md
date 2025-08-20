# Auth Service

## Overview

The Auth Service is a foundational microservice responsible for managing user and application client identities, authentication, and authorization within the PA Services platform. It integrates with Supabase for core user authentication functionalities while providing a FastAPI-based proxy layer for enhanced control and a robust Role-Based Access Control (RBAC) system.

For a broader understanding of how this service fits into the overall system, please see the main [System Workflow Guide](../../docs/system_workflow.md).

## Features

- **User Authentication & Registration**: Proxies Supabase for handling email/password and social logins.
- **M2M Client Authentication**: Implements OAuth 2.0 Client Credentials Grant for service-to-service communication.
- **Role-Based Access Control (RBAC)**: Manages roles and permissions for both human users and application clients.
- **JWT Management**: Enriches Supabase-issued JWTs with custom RBAC claims.

## Getting Started

The "paved path" for local development is to use the root `docker-compose.yml` file, which orchestrates all services. For detailed instructions, please refer to the main [Development Guide](../../docs/development.md).

### Database Migrations

This service uses Alembic to manage its own tables (profiles, roles, etc.). To apply migrations:

```bash
docker-compose exec auth_service alembic upgrade head
```

For a detailed guide on the migration workflow, especially its interaction with the Supabase auth schema, see MIGRATIONS.md.
## API Documentation

Once the service is running, API documentation is available at:

- [Swagger UI](http://localhost:8001/docs)
- [ReDoc](http://localhost:8001/redoc)


## Environment variables

All variables are prefixed with `AUTH_SERVICE_` to avoid cross-service collisions.

- `AUTH_SERVICE_ENVIRONMENT` — Environment name (development|staging|production).
- `AUTH_SERVICE_LOGGING_LEVEL` — Logging level (e.g., INFO, DEBUG).
- `AUTH_SERVICE_ROOT_PATH` — API root path (e.g., `/api/v1`).
- `AUTH_SERVICE_DATABASE_URL` — SQLAlchemy database URL for service tables.
- `AUTH_SERVICE_SUPABASE_URL` — Supabase Kong/Gateway base URL.
- `AUTH_SERVICE_SUPABASE_ANON_KEY` — Supabase anon key.
- `AUTH_SERVICE_SUPABASE_SERVICE_ROLE_KEY` — Supabase service role key.
- `AUTH_SERVICE_SUPABASE_EMAIL_CONFIRMATION_REQUIRED` — Require email confirmation (true/false).
- `AUTH_SERVICE_SUPABASE_AUTO_CONFIRM_NEW_USERS` — Auto-confirm on signup (true/false).
- `AUTH_SERVICE_M2M_JWT_SECRET_KEY` — Symmetric key for signing M2M tokens.
- `AUTH_SERVICE_M2M_JWT_ALGORITHM` — Signing algorithm (e.g., HS256).
- `AUTH_SERVICE_M2M_ACCESS_TOKEN_EXPIRE_MINUTES` — M2M token lifetime in minutes.
- `AUTH_SERVICE_INITIAL_ADMIN_EMAIL` — Seed admin email.
- `AUTH_SERVICE_INITIAL_ADMIN_PASSWORD` — Seed admin password.
- `AUTH_SERVICE_EMAIL_CONFIRMATION_REDIRECT_URL` — Frontend URL after email confirmation.
- `AUTH_SERVICE_PASSWORD_RESET_REDIRECT_URL` — Frontend URL after password reset.
- `AUTH_SERVICE_REDIS_URL` — Redis URL for caching/rate limits (if used).

See `.env.example` for a complete, up-to-date list.

## M2M token API (Client Credentials)

- Endpoint: `POST /api/v1/auth/token`
- Content-Type: `application/json`
- Request body:

```json
{
  "grant_type": "client_credentials",
  "client_id": "<your-service-client-id>",
  "client_secret": "<your-service-client-secret>"
}
```

- Successful response (shape focuses on `access_token`):

```json
{
  "access_token": "<jwt>",
  "token_type": "Bearer",
  "expires_in": 1800
}
```

### Example cURL

```bash
curl -s \
  -X POST "$AUTH_SERVICE_URL/api/v1/auth/token" \
  -H 'Content-Type: application/json' \
  -d '{
    "grant_type": "client_credentials",
    "client_id": "'$YOUR_SERVICE_M2M_CLIENT_ID'",
    "client_secret": "'$YOUR_SERVICE_M2M_CLIENT_SECRET'"
  }'
```

### Example Python (httpx)

```python
import httpx

async def get_m2m_token(base_url: str, client_id: str, client_secret: str) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{base_url}/api/v1/auth/token",
            json={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=20,
        )
        r.raise_for_status()
        return r.json()["access_token"]
```

## Integrating as an external service (FastAPI, Django, etc.)

Follow the three-step pattern used across this repository (see `data_capture_rightmove_service/scripts/script1/search_properties.py`):
Note: Ensure your client has the required permissions. To call Super ID Service, permission `super_id:generate` is required. See `../../docs/jwt_claims.md`.

1. Acquire an M2M token from Auth Service.
2. Request a `super_id` from Super ID Service (for workflow traceability).
3. Call the target internal API with:
   - `Authorization: Bearer <access_token>`
   - Provide `super_id` as required by the target service:
     - Many endpoints (e.g., Rightmove) expect `super_id` in the JSON body.
     - Some services may accept an `X-Super-ID` header.

Recommended environment variable naming for your service (prefix everything):

- `YOUR_SERVICE_AUTH_SERVICE_URL`
- `YOUR_SERVICE_SUPER_ID_SERVICE_URL`
- `YOUR_SERVICE_M2M_CLIENT_ID`
- `YOUR_SERVICE_M2M_CLIENT_SECRET`

See the central guide: `../../docs/integrating_external_services.md` and the conventions: `../../docs/service_env_var_conventions.md`.

## Related documentation

- `../../docs/jwt_claims.md` — JWT contents and custom claims.
- `../../docs/system_workflow.md` — End-to-end call sequence.
- `../../docs/integrating_external_services.md` — External integration cookbook.
- `../../docs/service_env_var_conventions.md` — Env var prefixing standard.


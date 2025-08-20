# Super ID Service

## Overview

The Super ID Service is a high-availability utility microservice responsible for generating and recording unique identifiers (UUIDs), referred to as `super_ids`. These identifiers are crucial for tracking and correlating multi-step workflows across the PA Services ecosystem.

For a broader understanding of how this service fits into the overall system, please see the main [System Workflow Guide](../../docs/system_workflow.md).

## Features

- **UUID Generation**: Generates version 4 UUIDs on demand.
- **Persistence**: Securely records every generated ID with metadata for auditability.
- **Secure Access**: Requires a valid M2M JWT with a `super_id:generate` scope.

## Getting Started

The "paved path" for local development is to use the root `docker-compose.yml` file. For detailed instructions, refer to the main [Development Guide](../../docs/development.md).

### Database Schema

The service requires a `generated_super_ids` table. This is created automatically by the Alembic migration job defined in the Kubernetes manifests during deployment. For local development, ensure you run the migrations after starting the service.

## API Endpoints

### Generate Super IDs

- **Endpoint**: `POST /super_ids`
- **Description**: Generates one or more new `super_ids`.
- **Authentication**: Requires a bearer token from the Auth Service.
- **Request Body**:
  ```json
  {
    "count": 1,
    "metadata": { "purpose": "Optional context for the workflow" }
  }
  ```

For detailed API documentation, access the service's `/docs` endpoint at [http://localhost:8002/docs](http://localhost:8002/docs) when running.

## Environment variables

All variables are prefixed with `SUPER_ID_SERVICE_` to avoid collisions.

- `SUPER_ID_SERVICE_ENVIRONMENT` — Environment name (development|staging|production).
- `SUPER_ID_SERVICE_LOGGING_LEVEL` — Logging level (e.g., INFO, DEBUG).
- `SUPER_ID_SERVICE_ROOT_PATH` — API root path (default `/api/v1`).
- `SUPER_ID_SERVICE_DATABASE_URL` — SQLAlchemy database URL for service tables.
- `SUPER_ID_SERVICE_SUPABASE_URL` — Supabase base URL.
- `SUPER_ID_SERVICE_SUPABASE_ANON_KEY` — Supabase anon key.
- `SUPER_ID_SERVICE_SUPABASE_SERVICE_ROLE_KEY` — Supabase service role key.
- `SUPER_ID_SERVICE_M2M_JWT_SECRET_KEY` — Symmetric key for validating Auth Service M2M JWTs.
- `SUPER_ID_SERVICE_AUTH_SERVICE_ISSUER` — Expected issuer for Auth Service tokens.
- `SUPER_ID_SERVICE_REDIS_URL` — Optional Redis URL for rate limiting.

See the service's `.env.example`/compose files for a complete list.

## Using the API

When running locally at `http://localhost:8002` with `ROOT_PATH=/api/v1`, the full endpoint is:

```
POST http://localhost:8002/api/v1/super_ids
```

### Example cURL

```bash
curl -s \
  -X POST "$SUPER_ID_SERVICE_URL/api/v1/super_ids" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "count": 1,
    "metadata": {"purpose": "search batch"}
  }'
```

### Example Python (httpx)

```python
import httpx

async def get_super_id(base_url: str, access_token: str, metadata: dict | None = None) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{base_url}/api/v1/super_ids",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"count": 1, "metadata": metadata or {}},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        # The API returns either {"super_id": uuid} or {"super_ids": [uuid, ...]}
        return data.get("super_id") or (data.get("super_ids") or [None])[0]
```

## Integrating as an external consumer

Use the standard three-step flow (example in `data_capture_rightmove_service/scripts/script1/search_properties.py`):

1. Get an M2M token from Auth Service (`/api/v1/auth/token`).
2. Request a `super_id` from Super ID Service (`/api/v1/super_ids`).
3. Call your target internal API with:
   - `Authorization: Bearer <token>`
   - Provide `super_id` as required by the target service:
     - Many endpoints (e.g., Rightmove) expect `super_id` in the JSON body.
     - Some services may accept an `X-Super-ID` header. Check that service's README.

See also: `../../docs/integrating_external_services.md`.

Recommended env vars for your service:

- `YOUR_SERVICE_AUTH_SERVICE_URL`
- `YOUR_SERVICE_SUPER_ID_SERVICE_URL`
- `YOUR_SERVICE_M2M_CLIENT_ID`
- `YOUR_SERVICE_M2M_CLIENT_SECRET`

See:

- `../../docs/integrating_external_services.md` — End-to-end external integration guide.
- `../../docs/service_env_var_conventions.md` — Prefixing conventions for env vars.

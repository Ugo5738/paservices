# Integrating External Services

This guide shows how any external microservice (FastAPI, Django, etc.), whether inside or outside this repo, should integrate with the PA Services platform.

## Prerequisites

- You have an internal client configured in the Auth Service with a `client_id` and `client_secret`.
- You follow the environment variable prefixing convention (see `service_env_var_conventions.md`).
- Your client has the required permissions (scopes). To call Super ID Service you must have: `super_id:generate`. See `jwt_claims.md`.

## Overview: 3-step pattern

1. Get an M2M token from Auth Service: `POST /api/v1/auth/token`.
2. Request a workflow ID (super_id) from Super ID Service: `POST /api/v1/super_ids`.
3. Call downstream internal APIs with:
   - `Authorization: Bearer <access_token>`
   - Provide `super_id` as required by each service:
     - Many endpoints (e.g., Rightmove) expect `super_id` in the JSON body.
     - Some services may accept an `X-Super-ID` header; check that service's README.

Reference implementation: `data_capture_rightmove_service/scripts/script1/search_properties.py`.

---

## Step 1 — Acquire M2M token (Client Credentials)

- Endpoint: `POST {AUTH_SERVICE_URL}/api/v1/auth/token`
- Body:

```json
{
  "grant_type": "client_credentials",
  "client_id": "<your-service-client-id>",
  "client_secret": "<your-service-client-secret>"
}
```

- Example cURL:

```bash
curl -s \
  -X POST "$YOUR_SERVICE_AUTH_SERVICE_URL/api/v1/auth/token" \
  -H 'Content-Type: application/json' \
  -d '{
    "grant_type": "client_credentials",
    "client_id": "'$YOUR_SERVICE_M2M_CLIENT_ID'",
    "client_secret": "'$YOUR_SERVICE_M2M_CLIENT_SECRET'"
  }'
```

- Example Python (httpx):

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

---

## Step 2 — Request a super_id

- Endpoint: `POST {SUPER_ID_SERVICE_URL}/api/v1/super_ids`
- Body (single ID):

```json
{
  "count": 1,
  "metadata": { "purpose": "optional context" }
}
```

- Example cURL:

```bash
curl -s \
  -X POST "$YOUR_SERVICE_SUPER_ID_SERVICE_URL/api/v1/super_ids" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "count": 1,
    "metadata": {"purpose": "search batch"}
  }'
```

- Example Python (httpx):

```python
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
        return data.get("super_id") or (data.get("super_ids") or [None])[0]
```

---

## Step 3 — Call downstream internal APIs

- Always include:
  - `Authorization: Bearer <access_token>`
  - The `super_id` in the JSON body when required. Rightmove endpoints accept `super_id` in the body. The `X-Super-ID` header is optional and may be ignored by some services.

- Optional: include a `callback` object if you want asynchronous status updates pushed to a webhook while the workflow executes. Example:

```json
{
  "super_id": "...",
  "property_url": "https://www.rightmove.co.uk/properties/123",
  "callback": {
    "url": "https://your-service/webhooks/rightmove",
    "headers": {
      "Authorization": "Bearer <token>"
    }
  }
}
```

When supplied, the Data Capture Rightmove Service writes progress snapshots to S3 and posts status payloads to the provided `callback.url`. The payload includes `status` (e.g., `started`, `in_progress`, `completed`, `failed`) and a `data_location` pointing to the latest snapshot JSON.

- Example cURL (Rightmove search):

```bash
curl -s \
  -X POST "$DATA_CAPTURE_RIGHTMOVE_SERVICE_URL/api/v1/properties/search/for-sale" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
        "location_identifier": "STATION^6956",
        "super_id": "'$SUPER_ID'"
      }'
# Optional: some services accept an X-Super-ID header as well
# -H "X-Super-ID: $SUPER_ID"
```

---

## Minimal Django example

For a runnable, ready-to-try project, see `../examples/django_minimal/README.md`.

- `.env` (example):

```ini
MY_SERVICE_AUTH_SERVICE_URL=http://localhost:8001
MY_SERVICE_SUPER_ID_SERVICE_URL=http://localhost:8002
MY_SERVICE_M2M_CLIENT_ID=your-client-id
MY_SERVICE_M2M_CLIENT_SECRET=your-client-secret
```

- `settings.py`:

```python
import os

AUTH_URL = os.getenv("MY_SERVICE_AUTH_SERVICE_URL", "http://localhost:8001")
SUPER_ID_URL = os.getenv("MY_SERVICE_SUPER_ID_SERVICE_URL", "http://localhost:8002")
M2M_ID = os.getenv("MY_SERVICE_M2M_CLIENT_ID")
M2M_SECRET = os.getenv("MY_SERVICE_M2M_CLIENT_SECRET")
```

- `views.py` (sync, using requests for brevity):

```python
import requests
from django.http import JsonResponse
from django.conf import settings

def start_workflow(request):
    # 1) Token
    r = requests.post(
        f"{settings.AUTH_URL}/api/v1/auth/token",
        json={
            "grant_type": "client_credentials",
            "client_id": settings.M2M_ID,
            "client_secret": settings.M2M_SECRET,
        },
        timeout=20,
    )
    r.raise_for_status()
    token = r.json()["access_token"]

    # 2) Super ID
    r = requests.post(
        f"{settings.SUPER_ID_URL}/api/v1/super_ids",
        headers={"Authorization": f"Bearer {token}"},
        json={"count": 1, "metadata": {"purpose": "demo"}},
        timeout=20,
    )
    r.raise_for_status()
    super_id = r.json().get("super_id")

    # 3) Use token + super_id (in JSON body, preferred) to call your downstream API(s).
    #    Some services may also accept an X-Super-ID header.
    return JsonResponse({"access_token": token, "super_id": super_id})
```

---

## Troubleshooting

- 401 Unauthorized: invalid/expired token — reacquire M2M token.
- 403 Forbidden: missing scope/permission — check client permissions in Auth Service.
- 429 Too Many Requests: throttled — back off and retry with jitter.

See also:

- `jwt_claims.md` — custom claims and semantics.
- `system_workflow.md` — call sequence reference.
- `troubleshooting.md` — common issues.

## Security notes

- Do not log secrets. Prefer secret managers (AWS Secrets Manager, SSM) in production.
- Keep per-service prefixes to prevent collisions and accidental secret leaks across services.

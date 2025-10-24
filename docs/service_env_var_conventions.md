# Service Environment Variable Conventions

To avoid collisions and make deployments predictable across multiple microservices, all environment variables must be prefixed per service.

## Prefixing standard

- Use an uppercase, snake_case service name followed by an underscore.
- Examples:
  - `AUTH_SERVICE_*`
  - `SUPER_ID_SERVICE_*`
  - `DATA_CAPTURE_RIGHTMOVE_SERVICE_*`
  - For external services, pick a consistent prefix like `YOUR_SERVICE_*`.

## Common variables and meanings

These names are intentionally similar across services for muscle memory while remaining namespaced.

- `<PREFIX>ENVIRONMENT` — One of `development|testing|staging|production`.
- `<PREFIX>LOGGING_LEVEL` — e.g., `INFO`, `DEBUG`.
- `<PREFIX>ROOT_PATH` — API root path (commonly `/api/v1`).
- `<PREFIX>DATABASE_URL` — SQLAlchemy-compatible DSN for service-owned tables.
- `<PREFIX>SUPABASE_URL` — Supabase base URL (via gateway if applicable).
- `<PREFIX>SUPABASE_ANON_KEY` — Supabase anon key.
- `<PREFIX>SUPABASE_SERVICE_ROLE_KEY` — Supabase service role key.
- `<PREFIX>REDIS_URL` — Optional Redis connection string for caching/rate limiting.

### Auth-specific

- `AUTH_SERVICE_M2M_JWT_SECRET_KEY` — Symmetric key for signing M2M tokens.
- `AUTH_SERVICE_M2M_JWT_ALGORITHM` — e.g., `RS256`.
- `AUTH_SERVICE_M2M_ACCESS_TOKEN_EXPIRE_MINUTES` — token TTL in minutes.

### Super ID-specific

- `SUPER_ID_SERVICE_M2M_JWT_SECRET_KEY` — Key used to validate M2M tokens (issued by Auth Service).
- `SUPER_ID_SERVICE_AUTH_SERVICE_ISSUER` — Expected `iss` claim for Auth tokens.

### Data Capture Rightmove-specific

- `DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_BUCKET_NAME` — S3 bucket used to store workflow snapshots for in-flight captures.
- `DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_PREFIX` — Key prefix within the bucket (defaults to `rightmove/status`).
- `DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_REGION` — Region for the snapshot bucket.
- `DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_PUBLIC_BASE_URL` — Optional base URL to build public links to the snapshot file.
- `DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_ENDPOINT_URL` — Optional overrides for S3-compatible storage endpoints (MinIO, etc.).
- `DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_WEBHOOK_URL` — Optional webhook URL that receives status updates.
- `DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_WEBHOOK_HEADERS` — JSON map of headers to include when calling the status webhook.
- `DATA_CAPTURE_RIGHTMOVE_SERVICE_AWS_ACCESS_KEY_ID` / `_SECRET_ACCESS_KEY` / `_SESSION_TOKEN` — Optional credentials if the environment doesn’t provide them via an instance profile.

## External integrators: recommended variables

When integrating an external microservice (FastAPI, Django, etc.), use a clear prefix, for example `YOUR_SERVICE_`:

- `YOUR_SERVICE_AUTH_SERVICE_URL`
- `YOUR_SERVICE_SUPER_ID_SERVICE_URL`
- `YOUR_SERVICE_M2M_CLIENT_ID`
- `YOUR_SERVICE_M2M_CLIENT_SECRET`

This keeps secrets and URLs scoped to your service and avoids accidental reuse by other microservices.

## Best practices

- Store secrets outside of the repo (Docker/Compose env files for local, secret manager in prod).
- Do not reuse variables across services without a prefix.
- Keep `.env.example` files updated so teammates understand required config.
- Prefer short, consistent names and avoid abbreviations that aren’t widely known.

## See also

- `integrating_external_services.md` — step-by-step external integration flow.
- `jwt_claims.md` — custom claims, token semantics.
- `system_workflow.md` — high-level call sequence.

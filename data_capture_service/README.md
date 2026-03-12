# Data Capture Service

Agnostic property data capture microservice with pluggable adapters for extracting structured property data from any listing URL.

## Architecture

- **Adapter Protocol** — plug-in interface (`DataCaptureAdapter`) with `fetch_raw`, `parse`, `score` methods
- **Firecrawl Baseline Provider** — pre-capture field-presence check used by the validation gate
- **Motie AI Adapter** — AI-powered extraction via the Motie agent API with exponential backoff polling
- **Validation Gate** — compares adapter output against baseline to catch missing critical fields
- **Completeness Scoring** — priority-weighted field scoring (P0 Essential → P5 Very Low)
- **Canonical Mapper** — normalises adapter output into a stable downstream schema

## Stack

- **FastAPI** + Uvicorn
- **PostgreSQL** (async via SQLAlchemy + psycopg3) — `data_capture` schema
- **Alembic** migrations
- **Pydantic Settings** with `DATA_CAPTURE_SERVICE_` env prefix

## Port

`8006` (dev and prod)

## Quick Start

```bash
# Install dependencies
poetry install

# Run unit tests (no DB required)
poetry run pytest tests/unit/ -v

# Boot with Docker (requires .env.dev)
cp .env.example .env.dev  # fill in credentials
docker compose -f docker-compose.dev.yml up
```

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Basic health check |
| `GET` | `/health/detailed` | Health with dependency checks |
| `POST` | `/api/v1/data_capture/start` | Start orchestrated capture pipeline |
| `GET` | `/api/v1/data_capture/runs/{id}` | Poll run status |
| `GET` | `/api/v1/data_capture/runs/{id}/result` | Get canonical result |
| `POST` | `/api/v1/data_capture/runs/{id}/retry` | Retry failed run |
| `POST` | `/api/v1/data_capture/adapters/motie` | Direct Motie capture |
| `POST` | `/api/v1/data_capture/adapters/firecrawl` | Baseline field check |
| `GET` | `/api/v1/data_capture/adapters/registry` | List registered adapters |

## Database Schema

All tables live in the `data_capture` PostgreSQL schema:

- `data_capture_runs` — central audit record per capture request
- `data_capture_run_steps` — per-adapter step tracking
- `source_raw_records` — raw provider responses (append-only)
- `source_parsed_records` — parsed field data with completeness scores
- `canonical_property_snapshots` — stable downstream contract (P0-P3 as columns, P4+ in extras_json)
- `canonical_media` — images and floorplans linked to snapshots
- `provider_data_captures` — registered adapter metadata
- `data_capture_usages` — credit and API usage tracking

## MCP Tools

Six tools registered in `pa_mcp` for AI agent access:

- `capture_property_data_tool` — full orchestrated pipeline
- `capture_property_with_motie_tool` — direct Motie extraction
- `check_property_fields_tool` — quick baseline field check
- `get_capture_run_status_tool` — poll run status
- `get_capture_run_result_tool` — fetch canonical result
- `retry_capture_run_tool` — retry failed runs

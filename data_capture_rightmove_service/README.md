# Data Capture Rightmove Service

## Overview

The Data Capture Rightmove Service is a microservice responsible for fetching property data from the Rightmove API (via RapidAPI), processing it, and storing it in a structured PostgreSQL database. It orchestrates calls to multiple Rightmove endpoints to build a comprehensive record for each property.

For a broader understanding of how this service fits into the overall system, see the main [System Workflow Guide](../../docs/system_workflow.md).

## Features

- **Combined Data Fetching**: Fetches data from multiple Rightmove API endpoints for a single property in one request.
- **Background Processing**: Uses background tasks for long-running data fetch and storage operations.
- **Secure Communication**: Utilizes M2M JWTs obtained from the Auth Service.
- **Workflow Tracking**: Integrates with the Super ID Service to use `super_ids` for tracking data capture workflows.

## Getting Started

The "paved path" for local development is to use the root `docker-compose.yml` file. For detailed instructions, refer to the main [Development Guide](../../docs/development.md).

### Prerequisites

- A RapidAPI account with a subscription to the Rightmove API.
- Your `RAPID_API_KEY` must be set in `data_capture_rightmove_service/.env.dev`.

### Database Migrations

Apply database migrations to set up the required tables:

```bash
docker-compose exec data_capture_rightmove_service alembic upgrade head
```

For a complete, end-to-end example of authentication and data capture workflow, see the integration test script:

➡️ **[Full System Flow Example](../../scripts/test_search_flow.py)**

### API Endpoints

- **Fetch and Store:** `POST /properties/fetch/combined`
- **Search:** `POST /properties/search/for-sale`

For detailed API documentation, access the service's `/docs` endpoint at [http://localhost:8003/docs](http://localhost:8003/docs) when running.

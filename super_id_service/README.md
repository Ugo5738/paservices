# Super ID Service

A microservice for generating and recording unique identifiers (UUIDs) for cross-service workflows.

## Overview

Super ID Service is a critical utility microservice within the property analysis ecosystem. Its primary responsibility is to generate, record, and provide unique identifiers (UUIDs, referred to as `super_ids`) on demand.

These `super_ids` serve as overarching workflow IDs, version IDs, or transaction IDs, typically generated at the inception of a multi-step process by an orchestrating entity (e.g., an Orchestrator Service, API Gateway/BFF, or an AI Agent).

## Features

- Generate universally unique IDs (UUID v4)
- Record all generated IDs for audit and tracking
- JWT-based authentication using the Auth Service
- Permission-based authorization ("super_id:generate")
- Rate limiting to prevent abuse

## Development

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Poetry for dependency management
- Access to a Supabase project

### Local Development Setup

1. Copy `.env.example` to `.env` and configure required variables:

```bash
cp .env.example .env
# Edit .env with your values
```

2. Start the service with Docker Compose:

```bash
docker-compose up -d
```

3. Run tests:

```bash
docker-compose exec super-id-service poetry run pytest
```

## API Endpoints

### Generate Super IDs

```
POST /super_ids
```

**Request Body:**

```json
{
  "count": 1 // Optional, defaults to 1
}
```

**Response:**

```json
{
  "super_id": "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"
}
```

Or for multiple IDs:

```json
{
  "super_ids": [
    "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx",
    "yyyyyyyy-yyyy-4yyy-zyyy-yyyyyyyyyyyy"
  ]
}
```

## Environment Variables

| Variable                                   | Description                      | Required |
| ------------------------------------------ | -------------------------------- | -------- |
| SUPER_ID_SERVICE_SUPABASE_URL              | URL of your Supabase project     | Yes      |
| SUPER_ID_SERVICE_SUPABASE_SERVICE_ROLE_KEY | Service role key from Supabase   | Yes      |
| JWT_SECRET_KEY                             | Secret key from Auth Service     | Yes      |
| AUTH_SERVICE_ISSUER                        | Expected issuer in JWTs          | Yes      |
| LOG_LEVEL                                  | Logging level (INFO, DEBUG, etc) | No       |
| ROOT_PATH                                  | Base path for API routes         | No       |
| RATE_LIMIT_REQUESTS_PER_MINUTE             | Rate limit for API requests      | No       |

## Database Schema

The service uses a single table in Supabase:

### Table: `generated_super_ids`

| Column Name            | Data Type   | Description               |
| ---------------------- | ----------- | ------------------------- |
| id                     | BIGSERIAL   | Primary key               |
| super_id               | UUID        | The generated UUID v4     |
| generated_at           | TIMESTAMPTZ | When the ID was generated |
| requested_by_client_id | TEXT        | Client ID from the JWT    |
| metadata               | JSONB       | Additional metadata       |

## Deployment

The service is deployed to Kubernetes using GitHub Actions. See the [Deployment Guide](../docs/deployment.md) for more information.

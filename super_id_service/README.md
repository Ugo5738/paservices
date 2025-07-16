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
    "description": "Optional description for the workflow."
  }
  ```

For detailed API documentation, access the service's `/docs` endpoint at [http://localhost:8002/docs](http://localhost:8002/docs) when running.

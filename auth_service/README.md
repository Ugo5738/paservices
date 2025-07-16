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


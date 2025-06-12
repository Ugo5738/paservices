# Property Analysis Services

A suite of microservices for property analysis and authentication.

## Overview

This repository (`paservices`) contains a collection of microservices that work together to provide property analysis capabilities. The services are designed to be independently deployable while sharing common infrastructure and CI/CD pipelines.

### Services

- **Auth Service**: Authentication and authorization service built with FastAPI and Supabase
- **Super ID Service**: UUID generation service for workflow tracking and request correlation

## Architecture

This project uses a microservice architecture with:

- FastAPI for REST API development
- Supabase for authentication and isolated PostgreSQL databases per service
- Kubernetes for container orchestration on AWS EKS
- GitHub Actions for CI/CD with conditional builds per service
- Redis for rate limiting and caching
- JWT-based service authentication

## Database Architecture

### Service Isolation

Each microservice uses its own dedicated database for proper service isolation:

- **Auth Service Database**: `auth_service_db` - Stores user credentials, roles, and permissions
- **Super ID Service Database**: `super_id_db` - Manages generated UUIDs and their audit logs

### Database Connection Format

Connection strings use the following format with proper quoting for options with spaces:

```
postgresql://user:password@host:port/dbname?sslmode=require&options='--client_encoding=utf8 --timezone=UTC --default_transaction_isolation=\'read committed\'''
```

> **Note**: The connection string uses single quotes around values with spaces in the `options` parameter to avoid invalid escape sequences.

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Kubernetes CLI (kubectl)
- Supabase account and CLI
- Python 3.12+ and Poetry

### Development

Each service has its own Docker Compose configuration for local development:

```bash
# Auth Service
cd auth_service
docker-compose up -d

# Super ID Service
cd super_id_service
docker-compose up -d
```

### Repository Structure

```
paservices/
├── auth_service/        # Auth Service source code
├── super_id_service/    # Super ID Service source code
├── k8s/                 # Kubernetes manifests
│   ├── auth/            # Auth Service K8s manifests
│   ├── super_id/        # Super ID Service K8s manifests
│   └── shared/          # Shared infrastructure manifests
└── .github/workflows/   # CI/CD pipeline configurations
```

See [Development Guide](docs/development.md) for detailed instructions.

### Deployment

The services are deployed to Kubernetes using GitHub Actions. The workflow:

1. Builds Docker images
2. Pushes to container registry
3. Applies Kubernetes manifests

See [Deployment Documentation](docs/deployment.md) for details.

## Project Structure

```
/paservices/
├── auth_service/        # Authentication and Authorization service
├── super_id_service/    # Super ID service (planned)
├── k8s/                 # Kubernetes manifests
├── docs/                # Documentation
└── scripts/             # Repository-level scripts
```

See [Project Structure](PROJECT_STRUCTURE.md) for more details.

## Contributing

1. Follow consistent code style using pre-commit hooks
2. Ensure tests pass for any changes
3. Update documentation as needed
4. Submit PRs against the main branch

## License

Proprietary - All rights reserved

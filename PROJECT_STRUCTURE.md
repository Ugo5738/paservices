# PA Services - Project Structure

## Overview

This repository follows a monorepo architecture for a collection of microservices that comprise the Property Analysis (PA) platform. Each service is designed to be independently deployable while sharing common infrastructure configuration.

## Directory Structure

```
/paservices/                            # Root directory
├── auth_service/                       # Authentication and Authorization service
│   ├── src/                            # Source code
│   ├── tests/                          # Tests
│   ├── alembic/                        # Database migrations
│   ├── scripts/                        # Utility scripts
│   └── README.md                       # Service-specific documentation
├── super_id_service/                   # Super ID generation service (planned)
│   ├── src/                            # Source code
│   ├── tests/                          # Tests
│   └── README.md                       # Service-specific documentation
├── k8s/                                # Kubernetes manifests (shared across services)
│   ├── auth/                           # Auth service manifests
│   ├── super_id/                       # Super ID service manifests (planned)
│   └── shared/                         # Shared infrastructure manifests
├── docs/                               # Documentation
│   ├── architecture/                   # Architecture diagrams and design docs
│   ├── deployment/                     # Deployment guidelines
│   └── service-specific/               # Service-specific documentation
├── scripts/                            # Repository-level utility scripts
└── supabase/                           # Supabase configuration and migrations
```

## Key Components

### Auth Service

Authentication and authorization microservice handling user registration, login, JWT management, and permission control. Provides authentication services for other microservices.

### Super ID Service (Planned)

Utility microservice for generating and recording unique identifiers (UUIDs) for cross-service workflows.

### Kubernetes Configuration

Centralized Kubernetes manifests for all services, organized by service with shared components for reuse.

### Supabase

Shared Supabase configuration for database access across services.

## Development Approach

1. **Independent Services**: Each service has its own directory with source code, tests, and service-specific documentation
2. **Shared Infrastructure**: Kubernetes configs, deployment scripts, and documentation are shared
3. **Consistent Patterns**: All services follow similar structure and coding patterns
4. **Separate Concerns**: Each service has a specific, well-defined responsibility

## Getting Started

See individual service READMEs for service-specific setup instructions.

For repository-wide setup and development workflow, refer to the [Development Guide](docs/development.md).

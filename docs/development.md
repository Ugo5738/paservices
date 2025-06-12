# Development Guide

## Prerequisites

- **Docker & Docker Compose**: Required for local development environments
- **kubectl**: For interacting with Kubernetes clusters
- **AWS CLI**: Configured with appropriate credentials for EKS access
- **Supabase CLI**: For local Supabase development
- **Python 3.12+**: For local development outside containers
- **Poetry**: For Python dependency management

## Repository Setup

1. Clone the repository
   ```bash
   git clone https://github.com/Ugo5738/paservices.git
   cd paservices
   ```

2. Set up service-specific environment
   - Copy `.env.example` to `.env` in each service directory
   - Configure required environment variables

## Development Workflow

### Local Development with Docker

Each service includes its own Docker Compose configuration for local development:

```bash
# Start auth_service locally
cd auth_service
docker-compose up -d

# Start super_id_service locally (when available)
cd ../super_id_service
docker-compose up -d
```

### Running Tests

```bash
# Run auth_service tests
cd auth_service
docker-compose exec auth_service pytest

# Run super_id_service tests (when available)
cd ../super_id_service
docker-compose exec super_id_service pytest
```

### Database Migrations (Auth Service)

```bash
# Apply migrations
cd auth_service
docker-compose exec auth_service alembic upgrade head

# Create new migration
docker-compose exec auth_service alembic revision -m "description_of_change" --autogenerate
```

## Adding a New Service

1. Create service directory structure:
   ```
   new_service/
   ├── src/
   │   └── new_service/
   │       ├── __init__.py
   │       └── main.py
   ├── tests/
   ├── Dockerfile
   ├── docker-compose.yml
   ├── pyproject.toml
   ├── .env.example
   └── README.md
   ```

2. Add Kubernetes manifests:
   ```
   k8s/
   └── new_service/
       ├── deployment.yaml
       ├── service.yaml
       ├── ingress.yaml
       └── secrets.yaml
   ```

3. Update CI/CD workflows in `.github/workflows/`

## Kubernetes Deployment

### Creating Secrets

Before deployment, create necessary Kubernetes secrets:

```bash
# Create auth service secrets
kubectl create secret generic paauth-secrets \
  --from-literal=AUTH_SERVICE_SUPABASE_URL=your-supabase-url \
  --from-literal=AUTH_SERVICE_SUPABASE_ANON_KEY=your-anon-key \
  --from-literal=AUTH_SERVICE_SUPABASE_SERVICE_ROLE_KEY=your-service-role-key \
  --from-literal=AUTH_SERVICE_M2M_JWT_SECRET_KEY=your-jwt-secret \
  --from-literal=AUTH_SERVICE_DATABASE_URL=your-db-url \
  --from-literal=USE_PGBOUNCER=false
```

### Applying Manifests

```bash
# Apply auth service manifests
kubectl apply -f k8s/auth/secrets.yaml
kubectl apply -f k8s/auth/migration-job.yaml
kubectl apply -f k8s/auth/deployment.yaml
kubectl apply -f k8s/auth/service.yaml
kubectl apply -f k8s/auth/ingress.yaml

# Apply super_id service manifests (when available)
kubectl apply -f k8s/super_id/secrets.yaml
kubectl apply -f k8s/super_id/deployment.yaml
kubectl apply -f k8s/super_id/service.yaml
kubectl apply -f k8s/super_id/ingress.yaml
```

## Environment Variables

### Critical Environment Settings

- **USE_PGBOUNCER=false**: Must be consistent across deployments and secrets
- **Database Connection Options**: Use raw string literals and proper quoting for PostgreSQL connection options

Refer to service-specific READMEs for detailed environment variable documentation.

## Troubleshooting

### Kubernetes Deployment Issues

1. **Pod startup failures**:
   ```bash
   kubectl describe pod <pod-name>
   kubectl logs <pod-name>
   ```

2. **Database connection issues**:
   - Verify secrets are correctly created and mounted
   - Check for PostgreSQL connection option syntax
   - Confirm `USE_PGBOUNCER=false` is set consistently

3. **Environment variable debugging**:
   ```bash
   kubectl exec -it <pod-name> -- env | grep VARIABLE_NAME
   ```

### Local Development Issues

1. **Container startup issues**:
   ```bash
   docker-compose logs -f service_name
   ```

2. **Database connection issues**:
   - Check `.env` configuration
   - Verify network connectivity between containers

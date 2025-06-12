# Production Deployment Guide

## Overview

This document outlines the steps required to deploy the Authentication Service to a production environment. The authentication service supports deployment to multiple cloud providers (AWS, Digital Ocean) using either Kubernetes or Docker Compose with Traefik.

## Architecture

The production deployment consists of:

1. **Authentication Service** - FastAPI application running in a Docker container
2. **PostgreSQL Database** - Managed by Supabase (self-hosted or cloud)
3. **Redis** - For rate limiting, token blacklisting, and caching
4. **Traefik** - Reverse proxy with automatic HTTPS using Let's Encrypt (for Docker Compose deployment)
5. **Kubernetes** - Container orchestration (optionally using MicroK8s on EC2 or other providers)

## Self-hosted Supabase Setup

### Prerequisites

- Docker and Docker Compose
- A server with at least 4GB RAM and 2 CPUs
- Domain name with SSL certificates (for production)

### Steps to Set Up Self-hosted Supabase

1. Clone the Supabase Docker repository:

```bash
git clone https://github.com/supabase/supabase-docker.git
cd supabase-docker
```

2. Configure environment variables in a `.env` file:

```bash
cp .env.example .env
```

3. Modify the `.env` file with your specific configuration:

```
# Supabase configuration
SUPABASE_DB_PASSWORD=your_secure_db_password
JWT_SECRET=your_secure_jwt_secret
ANON_KEY=your_anon_key  # Generated during setup
SERVICE_ROLE_KEY=your_service_role_key  # Generated during setup

# Domain configuration
DOMAIN_NAME=your_domain.com
EMAIL_ADDRESS=your_email@example.com  # For SSL certificate
```

4. Generate JWT keys and Supabase API keys:

```bash
cd scripts
./generate-keys.sh
```

5. Start the Supabase services:

```bash
cd ..
docker-compose up -d
```

6. Verify the installation by accessing the Supabase Studio at `https://your_domain.com/studio`

## Configuring Authentication Service for Self-hosted Supabase

### Environment Variables

Create a `.env.production` file in the root of the auth_service directory with the following variables:

```
# Self-hosted Supabase connection
SUPABASE_URL=https://your_domain.com
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# Database connection (to the same Postgres database that Supabase uses)
AUTH_SERVICE_DATABASE_URL=postgresql+asyncpg://postgres:your_secure_db_password@db:5432/postgres

# JWT secrets
M2M_JWT_SECRET_KEY=your_secure_jwt_secret_for_m2m

# Admin user setup
INITIAL_ADMIN_EMAIL=admin@your_domain.com
INITIAL_ADMIN_PASSWORD=secure_admin_password

# API configuration
ROOT_PATH=/api/v1
ENVIRONMENT=production
LOGGING_LEVEL=INFO

# Rate limiting
RATE_LIMIT_LOGIN=20/minute
RATE_LIMIT_REGISTER=10/minute
RATE_LIMIT_TOKEN=30/minute
RATE_LIMIT_PASSWORD_RESET=5/minute
```

### Network Configuration

Ensure that the Authentication Service can reach the self-hosted Supabase services. If deploying with Docker Compose, add the Auth Service to the same network as Supabase:

```yaml
# In docker-compose.prod.yml
services:
  auth_service:
    # ... other configurations ...
    networks:
      - supabase_network

networks:
  supabase_network:
    external: true # This network should be created by the Supabase Docker Compose setup
```

## Deployment Options

### Option 1: Docker Compose with Traefik

This option is suitable for single-server deployments on AWS EC2, Digital Ocean Droplets, or other VPS providers.

#### Prerequisites

- Server with Docker and Docker Compose installed
- Domain name pointing to your server
- Open ports 80 and 443 on your server

#### Configuration

1. Create an `.env.production` file in the `auth_service` directory with all required environment variables (see Environment Variables section below).

2. Set the following additional environment variables for Traefik (create a `.env` file in the same directory as your docker-compose.prod.yml):

```bash
ACME_EMAIL=your-email@example.com  # Used for Let's Encrypt registration
AUTH_DOMAIN=auth.yourdomain.com    # Domain for the auth service
```

#### Deployment

1. Navigate to the auth_service directory containing the docker-compose.prod.yml file:

```bash
cd /path/to/paservices/auth_service
```

2. Start the services:

```bash
docker compose -f docker-compose.prod.yml up -d
```

3. Run database migrations:

```bash
docker compose -f docker-compose.prod.yml exec auth_service alembic upgrade head
```

4. Verify the services are running:

```bash
docker compose -f docker-compose.prod.yml ps
```

5. Check Traefik logs for Let's Encrypt certificate acquisition:

```bash
docker compose -f docker-compose.prod.yml logs -f traefik
```

### Option 2: Kubernetes Deployment

This option is suitable for more scalable and resilient deployments. You can use AWS EKS, Digital Ocean Kubernetes, or MicroK8s on an EC2 instance.

#### Prerequisites

- Kubernetes cluster (AWS EKS, Digital Ocean Kubernetes, or MicroK8s)
- `kubectl` configured to access your cluster
- Domain name pointing to your cluster's load balancer

#### Configuration

1. Update Kubernetes manifests in the `k8s` directory:

   - `deployment.yaml`: Update image name, resource limits, etc.
   - `service.yaml`: Verify service ports
   - `ingress.yaml`: Update host domain name
   - `secrets.yaml`: Prepare for your environment variables

2. For EC2 with MicroK8s, you can use the provided setup script:

```bash
sudo /path/to/paservices/scripts/setup_microk8s.sh
```

#### Deployment

1. Apply Kubernetes secrets with proper substitution:

```bash
# First, base64 encode all your sensitive values
SUPABASE_URL_B64=$(echo -n "your-supabase-url" | base64 -w 0)
SUPABASE_ANON_KEY_B64=$(echo -n "your-anon-key" | base64 -w 0)
SUPABASE_SERVICE_ROLE_KEY_B64=$(echo -n "your-service-role-key" | base64 -w 0)
AUTH_SERVICE_DATABASE_URL_B64=$(echo -n "your-db-url" | base64 -w 0)
M2M_JWT_SECRET_KEY_B64=$(echo -n "your-jwt-secret" | base64 -w 0)
REDIS_URL_B64=$(echo -n "your-redis-url" | base64 -w 0)
DOCKER_REGISTRY="your-docker-registry" # e.g., your DockerHub username
IMAGE_TAG="latest"  # or specific version/git sha
AUTH_DOMAIN="auth.yourdomain.com"  # your auth service domain

# Apply the secrets with variable substitution using sed
cat k8s/secrets.yaml | \
  sed "s|SUPABASE_URL_BASE64|$SUPABASE_URL_B64|g" | \
  sed "s|SUPABASE_ANON_KEY_BASE64|$SUPABASE_ANON_KEY_B64|g" | \
  sed "s|SUPABASE_SERVICE_ROLE_KEY_BASE64|$SUPABASE_SERVICE_ROLE_KEY_B64|g" | \
  sed "s|AUTH_SERVICE_DATABASE_URL_BASE64|$AUTH_SERVICE_DATABASE_URL_B64|g" | \
  sed "s|M2M_JWT_SECRET_KEY_BASE64|$M2M_JWT_SECRET_KEY_B64|g" | \
  sed "s|REDIS_URL_BASE64|$REDIS_URL_B64|g" | \
  kubectl apply -f -
```

2. Apply the remaining Kubernetes manifests with substitution:

```bash
# Apply deployment with image substitution
cat k8s/deployment.yaml | \
  sed "s|DOCKER_REGISTRY|$DOCKER_REGISTRY|g" | \
  sed "s|IMAGE_TAG|$IMAGE_TAG|g" | \
  kubectl apply -f -

# Apply service as-is
kubectl apply -f k8s/service.yaml

# Apply ingress with domain substitution
cat k8s/ingress.yaml | \
  sed "s|AUTH_DOMAIN_VALUE|$AUTH_DOMAIN|g" | \
  kubectl apply -f -
```

3. Verify deployment:

```bash
kubectl get pods
kubectl get services
kubectl get ingress
```

4. Check pod logs:

```bash
kubectl logs -f deployment/paservices
```

### Option 3: Using GitHub Actions CI/CD Pipeline

The repository includes workflows for continuous deployment to either Docker Compose or Kubernetes environments.

#### GitHub Secrets Configuration

Set up the following secrets in your GitHub repository:

**For Docker Registry Authentication:**

- `DOCKERHUB_USERNAME`: Your Docker Hub username
- `DOCKERHUB_TOKEN`: Your Docker Hub access token

**For AWS EKS Deployment:**

- `AWS_ACCESS_KEY_ID`: AWS access key with EKS permissions
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `AWS_REGION`: AWS region where your EKS cluster is located

**For Digital Ocean Deployment:**

- `DIGITALOCEAN_ACCESS_TOKEN`: Digital Ocean API token
- `DIGITALOCEAN_CLUSTER_NAME`: Name of your Digital Ocean Kubernetes cluster

**Application Environment Variables:**

- `SUPABASE_URL`: URL of your Supabase instance
- `SUPABASE_ANON_KEY`: Supabase anonymous key
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key
- `AUTH_SERVICE_DATABASE_URL`: PostgreSQL connection string
- `M2M_JWT_SECRET_KEY`: Secret key for M2M JWT token generation
- `REDIS_URL`: Connection URL for Redis

#### Triggering Deployment

1. Push to the main branch with a commit message containing `[deploy]` or manually trigger the workflow via GitHub Actions UI.
2. Select your target environment (staging/production) and cloud provider (aws/digitalocean).
3. The workflow will build a Docker image, push it to Docker Hub, and deploy it to the specified environment.

## Database Migrations

Before deploying a new version, ensure all database migrations are applied:

```bash
docker-compose -f docker-compose.prod.yml exec auth_service alembic upgrade head
```

## Monitoring and Logging

### Health Check

The service provides a health check endpoint at `/health` that returns the status of:

- API service
- Database connection
- Supabase connection

### Structured Logging

In production, logs are output in JSON format with the following fields:

- `timestamp`: ISO 8601 formatted timestamp
- `level`: Log level (INFO, WARNING, ERROR, etc.)
- `logger`: Logger name
- `message`: Log message
- `request_id`: Unique ID for tracking requests across the system
- `environment`: Deployment environment
- Additional context-specific fields

### Log Collection

Since logs are output to stdout/stderr in Docker, you can use standard Docker log drivers or container orchestration platforms to collect and analyze logs.

## Backup and Recovery

### Database Backups

Regular backups of the PostgreSQL database should be configured. With self-hosted Supabase, this involves backing up the PostgreSQL database:

```bash
# Example backup command
docker-compose exec db pg_dump -U postgres postgres > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore Procedure

1. Stop the services:

```bash
docker-compose down
```

2. Restore the database:

```bash
cat backup_file.sql | docker-compose exec -T db psql -U postgres
```

3. Restart the services:

```bash
docker-compose up -d
```

## Security Considerations

### JWT Management

- Ensure JWT secret keys are kept secure and rotated periodically
- Use environment variables or secrets management solutions to store sensitive values

### Network Security

- Use a reverse proxy (e.g., Nginx, Traefik) with SSL termination
- Implement proper firewall rules to restrict access to the services

### Rate Limiting

The service includes rate limiting for sensitive endpoints. Configure the limits based on your expected traffic patterns.

## Troubleshooting

### Common Issues

1. **Connection to Supabase fails:**

   - Verify network connectivity between containers
   - Check Supabase URL and API keys in environment variables
   - Ensure Supabase services are running

2. **Database migrations fail:**

   - Check database connection string
   - Verify database user permissions
   - Review Alembic migration logs

3. **Admin user creation fails during bootstrap:**
   - Check if the admin user already exists
   - Verify Supabase service role key permissions
   - Review service logs for detailed error messages

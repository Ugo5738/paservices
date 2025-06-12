# Multi-Service Deployment Checklist

This checklist ensures a smooth transition from our monolithic `paauth` service to the multi-service `paservices` architecture.

## Pre-Deployment Tasks

### Infrastructure Setup
- [ ] Verify EKS cluster has sufficient resources for both services
- [ ] Confirm cert-manager and nginx ingress controller are properly configured
- [ ] Validate shared cluster resources in `k8s/shared/`

### Database Infrastructure
- [ ] Ensure separate databases created for each service (auth-service-db, super-id-db)
- [ ] Verify connection string formats use single quotes for values with spaces in options
- [ ] Confirm proper database user permissions for each service (least privilege)

### Auth Service
- [ ] Verify all references have been updated from `paauth` to `auth-service` in:
  - [x] K8s manifests (deployment, service, ingress, secrets)
  - [ ] Code references (imports, configuration)
  - [ ] Database connection strings (check for escaping issues)
- [ ] Confirm `USE_PGBOUNCER=false` is set correctly
- [ ] Verify service connectivity with Supabase

### Super ID Service
- [x] Implement database schema for Super ID service
- [ ] Configure dedicated database with proper connection string format
  - [ ] Ensure single quotes are used for values with spaces in connection options
  - [ ] Verify proper isolation from Auth Service database
- [ ] Execute schema migrations against Super ID database only
- [ ] Complete unit and integration tests
- [ ] Configure rate limiting with Redis
- [ ] Validate JWT authentication with Auth Service tokens using M2M_JWT_SECRET_KEY
- [ ] Complete API documentation

## Deployment Process

### CI/CD Pipeline
- [ ] Push all changes to the GitHub repository
- [ ] Monitor GitHub Actions workflow execution
- [ ] Verify conditional builds are working correctly
- [ ] Check image tags and registry pushes

### Kubernetes Deployment
- [ ] Apply shared infrastructure manifests first
- [ ] Deploy Auth Service and verify functionality
- [ ] Deploy Super ID Service and verify functionality
- [ ] Check all service-to-service communications

### Post-Deployment Verification
- [ ] Validate all API endpoints through ingress
- [ ] Check TLS certificates are working
- [ ] Verify logs are being generated correctly
- [ ] Test authentication flows end-to-end
- [ ] Monitor resource usage and performance

## Long-Term Tasks

### Documentation
- [ ] Update API documentation for both services
- [ ] Create onboarding guides for new developers
- [ ] Document deployment and rollback procedures

### Security and Compliance
- [ ] Implement IAM roles with least privilege principle
- [ ] Set up RBAC for Kubernetes access control
- [ ] Configure network policies for service isolation
- [ ] Plan for secret rotation procedures

### Monitoring and Alerting
- [ ] Set up Prometheus for metrics collection
- [ ] Configure Grafana dashboards for visualization
- [ ] Implement alerting for critical service issues
- [ ] Create on-call rotation schedule

## Known Issues and Workarounds

1. **PostgreSQL Connection String**: Avoid using backslash escapes in connection strings. Instead, use single quotes around values with spaces (e.g., 'read committed' instead of read\ committed).

2. **Docker Image Tags**: If using environment variables in Kubernetes manifests, ensure they are properly substituted during the CI/CD process.

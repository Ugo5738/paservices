# Troubleshooting Guide

This guide contains solutions to common problems encountered during development and deployment of the PA Services platform.

## Database Connection Issues

#### **Problem:** The service fails to start with a database connection error.

- **Solution 1: Check `docker-compose` Networking**
  Ensure that the service container is on the same Docker network as the Supabase database container. The Supabase network name is typically `[project_name]_default_network`. Verify this in your root `docker-compose.yml`.

- **Solution 2: Verify Connection String**
  The PostgreSQL connection string in your `.env` file must be correct. Pay special attention to the `options` parameter.

  > **Note on Database Connections:**
  > When using PostgreSQL, connection string options with spaces must be wrapped in single quotes (e.g., `'read committed'`). See the `.env` file for an example.

- **Solution 3: pgBouncer Conflicts**
  If you see errors related to "prepared statements," ensure `USE_PGBOUNCER=false` is set consistently across your configuration, especially in Kubernetes secrets and deployment manifests.

## Kubernetes Deployment Issues

#### **Problem:** A pod is failing to start (`CrashLoopBackOff` status).

- **Solution 1: Check Pod Logs**
  The first step is always to get the logs from the failing pod.

  ```bash
  kubectl logs <pod-name>
  ```

- **Solution 2: Describe the Pod**
  This command gives detailed information about the pod's state, including events that might indicate why it's failing (e.g., "Failed to pull image," "secret not found").

  ```bash
  kubectl describe pod <pod-name>
  ```

- **Solution 3: Verify Secrets**
  Ensure that the Kubernetes secrets required by the pod exist and are correctly mounted. You can debug this by checking for the secret's existence and keys:
  ```bash
  kubectl get secret [your-secret-name] -o json | jq '.data | keys[]'
  ```

## CI/CD Pipeline Failure

#### **Problem:** The GitHub Actions workflow is failing.

- **Solution:** Review the logs for the failing step in the GitHub Actions UI. Common causes include:
  - **Docker Build Failure:** An issue in a `Dockerfile` or a dependency installation failure.
  - **Authentication Error:** Incorrect or expired `DOCKERHUB_TOKEN` or `AWS_ACCESS_KEY_ID` in GitHub Secrets.
  - **Kubernetes Apply Failure:** A syntax error in a Kubernetes manifest file. The workflow logs will show the output from `kubectl`, which usually contains the specific error.

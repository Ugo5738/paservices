# Super ID Service Migrations

This directory contains database migration scripts for the Super ID service.

## Overview

The Super ID service uses an isolated database separate from the Auth service to ensure proper service boundaries and independence. Migrations are managed with Alembic and run as Kubernetes jobs during deployment.

## Migration Process

1. Migrations are applied using Alembic with the command `alembic upgrade head`
2. Each service has its own separate migration history and database
3. Migration jobs are run with a dedicated Kubernetes job before deploying the main service

## Database Connectivity

The Super ID service connects to its dedicated database using a properly formatted PostgreSQL connection string:

```
postgresql://user:password@host:port/super_id_db?sslmode=require&options='--client_encoding=utf8 --timezone=UTC --default_transaction_isolation=\'read committed\''
```

**Important**: Note the use of single quotes around values with spaces in the `options` parameter. This follows PostgreSQL best practices for connection string formatting.

## Development Workflow

1. Create a new migration script with: `alembic revision -m "description"`
2. Edit the migration script with your schema changes
3. Test locally before committing
4. When deploying, the migration job will run these scripts against the production database

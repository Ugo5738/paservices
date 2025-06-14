# Auth Service

Authentication and Authorization service for managing users, application clients, roles, and permissions.

## Development

**Prerequisites**

- Docker & Docker Compose installed
- `.env` file configured with required variables (see [Environment Variables](#environment-variables) section).

**Running the Application**

```bash
# from auth_service root
docker-compose up -d
```

**Viewing Logs**

```bash
docker-compose logs -f auth_service
```

**Stopping Services**

```bash
docker-compose down
```

## Inside the Container (Development Workflow)

- **Run tests**

  ```bash
  docker-compose exec auth_service pytest
  ```

````

- **Apply migrations**

  ```bash
docker-compose exec auth_service alembic upgrade head
````

- **Open shell**

  ```bash
  docker-compose exec auth_service bash
  ```

````

- **Manage dependencies**

  ```bash
docker-compose exec auth_service poetry add <package>
````

## IDE Integration (VS Code)

1. Install the **Docker** & **Remote Development** extensions.
2. Start containers (`docker-compose up -d`).
3. Open Command Palette → **Remote-Containers: Attach to Running Container...**
4. Select the `auth_service` container.
5. Use VS Code debugger & terminal inside the container.

## Environment Variables

The application requires several environment variables to be configured. A `.env.example` file is provided as a template.

### Core Configuration

| Variable        | Description                                            | Example                                | Required |
| --------------- | ------------------------------------------------------ | -------------------------------------- | -------- |
| `ENVIRONMENT`   | Application environment                                | `development`, `testing`, `production` | Yes      |
| `ROOT_PATH`     | Base path for API routes                               | `/api/v1`                              | Yes      |
| `BASE_URL`      | Base URL for the service (must be HTTPS in production) | `https://auth.example.com`             | Yes      |
| `LOGGING_LEVEL` | Log verbosity level                                    | `INFO`, `DEBUG`, `WARNING`, `ERROR`    | Yes      |

### Supabase Configuration

| Variable                                 | Description                                  | Example                                   | Required |
| ---------------------------------------- | -------------------------------------------- | ----------------------------------------- | -------- |
| `AUTH_SERVICE_SUPABASE_URL`              | URL of your Supabase project                 | `https://project-ref.supabase.co`         | Yes      |
| `AUTH_SERVICE_SUPABASE_ANON_KEY`         | Anon/public key from Supabase                | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` | Yes      |
| `AUTH_SERVICE_SUPABASE_SERVICE_ROLE_KEY` | Service role key from Supabase (keep secure) | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` | Yes      |

### Database Configuration

| Variable                    | Description                  | Example                                           | Required |
| --------------------------- | ---------------------------- | ------------------------------------------------- | -------- |
| `AUTH_SERVICE_DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@host:5432/dbname` | Yes      |

### JWT Configuration

| Variable                              | Description                           | Example                               | Required         |
| ------------------------------------- | ------------------------------------- | ------------------------------------- | ---------------- |
| `AUTH_SERVICE_M2M_JWT_SECRET_KEY`     | Secret key for signing M2M JWTs       | `your-secure-random-key-min-32-chars` | Yes              |
| `M2M_JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Expiry time for M2M tokens in minutes | `15`                                  | No (default: 15) |

### Rate Limiting Configuration

| Variable                    | Description                            | Example     | Required                |
| --------------------------- | -------------------------------------- | ----------- | ----------------------- |
| `RATE_LIMIT_LOGIN`          | Rate limit for login endpoint          | `5/minute`  | No (default: 5/minute)  |
| `RATE_LIMIT_REGISTER`       | Rate limit for registration endpoint   | `5/minute`  | No (default: 5/minute)  |
| `RATE_LIMIT_TOKEN`          | Rate limit for token endpoint          | `10/minute` | No (default: 10/minute) |
| `RATE_LIMIT_PASSWORD_RESET` | Rate limit for password reset endpoint | `3/minute`  | No (default: 3/minute)  |

### Initial Admin Configuration

| Variable                 | Description                   | Example             | Required        |
| ------------------------ | ----------------------------- | ------------------- | --------------- |
| `INITIAL_ADMIN_EMAIL`    | Email for first admin user    | `admin@example.com` | Yes (for setup) |
| `INITIAL_ADMIN_PASSWORD` | Password for first admin user | `strong-password`   | Yes (for setup) |

### OAuth Configuration

| Variable                    | Description                    | Example                      | Required                                 |
| --------------------------- | ------------------------------ | ---------------------------- | ---------------------------------------- |
| `OAUTH_STATE_COOKIE_NAME`   | Name of cookie for OAuth state | `supabase-auth-state`        | No (default: supabase-auth-state)        |
| `OAUTH_CALLBACK_ROUTE_BASE` | Base route for OAuth callbacks | `/auth/users/oauth/callback` | No (default: /auth/users/oauth/callback) |

### Password Reset Configuration

| Variable                      | Description                          | Example                                  | Required |
| ----------------------------- | ------------------------------------ | ---------------------------------------- | -------- |
| `PASSWORD_RESET_REDIRECT_URL` | URL to redirect after password reset | `https://app.example.com/reset-password` | Yes      |

### Security Notes

- Never commit `.env` files to version control
- Use different secrets for development, testing, and production environments
- In production, use a secure method to provide environment variables (e.g., Docker secrets, Kubernetes secrets)
- Rotate sensitive credentials periodically, especially `M2M_JWT_SECRET_KEY` and `SUPABASE_SERVICE_ROLE_KEY`

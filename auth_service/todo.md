# TODO List for Auth Service - For AI Agent (Cursor)

This TODO list breaks down the development of the Auth Service into manageable tasks, with testing integrated into each development step. The goal is an incremental build process with high test coverage.

## Phase 0: Project Setup & Core Configuration

- [x] **0.1: Initialize Python Project with Poetry**
  - [x] 0.1.a: Run `poetry new auth_service && cd auth_service`.
  - [x] 0.1.b: Initialize git repository (`git init && git add . && git commit -m "Initial project structure from poetry"`).
  - [x] **0.1.c: Create/Verify .gitignore File**
    - [x] 0.1.c.i: Ensure standard Python, Poetry, OS, and IDE specific files/directories are ignored (e.g., .env, **pycache**/, \*.pyc, .pytest_cache/, .mypy_cache/, .venv/, venv/, .vscode/, .idea/).
- [x] **0.2: Install Core Dependencies using Poetry**
  - [x] 0.2.a: Add `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings` (for env management), `sqlalchemy` (or `sqlmodel`), `asyncpg`, `psycopg2-binary` (for Alembic sync operations if needed, or Supabase direct connections), `python-jose[cryptography]` (for M2M JWTs), `passlib[bcrypt]` (for hashing client secrets), `supabase-py`, `alembic`, `slowapi`, `httpx` (for testing FastAPI).
  - [x] 0.2.b: Add development dependencies for testing, linting, and formatting: poetry add --group dev pytest pytest-asyncio pytest-cov black ruff mypy pre-commit httpx.
  - [x] 0.2.c: Configure Linters, Formatters, and Pre-commit Hooks
    - [x] 0.2.c.i: Configure pyproject.toml with settings for Black (e.g., line length) and Ruff (select rules, target Python version).
    - [x] 0.2.c.ii: Configure pyproject.toml for MyPy (e.g., strict mode options).
    - [x] 0.2.c.iii: Initialize pre-commit: pre-commit install
    - [x] 0.2.c.iv: Create a pre-commit-config.yaml file with hooks for Black, Ruff, and MyPy.
    - [x] 0.2.c.v: Test pre-commit hooks by trying to commit a non-compliant file.
  - [x] 0.2.d: Write initial GitHub Actions workflow for linting/testing on push/PR. (This provides early CI).
- [x] **0.3: Configure Environment Variable Management**
  - [x] 0.3.a: Create a `config.py` using `pydantic-settings` to load variables from a `.env` file.
    - [x] 0.3.a.i: Ensure `config.py` imports `BaseSettings` from `pydantic_settings` (not `pydantic` for Pydantic v2+).
    - [x] 0.3.a.ii: Define all environment variables present in `.env` (e.g., `RATE_LIMIT_...`, `INITIAL_ADMIN_...`, `LOGGING_LEVEL`) as fields in the `Settings` class in `config.py` to avoid `ValidationError` for extra fields.
  - [x] 0.3.b: Define initial required environment variables in `.env.example` and `.env`: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `M2M_JWT_SECRET_KEY`, `AUTH_SERVICE_DATABASE_URL`, `ROOT_PATH`.
    - [x] 0.3.b.i: For `AUTH_SERVICE_DATABASE_URL`, when using Supabase locally and Docker for `auth_service`:
      - The format should be `postgresql://<user>:<password>@<supabase_db_container_name>:<internal_port>/<db_name>`.
      - Example: `postgresql://postgres:postgres@supabase_db_projectname:5432/postgres`.
      - Find `<supabase_db_container_name>` (e.g., `supabase_db_projectname`) using `docker ps` after running `supabase start` in the project root (e.g., `projectname/`).
    - [x] 0.3.b.ii: Ensure `.env.example` lists all fields defined in the `Settings` class in `config.py`.
- [x] **0.4: Establish Asynchronous Database Connection (for Auth Service specific tables)**
  - [x] 0.4.a: Create database utility functions (`db.py`) for SQLAlchemy/SQLModel async engine setup, session management, and a base model.
  - [x] 0.4.b: Write a simple test to verify database connectivity, using the `AUTH_SERVICE_DATABASE_URL`, to the PostgreSQL instance where the `auth_service_data` schema will reside (this will typically be the Supabase-managed PostgreSQL instance). The test should run from within the `auth_service` container.
- [x] **0.5: Initialize Supabase Async Client**
  - [x] 0.5.a: Create a Supabase utility module (`supabase_client.py`) to initialize and provide the `supabase-py` AsyncClient as a FastAPI dependency.
  - [x] 0.5.b: Write a test to verify Supabase client initialization (can mock actual connection for this unit test).
- [x] **0.6: Define Core Pydantic Models**
  - [x] 0.6.a: Define initial Pydantic models in `auth_service/src/auth_service/schemas/common_schemas.py` (e.g., `MessageResponse`).
  - [x] 0.6.b: Define Pydantic models for JWT payloads in `auth_service/src/auth_service/schemas/user_schemas.py` (e.g., `UserTokenData`) and `auth_service/src/auth_service/schemas/app_client_schemas.py` (e.g., `AppClientTokenData`).
  - [x] 0.6.c: Organize Pydantic models into a dedicated `auth_service/src/auth_service/schemas/` directory with submodules (e.g., `user_schemas.py`, `app_client_schemas.py`, `common_schemas.py`) and an `__init__.py` for exports. Consolidate FastAPI dependencies into `auth_service/src/auth_service/dependencies/` (e.g., `user_deps.py`).
- [x] **0.7: Setup Alembic for Database Migrations (Auth Service Specific Schema)**
  - [x] 0.7.a: Initialize Alembic (`alembic init alembic`).
  - [x] 0.7.b: Configure `alembic/env.py` for asynchronous environment and to use `AUTH_SERVICE_DATABASE_URL`. Point `script.py.mako` to use the correct metadata object from `db.py`.
    - [x] 0.7.b.i: Ensure `alembic.ini` has `prepend_sys_path = .` to help resolve module paths when running alembic commands from the service root.
  - [x] 0.7.c: Specify the target schema (e.g., `auth_service_data`) in `env.py` if not using `public`.
- [x] **0.8: Basic FastAPI Application Structure**
  - [x] 0.8.a: Create `main.py` with a basic FastAPI app instance.
    - [x] 0.8.a.i: Ensure `FastAPI` instance in `main.py` is initialized with `root_path=settings.root_path` from your `config.py`.
  - [x] 0.8.b: Implement a health check endpoint (e.g., `GET /health`) and write a test for it.
- [x] **0.9: Logging and Error Handling Setup**
  - [x] 0.9.a: Configure basic structured logging (e.g., JSON format) for the application. Define key auditable events to be logged.
  - [x] 0.9.b: Implement custom exception handlers for common HTTP errors and validation errors to ensure consistent JSON error responses. Write tests for these handlers.
- [x] **0.10: CORS Configuration**
  - [x] 0.10.a: Add `CORSMiddleware` to the FastAPI app, configuring allowed origins, methods, and headers (initially permissive for local dev, configurable for prod).
- [x] **0.11: Create Initial Dockerfile for Development**
  - [x] 0.11.a: Create a basic Dockerfile that:
    - Uses an official Python base image (e.g., python:3.12-slim).
    - Sets appropriate environment variables (e.g., PYTHONUNBUFFERED, PYTHONDONTWRITEBYTECODE).
    - Adds `ENV PYTHONPATH="${PYTHONPATH}:/app/src"` to ensure Python's import system can find modules in the `src` directory for `src`-layouts.
    - Sets up Poetry (installs it if not in base image, or ensures correct version).
    - Sets a WORKDIR (e.g., /app).
    - Copies `pyproject.toml` and `poetry.lock` first (to leverage Docker layer caching).
    - Installs dependencies using `poetry install --no-root --no-interaction --no-ansi` (and `poetry config virtualenvs.create false`). `--no-root` is important as the project source is copied separately.
    - Copies the entire application source code into the WORKDIR (`COPY . /app`).
    - EXPOSE the application port (e.g., 8000).
    - Specifies a CMD to run the FastAPI app with Uvicorn (enabling hot reloading e.g., `CMD ["poetry", "run", "uvicorn", "auth_service.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]`).
  - [x] 0.11.b: Build the Docker image using `docker build -t auth_service_dev .` (or via `docker-compose build`) and ensure it builds and runs successfully.
- [x] **0.12: Create Initial docker-compose.yml for Development**

  - [x] 0.12.a: Define a service for your auth_service using the Dockerfile.
  - [x] 0.12.b: Database Service for Local Development:

    - [x] 0.12.b.i: If using Supabase locally (via Supabase CLI `supabase start` or its own `docker-compose.yml`), ensure your `auth_service` container can connect to the PostgreSQL service provided by the local Supabase stack. The `AUTH_SERVICE_DATABASE_URL` will point to this Supabase PostgreSQL.
      - The `auth_service/docker-compose.yml` should **not** define its own `db` service for PostgreSQL.
        - Configure the `networks` section in `auth_service/docker-compose.yml` to connect to the external network created by the Supabase CLI.
          - Example:
            ```yaml
            networks:
              supabase_project_network: # Logical name for this service
                name: projectname_default_network # ACTUAL name of Supabase network
                external: true
            ```
          - Find the `ACTUAL name of Supabase network` (e.g., `projectname_default_network`) by running `docker network ls` after `supabase start` (run from project root, e.g., `projectname/`).

  - [x] 0.12.c: Configure volume mounts to map your local source code into the container for live reloading.
  - [x] 0.12.d: Set up port mappings.
  - [x] 0.12.e: Configure environment variables for the auth_service, ideally using `env_file: ./.env` in the `docker-compose.yml` for the service.

- [x] **0.13: Develop Inside the Container**
  - [x] 0.13.a: Document how to run the application using docker-compose up.
  - [x] 0.13.b: Document and establish the workflow for running all development commands (e.g., `pytest`, `alembic`, `poetry add/remove/update`) inside the service container using `docker-compose exec auth_service <command>` or an interactive shell via `docker-compose exec auth_service bash`.
  - [x] 0.13.c: Configure your IDE (e.g., VS Code with Docker extension) to work with the containerized environment (for debugging, terminal access).

## Phase 1: Database Schema & Models (Auth Service Specific Data)

- [x] **1.1: `profiles` Table (for user data extending Supabase users)**
  - [x] 1.1.a: Define SQLAlchemy/SQLModel model for `profiles` (`user_id` (PK, FK to `supabase.auth.users.id`), `username` (unique, nullable), `first_name` (nullable), `last_name` (nullable), `is_active` (default true), `created_at`, `updated_at`).
  - [x] 1.1.b: Generate Alembic migration script for `profiles` table.
  - [x] 1.1.c: Apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.
- [x] **1.2: `app_clients` Table (for M2M authentication)**
  - [x] 1.2.a: Define SQLAlchemy/SQLModel model for `app_clients` (`id` (PK, UUID), `client_name` (unique), `client_secret_hash`, `is_active` (default true), `description` (nullable), `created_at`, `updated_at`).
  - [x] 1.2.b: Generate Alembic migration script for `app_clients` table.
  - [x] 1.2.c: Apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.
- [x] **1.3: `roles` Table**
  - [x] 1.3.a: Define SQLAlchemy/SQLModel model for `roles` (`id` (PK, auto-increment or UUID), `name` (unique), `description` (nullable), `created_at`, `updated_at`).
  - [x] 1.3.b: Generate Alembic migration script for `roles` table.
  - [x] 1.3.c: Apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.
- [x] **1.4: `permissions` Table**
  - [x] 1.4.a: Define SQLAlchemy/SQLModel model for `permissions` (`id` (PK, auto-increment or UUID), `name` (unique, e.g., `resource:action`), `description` (nullable), `created_at`, `updated_at`).
  - [x] 1.4.b: Generate Alembic migration script for `permissions` table.
  - [x] 1.4.c: Apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.
- [x] **1.5: `user_roles` Junction Table**
  - [x] 1.5.a: Define SQLAlchemy/SQLModel model for `user_roles` (`user_id` (FK to `supabase.auth.users.id`), `role_id` (FK to `roles.id`), `assigned_at`; composite PK on `user_id`, `role_id`).
  - [x] 1.5.b: Generate Alembic migration script for `user_roles` table.
  - [x] 1.5.c: Apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.
- [x] **1.6: `app_client_roles` Junction Table**
  - [x] 1.6.a: Define SQLAlchemy/SQLModel model for `app_client_roles` (`app_client_id` (FK to `app_clients.id`), `role_id` (FK to `roles.id`), `assigned_at`; composite PK on `app_client_id`, `role_id`).
  - [x] 1.6.b: Generate Alembic migration script for `app_client_roles` table.
  - [x] 1.6.c: Apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.
- [x] **1.7: `role_permissions` Junction Table**
  - [x] 1.7.a: Define SQLAlchemy/SQLModel model for `role_permissions` (`role_id` (FK to `roles.id`), `permission_id` (FK to `permissions.id`), `assigned_at`; composite PK on `role_id`, `permission_id`).
  - [x] 1.7.b: Generate Alembic migration script for `role_permissions` table.
  - [x] 1.7.c: Apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.
- [x] **1.8: (Optional) `refresh_tokens` Table for `app_clients`**
  - [x] 1.8.a: If implementing: Define model, generate Alembic migration script, and apply the migration by running inside the container: `docker-compose exec auth_service alembic upgrade head`.

## Phase 2: Human User Authentication (Proxying Supabase)

- [x] **2.1: User Registration (`POST /auth/users/register`)**
  - [x] 2.1.a: Define Pydantic models in `auth_service/src/auth_service/schemas/user_schemas.py`: `UserCreateRequest` (for request) and `UserResponse` (for response, including profile info), `SupabaseSession` (for session data).
  - [x] 2.1.b: Write unit tests for any pre/post Supabase call logic (e.g., profile data preparation). (Implicitly covered by successful integration tests for profile creation path)
  - [x] 2.1.c: Write integration tests for the endpoint:
    - [x] Successful registration and profile creation.
    - [x] Email already exists (Supabase error).
    - [x] Invalid password/email format.
    - [x] Supabase service unavailable (mocked).
  - [x] 2.1.d: Implement endpoint logic: call `supabase.auth.sign_up()`, then on success, create a local `profiles` entry. Handle Supabase errors.
  - [x] 2.1.e: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **2.2: User Login (Email/Password) (`POST /auth/users/login`)**
  - [x] 2.2.a: Define Pydantic models in `auth_service/src/auth_service/schemas/user_schemas.py`: `UserLoginRequest` (for request) and `SupabaseSession` (for response).
  - [x] 2.2.b: Write integration tests:
    - Successful login.
    - Invalid credentials.
    - User not found (Supabase might return generic invalid creds).
  - [x] 2.2.c: Implement endpoint logic: call supabase.auth.sign_in_with_password(). Handle Supabase errors and return session/user data.
  - [x] 2.2.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **2.3: User Login (Magic Link) (`POST /auth/users/login/magiclink`)**
  - [x] 2.3.a: Define Pydantic model `MagicLinkLoginRequest` in `auth_service/src/auth_service/schemas/user_schemas.py`.
  - [x] 2.3.b: Write integration tests: successful request, invalid email.
  - [x] 2.3.c: Implement endpoint: call `supabase.auth.sign_in_with_otp()` (or equivalent for magic link).
  - [x] 2.3.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **2.4: User Logout (`POST /auth/users/logout`)**
  - [x] 2.4.a: Implement FastAPI dependency `get_current_supabase_user` in `auth_service/src/auth_service/dependencies/user_deps.py` to get current authenticated Supabase user from JWT.
  - [x] 2.4.b: Write integration tests: successful logout, invalid/expired token.
  - [x] 2.4.c: Implement endpoint: require Supabase JWT, call `supabase.auth.sign_out()`.
  - [x] 2.4.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **2.5: Password Reset Request (`POST /auth/users/password/reset`)**
  - [x] 2.5.a: Define Pydantic model `PasswordResetRequest` in `auth_service/src/auth_service/schemas/user_schemas.py`.
  - [x] 2.5.b: Write integration tests: successful request, email not found, invalid email, Supabase API errors.
  - [x] 2.5.c: Implement the endpoint in `user_auth_routes.py`..
  - [x] 2.5.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **2.6: Password Update (`POST /auth/users/password/update`)**
  - [x] 2.6.a: Define Pydantic model `PasswordUpdateRequest` in `auth_service/src/auth_service/schemas/user_schemas.py`.
  - [x] 2.6.b: Write integration tests: successful update, weak new password (if Supabase enforces), invalid current token.
  - [x] 2.6.c: Implement endpoint: require Supabase JWT, call `supabase.auth.update_user()` with new password.
  - [x] 2.6.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **2.7: OAuth Provider Login Initiation and Callback**
  - [x] 2.7.a: Define Pydantic models for OAuth, including `OAuthProvider` enum and `OAuthRedirectResponse`.
  - [x] 2.7.b: Write integration tests for OAuth login flows:
    - [x] 2.7.b.1: Test OAuth callback with new users (profile creation)
    - [x] 2.7.b.2: Test OAuth callback with existing users (profile retrieval)
    - [x] 2.7.b.3: Test state validation and error handling
  - [x] 2.7.c: Implement OAuth endpoints:
    - [x] 2.7.c.1: Initiate endpoint to generate OAuth URL and set state cookie
    - [x] 2.7.c.2: Callback endpoint to process provider response and create session
    - [x] 2.7.c.3: Handle profile creation for new OAuth users
  - [x] 2.7.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.

## Phase 3: User Profile Management (Auth Service Specific Data)

- [x] **3.1: Get User Profile (`GET /auth/users/me`)**
  - [x] 3.1.a: Define Pydantic response model `ProfileResponse` in `auth_service/src/auth_service/schemas/user_schemas.py` (based on `profiles` table fields).
  - [x] 3.1.b: Write integration tests:
    - Successful retrieval for authenticated user.
    - User profile not found (edge case, should exist if registered via this service).
    - Unauthenticated access.
  - [x] 3.1.c: Implement endpoint: require Supabase JWT, extract `user_id`, fetch from local `profiles` table.
  - [x] 3.1.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **3.2: Update User Profile (`PUT /auth/users/me`)**
  - [x] 3.2.a: Define Pydantic request model `ProfileUpdate` in `auth_service/src/auth_service/schemas/user_schemas.py`.
  - [x] 3.2.b: Write integration tests: (Covered: successful full/partial updates, username conflict, unauthenticated access, basic Pydantic validation for request model)
    - Successful update.
    - Validation errors (e.g., invalid username format if rules apply).
    - Unauthenticated access.
  - [x] 3.2.c: Implement endpoint: require Supabase JWT, extract `user_id`, update local `profiles` table.
  - [x] 3.2.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.

## Phase 4: `app_client` (M2M) Authentication & Management

- [x] **4.1: Client Secret Hashing Utilities**
  - [x] 4.1.a: Implement helper functions (`security.py`) to hash secrets (`passlib.hash.bcrypt.hash`) and verify secrets (`passlib.hash.bcrypt.verify`).
  - [x] 4.1.b: Write unit tests for these helper functions.
- [x] **4.2: M2M JWT Generation & Decoding Utilities**
  - [x] 4.2.a: Implement `create_m2m_access_token` in `security.py` to generate JWTs with `sub` (client_id), `roles`, `permissions`, `exp`, `iss`, `aud` claims.
  - [x] 4.2.b: Implement `decode_m2m_access_token` in `security.py` to validate and decode these JWTs, checking signature, expiry, issuer, and audience.
  - [x] 4.2.c: Write unit tests for JWT creation and decoding (success, expiry, invalid signature, wrong issuer/audience).
  - [x] 4.2.d: Ensure M2M JWT settings (secret, algorithm, issuer, audience, expiry) are in `config.py` and loaded from `.env`.
- [x] **4.3: Define Admin Auth Dependency**
  - [x] 4.3.a: Create a FastAPI dependency that verifies if the current user (from Supabase JWT) has an 'admin' role (this role will be manually assigned initially or via a seeding script). This is a placeholder; full RBAC for admins comes later but basic protection is needed now.
  - [x] 4.3.b: Write unit tests for this dependency (mocking user roles).
- [x] **4.4: Create `app_client` (`POST /auth/admin/clients`) (Admin Protected)**
  - [x] 4.4.a: Define Pydantic models for request (`AppClientCreateRequest`) and response (`AppClientCreatedResponse` - including plain secret once).
  - [x] 4.4.b: Write integration tests:
    - Successful creation, secret is returned.
    - Duplicate client name.
    - Unauthorized access (not admin).
  - [x] 4.4.c: Implement endpoint: Use admin dependency. Generate `client_id` (UUID), generate secure `client_secret`, hash it, store hash. Return plain secret once.
  - [x] 4.4.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **4.5: List/Get `app_clients` (Admin Protected)**
  - [x] 4.5.a: Define Pydantic response models (`AppClientResponse` - no secret, `AppClientListResponse`).
  - [x] 4.5.b: Write integration tests for `GET /auth/admin/clients` and `GET /auth/admin/clients/{client_id}`:
    - Successful retrieval.
    - Client not found.
    - Unauthorized access.
  - [x] 4.5.c: Implement endpoints using admin dependency.
  - [x] 4.5.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **4.6: Update `app_client` (`PUT /auth/admin/clients/{client_id}`) (Admin Protected)**
  - [x] 4.6.a: Define Pydantic request model (`AppClientUpdateRequest`).
  - [x] 4.6.b: Write integration tests: successful update, client not found, unauthorized.
  - [x] 4.6.c: Implement endpoint using admin dependency.
  - [x] 4.6.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **4.7: Delete `app_client` (`DELETE /auth/admin/clients/{client_id}`) (Admin Protected)**
  - [x] 4.7.a: Write integration tests: successful deletion, client not found, unauthorized.
  - [x] 4.7.b: Implement endpoint using admin dependency.
  - [x] 4.7.c: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **4.8: `app_client` Token Acquisition (`POST /auth/token`)**
  - [x] 4.8.a: Define Pydantic request (`AppClientTokenRequest` - `grant_type`, `client_id`, `client_secret`) and response (`AccessTokenResponse`).
  - [x] 4.8.b: Write integration tests:
    - Successful token grant for active client with correct credentials.
    - Invalid `client_id` or `client_secret`.
    - Inactive client.
    - Missing parameters.
    - Incorrect `grant_type`.
    - Verify JWT claims (`sub`, `roles`, `permissions` - roles/perms will be empty initially).
  - [x] 4.8.c: Implement endpoint: Validate `grant_type=client_credentials`. Verify `client_id` and `client_secret` (using hashed secret). Fetch client's roles/permissions (will be empty for now). Generate M2M JWT.
  - [x] 4.8.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.

## Phase 5: RBAC Implementation & Admin Endpoints

Define `RoleCreate`, `RoleUpdate`, `RoleResponse`, `PermissionCreate`, `PermissionUpdate`, `PermissionResponse` Pydantic models.

- [x] **5.1: CRUD for `roles` (`/auth/admin/roles`) (Admin Protected)**
  - [x] 5.1.a: Write integration tests for `POST`, `GET` (list & single), `PUT`, `DELETE` for roles.
  - [x] 5.1.b: Implement CRUD endpoints for `roles` using admin dependency.
  - [x] 5.1.c: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **5.2: CRUD for `permissions` (`/auth/admin/permissions`) (Admin Protected)**
  - [x] 5.2.a: Write integration tests for `POST`, `GET` (list & single), `PUT`, `DELETE` for permissions.
  - [x] 5.2.b: Implement CRUD endpoints for `permissions` using admin dependency.
  - [x] 5.2.c: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **5.3: Assign/Remove Permissions from Roles (`/auth/admin/roles/{role_id}/permissions`) (Admin Protected)**
  - [x] 5.3.a: Define Pydantic request for assigning permission ID.
  - [x] 5.3.b: Write integration tests for `POST /auth/admin/roles/{role_id}/permissions/{permission_id}` (or with request body) and `DELETE /auth/admin/roles/{role_id}/permissions/{permission_id}`. Test for role/permission not found, already assigned/not assigned.
  - [x] 5.3.c: Implement endpoints using admin dependency. Manage entries in `role_permissions` table.
  - [x] 5.3.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **5.4: Assign/Remove Roles for Human Users (`/auth/admin/users/{user_id}/roles`) (Admin Protected)**
  - [x] 5.4.a: Define Pydantic request for assigning role ID.
  - [x] 5.4.b: Write integration tests for `POST /auth/admin/users/{user_id}/roles/{role_id}` and `DELETE /auth/admin/users/{user_id}/roles/{role_id}`. Test for user/role not found, already assigned/not assigned. (Note: `user_id` is Supabase `auth.users.id`).
  - [x] 5.4.c: Implement endpoints using admin dependency. Manage entries in `user_roles` table.
  - [x] 5.4.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **5.5: Assign/Remove Roles for `app_clients` (`/auth/admin/clients/{client_id}/roles`) (Admin Protected)**
  - [x] 5.5.a: Define Pydantic request for assigning role ID.
  - [x] 5.5.b: Write integration tests for `POST /auth/admin/clients/{client_id}/roles/{role_id}` and `DELETE /auth/admin/clients/{client_id}/roles/{role_id}`. Test for client/role not found, already assigned/not assigned.
  - [x] 5.5.c: Implement endpoints using admin dependency. Manage entries in `app_client_roles` table.
  - [x] 5.5.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.
- [x] **5.6: Refine Admin Auth Dependency**
  - [x] 5.6.a: Update the admin auth dependency created in 4.3.a to check for specific admin roles/permissions (e.g., `role:admin_manage` permission) once RBAC is in place.
  - [x] 5.6.b: Write/update unit tests for this refined dependency.

## Phase 6: JWT Customization & Claims

- [x] **6.1: PostgreSQL Function for Supabase JWT Custom Claims `get_user_rbac_claims(user_id UUID)`**
  - [x] 6.1.a: Design the SQL function to query `user_roles`, `role_permissions`, `roles`, `permissions` tables (in `auth_service_data` schema) to aggregate roles and permissions for a given `user_id`.
  - [x] 6.1.b: Write the SQL function. It should return JSON like `{"roles": ["role_name_1"], "permissions": ["perm_slug_1"]}`.
  - [x] 6.1.c: Test the SQL function directly in PostgreSQL with sample data.
- [x] **6.2: Apply and Configure Supabase Custom Claims**
  - [x] 6.2.a: Apply the `get_user_rbac_claims` function to the Supabase PostgreSQL database.
  - [x] 6.2.b: Research and implement the Supabase configuration (e.g., Auth Hooks, `config.toml`, or triggers) to call this function and add its output to JWTs during user login/token refresh. Document this setup clearly.
  - [x] 6.2.c: Manually test the human user login flow and inspect the Supabase JWT to ensure custom claims are present.
- [x] **6.3: Update `app_client` Token Generation to Include RBAC Claims**
  - [x] 6.3.a: Modify the `POST /auth/token` endpoint (Task 4.8.c) to fetch the `app_client`'s assigned roles and their associated permissions.
  - [x] 6.3.b: Update the M2M JWT generation utility (Task 4.2.a) to include these roles and permissions in the `app_client` JWT.
  - [x] 6.3.c: Update integration tests for `POST /auth/token` (Task 4.8.b) to verify the presence and correctness of roles and permissions claims in the M2M JWT.
  - [x] 6.3.d: Run and verify all tests pass using 'docker-compose exec auth_service pytest'.

## Phase 7: Security, Middleware & Final Touches

- [x] **7.1: Rate Limiting Implementation (`slowapi`)**
  - [x] 7.1.a: Apply `slowapi` rate limiting to sensitive endpoints (login, token, registration, password reset).
  - [x] 7.1.b: Define sensible default limits (e.g., 5 requests per minute per IP) and ensure they are configurable via environment variables.
  - [x] 7.1.c: Implement a test-aware rate limiting solution that disables rate limiting during tests to prevent test interference.
  - [x] 7.1.d: Create a custom rate limit exceeded handler that provides useful information in the response.
  - [x] 7.1.e: Write tests to verify rate limiting is active and responds with 429 when limits are exceeded.
- [x] **7.2: Final Security Review of Endpoints and Dependencies**
  - [x] 7.2.a: Ensure all admin-only endpoints properly use the admin auth dependency.
  - [x] 7.2.b: Ensure all user-authenticated endpoints properly validate the Supabase JWT.
  - [x] 7.2.c: Review input validation (Pydantic models) for all endpoints.
- [x] **7.3: Ensure HTTPS is Enforced (Deployment Concern)**
  - [x] 7.3.a: Document that production deployment must be behind a reverse proxy (e.g., Nginx, Traefik) that handles TLS termination and enforces HTTPS.
  - [x] 7.3.b: If using Uvicorn with `--ssl-keyfile` and `--ssl-certfile` for local HTTPS testing, document this.

## Phase 8: Documentation

- [x] **8.1: Generate/Update OpenAPI Documentation**
  - [x] 8.1.a: Ensure FastAPI's OpenAPI docs (`/docs`, `/redoc`) are comprehensive.
  - [x] 8.1.b: Add detailed descriptions, examples for request/response bodies, and auth requirements to endpoint docstrings.
- [x] **8.2: Document JWT Claims Structure**
  - [x] 8.2.a: Create documentation (e.g., in `README.md` or a `docs/` folder) detailing the claims structure for human user (Supabase) JWTs and `app_client` (M2M) JWTs.
- [x] **8.3: Document Supabase Custom Claims Setup**
  - [x] 8.3.a: Document the SQL function and the Supabase configuration steps for custom claims.
- [x] **8.4: Document Environment Variables**
  - [x] 8.4.a: Ensure `.env.example` is complete and `README.md` lists all required environment variables and their purpose.
- [x] **8.5: Document Admin Bootstrapping / Seeding**
  - [x] 8.5.a: Document how the initial admin user is created and how the core RBAC components are seeded.

## Phase 9: Deployment Preparation & Finalization

- [ ] **9.1: Production Docker Configuration**

  - [x] 9.1.a: Write a multi-stage Dockerfile for a lean, secure production image:
    - [x] 9.1.a.1: Use Python 3.12 slim as base image
    - [x] 9.1.a.2: Install only production dependencies using Poetry
    - [x] 9.1.a.3: Implement proper user permissions (non-root user)
    - [x] 9.1.a.4: Configure reasonable health checks and defaults
  - [x] 9.1.b: Create optimized docker-compose.prod.yml for production-like deployments
  - [x] 9.1.c: Test building and running the production Docker image locally

- [x] **9.2: Implement Admin and RBAC Bootstrapping**

  - [x] 9.2.a: Create a bootstrap.py module that runs during application startup
  - [x] 9.2.b: Implement automatic creation of initial admin user if none exists
  - [x] 9.2.c: Create core roles (admin, user, service) and base permissions automatically
  - [x] 9.2.d: Add configurable environment variables for initial admin credentials
  - [x] 9.2.e: Write tests to verify the bootstrapping process

- [x] **9.3: Production Logging and Monitoring**

  - [x] 9.3.a: Configure structured JSON logging for production
  - [x] 9.3.b: Implement request ID generation and tracking across components
  - [x] 9.3.c: Add health check endpoints with appropriate metrics
  - [x] 9.3.d: Document monitoring recommendations (e.g., Prometheus, Grafana)

## Phase 10: Kubernetes (AWS EKS) Infrastructure Setup (Manual Steps - First Time Only)

This phase details the one-time setup of the AWS EKS infrastructure required to host the application. These steps are typically performed manually or via Infrastructure as Code (IaC) tools outside the application's CI/CD for the initial environment provisioning.

- [x] **10.1: AWS Account and CLI Setup**
  - [x] 10.1.a: Ensure an active AWS account is available.
  - [x] 10.1.b: Install AWS CLI locally (`brew install awscli` or official installer).
  - [x] 10.1.c: Configure AWS CLI with an IAM user (`paauth-service-user` or similar) that has sufficient permissions to create EKS clusters and related resources.
    - Action: Run `aws configure` and provide Access Key ID, Secret Access Key, default region, and output format.
    - Note: For initial cluster creation, this user might temporarily need broad permissions (e.g., `AdministratorAccess`). These should be scoped down post-setup.
- [x] **10.2: Install `eksctl` and `kubectl` Locally**
  - [x] 10.2.a: Install `eksctl` CLI (`curl ... | tar ...; sudo mv ...`).
  - [x] 10.2.b: Install `kubectl` CLI (`brew install kubectl` or official installer).
- [x] **10.3: Create AWS EKS Cluster (`paauth-cluster`)**
  - [x] 10.3.a: Decide on Kubernetes version (e.g., 1.32), region, node type (e.g., `t3.medium`), and node count.
  - [x] 10.3.b: Run `eksctl create cluster` command with appropriate flags:
    ```bash
    # Example:
    eksctl create cluster --name paauth-cluster \
                          --version 1.32 \
                          --region YOUR_AWS_REGION \
                          --nodegroup-name standard-workers \
                          --node-type t3.medium \
                          --nodes 2 \
                          --nodes-min 1 \
                          --nodes-max 3 \
                          --managed \
                          --with-oidc \
                          --alb-ingress-access
    ```
  - [x] 10.3.c: Wait for cluster creation (15-25 minutes).
  - [x] 10.3.d: Verify `kubectl` access to the new cluster (`kubectl get nodes`). `eksctl` auto-updates `~/.kube/config`.
- [x] **10.4: Set up IAM Roles for Service Accounts (IRSA) for AWS Load Balancer Controller**
  - [x] 10.4.a: Download the IAM policy JSON for the AWS Load Balancer Controller (ensure using a recent version URL).
    ```bash
    # Example for a specific version:
    curl -o iam_policy.json https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.13.2/docs/install/iam_policy.json
    ```
  - [x] 10.4.b: Create the IAM policy in AWS using the downloaded JSON.
    ```bash
    aws iam create-policy \
        --policy-name AWSLoadBalancerControllerIAMPolicy \
        --policy-document file://iam_policy.json
    ```
    (Note the ARN of the created policy).
  - [x] 10.4.c: Create the IAM service account for the AWS Load Balancer Controller using `eksctl`.
    ```bash
    eksctl create iamserviceaccount \
      --cluster=paauth-cluster \
      --namespace=kube-system \
      --name=aws-load-balancer-controller \
      --role-name "AmazonEKSLoadBalancerControllerRole" \
      --attach-policy-arn=arn:aws:iam::YOUR_ACCOUNT_ID:policy/AWSLoadBalancerControllerIAMPolicy \
      --approve \
      --region YOUR_AWS_REGION
    ```
- [x] **10.5: Install In-Cluster Components using Helm**
  - [x] 10.5.a: Install Helm locally (`brew install helm`).
  - [x] 10.5.b: Install AWS Load Balancer Controller.
    ```bash
    helm repo add eks https://aws.github.io/eks-charts && helm repo update eks
    helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
      -n kube-system \
      --set clusterName=paauth-cluster \
      --set serviceAccount.create=false \
      --set serviceAccount.name=aws-load-balancer-controller \
      --set region YOUR_AWS_REGION \
      --set vpcId YOUR_VPC_ID
    ```
    (Get `YOUR_VPC_ID` using `eksctl get cluster --name paauth-cluster -o json | jq -r '.[0].ResourcesVpcConfig.VpcId'`).
  - [x] 10.5.c: Install Nginx Ingress Controller.
    ```bash
    helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx && helm repo update ingress-nginx
    helm install ingress-nginx ingress-nginx/ingress-nginx \
      --create-namespace \
      --namespace ingress-nginx \
      --set controller.ingressClass=nginx \
      --set controller.ingressClassResource.name=nginx \
      --set controller.ingressClassResource.enabled=true \
      --set controller.ingressClassResource.default=false \
      --set controller.admissionWebhooks.patch.nodeSelector."kubernetes\.io/os"=linux \
      --set controller.service.type=NodePort
    ```
  - [x] 10.5.d: Install Cert-Manager for TLS.
    ```bash
    kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/vX.Y.Z/cert-manager.crds.yaml # Use latest CRD version
    helm repo add jetstack https://charts.jetstack.io && helm repo update jetstack
    helm install cert-manager jetstack/cert-manager \
      --namespace cert-manager \
      --create-namespace \
      --version vX.Y.Z # Use latest chart version
    ```
  - [x] 10.5.e: Create `ClusterIssuer` for Let's Encrypt. (Create `letsencrypt-prod-issuer.yaml` and `kubectl apply -f letsencrypt-prod-issuer.yaml`).
  - [x] 10.5.f: Install Redis using Helm (e.g., Bitnami chart).
    ```bash
    helm repo add bitnami https://charts.bitnami.com/bitnami && helm repo update
    helm install paauth-redis bitnami/redis \
      --namespace default \ # Or a dedicated namespace
      --set auth.password="YOUR_STRONG_REDIS_PASSWORD" # Set other values as needed
    ```
    (Note the Redis service DNS name and password).
- [x] **10.6: Database Setup (Alembic for Supabase Cloud)**
  - [x] 10.6.a: Ensure Supabase Cloud project is ready.
  - [x] 10.6.b: Clean custom application tables and `alembic_version` table from Supabase Cloud DB (if any previous attempts).
  - [x] 10.6.c: In `auth_service/.env`, ensure `AUTH_SERVICE_DATABASE_URL` points to Supabase Cloud (preferably pooler URL).
  - [x] 10.6.d: Delete old migration files from `auth_service/alembic/versions/`.
  - [x] 10.6.e: In `auth_service/alembic/env.py`, refine `include_object` to exclude Supabase's `auth` schema from modification by autogenerate.
  - [x] 10.6.f: From `auth_service/` directory, run `poetry run alembic revision -m "initial_schema_setup" --autogenerate`.
  - [x] 10.6.g: Review the generated migration script. Ensure it ONLY creates your application tables and does NOT modify `auth` schema.
  - [x] 10.6.h: Run `poetry run alembic upgrade head` to apply the initial schema to Supabase Cloud.
- [x] **10.7: Configure `aws-auth` ConfigMap in EKS**
  - [x] 10.7.a: Map the IAM user used by GitHub Actions (`paauth-service-user`) to a Kubernetes user/group with sufficient permissions (e.g., `system:masters` for initial setup, or a custom role).
    ```bash
    kubectl edit configmap aws-auth -n kube-system
    # Add to mapUsers:
    # - userarn: arn:aws:iam::YOUR_ACCOUNT_ID:user/paauth-service-user
    #   username: github-actions-paauth
    #   groups:
    #     - system:masters
    ```

## Phase 11: CI/CD Pipeline Setup & Deployment (GitHub Actions)

- [x] **11.1: Prepare Kubernetes Manifests**
- [x] 11.1.a: Create/Finalize `k8s/secrets.yaml` (placeholders for actual secret values).
- [x] 11.1.b: Create/Finalize `k8s/deployment.yaml` (placeholders for image name/tag).
- [x] 11.1.c: Create/Finalize `k8s/service.yaml`.
- [x] 11.1.d: Create/Finalize `k8s/ingress.yaml` (placeholders for auth domain, references Nginx class and Cert-Manager issuer).
- [x] 11.1.e: Create `k8s/migration-job.yaml` to run Alembic migrations.
- [x] **11.2: Configure GitHub Secrets**
  - [x] 11.2.a: Set up repository or environment secrets in GitHub for `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AUTH_DOMAIN`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `AUTH_SERVICE_DATABASE_URL` (Supabase pooler URL), `M2M_JWT_SECRET_KEY`, `REDIS_URL` (internal EKS Redis service URL with password).
- [x] **11.3: Finalize GitHub Actions Workflow (`.github/workflows/deploy-k8s.yml`)**
  - [x] 11.3.a: Ensure build job pushes to Docker Hub.
  - [x] 11.3.b: Ensure deploy job configures AWS creds, `kubectl`.
  - [x] 11.3.c: Implement step to prepare/substitute variables in K8s manifests.
  - [x] 11.3.d: Implement step to apply `paauth-secrets` K8s Secret.
  - [x] 11.3.e: Implement step to run the database migration K8s Job and wait for completion.
  - [x] 11.3.f: Implement steps to apply deployment, service, and ingress.
  - [x] 11.3.g: Implement step to verify deployment rollout.
- [x] **11.4: Initial Deployment via GitHub Actions**
  - [x] 11.4.a: Commit all code, K8s manifests, and workflow files. Push to `main`/`master` or trigger `workflow_dispatch`.
  - [x] 11.4.b: Monitor the GitHub Actions workflow run.
- [x] **11.4.c: K8s Deployment Debugging and Fixes**
  - [x] 11.4.c.i: Fix invalid escape sequences in PostgreSQL connection options by using raw string literals and properly quoting 'read committed'.
  - [x] 11.4.c.ii: Address pgBouncer mode conflicts by setting `USE_PGBOUNCER=false` consistently in both deployment and secrets.
  - [x] 11.4.c.iii: Add explicit environment variable references from Kubernetes secrets in deployment manifest.
  - [x] 11.4.c.iv: Add debugging commands in container startup to verify environment variable presence.
- [ ] **11.5: Post-Deployment DNS Configuration**
  - [ ] 11.5.a: After the Ingress is created by the workflow, get the AWS ALB DNS name (`kubectl get ingress paauth-ingress -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'`).
  - [ ] 11.5.b: Update your `AUTH_DOMAIN`'s CNAME record at your DNS provider to point to this ALB DNS name (k8s-ingressn-ingressn-59ed0fe6fd-571865a27d56a53b.elb.us-east-1.amazonaws.com).
  - [ ] 11.5.c: Verify Cert-Manager issues a TLS certificate.
- [ ] **11.6: Test Deployed Application**
  - [ ] 11.6.a: Access the application via `https://auth.supersami.com`.
  - [ ] 11.6.b: Perform end-to-end tests.
- [ ] **11.7: Security Hardening (Post Initial Setup)**
  - [ ] 11.7.a: Review and scope down IAM permissions for `paauth-service-user` to least privilege.
  - [ ] 11.7.b: Review and scope down Kubernetes RBAC for the CI/CD user (move away from `system:masters`).

## Phase 12: Documentation and Handover (Original Phase 9.6)

- [ ] **12.1: Create comprehensive deployment documentation**
- [ ] **12.2: Document scaling considerations and limitations**
- [ ] **12.3: Prepare runbook for common operations and troubleshooting**
- [ ] **12.4: Update API documentation with production-specific notes**
- [ ] **12.5: Final Quality Assurance**

## Phase 13: Additional Security and Quality Improvements

- [ ] **13.1: Email Verification Enhancement**

  - [ ] 13.1.a: Implement email verification resend functionality at endpoint `/auth/users/verify/resend`.
  - [ ] 13.1.b: Add tests to verify the resend functionality works correctly.
  - [ ] 13.1.c: Document the email verification flow in the API documentation.

- [x] **13.2: Enhanced Audit Logging**

  - [x] 13.2.a: Implement structured logging for security-critical events (login attempts, admin actions, etc.).
  - [x] 13.2.b: Add request IDs to all requests for better traceability.
  - [x] 13.2.c: Create a logging middleware that captures request and response metadata.
  - [x] 13.2.d: Ensure sensitive data is not logged (passwords, tokens, etc.).

- [ ] **13.3: Token Revocation Mechanism**

  - [ ] 13.3.a: Design and implement a token denylist/blocklist for critical revocation cases.
  - [ ] 13.3.b: Add an endpoint for token revocation (`POST /auth/token/revoke`).
  - [ ] 13.3.c: Implement a Redis-based storage for the token denylist (optional, can use database initially).
  - [ ] 13.3.d: Update token validation to check against the denylist.

- [ ] **13.4: Multi-Factor Authentication**

  - [ ] 13.4.a: Implement MFA enrollment endpoint (`POST /auth/users/mfa/enroll`).
  - [ ] 13.4.b: Implement MFA challenge endpoint (`POST /auth/users/mfa/challenge`).
  - [ ] 13.4.c: Update login flow to accommodate MFA verification.
  - [ ] 13.4.d: Add tests for MFA enrollment and verification.

- [ ] **13.5: Expanded Test Coverage**
  - [ ] 13.5.a: Add more integration tests for admin endpoints.
  - [ ] 13.5.b: Implement load testing for performance requirements.
  - [ ] 13.5.c: Add security-focused tests (e.g., test rate limiting, token validation edge cases).

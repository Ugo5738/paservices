# Auth Service

## Overview

The Auth Service is a critical component of the Paservices platform responsible for managing user authentication, authorization, and identity management. This service integrates with Supabase Auth for underlying authentication while implementing custom permission models, profiles, API key management, and service-to-service authentication features.

## Technical Stack

- **Framework**: FastAPI with async support
- **Database**: PostgreSQL via SQLAlchemy 2.0 (async)
- **Migration**: Alembic
- **Authentication**: Supabase Auth integration + JWT
- **Testing**: Pytest with async fixtures
- **Documentation**: Swagger UI / OpenAPI

## Features

- User authentication & registration
- Role-based access control
- API key generation and management
- Profile management
- Application client registration and management
- Service-to-service authentication
- JWT token validation and generation

## Project Structure

```
auth_service/
├── alembic/               # Database migration configuration and versions
├── scripts/               # Utility scripts for setup, testing and migration
├── src/
│   └── auth_service/
│       ├── api/           # API endpoints and routers
│       ├── config/        # Configuration settings
│       ├── core/          # Core functionality
│       ├── crud/          # Database CRUD operations
│       ├── db.py          # Database connection setup
│       ├── models/        # SQLAlchemy models
│       ├── schemas/       # Pydantic schemas for validation
│       └── utils/         # Utility functions
├── tests/                 # Test suite
│   ├── unit/              # Unit tests
│   └── integration/       # Integration tests
├── .env.example           # Example environment variables
├── alembic.ini            # Alembic configuration
├── pyproject.toml         # Python dependencies and project metadata
├── Dockerfile             # Container configuration
└── MIGRATIONS.md          # Detailed migration documentation
```

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 15+ (local or Supabase instance)
- Docker and Docker Compose (optional)

### Environment Setup

1. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd auth_service
   ```

2. **Create a virtual environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -e .
   ```

4. **Copy environment template**:

   ```bash
   cp .env.example .env
   ```

5. **Configure environment variables**:
   Edit the `.env` file with your database connection details and other settings.

### Database Setup

The auth_service database has a critical dependency on Supabase's auth schema. Follow these steps to set up a development database correctly:

1. **Create a development database**:

   ```bash
   createdb -h 127.0.0.1 -p 54322 -U postgres auth_dev_db
   ```

2. **Set up the auth schema** (required for Supabase integration):

   ```bash
   python scripts/copy_auth_schema.py --source-db postgres --target-db auth_dev_db --host 127.0.0.1 --port 54322
   ```

3. **Run migrations**:

   ```bash
   alembic upgrade head
   ```

4. **Verify migrations**:
   ```bash
   python scripts/verify_migrations.py
   ```

### Running the Service

**Development Mode**:

```bash
uvicorn src.auth_service.main:app --reload --host 0.0.0.0 --port 8000
```

**Production Mode**:

```bash
uvicorn src.auth_service.main:app --host 0.0.0.0 --port 8000
```

## API Documentation

When the service is running, access the API documentation at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Development Workflow

### Creating New Endpoints

1. Define Pydantic schemas in `src/auth_service/schemas/`
2. Create CRUD operations in `src/auth_service/crud/`
3. Implement API endpoints in `src/auth_service/api/`
4. Add appropriate tests in `tests/`

### Database Migrations

The auth_service uses a special migration approach due to its integration with Supabase's auth schema:

1. **Add or modify models** in `src/auth_service/models/`
2. **Generate a migration**:
   ```bash
   alembic revision --autogenerate -m "describe_changes"
   ```
3. **Review the generated migration** in `alembic/versions/`
   - If the migration includes auth schema tables, modify it to skip those tables
4. **Apply the migration**:
   ```bash
   alembic upgrade head
   ```
5. **Verify your changes**:
   ```bash
   python scripts/verify_migrations.py
   ```

For a complete migration guide, see [MIGRATIONS.md](./MIGRATIONS.md).

### Common Issues and Solutions

#### Circular Import Issues

- Use string-based relationship references (`"src.auth_service.models.SomeModel"`)
- Import models through `src.auth_service.models` module (preferred), not directly
- Ensure models are correctly registered with `Base.metadata`

#### Auth Schema Issues

- The `auth` schema is managed by Supabase, not Alembic
- Always run the `copy_auth_schema.py` script before migrations on a fresh database
- If migrations try to create `auth` tables, modify the migration to skip them

## Testing

The service includes comprehensive testing capabilities:

```bash
# Run all tests
pytest

# Run specific test groups
pytest tests/unit/
pytest tests/integration/

# Test coverage report
pytest --cov=src/auth_service
```

## Integration with Other Services

The auth_service provides authentication for other services in the Paservices platform:

- **Token validation**: Other services can validate JWT tokens issued by the auth_service
- **Service-to-service authentication**: Secure communication between microservices
- **User permissions**: Central authority for user roles and permissions

## Architecture Highlights

- **Async First**: Fully asynchronous request handling and database access
- **Clean Architecture**: Separation of concerns between models, schemas, and CRUD operations
- **Type Safety**: Comprehensive type hints throughout the codebase
- **Security Focus**: JWT-based authentication with proper token handling

## Contributing

1. Follow the project's code style and architecture patterns
2. Write tests for new features
3. Update documentation when making changes
4. Use descriptive commit messages

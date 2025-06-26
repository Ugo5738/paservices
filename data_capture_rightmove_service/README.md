# Data Capture Rightmove Service

A microservice for capturing and processing property data from the Rightmove API.

## Architecture

This service follows the PA Services microservice architecture patterns with standardized configurations and utilities:

- **FastAPI** for the REST API framework
- **SQLAlchemy 2.0** with async capabilities for database operations
- **Pydantic V2** for data validation and serialization
- **JWT-based authentication** for service-to-service communication
- **Rate limiting** to protect downstream services and APIs
- **Structured JSON logging** for production environments
- **Alembic** for database migrations

## Project Structure

```
data_capture_rightmove_service/
├── alembic/                      # Database migration files
├── k8s/                          # Kubernetes deployment manifests
├── src/
│   └── data_capture_rightmove_service/
│       ├── clients/              # API clients for external services
│       ├── crud/                 # Database CRUD operations
│       ├── models/               # SQLAlchemy ORM models
│       ├── routers/              # API route handlers
│       ├── schemas/              # Pydantic models for request/response validation
│       ├── utils/                # Utility modules for logging, security, etc.
│       ├── config.py             # Configuration settings with environment variables
│       ├── db.py                 # Database connection management
│       ├── main.py               # Application entrypoint
├── tests/                        # Test suite
├── alembic.ini                   # Alembic configuration
├── docker-compose.yml            # Local development environment
├── Dockerfile                    # Container build configuration
├── pyproject.toml                # Project metadata and dependencies
└── README.md                     # Project documentation
```

## Environment Variables

The service uses environment variables with the `DATA_CAPTURE_RIGHTMOVE_SERVICE_` prefix to avoid conflicts with other services:

| Variable                                            | Description                                                | Default                  |
| --------------------------------------------------- | ---------------------------------------------------------- | ------------------------ |
| DATA_CAPTURE_RIGHTMOVE_SERVICE_ENVIRONMENT          | Application environment (development, testing, production) | development              |
| DATA_CAPTURE_RIGHTMOVE_SERVICE_ROOT_PATH            | API root path for reverse proxies                          | /api/v1                  |
| DATA_CAPTURE_RIGHTMOVE_SERVICE_LOGGING_LEVEL        | Logging level                                              | INFO                     |
| DATA_CAPTURE_RIGHTMOVE_SERVICE_DATABASE_URL         | PostgreSQL connection string                               | (Required)               |
| DATA_CAPTURE_RIGHTMOVE_SERVICE_AUTH_SERVICE_URL     | URL for the Auth Service API                               | (Required)               |
| DATA_CAPTURE_RIGHTMOVE_SERVICE_SUPER_ID_SERVICE_URL | URL for the Super ID Service API                           | (Required)               |
| DATA_CAPTURE_RIGHTMOVE_SERVICE_M2M_CLIENT_ID        | Client ID for machine-to-machine auth                      | (Required)               |
| DATA_CAPTURE_RIGHTMOVE_SERVICE_M2M_CLIENT_SECRET    | Client secret for machine-to-machine auth                  | (Required)               |
| DATA_CAPTURE_RIGHTMOVE_SERVICE_JWT_SECRET_KEY       | Secret key for JWT validation                              | (Required)               |
| DATA_CAPTURE_RIGHTMOVE_SERVICE_REDIS_URL            | Redis connection string                                    | redis://localhost:6379/0 |
| DATA_CAPTURE_RIGHTMOVE_SERVICE_RATE_LIMIT           | Rate limit configuration                                   | 100/minute               |
| DATA_CAPTURE_RIGHTMOVE_SERVICE_RAPIDAPI_KEY         | API key for RapidAPI                                       | (Required)               |

## Local Development

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- PostgreSQL 15+
- Redis

### Setup

1. Clone the repository:

```bash
git clone https://github.com/your-organization/paservices.git
cd paservices/data_capture_rightmove_service
```

2. Set up the development environment:

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

3. Start services with Docker Compose:

```bash
docker-compose up -d
```

4. Run database migrations:

```bash
alembic upgrade head
```

5. Start the development server:

```bash
uvicorn data_capture_rightmove_service.main:app --reload
```

The API will be available at http://localhost:8000

### Database Migrations

Create a new migration:

```bash
alembic revision --autogenerate -m "description"
```

Apply migrations:

```bash
alembic upgrade head
```

## Testing

Run the test suite:

```bash
pytest
```

Run with coverage report:

```bash
pytest --cov=data_capture_rightmove_service
```

## Deployment

### Docker

Build the container:

```bash
docker build -t data-capture-rightmove-service:latest .
```

### Kubernetes

1. Create the required namespace (if not already created):

```bash
kubectl create namespace paservices
```

2. Apply ConfigMap:

```bash
kubectl apply -f k8s/configmap.yaml
```

3. Create secrets (replace placeholders with actual values):

```bash
# Create from template
envsubst < k8s/secret.yaml.template > k8s/secret.yaml
# Apply secret
kubectl apply -f k8s/secret.yaml
```

4. Deploy the service:

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

## API Documentation

When the service is running, OpenAPI documentation is available at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Security

- All endpoints are protected with JWT authentication
- M2M (machine-to-machine) authentication uses OAuth2 client credentials flow
- Tokens are validated with scope enforcement
- Rate limiting is applied to prevent abuse

## Additional Documentation

For more detailed documentation on specific components, refer to the following:

- [API Client Documentation](docs/api-clients.md)
- [Database Model Documentation](docs/database-models.md)
- [Deployment Guidelines](docs/deployment.md)

curl -X POST "http://localhost:8003/api/v1/properties/fetch/combined" -H "Content-Type: application/json" -d '{"property_url": "https://www.rightmove.co.uk/properties/154508327#/?channel=RES_LET"}' | jq

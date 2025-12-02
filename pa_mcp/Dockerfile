# pa_mcp/Dockerfile
FROM python:3.12-slim

# Poetry setup (consistent with super_id_service)
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=false \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install deps
RUN poetry install --no-root

# Copy code
COPY . .

# Expose MCP port
EXPOSE 8000

# Run MCP server with autoreload
CMD ["uvicorn", "pa_mcp.server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

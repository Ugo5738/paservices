FROM python:3.12-slim

# Set environment variables
# PYTHONUNBUFFERED: Prevents Python from buffering stdout and stderr
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files to disc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set Poetry configuration
# POETRY_NO_INTERACTION: Disables interactive prompts
# POETRY_VIRTUALENVS_CREATE: Tells Poetry not to create a new virtual environment
# POETRY_CACHE_DIR: Specifies a custom cache directory for Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/tmp/poetry_cache'

# Set pip timeout
ENV PIP_DEFAULT_TIMEOUT=100

# Explicitly add /app/src to PYTHONPATH
ENV PYTHONPATH="${PYTHONPATH}:/app/src"

# System dependencies for some Python packages
# build-essential: Common packages required for compiling software
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry
# Ensure poetry's install location is in PATH
ENV PATH="/root/.local/bin:/usr/local/bin:${PATH}"

# Diagnostic commands to find poetry
RUN which poetry
RUN poetry --version

WORKDIR /app

# Copy only essential files for dependency installation
COPY pyproject.toml poetry.lock ./

# Install project dependencies strictly from the lock file
# --sync ensures that the environment matches the lock file exactly
# --no-root because we are not installing the application itself as editable
# --with dev to include development dependencies
RUN poetry install --sync --no-root --with dev

# Re-install poetry CLI in case 'poetry install --sync' removed it when not using venvs
RUN pip install --no-cache-dir poetry
RUN which poetry 

# Copy the rest of the application code
COPY . .

# Expose port
EXPOSE 8000

# Default command
CMD ["uvicorn", "auth_service.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add the parent directory to the path so we can import the models
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import the models metadata for autogenerate support
from super_id_service.models import Base
target_metadata = Base.metadata

# Get database URL from environment variable
def get_url():
    # Get database URL from environment with proper connection string format
    # Uses single quotes for values with spaces in the options parameter
    url = os.getenv("SUPER_ID_SERVICE_DATABASE_URL")
    
    if not url:
        # Fallback for local development
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "postgres")
        db_name = os.getenv("DB_NAME", "super_id_db")
        
        # Note: Using single quotes for values with spaces as per best practices
        url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}?sslmode=prefer&options='--client_encoding=utf8 --timezone=UTC --default_transaction_isolation=\\'read committed\\''"
    
    return url

def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode."""
    # Override the database URL
    alembic_config = config.get_section(config.config_ini_section)
    alembic_config["sqlalchemy.url"] = get_url()
    
    connectable = engine_from_config(
        alembic_config,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

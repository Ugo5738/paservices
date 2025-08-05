# floorplan_service/scripts/manage_db.py

import argparse
import asyncio
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict

# --- Path Setup ---
service_dir = Path(__file__).parent.parent.absolute()
project_root = service_dir.parent
sys.path.insert(0, str(service_dir / "src"))
sys.path.insert(0, str(project_root))

from floorplan_service.config import settings

# --- Logging and Helpers ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("manage_db")


def colored(text: str, color: str) -> str:
    """Applies ANSI color codes to text for better terminal output."""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "reset": "\033[0m",
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"


def run_command(command: str, check: bool = True):
    logger.info(colored(f"--- Running: {command} ---", "yellow"))
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=service_dir,
            bufsize=1,
        )
        for line in iter(process.stdout.readline, ""):
            print(line, end="")
        process.wait()
        if check and process.returncode != 0:
            raise RuntimeError(f"Command failed with exit code {process.returncode}")
    except Exception as e:
        logger.error(
            colored(f"An error occurred while running the command: {e}", "red")
        )
        raise


def get_db_params_from_url(db_url: str) -> dict:
    from urllib.parse import urlparse

    parsed = urlparse(str(db_url))
    return {
        "user": parsed.username or "postgres",
        "password": parsed.password or "postgres",
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "dbname": parsed.path.lstrip("/"),
    }


def create_db(db_params: Dict):
    """Creates the service-specific database if it doesn't exist."""
    db_name = db_params["dbname"]
    admin_db_name = "postgres"  # Default DB to connect to for CREATE DATABASE
    logger.info(
        f"Ensuring database '{db_name}' exists on host '{db_params['host']}'..."
    )

    conn_str_admin = f"postgresql://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/{admin_db_name}"

    try:
        # The `check=False` allows the command to "fail" gracefully if the DB already exists.
        run_command(
            f'psql "{conn_str_admin}" -c "CREATE DATABASE {db_name}"', check=False
        )
        logger.info(
            colored(f"Database '{db_name}' created or already exists.", "green")
        )
    except Exception as e:
        logger.warning(f"Could not create database (it may already exist). Error: {e}")


async def delete_db(db_params: dict):
    """Deletes the service-specific database."""
    db_name = db_params["dbname"]
    logger.info(f"Deleting database '{db_name}'...")
    conn_str_admin = f"postgresql://{db_params['user']}:{db_params['password']}@{db_params['host']}:{db_params['port']}/postgres"
    # Terminate connections and drop
    run_command(
        f'psql "{conn_str_admin}" -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = \'{db_name}\';"',
        check=False,
    )
    run_command(f'psql "{conn_str_admin}" -c "DROP DATABASE IF EXISTS {db_name}"')
    logger.info(colored(f"Database '{db_name}' deleted.", "green"))


def reset_migrations():
    versions_dir = service_dir / "alembic" / "versions"
    logger.info(
        colored(f"--- Resetting migration history in {versions_dir} ---", "yellow")
    )
    if versions_dir.exists():
        for item in versions_dir.glob("*.py"):
            if item.name != "__init__.py":
                logger.info(f"Deleting migration file: {item.name}")
                item.unlink()
    else:
        versions_dir.mkdir(parents=True)
    (versions_dir / "__init__.py").touch(exist_ok=True)
    logger.info(colored("Migration history has been reset.", "green"))


# Placeholder for future bootstrap logic
async def bootstrap_service():
    logger.info("Running service data bootstrap for floorplan_service...")
    # Add any data seeding logic here if needed in the future
    logger.info(colored("Bootstrap complete (no-op for now).", "green"))


async def recreate_environment(db_params: Dict):
    """
    Stops, resets, and restarts the entire Supabase stack, then migrates and bootstraps the database.
    This is the definitive way to get a clean slate.
    """
    logger.info("--- Recreating environment for Floorplan Service ---")
    # logger.info("--- Stopping Supabase stack for a full reset ---")
    # run_command("supabase stop --no-backup")
    # logger.info(colored("Supabase stack stopped.", "green"))

    # time.sleep(2)

    # logger.info("--- Starting a fresh Supabase stack ---")
    # run_command("supabase start")
    # logger.info(colored("Fresh Supabase stack is running.", "green"))

    # time.sleep(5)

    await delete_db(db_params)

    # Create our application-specific database
    logger.info("--- Creating application database ---")
    create_db(db_params)

    reset_migrations()
    run_command("alembic revision --autogenerate -m 'Initial schema'")
    run_command("alembic upgrade head")

    # Verify the tables were created before bootstrapping
    logger.info("--- Verifying database schema before bootstrap ---")
    run_command(
        f"psql -h {db_params['host']} -p {db_params['port']} -U {db_params['user']} -d {db_params['dbname']} -c '\\dt floorplan_service_data.*'"
    )


# --- Main Command Floorplan ---
async def main():
    parser = argparse.ArgumentParser(
        description=f"{settings.PROJECT_NAME} Database Management Tool"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "init", help="Fully initializes the database (create, migrate, bootstrap)."
    )
    subparsers.add_parser(
        "recreate", help="Deletes and then fully initializes the database."
    )
    subparsers.add_parser("delete-db", help="Deletes the database entirely.")
    create_mig_parser = subparsers.add_parser(
        "create-migration", help="Create a new Alembic migration file."
    )
    create_mig_parser.add_argument(
        "-m", "--message", required=True, help="Migration description."
    )
    subparsers.add_parser(
        "upgrade", help="Apply all pending migrations to the database."
    )
    downgrade_parser = subparsers.add_parser(
        "downgrade", help="Downgrade migrations by a number of steps."
    )
    downgrade_parser.add_argument(
        "-s",
        "--step",
        type=int,
        default=1,
        help="Number of steps to downgrade (default: 1).",
    )
    subparsers.add_parser(
        "verify", help="Verify that the DB schema matches the SQLAlchemy models."
    )

    args = parser.parse_args()

    # Set PGPASSWORD for psql and pg_dump commands
    db_params = get_db_params_from_url(str(settings.DATABASE_URL))
    os.environ["PGPASSWORD"] = db_params["password"]

    try:
        if args.command == "init":
            create_db(db_params)
            run_command("alembic upgrade head")
        elif args.command == "recreate":
            await recreate_environment(db_params)
        elif args.command == "delete-db":
            await delete_db(db_params)
        elif args.command == "create-migration":
            run_command(f'alembic revision --autogenerate -m "{args.message}"')
        elif args.command == "upgrade":
            run_command("alembic upgrade head")
        elif args.command == "downgrade":
            run_command(f"alembic downgrade -{args.step}")
        elif args.command == "verify":
            run_command("alembic check")

        print(colored("\nOperation completed successfully.", "green"))

    except Exception as e:
        logger.error(colored(f"\nOperation failed: {e}", "red"), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

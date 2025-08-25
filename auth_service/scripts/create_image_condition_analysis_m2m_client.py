# auth_service/scripts/create_image_condition_analysis_m2m_client.py
import asyncio
import os
import sys
import uuid
from pathlib import Path

# Add the project's 'src' directory to the Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUTH_SERVICE_SRC = PROJECT_ROOT / "auth_service" / "src"
sys.path.insert(0, str(AUTH_SERVICE_SRC))

from sqlalchemy.future import select

from auth_service.db import AsyncSessionLocal
from auth_service.models.app_client import AppClient
from auth_service.models.role import Role
from auth_service.security import hash_secret

# --- Configuration for the new M2M Client ---
CLIENT_ID = (
    "a4b1c2d3-e4f5-4a5b-8c6d-7e8f9a0b1c2d"  # A new, unique UUID for this service
)
CLIENT_NAME = "image-condition-analysis-service"
CLIENT_SECRET = "dev-image-condition-analysis-service-secret"
ROLE_TO_ASSIGN = "service"  # The generic role for internal services


def print_color(text: str, color: str):
    colors = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "blue": "\033[94m",
        "reset": "\033[0m",
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")


async def create_client():
    print_color(f"--- Creating M2M Client: {CLIENT_NAME} ---", "yellow")
    async with AsyncSessionLocal() as db:
        try:
            # Check if the role exists
            role = (
                (await db.execute(select(Role).where(Role.name == ROLE_TO_ASSIGN)))
                .scalars()
                .first()
            )
            if not role:
                print_color(
                    f"ERROR: Role '{ROLE_TO_ASSIGN}' not found. Please create it first.",
                    "red",
                )
                return

            # Check if client already exists
            client = (
                (
                    await db.execute(
                        select(AppClient).where(AppClient.id == uuid.UUID(CLIENT_ID))
                    )
                )
                .scalars()
                .first()
            )
            if not client:
                print_color("Client not found, creating new one...", "blue")
                client = AppClient(id=uuid.UUID(CLIENT_ID), client_name=CLIENT_NAME)
                db.add(client)

            # Set or update details
            client.client_secret_hash = hash_secret(CLIENT_SECRET)
            client.is_active = True
            client.description = "M2M client for the Image Condition Analysis Service"
            client.roles = [role]  # Assign the role

            await db.commit()
            print_color(f"✅ Successfully configured client '{CLIENT_NAME}'.", "green")
            print_color(
                "--- Use these credentials for the service and its tests ---", "blue"
            )
            print_color(f"CLIENT_ID: {CLIENT_ID}", "blue")
            print_color(f"CLIENT_SECRET: {CLIENT_SECRET}", "blue")

        except Exception as e:
            print_color(f"❌ An error occurred: {e}", "red")
            await db.rollback()


if __name__ == "__main__":
    asyncio.run(create_client())

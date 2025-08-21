import asyncio
import os
import sys
import uuid
from pathlib import Path

# Add the project's 'src' directory to the Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUTH_SERVICE_SRC = PROJECT_ROOT / "auth_service" / "src"
sys.path.insert(0, str(AUTH_SERVICE_SRC))

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from auth_service.models.app_client import AppClient
from auth_service.models.permission import Permission
from auth_service.models.role import Role
from auth_service.models.role_permission import RolePermission
from auth_service.security import hash_secret

# --- Configuration for the M2M Client ---
CLIENT_ID = "412485C7-FD7E-46AF-989F-443B9CAEC95D"
CLIENT_NAME = "floorplan-service"
CLIENT_SECRET = "dev-floorplan-service-secret"
ROLE_NAME = "service"
PERMISSION_NAME = "super_id:generate"


def print_color(text: str, color: str):
    colors = {
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "blue": "\033[94m",
        "reset": "\033[0m",
    }
    print(f"{colors.get(color, '')}{text}{colors['reset']}")


async def main():
    print_color(
        "--- Starting Full M2M Client and Permissions Setup Script ---", "yellow"
    )

    # This script runs inside the container and relies on the env_file from docker-compose
    # to set the database URL in the environment.
    db_url = os.getenv("AUTH_SERVICE_DATABASE_URL")
    if not db_url:
        print_color(
            "❌ ERROR: AUTH_SERVICE_DATABASE_URL is not set in the container's environment.",
            "red",
        )
        return

    engine = create_async_engine(db_url, echo=False)
    AsyncSessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionLocal() as db:
        try:
            # Step 1: Ensure the 'service' role exists
            print_color(f"Step 1: Verifying role '{ROLE_NAME}'...", "blue")
            role_stmt = select(Role).where(Role.name == ROLE_NAME)
            role = (await db.execute(role_stmt)).scalars().first()
            if not role:
                print_color(
                    f"   - Role '{ROLE_NAME}' not found. Creating it...", "yellow"
                )
                role = Role(
                    name=ROLE_NAME, description="For machine-to-machine communication"
                )
                db.add(role)
                await db.flush()
            print_color(f"   - Role '{ROLE_NAME}' found (ID: {role.id}).", "green")

            # Step 2: Ensure the 'super_id:generate' permission exists
            print_color(f"Step 2: Verifying permission '{PERMISSION_NAME}'...", "blue")
            perm_stmt = select(Permission).where(Permission.name == PERMISSION_NAME)
            permission = (await db.execute(perm_stmt)).scalars().first()
            if not permission:
                print_color(
                    f"   - Permission '{PERMISSION_NAME}' not found. Creating it...",
                    "yellow",
                )
                permission = Permission(
                    name=PERMISSION_NAME, description="Allows generating new Super IDs."
                )
                db.add(permission)
                await db.flush()
            print_color(
                f"   - Permission '{PERMISSION_NAME}' found (ID: {permission.id}).",
                "green",
            )

            # Step 3: Assign the permission to the role
            print_color(
                f"Step 3: Assigning '{PERMISSION_NAME}' to '{ROLE_NAME}'...", "blue"
            )
            assoc_stmt = select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_id == permission.id,
            )
            association = (await db.execute(assoc_stmt)).scalars().first()
            if not association:
                new_association = RolePermission(
                    role_id=role.id, permission_id=permission.id
                )
                db.add(new_association)
                print_color("   - ✅ Association created.", "green")
            else:
                print_color("   - ✅ Association already exists.", "green")

            # Step 4: Create or Update the App Client
            print_color(f"Step 4: Verifying app client '{CLIENT_NAME}'...", "blue")
            client_stmt = select(AppClient).where(AppClient.id == uuid.UUID(CLIENT_ID))
            client = (await db.execute(client_stmt)).scalars().first()
            if not client:
                client = AppClient(id=uuid.UUID(CLIENT_ID), client_name=CLIENT_NAME)
                db.add(client)
                print_color("   - Client not found. Creating new client.", "yellow")
            else:
                print_color("   - Client found. Ensuring it is up-to-date.", "yellow")

            client.client_secret_hash = hash_secret(CLIENT_SECRET)
            client.is_active = True
            client.description = "M2M client for the Floorplan Service"
            client.roles = [role]

            await db.commit()
            print_color(
                f"✅ Successfully configured client '{CLIENT_NAME}' with necessary permissions.",
                "green",
            )

        except Exception as e:
            print_color(f"❌ An error occurred: {e}", "red")
            await db.rollback()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

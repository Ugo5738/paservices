# /paservices/auth_service/scripts/create_oauth_client.py

import argparse
import asyncio

# This script is run from within the container, so pathing is based on /app
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.future import select

from auth_service.db import get_db

# The Dockerfile sets PYTHONPATH=/app/src, so we can import from the package root
from auth_service.models.app_client import AppClient
from auth_service.security import hash_secret


async def create_or_update_client(client_id_str, client_name, client_secret):
    """
    Finds a client by its name and updates it, or creates a new one if it doesn't exist.
    This is a robust "upsert" operation.
    """
    print(f"Ensuring OAuth client exists: {client_name}")

    try:
        # Generate the deterministic UUID that this client *should* have
        client_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, client_id_str)
        print(f"Expected Client ID (UUIDv5 from '{client_id_str}'): {client_uuid}")

        async for session in get_db():
            try:
                # First, try to find an existing client by its unique name
                stmt = select(AppClient).where(AppClient.client_name == client_name)
                result = await session.execute(stmt)
                client = result.scalars().first()

                if client:
                    print(
                        f"Found existing client by name: '{client.client_name}' (ID: {client.id})"
                    )
                    print("Updating its secret and ensuring it is active...")
                    client.client_secret_hash = hash_secret(client_secret)
                    client.is_active = True
                    client.id = (
                        client_uuid  # Ensure it has the correct deterministic ID
                    )
                    client.updated_at = datetime.now(timezone.utc)
                else:
                    print(f"No client named '{client_name}' found. Creating a new one.")
                    client = AppClient(
                        id=client_uuid,
                        client_name=client_name,
                        client_secret_hash=hash_secret(client_secret),
                        is_active=True,
                        description=f"OAuth client for {client_name}",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                    session.add(client)

                await session.commit()
                print(f"✅ Client '{client_name}' is configured correctly.")
                return True

            except Exception as e:
                await session.rollback()
                raise e

    except Exception as e:
        print(f"❌ Error during client configuration: {e}")
        return False


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create or update an OAuth client for the Auth Service"
    )
    parser.add_argument(
        "--id",
        required=True,
        help="Client ID string (e.g., 'rightmove-data-capture-service')",
    )
    parser.add_argument("--name", required=True, help="Client's user-friendly name")
    parser.add_argument("--secret", required=True, help="Client secret")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(create_or_update_client(args.id, args.name, args.secret))

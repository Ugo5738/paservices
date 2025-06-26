#!/usr/bin/env python3
"""
Create an OAuth client for M2M authentication in the Auth Service
"""

import asyncio
import argparse
import uuid
from datetime import datetime, timezone

async def create_client(client_id, client_name, client_secret):
    """Create an OAuth client for the Auth Service."""
    try:
        # Import here to ensure the app context is loaded
        # with all dependencies available
        import sys
        from pathlib import Path
        # Add auth_service to the path
        sys.path.insert(0, str(Path("/app/src").resolve()))
        
        from auth_service.models.app_client import AppClient
        from auth_service.db import get_db
        from auth_service.security import hash_secret
        
        print(f"Creating OAuth client: {client_name}")
        
        # Create a deterministic UUID from the client_id string if it's not already a UUID
        try:
            client_uuid = uuid.UUID(client_id)
            print(f"Using provided UUID: {client_uuid}")
        except ValueError:
            # Hash the client_id string to create a deterministic UUID using version 5 (SHA-1) and DNS namespace
            client_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, client_id)
            print(f"Generated UUID from string: {client_uuid}")
        
        # Use an async iterator pattern since get_db is an async generator
        async for session in get_db():
            try:
                # Check if client already exists
                client = await session.get(AppClient, client_uuid)
                
                if client:
                    print(f"Updating existing client: {client.id}")
                    
                    # Update existing client
                    client.client_name = client_name
                    client.client_secret_hash = hash_secret(client_secret)
                    client.is_active = True
                    client.updated_at = datetime.now(timezone.utc)
                else:
                    print(f"Creating new client with ID: {client_uuid}")
                    
                    # Create new client
                    new_client = AppClient(
                        id=client_uuid,
                        client_name=client_name,
                        client_secret_hash=hash_secret(client_secret),
                        is_active=True,
                        description="OAuth client for data capture Rightmove service",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc)
                    )
                    session.add(new_client)
                
                # Commit the transaction
                await session.commit()
                print(f"✅ Client saved successfully: {client_name}")
                return True
            except Exception as e:
                await session.rollback()
                raise e  # Re-raise to be caught by the outer try-except
            
    except Exception as e:
        print(f"❌ Error creating/updating client: {e}")
        return False

def parse_args():
    parser = argparse.ArgumentParser(description="Create or update an OAuth client for the Auth Service")
    parser.add_argument("--id", default="data_capture_rightmove_service", help="Client ID (UUID or string)")
    parser.add_argument("--name", default="Data Capture Rightmove Service", help="Client name")
    parser.add_argument("--secret", default="dev_client_secret", help="Client secret")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(create_client(args.id, args.name, args.secret))

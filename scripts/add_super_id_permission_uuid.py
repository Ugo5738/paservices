#!/usr/bin/env python3
"""
Script to add super_id:generate permission and assign it to the correct client.
This script uses psycopg directly to connect to the database, with proper transaction handling
and manually generated UUIDs for new records.
"""

import os
import sys
import uuid
import psycopg
from datetime import datetime

# Client ID to assign the role and permission to based on what we found
CLIENT_ID_STR = "Data Capture Rightmove Service"  # The actual name in the database
CLIENT_UUID = uuid.UUID("b46276a5-4998-5f7c-9a25-a16a2ffc6b11")  # The actual UUID in the database

# Database connection string from environment variables
DB_URL = os.environ.get("AUTH_SERVICE_DATABASE_URL", "")
if not DB_URL.startswith("postgresql"):
    print("Error: No PostgreSQL connection string found in AUTH_SERVICE_DATABASE_URL")
    sys.exit(1)

# Transform SQLAlchemy URL to psycopg format if needed
if "postgresql+psycopg" in DB_URL:
    DB_URL = DB_URL.replace("postgresql+psycopg", "postgresql")

# Remove SQLAlchemy options if present
if "?options=" in DB_URL:
    DB_URL = DB_URL.split("?options=")[0]

print(f"Connecting to database: {DB_URL}")
print(f"Working with client: {CLIENT_ID_STR} (UUID: {CLIENT_UUID})")

try:
    # Connect to the database - autocommit=False for transaction support
    with psycopg.connect(DB_URL, autocommit=False) as conn:
        with conn.cursor() as cur:
            # Verify the client exists
            cur.execute("SELECT id, client_name FROM app_clients WHERE id = %s", (CLIENT_UUID,))
            client = cur.fetchone()
            
            if not client:
                print(f"Error: Client with ID {CLIENT_UUID} does not exist")
                sys.exit(1)
            
            print(f"Found client: {client[0]} - {client[1]}")
            
            try:
                # Get current timestamp for created_at and updated_at fields
                now = datetime.utcnow()
                
                # First check if permission already exists
                cur.execute("SELECT id FROM permissions WHERE name = %s", ("super_id:generate",))
                existing_permission = cur.fetchone()
                
                if existing_permission:
                    permission_id = existing_permission[0]
                    print(f"Using existing permission super_id:generate with ID: {permission_id}")
                else:
                    # Generate a UUID for the new permission
                    permission_id = uuid.uuid4()
                    
                    # Insert permission with manually generated UUID
                    cur.execute(
                        "INSERT INTO permissions (id, name, description, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)",
                        (permission_id, "super_id:generate", "Permission to generate Super IDs", now, now)
                    )
                    print(f"Created new permission super_id:generate with ID: {permission_id}")
                
                # Check if role already exists
                cur.execute("SELECT id FROM roles WHERE name = %s", ("MICROSERVICE",))
                existing_role = cur.fetchone()
                
                if existing_role:
                    role_id = existing_role[0]
                    print(f"Using existing role MICROSERVICE with ID: {role_id}")
                else:
                    # Generate a UUID for the new role
                    role_id = uuid.uuid4()
                    
                    # Insert role with manually generated UUID
                    cur.execute(
                        "INSERT INTO roles (id, name, description, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)",
                        (role_id, "MICROSERVICE", "Role for internal microservice communication", now, now)
                    )
                    print(f"Created new role MICROSERVICE with ID: {role_id}")
                
                # Check if permission is already assigned to role
                cur.execute(
                    "SELECT 1 FROM role_permissions WHERE role_id = %s AND permission_id = %s",
                    (role_id, permission_id)
                )
                existing_role_perm = cur.fetchone()
                
                if existing_role_perm:
                    print(f"Permission {permission_id} already assigned to role {role_id}")
                else:
                    # Assign permission to role with manually generated UUID
                    role_perm_id = uuid.uuid4()
                    cur.execute(
                        "INSERT INTO role_permissions (id, role_id, permission_id, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)",
                        (role_perm_id, role_id, permission_id, now, now)
                    )
                    print(f"Assigned permission {permission_id} to role {role_id}")
                
                # Check if role is already assigned to client
                cur.execute(
                    "SELECT 1 FROM app_client_roles WHERE app_client_id = %s AND role_id = %s",
                    (CLIENT_UUID, role_id)
                )
                existing_client_role = cur.fetchone()
                
                if existing_client_role:
                    print(f"Role {role_id} already assigned to client {CLIENT_UUID}")
                else:
                    # Assign role to client with manually generated UUID
                    client_role_id = uuid.uuid4()
                    cur.execute(
                        "INSERT INTO app_client_roles (id, app_client_id, role_id, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)",
                        (client_role_id, CLIENT_UUID, role_id, now, now)
                    )
                    print(f"Assigned role {role_id} to client {CLIENT_UUID}")
                
                # Commit the transaction
                conn.commit()
                print("Successfully added permission and role assignments")
                
            except Exception as e:
                conn.rollback()
                print(f"Error during database operations: {str(e)}")
                sys.exit(1)
                
except Exception as e:
    print(f"Database connection error: {str(e)}")
    sys.exit(1)

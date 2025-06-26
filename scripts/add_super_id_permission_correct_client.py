#!/usr/bin/env python3
"""
Script to add super_id:generate permission and assign it to the correct client.
This script uses psycopg directly to connect to the database.
"""

import os
import sys
import uuid
import psycopg

# Client ID to assign the role and permission to - matching what's used in test_rightmove_flow.py
CLIENT_ID_STR = "data_capture_rightmove_service"

# Generate deterministic UUID v5 for the client ID (matching what's used in the system)
CLIENT_UUID = uuid.uuid5(uuid.NAMESPACE_DNS, CLIENT_ID_STR)

# Database connection string from environment variables
# Using the standardized environment variable with service-specific prefix
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
print(f"Looking for client: {CLIENT_ID_STR} (UUID: {CLIENT_UUID})")

try:
    # Connect to the database
    with psycopg.connect(DB_URL) as conn:
        conn.autocommit = False
        
        with conn.cursor() as cur:
            # First, list all clients to see what's available
            print("Listing all available clients:")
            cur.execute("SELECT id, client_name FROM app_clients")
            clients = cur.fetchall()
            
            if clients:
                for c_id, c_name in clients:
                    print(f"- {c_name} (UUID: {c_id})")
            else:
                print("No clients found in the database")
            
            # Check if our target client exists - using corrected table name (plural)
            cur.execute("SELECT id, client_name FROM app_clients WHERE id = %s", (CLIENT_UUID,))
            client = cur.fetchone()
            
            if not client:
                print(f"Error: Client with ID {CLIENT_UUID} does not exist")
                
                # Try to find a client by name
                cur.execute("SELECT id, client_name FROM app_clients WHERE client_name = %s", (CLIENT_ID_STR,))
                client_by_name = cur.fetchone()
                
                if client_by_name:
                    print(f"Found client by name: {client_by_name[0]} - {client_by_name[1]}")
                    CLIENT_UUID = client_by_name[0]
                    client = client_by_name
                else:
                    print("No suitable client found. Exiting.")
                    sys.exit(1)
            
            print(f"Found client: {client[0]} - {client[1]}")
            
            # Start a transaction
            conn.begin()
            
            try:
                # 1. Add permission if it doesn't exist - using corrected table name (plural)
                cur.execute(
                    "INSERT INTO permissions (name, description) VALUES (%s, %s) "
                    "ON CONFLICT (name) DO NOTHING RETURNING id",
                    ("super_id:generate", "Permission to generate Super IDs")
                )
                permission_id = cur.fetchone()
                
                if permission_id:
                    permission_id = permission_id[0]
                    print(f"Created new permission super_id:generate with ID: {permission_id}")
                else:
                    cur.execute("SELECT id FROM permissions WHERE name = %s", ("super_id:generate",))
                    permission_id = cur.fetchone()[0]
                    print(f"Using existing permission super_id:generate with ID: {permission_id}")
                
                # 2. Add role if it doesn't exist - using corrected table name (plural)
                cur.execute(
                    "INSERT INTO roles (name, description) VALUES (%s, %s) "
                    "ON CONFLICT (name) DO NOTHING RETURNING id",
                    ("MICROSERVICE", "Role for internal microservice communication")
                )
                role_id = cur.fetchone()
                
                if role_id:
                    role_id = role_id[0]
                    print(f"Created new role MICROSERVICE with ID: {role_id}")
                else:
                    cur.execute("SELECT id FROM roles WHERE name = %s", ("MICROSERVICE",))
                    role_id = cur.fetchone()[0]
                    print(f"Using existing role MICROSERVICE with ID: {role_id}")
                
                # 3. Assign permission to role - using corrected table name (plural)
                cur.execute(
                    "INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s) "
                    "ON CONFLICT (role_id, permission_id) DO NOTHING",
                    (role_id, permission_id)
                )
                print(f"Assigned permission {permission_id} to role {role_id}")
                
                # 4. Assign role to client - using corrected table name (plural)
                cur.execute(
                    "INSERT INTO app_client_roles (app_client_id, role_id) VALUES (%s, %s) "
                    "ON CONFLICT (app_client_id, role_id) DO NOTHING",
                    (CLIENT_UUID, role_id)
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

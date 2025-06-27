"""
Simple script to update the client credentials in the .env.dev file.

This avoids running a complex database operation when we can simply
update the environment variables to use known good values.
"""

import os
import sys


def update_credentials(env_file, client_id, client_secret):
    """Update the client credentials in the .env file"""
    with open(env_file, "r") as f:
        lines = f.readlines()

    m2m_client_id_found = False
    m2m_client_secret_found = False

    for i, line in enumerate(lines):
        if line.startswith("DATA_CAPTURE_RIGHTMOVE_SERVICE_M2M_CLIENT_ID="):
            lines[i] = f"DATA_CAPTURE_RIGHTMOVE_SERVICE_M2M_CLIENT_ID={client_id}\n"
            m2m_client_id_found = True
        elif line.startswith("DATA_CAPTURE_RIGHTMOVE_SERVICE_M2M_CLIENT_SECRET="):
            lines[i] = (
                f"DATA_CAPTURE_RIGHTMOVE_SERVICE_M2M_CLIENT_SECRET={client_secret}\n"
            )
            m2m_client_secret_found = True

    if not m2m_client_id_found:
        lines.append(f"DATA_CAPTURE_RIGHTMOVE_SERVICE_M2M_CLIENT_ID={client_id}\n")

    if not m2m_client_secret_found:
        lines.append(
            f"DATA_CAPTURE_RIGHTMOVE_SERVICE_M2M_CLIENT_SECRET={client_secret}\n"
        )

    with open(env_file, "w") as f:
        f.writelines(lines)

    print(f"Updated client credentials in {env_file}")


if __name__ == "__main__":
    # Use hardcoded known good values for our dev environment
    # In production, these would be securely generated and stored
    client_id = "rightmove-data-capture-service"
    client_secret = "dev-rightmove-service-secret"

    env_file = os.path.join("data_capture_rightmove_service", ".env.dev")

    if not os.path.exists(env_file):
        print(f"Error: Environment file {env_file} not found!")
        sys.exit(1)

    update_credentials(env_file, client_id, client_secret)
    print("\nAlso need to update the auth service database!")
    print("\nRun the following commands to update the auth service database:")
    print("1. Connect to the auth service container:")
    print("   docker exec -it paservices-auth_service-1 /bin/bash")
    print("\n2. Create a temporary script:")
    print("   cat > /app/scripts/add_client.py << 'EOL'")
    print("import asyncio")
    print("import uuid")
    print("from datetime import datetime")
    print("import bcrypt")
    print("from sqlalchemy import select")
    print("from sqlalchemy.ext.asyncio import AsyncSession")
    print("from auth_service.db import get_db_session")
    print("from auth_service.models.app_client import AppClient")
    print("from auth_service.models.role import Role")
    print("from auth_service.models.permission import Permission")
    print("from auth_service.models.app_client_role import AppClientRole")
    print("from auth_service.models.role_permission import RolePermission")
    print("")
    print("async def create_client():")
    print("    async with get_db_session() as db:")
    print("        # Create super_id:generate permission if it doesn't exist")
    print("        permission_name = 'super_id:generate'")
    print(
        "        result = await db.execute(select(Permission).where(Permission.name == permission_name))"
    )
    print("        permission = result.scalars().first()")
    print("        if not permission:")
    print(
        "            permission = Permission(name=permission_name, description='Permission to generate Super IDs')"
    )
    print("            db.add(permission)")
    print("            await db.flush()")
    print("            print(f'Created permission: {permission_name}')")
    print("")
    print("        # Create role if it doesn't exist")
    print("        role_name = 'rightmove_service_role'")
    print(
        "        result = await db.execute(select(Role).where(Role.name == role_name))"
    )
    print("        role = result.scalars().first()")
    print("        if not role:")
    print(
        "            role = Role(name=role_name, description='Role for Rightmove Service')"
    )
    print("            db.add(role)")
    print("            await db.flush()")
    print("            print(f'Created role: {role_name}')")
    print("")
    print("        # Attach permission to role if not already attached")
    print("        if role and permission:")
    print("            result = await db.execute(")
    print("                select(RolePermission).where(")
    print("                    RolePermission.role_id == role.id,")
    print("                    RolePermission.permission_id == permission.id")
    print("                )")
    print("            )")
    print("            role_permission = result.scalars().first()")
    print("            if not role_permission:")
    print(
        "                role_permission = RolePermission(role_id=role.id, permission_id=permission.id)"
    )
    print("                db.add(role_permission)")
    print("                await db.flush()")
    print("                print(f'Attached permission to role')")
    print("")
    print("        # Create or update client")
    print("        client_id = 'rightmove-data-capture-service'")
    print("        client_secret = 'dev-rightmove-service-secret'")
    print(
        "        result = await db.execute(select(AppClient).where(AppClient.client_id == client_id))"
    )
    print("        client = result.scalars().first()")
    print("        if client:")
    print("            # Update existing client")
    print("            salt = bcrypt.gensalt()")
    print("            hashed = bcrypt.hashpw(client_secret.encode('utf-8'), salt)")
    print("            client.client_secret_hash = hashed.decode('utf-8')")
    print("            client.is_active = True")
    print("            print(f'Updated client: {client_id}')")
    print("        else:")
    print("            # Create new client")
    print("            salt = bcrypt.gensalt()")
    print("            hashed = bcrypt.hashpw(client_secret.encode('utf-8'), salt)")
    print("            client = AppClient(")
    print("                name='Data Capture Rightmove Service',")
    print("                client_id=client_id,")
    print("                client_secret_hash=hashed.decode('utf-8'),")
    print(
        "                description='Machine-to-machine client for Rightmove Data Capture'"
    )
    print("            )")
    print("            db.add(client)")
    print("            await db.flush()")
    print("            print(f'Created client: {client_id}')")
    print("")
    print("        # Attach role to client if not already attached")
    print("        if client and role:")
    print("            result = await db.execute(")
    print("                select(AppClientRole).where(")
    print("                    AppClientRole.app_client_id == client.id,")
    print("                    AppClientRole.role_id == role.id")
    print("                )")
    print("            )")
    print("            client_role = result.scalars().first()")
    print("            if not client_role:")
    print(
        "                client_role = AppClientRole(app_client_id=client.id, role_id=role.id)"
    )
    print("                db.add(client_role)")
    print("                await db.flush()")
    print("                print(f'Attached role to client')")
    print("")
    print("        await db.commit()")
    print("        print('Done!')")
    print("")
    print("if __name__ == '__main__':")
    print("    asyncio.run(create_client())")
    print("EOL")
    print("\n3. Run the script:")
    print("   python /app/scripts/add_client.py")
    print("\n4. Restart the Rightmove service:")
    print("   exit ")
    print(
        "   docker-compose -f docker-compose.yml restart data_capture_rightmove_service"
    )

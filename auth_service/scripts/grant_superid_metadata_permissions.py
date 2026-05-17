"""Grant SuperID Metadata store permissions to the `service` role.

Run this inside the `auth_service` container so it picks up the same
`AUTH_SERVICE_DATABASE_URL` the other M2M-client scripts use, e.g.:

    docker compose run --rm auth_service \\
        python auth_service/scripts/grant_superid_metadata_permissions.py

Or for k8s, exec into a running auth_service pod and run the script.

Chunk 2 of the V2 SuperID implementation added two new permissions:

    superid_metadata:write — POST /activity_records, POST /link_records
                             on super_id_service
    superid_metadata:read  — GET /super_ids/{id}/activity_records,
                             GET /super_ids/{id}/link_records

Until both are granted to every M2M client that talks to super_id_service,
the chunk 3 / 4.5 activity-recording calls quietly fail with 403 and log
warnings (the operational paths continue green by design).

This script:
  1. Creates the two permissions if they don't already exist.
  2. Assigns both to the `service` role.
  3. Idempotent — safe to re-run any number of times.

Every existing M2M client (data_capture_rightmove_service,
floorplan_service, image_condition_analysis_service, pa_mcp, etc.) that
has the `service` role automatically inherits the new permissions.

If pa_mcp's M2M client doesn't have the `service` role, edit its app
client row to add it (or follow the pattern in
create_data_capture_m2m_client.py to grant the role).
"""

import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUTH_SERVICE_SRC = PROJECT_ROOT / "auth_service" / "src"
sys.path.insert(0, str(AUTH_SERVICE_SRC))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from auth_service.models.permission import Permission
from auth_service.models.role import Role
from auth_service.models.role_permission import RolePermission


ROLE_NAME = "service"
NEW_PERMISSIONS = [
    (
        "superid_metadata:write",
        "Write activity records and link records to the SuperID Metadata store.",
    ),
    (
        "superid_metadata:read",
        "Read activity records and link records from the SuperID Metadata store.",
    ),
]


def _c(text: str, color: str) -> str:
    return f"\033[{ {'g': 92, 'y': 93, 'r': 91, 'b': 94}[color] }m{text}\033[0m"


async def main() -> None:
    db_url = os.getenv("AUTH_SERVICE_DATABASE_URL")
    if not db_url:
        print(_c("❌ AUTH_SERVICE_DATABASE_URL is not set.", "r"))
        sys.exit(1)

    engine = create_async_engine(db_url, echo=False)
    SessionFactory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    print(_c("--- Granting SuperID Metadata permissions to the `service` role ---", "y"))

    async with SessionFactory() as db:
        try:
            # 1. Resolve (or create) the service role
            role = (
                await db.execute(select(Role).where(Role.name == ROLE_NAME))
            ).scalars().first()
            if not role:
                print(_c(f"   - Role '{ROLE_NAME}' not found. Creating.", "y"))
                role = Role(name=ROLE_NAME, description="M2M service role")
                db.add(role)
                await db.flush()
            print(_c(f"   - Role '{ROLE_NAME}' OK (id={role.id})", "g"))

            # 2. For each new permission: upsert + assign to role
            for perm_name, perm_desc in NEW_PERMISSIONS:
                perm = (
                    await db.execute(
                        select(Permission).where(Permission.name == perm_name)
                    )
                ).scalars().first()
                if not perm:
                    print(_c(f"   - Permission '{perm_name}' missing. Creating.", "y"))
                    perm = Permission(name=perm_name, description=perm_desc)
                    db.add(perm)
                    await db.flush()
                print(_c(f"   - Permission '{perm_name}' OK (id={perm.id})", "g"))

                association = (
                    await db.execute(
                        select(RolePermission).where(
                            RolePermission.role_id == role.id,
                            RolePermission.permission_id == perm.id,
                        )
                    )
                ).scalars().first()
                if not association:
                    db.add(RolePermission(role_id=role.id, permission_id=perm.id))
                    print(_c(f"   - Assigned '{perm_name}' → '{ROLE_NAME}'", "g"))
                else:
                    print(_c(f"   - '{perm_name}' already on '{ROLE_NAME}'", "b"))

            await db.commit()
            print(_c("✅ Done. Every M2M client with the `service` role now has access.", "g"))
        except Exception as exc:
            await db.rollback()
            print(_c(f"❌ Failed: {exc}", "r"))
            sys.exit(1)
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

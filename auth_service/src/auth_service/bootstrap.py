import logging
import uuid
from typing import Dict, List, Optional

from gotrue.errors import AuthApiError as SupabaseAPIError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from supabase._async.client import AsyncClient as AsyncSupabaseClient

from auth_service.config import settings as app_settings
from auth_service.crud import user_crud
from auth_service.models.permission import Permission
from auth_service.models.role import Role
from auth_service.models.role_permission import RolePermission
from auth_service.models.user_role import UserRole
from auth_service.schemas.user_schemas import ProfileCreate, SupabaseUser
from auth_service.supabase_client import get_supabase_admin_client

logger = logging.getLogger(__name__)

# Core roles to be created during bootstrapping
CORE_ROLES = {
    "admin": "Full system access",
    "user": "Basic authenticated user access",
    "service": "For machine-to-machine communication",
}

# Core permissions to be created during bootstrapping
CORE_PERMISSIONS = [
    {"name": "users:read", "description": "View user information"},
    {"name": "users:write", "description": "Create/update user information"},
    {"name": "roles:read", "description": "View roles"},
    {"name": "roles:write", "description": "Create/update roles"},
    {"name": "permissions:read", "description": "View permissions"},
    {"name": "permissions:write", "description": "Create/update permissions"},
    {
        "name": "role:admin_manage",
        "description": "Special permission for admin operations",
    },
]

# Role-permission mapping for initial setup
ROLE_PERMISSIONS_MAP = {
    "admin": [p["name"] for p in CORE_PERMISSIONS],  # Admin gets all permissions
    "user": ["users:read"],  # Users can only view their own profile
    "service": [],  # Empty by default, to be configured based on specific service needs
}


async def create_core_roles(db: AsyncSession) -> Dict[str, uuid.UUID]:
    """Create the core roles if they don't exist yet."""
    role_ids = {}

    for role_name, role_description in CORE_ROLES.items():
        # Check if role already exists
        stmt = select(Role).where(Role.name == role_name)
        result = await db.execute(stmt)
        existing_role = result.scalars().first()

        if existing_role:
            logger.info(f"Role '{role_name}' already exists")
            role_ids[role_name] = existing_role.id
        else:
            # Create new role
            new_role = Role(
                id=uuid.uuid4(),
                name=role_name,
                description=role_description,
            )
            db.add(new_role)
            await db.flush()  # Flush to get the ID
            role_ids[role_name] = new_role.id
            logger.info(f"Created new role: {role_name}")

    await db.commit()
    return role_ids


async def create_core_permissions(db: AsyncSession) -> Dict[str, uuid.UUID]:
    """Create the core permissions if they don't exist yet."""
    permission_ids = {}

    for perm_data in CORE_PERMISSIONS:
        # Check if permission already exists
        stmt = select(Permission).where(Permission.name == perm_data["name"])
        result = await db.execute(stmt)
        existing_perm = result.scalars().first()

        if existing_perm:
            logger.info(f"Permission '{perm_data['name']}' already exists")
            permission_ids[perm_data["name"]] = existing_perm.id
        else:
            # Create new permission
            new_perm = Permission(
                id=uuid.uuid4(),
                name=perm_data["name"],
                description=perm_data["description"],
            )
            db.add(new_perm)
            await db.flush()  # Flush to get the ID
            permission_ids[perm_data["name"]] = new_perm.id
            logger.info(f"Created new permission: {perm_data['name']}")

    await db.commit()
    return permission_ids


async def assign_permissions_to_roles(
    db: AsyncSession,
    role_ids: Dict[str, uuid.UUID],
    permission_ids: Dict[str, uuid.UUID],
) -> None:
    """Assign permissions to roles according to the mapping."""
    for role_name, permission_names in ROLE_PERMISSIONS_MAP.items():
        if role_name not in role_ids:
            logger.warning(
                f"Role '{role_name}' not found, skipping permission assignment"
            )
            continue

        role_id = role_ids[role_name]

        for perm_name in permission_names:
            if perm_name not in permission_ids:
                logger.warning(
                    f"Permission '{perm_name}' not found, skipping assignment to role '{role_name}'"
                )
                continue

            perm_id = permission_ids[perm_name]

            # Check if assignment already exists
            stmt = select(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == perm_id,
            )
            result = await db.execute(stmt)
            existing_assignment = result.scalars().first()

            if existing_assignment:
                logger.info(
                    f"Permission '{perm_name}' already assigned to role '{role_name}'"
                )
                continue

            # Create new assignment
            new_assignment = RolePermission(role_id=role_id, permission_id=perm_id)
            db.add(new_assignment)
            logger.info(f"Assigned permission '{perm_name}' to role '{role_name}'")

    await db.commit()


async def create_admin_user(
    db: AsyncSession, email: str, password: str
) -> Optional[SupabaseUser]:
    """
    Efficiently checks for and creates an admin user in Supabase if one doesn't exist.
    If the user already exists, it fetches their data.
    """
    logger.info(f"Attempting to verify or create admin user: {email}")
    admin_supabase = get_supabase_admin_client()

    try:
        # First, try to create the user.
        logger.info(f"Attempting to create admin user '{email}' via Supabase API.")
        signup_response = await admin_supabase.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,  # Automatically confirm the email
                "user_metadata": {"roles": ["admin"]},
            }
        )

        if not signup_response or not signup_response.user:
            logger.error(
                "Failed to create admin user: no user object returned from Supabase."
            )
            return None

        logger.info(f"Successfully created new admin user: {email}")
        return SupabaseUser.model_validate(signup_response.user)

    except SupabaseAPIError as e:
        # If the error is "User already registered", fetch the existing user.
        if "already registered" in e.message.lower():
            logger.warning(
                f"Admin user '{email}' already exists. Fetching existing user data."
            )
            try:
                existing_user_response = (
                    await admin_supabase.auth.admin.get_user_by_email(email)
                )
                if not existing_user_response or not existing_user_response.user:
                    logger.error(
                        f"Could not fetch existing admin user '{email}' despite registration error."
                    )
                    return None
                logger.info(f"Successfully fetched existing admin user: {email}")
                return SupabaseUser.model_validate(existing_user_response.user)
            except Exception as fetch_error:
                logger.error(
                    f"Error fetching existing admin user '{email}': {fetch_error}",
                    exc_info=True,
                )
                return None
        else:
            # For other API errors, log it and fail.
            logger.error(
                f"Supabase API error during admin user creation for '{email}': {e}",
                exc_info=True,
            )
            return None
    except Exception as e:
        logger.error(
            f"Unexpected error during admin user creation for '{email}': {e}",
            exc_info=True,
        )
        return None


async def assign_admin_role_to_user(
    db: AsyncSession, user_id: uuid.UUID, admin_role_id: uuid.UUID
) -> bool:
    """Assigns the admin role to a user in the local database."""
    try:
        stmt = select(UserRole).where(
            UserRole.user_id == user_id, UserRole.role_id == admin_role_id
        )
        result = await db.execute(stmt)
        if result.scalars().first():
            logger.info(f"Admin role already assigned to user '{user_id}'")
            return True

        new_assignment = UserRole(user_id=user_id, role_id=admin_role_id)
        db.add(new_assignment)
        await db.flush()
        logger.info(f"Assigned admin role to user '{user_id}'")
        return True
    except Exception as e:
        logger.error(
            f"Error assigning admin role to user '{user_id}': {e}", exc_info=True
        )
        await db.rollback()
        return False


async def create_admin_profile(db: AsyncSession, admin_supa_user: SupabaseUser) -> bool:
    """Creates a local profile for the admin user if it doesn't exist."""
    if not admin_supa_user or not admin_supa_user.id or not admin_supa_user.email:
        logger.error("Invalid SupabaseUser data for profile creation.")
        return False

    existing_profile = await user_crud.get_profile_by_user_id_from_db(
        db, admin_supa_user.id
    )
    if existing_profile:
        logger.info(
            f"Local profile for admin user {admin_supa_user.id} already exists."
        )
        return True

    logger.info(
        f"Local profile for admin user {admin_supa_user.id} not found, creating..."
    )
    profile_data = ProfileCreate(
        user_id=admin_supa_user.id,
        email=admin_supa_user.email,
        username=f"admin_{str(admin_supa_user.id)[:8]}",
        first_name="Admin",
        last_name="User",
    )
    created_profile = await user_crud.create_profile_in_db(db, profile_data)

    if created_profile:
        logger.info(f"Local profile created for admin {admin_supa_user.id}")
        return True
    else:
        logger.error(f"Failed to create local profile for admin {admin_supa_user.id}")
        return False


async def bootstrap_admin_and_rbac(db: AsyncSession) -> bool:
    """Main bootstrapping function to setup initial admin and RBAC components."""
    try:
        logger.info("Starting admin and RBAC bootstrapping process")

        # 1. Create core roles
        role_ids = await create_core_roles(db)

        # 2. Create core permissions
        permission_ids = await create_core_permissions(db)

        # 3. Assign permissions to roles
        await assign_permissions_to_roles(db, role_ids, permission_ids)

        logger.info(
            "Bootstrap: Core RBAC tables (roles, permissions, role_permissions) processed."
        )

        # 4. Create admin user if environment variables are set
        if app_settings.INITIAL_ADMIN_EMAIL and app_settings.INITIAL_ADMIN_PASSWORD:
            admin_supa_user = await create_admin_user(
                db,
                app_settings.INITIAL_ADMIN_EMAIL,
                app_settings.INITIAL_ADMIN_PASSWORD,
            )

            if admin_supa_user and admin_supa_user.id:
                logger.info(
                    f"Bootstrap: Supabase admin user '{admin_supa_user.email}' processed (ID: {admin_supa_user.id})."
                )
                # 5. Create admin profile
                await create_admin_profile(db, admin_supa_user)

                # 6. Assign admin role to user
                if "admin" in role_ids and role_ids["admin"]:
                    await assign_admin_role_to_user(
                        db, admin_supa_user.id, role_ids["admin"]
                    )
                else:
                    logger.error(
                        "Bootstrap: 'admin' role ID not found in local DB. Cannot assign to Supabase admin user."
                    )
            await db.commit()  # Final commit for the bootstrap session
        logger.info("Bootstrap process completed successfully.")
        return True
    except Exception as e:
        await db.rollback()
        logger.error(f"Bootstrap process failed: {e}", exc_info=True)
        return False


# Entry point for CLI command
async def run_bootstrap(db: AsyncSession, supabase: AsyncSupabaseClient = None):
    """Run the bootstrapping process. Can be called from CLI or during startup."""
    # This function ignores the supabase parameter since we're not using it directly
    # And bootstrap_admin_and_rbac doesn't need it anymore as it creates its own client

    success = await bootstrap_admin_and_rbac(db)
    if success:
        logger.info("Bootstrap process completed successfully")
    else:
        logger.error("Bootstrap process failed")
    return success

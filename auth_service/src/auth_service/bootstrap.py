import logging
import uuid
from typing import Dict, List, Optional

from gotrue.errors import AuthApiError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from supabase._async.client import AsyncClient as AsyncSupabaseClient

from auth_service.config import settings as app_settings
from auth_service.crud import user_crud
from auth_service.models.permission import Permission
from auth_service.models.role import Role
from auth_service.models.role_permission import RolePermission
from auth_service.models.user_role import UserRole
from auth_service.routers.user_auth_routes import create_profile_in_db
from auth_service.schemas.user_schemas import ProfileCreate, SupabaseUser
from auth_service.supabase_client import get_supabase_admin_client

logger = logging.getLogger(__name__)

# Core roles to be created during bootstrapping
CORE_ROLES = [
    {"name": "admin", "description": "Full system access"},
    {"name": "user", "description": "Basic authenticated user access"},
    {"name": "service", "description": "For machine-to-machine communication"},
]

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
    "admin": [
        "users:read",
        "users:write",
        "roles:read",
        "roles:write",
        "permissions:read",
        "permissions:write",
        "role:admin_manage",
    ],
    "user": ["users:read"],  # Users can only view their own profile
    "service": [],  # Empty by default, to be configured based on specific service needs
}


async def create_core_roles(db: AsyncSession) -> Dict[str, uuid.UUID]:
    """Create the core roles if they don't exist yet."""
    role_ids = {}

    for role_data in CORE_ROLES:
        # Check if role already exists
        stmt = select(Role).where(Role.name == role_data["name"])
        result = await db.execute(stmt)
        existing_role = result.scalars().first()

        if existing_role:
            logger.info(f"Role '{role_data['name']}' already exists")
            role_ids[role_data["name"]] = existing_role.id
        else:
            # Create new role
            new_role = Role(
                id=uuid.uuid4(),
                name=role_data["name"],
                description=role_data["description"],
            )
            db.add(new_role)
            await db.flush()  # Flush to get the ID
            role_ids[role_data["name"]] = new_role.id
            logger.info(f"Created new role: {role_data['name']}")

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


async def create_admin_user(email: str, password: str) -> Optional[SupabaseUser]:
    """Create an admin user in Supabase if one doesn't exist."""
    logger.info(f"Attempting to create or verify admin user: {email}")

    try:
        # Use the admin client specifically for this operation
        # Don't use async with since the client doesn't support async context manager protocol
        admin_supabase = await get_supabase_admin_client()
        logger.debug(
            "Admin Supabase client obtained. Listing users to check existence."
        )

        user_list_response = await admin_supabase.auth.admin.list_users(per_page=1000)

        existing_admin_user_data = None
        # The response is a list directly, not an object with a users property
        if user_list_response:
            logger.debug(f"Got {len(user_list_response)} users from Supabase")
            for user_data in user_list_response:
                if hasattr(user_data, "email") and user_data.email == email:
                    logger.info(
                        f"Admin user with email '{email}' already exists (ID: {user_data.id})."
                    )
                    existing_admin_user_data = user_data
                    break

        if existing_admin_user_data:
            # Map to your SupabaseUser Pydantic model
            return SupabaseUser(
                id=existing_admin_user_data.id,
                aud=existing_admin_user_data.aud or "",
                role=existing_admin_user_data.role,  # This is Supabase 'role', not your custom app roles
                email=existing_admin_user_data.email,
                phone=existing_admin_user_data.phone,
                email_confirmed_at=existing_admin_user_data.email_confirmed_at,
                phone_confirmed_at=existing_admin_user_data.phone_confirmed_at,
                confirmed_at=getattr(
                    existing_admin_user_data,
                    "confirmed_at",
                    existing_admin_user_data.email_confirmed_at
                    or existing_admin_user_data.phone_confirmed_at,
                ),
                last_sign_in_at=existing_admin_user_data.last_sign_in_at,
                app_metadata=existing_admin_user_data.app_metadata or {},
                user_metadata=existing_admin_user_data.user_metadata
                or {},  # RBAC roles go here
                identities=existing_admin_user_data.identities or [],
                created_at=existing_admin_user_data.created_at,
                updated_at=existing_admin_user_data.updated_at,
            )

        # If not found, create a new admin user
        logger.info(f"Admin user '{email}' not found. Attempting to create.")
        signup_response = await admin_supabase.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,  # Auto-confirm email for admin
                "user_metadata": {
                    "roles": ["admin"]
                },  # Add initial RBAC role directly here
            }
        )

        if not signup_response or not signup_response.user:
            logger.error(
                "Failed to create admin user - no user object returned from Supabase."
            )
            return None

        logger.info(
            f"Successfully created new admin user: {signup_response.user.email} (ID: {signup_response.user.id})"
        )
        # Map to Pydantic model
        return SupabaseUser(
            id=signup_response.user.id,
            aud=signup_response.user.aud or "",
            role=signup_response.user.role,
            email=signup_response.user.email,
            phone=signup_response.user.phone,
            email_confirmed_at=signup_response.user.email_confirmed_at,
            phone_confirmed_at=signup_response.user.phone_confirmed_at,
            confirmed_at=getattr(
                signup_response.user,
                "confirmed_at",
                signup_response.user.email_confirmed_at
                or signup_response.user.phone_confirmed_at,
            ),
            last_sign_in_at=signup_response.user.last_sign_in_at,
            app_metadata=signup_response.user.app_metadata or {},
            user_metadata=signup_response.user.user_metadata or {},
            identities=signup_response.user.identities or [],
            created_at=signup_response.user.created_at,
            updated_at=signup_response.user.updated_at,
        )

    except AuthApiError as e:
        logger.error(
            f"Supabase API error during admin user creation/verification for '{email}': {e.message} (Status: {getattr(e, 'status', 'N/A')})"
        )
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error during admin user creation/verification for '{email}': {e}",
            exc_info=True,
        )
        return None


async def assign_admin_role_to_user(
    db: AsyncSession, user_id: str, admin_role_id: uuid.UUID
) -> bool:
    """Assign the admin role to a user."""
    try:
        # Check if assignment already exists
        stmt = select(UserRole).where(
            UserRole.user_id == user_id, UserRole.role_id == admin_role_id
        )
        result = await db.execute(stmt)
        existing_assignment = result.scalars().first()

        if existing_assignment:
            logger.info(f"Admin role already assigned to user '{user_id}'")
            return True

        # Create new assignment
        new_assignment = UserRole(user_id=user_id, role_id=admin_role_id)
        db.add(new_assignment)
        await db.commit()

        logger.info(f"Assigned admin role to user '{user_id}'")
        return True

    except Exception as e:
        logger.error(f"Error assigning admin role to user '{user_id}': {e}")
        await db.rollback()
        return False


async def create_admin_profile(db: AsyncSession, admin_supa_user: SupabaseUser) -> bool:
    """Creates a local profile for the admin user if it doesn't exist."""
    if not admin_supa_user or not admin_supa_user.id or not admin_supa_user.email:
        logger.error("Invalid SupabaseUser data provided for profile creation.")
        return None

    logger.info(
        f"Checking or creating local profile for admin user ID: {admin_supa_user.id}"
    )
    existing_profile = await user_crud.get_profile_by_user_id_from_db(
        db, admin_supa_user.id
    )
    if not existing_profile:
        logger.info(
            f"Local profile for admin user {admin_supa_user.id} not found, creating..."
        )
        profile_data = ProfileCreate(
            user_id=admin_supa_user.id,
            email=admin_supa_user.email,
            username=f"admin_{str(admin_supa_user.id)[:8]}",
            first_name="Admin",
            last_name="User",
            # is_active is True by default in model
        )
        created_profile = await user_crud.create_profile_in_db(db, profile_data)
        if created_profile:
            logger.info(f"Local profile created for admin {admin_supa_user.id}")
            # Convert ORM to dictionary, then to Pydantic
            profile_dict = {
                "user_id": str(created_profile.user_id),
                "email": created_profile.email,
                "username": created_profile.username,
                "first_name": created_profile.first_name,
                "last_name": created_profile.last_name,
                "is_active": created_profile.is_active,
            }
            return ProfileCreate.model_validate(profile_dict)
        else:
            logger.error(
                f"Failed to create local profile for admin {admin_supa_user.id}"
            )
            return None
    else:
        logger.info(
            f"Local profile for admin user {admin_supa_user.id} already exists."
        )
        # Convert ORM to dictionary, then to Pydantic
        profile_dict = {
            "user_id": str(existing_profile.user_id),
            "email": existing_profile.email,
            "username": existing_profile.username,
            "first_name": existing_profile.first_name,
            "last_name": existing_profile.last_name,
            "is_active": existing_profile.is_active,
        }
        return ProfileCreate.model_validate(profile_dict)


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
        if app_settings.initial_admin_email and app_settings.initial_admin_password:
            logger.info(
                f"Bootstrap: Processing initial Supabase admin user: {app_settings.initial_admin_email}"
            )
            admin_supa_user_data = await create_admin_user(
                app_settings.initial_admin_email,
                app_settings.initial_admin_password,
            )

            if admin_supa_user_data and admin_supa_user_data.id:
                logger.info(
                    f"Bootstrap: Supabase admin user '{admin_supa_user_data.email}' processed (ID: {admin_supa_user_data.id})."
                )
                # 5. Create admin profile
                await create_admin_profile(db, admin_supa_user_data)

                # 6. Assign admin role to user
                if "admin" in role_ids and role_ids["admin"]:
                    await assign_admin_role_to_user(
                        db, admin_supa_user_data.id, role_ids["admin"]
                    )
                else:
                    logger.error(
                        "Bootstrap: 'admin' role ID not found in local DB. Cannot assign to Supabase admin user."
                    )
            else:
                logger.warning(
                    f"Bootstrap: Initial Supabase admin user processing failed for {app_settings.initial_admin_email}."
                )
        else:
            logger.info(
                "Bootstrap: Initial Supabase admin user creation skipped (email or password not set in config)."
            )

        logger.info("Bootstrap: Admin and RBAC setup completed.")
        return True

    except Exception as e:
        logger.error(
            f"Bootstrap: Error during admin and RBAC setup: {e}", exc_info=True
        )
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

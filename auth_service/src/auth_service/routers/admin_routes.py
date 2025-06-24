# auth_service/src/routers/admin_routes.py
from fastapi import APIRouter, Depends

from ..dependencies import require_admin_user
from . import (
    _admin_client_role_routes,
    _admin_client_routes,
    _admin_permission_routes,
    _admin_role_permission_routes,
    _admin_role_routes,
    _admin_user_role_routes,
)

# This is the main router that will be included in the FastAPI app
router = APIRouter(
    # All routes in this router will be protected by the admin dependency
    dependencies=[Depends(require_admin_user)]
)

# Include each sub-router with its own specific prefix
router.include_router(
    _admin_client_routes.router, prefix="/clients", tags=["Admin - App Clients"]
)
router.include_router(
    _admin_role_routes.router, prefix="/roles", tags=["Admin - Roles"]
)
router.include_router(
    _admin_permission_routes.router, prefix="/permissions", tags=["Admin - Permissions"]
)
router.include_router(
    _admin_user_role_routes.router, prefix="/users", tags=["Admin - User Roles"]
)
router.include_router(
    _admin_client_role_routes.router, prefix="/clients", tags=["Admin - Client Roles"]
)
router.include_router(
    _admin_role_permission_routes.router,
    prefix="/roles",
    tags=["Admin - Role Permissions"],
)

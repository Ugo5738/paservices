"""
API routers for the Floorplan Service.
"""

from floorplan_service.routers.floorplan_router import router as floorplan_router
from floorplan_service.routers.health_router import router as health_router
from floorplan_service.routers.workflow_status_router import (
    router as workflow_status_router,
)

__all__ = ["health_router", "floorplan_router", "workflow_status_router"]

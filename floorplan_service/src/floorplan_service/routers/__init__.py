"""
API routers for the Floorplan Service.
"""

from floorplan_service.routers.floorplan_router import router as floorplan_router
from floorplan_service.routers.health_router import router as health_router

__all__ = ["health_router", "floorplan_router"]

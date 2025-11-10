"""
API routers for the Data Capture Rightmove Service.
"""

from data_capture_rightmove_service.routers.health_router import router as health_router
from data_capture_rightmove_service.routers.property_router import (
    router as property_router,
)
from data_capture_rightmove_service.routers.workflow_status_router import (
    router as workflow_status_router,
)
from data_capture_rightmove_service.routers.workflow_test_router import (
    router as workflow_test_router,
)

__all__ = [
    "health_router",
    "property_router",
    "workflow_status_router",
    "workflow_test_router",
]

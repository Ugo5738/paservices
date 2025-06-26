"""
API routers for the Data Capture Rightmove Service.
"""

from data_capture_rightmove_service.routers.health_router import router as health_router
from data_capture_rightmove_service.routers.property_router import router as property_router

__all__ = ['health_router', 'property_router']

"""
Database models for the Floorplan Service.
"""

from floorplan_service.models.base import Base, SuperIdMixin

# Export all models to make them discoverable by Alembic's 'import *'
__all__ = [
    "Base",
    "SuperIdMixin",
]

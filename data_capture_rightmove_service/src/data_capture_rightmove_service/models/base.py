"""
Base model classes and common SQLAlchemy components.
"""

from sqlalchemy import Column, DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase

# Define naming convention for constraints to ensure consistent naming
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Create metadata with naming convention and schema
metadata = MetaData(naming_convention=convention, schema="rightmove")


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    
    metadata = metadata
    
    # Add created_at and updated_at timestamps to all tables
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Add tablename based on class name, using snake_case format
    @declared_attr.directive
    def __tablename__(cls) -> str:
        # Convert camel case to snake case
        import re
        name = re.sub('(?<!^)(?=[A-Z])', '_', cls.__name__).lower()
        return name


class SuperIdMixin:
    """Mixin for models that require a super_id field for tracking."""
    
    super_id = Column(UUID(as_uuid=True), nullable=False, index=True)

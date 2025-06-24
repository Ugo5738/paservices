import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship
from src.auth_service.db import Base


class AppClient(Base):
    __tablename__ = "app_clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_name = Column(String, unique=True, nullable=False, index=True)
    client_secret_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    description = Column(String, nullable=True)
    allowed_callback_urls = Column(ARRAY(String), nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Define many-to-many relationship with Role via AppClientRole
    roles = relationship(
        "Role",
        secondary="app_client_roles",
        lazy="selectin",
        back_populates="app_clients",
        overlaps="app_client_association_objects,role",  # Fix for SQLAlchemy relationship conflict warning
    )

    def __repr__(self):
        return f"<AppClient(id='{self.id}', client_name='{self.client_name}')>"

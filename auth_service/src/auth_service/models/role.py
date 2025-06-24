import uuid

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.auth_service.db import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    # Properly define overlaps to address all relationship conflicts
    users = relationship(
        "Profile",
        secondary="user_roles",
        back_populates="roles",
        overlaps="user_roles,role,user_profile",
    )

    user_roles = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan",
        overlaps="users,profile_role,profile,user_profile",
    )

    app_clients = relationship(
        "AppClient",
        secondary="app_client_roles",
        lazy="selectin",
        back_populates="roles",  # Matches the back_populates in AppClient.roles
        overlaps="app_client,role",  # Fix for SQLAlchemy relationship conflict warning
    )
    app_client_association_objects = relationship(
        "AppClientRole", back_populates="role", overlaps="app_clients"
    )
    permissions = relationship("Permission", secondary="role_permissions")

    def __repr__(self):
        return f"<Role(id='{self.id}', name='{self.name}')>"

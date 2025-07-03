from sqlalchemy import Column, DateTime, ForeignKey, PrimaryKeyConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from auth_service.db import Base


class AppClientRole(Base):
    __tablename__ = "app_client_roles"

    app_client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_id = Column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    assigned_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        PrimaryKeyConstraint("app_client_id", "role_id", name="app_client_roles_pkey"),
    )

    # Relationships
    role = relationship(
        "Role", back_populates="app_client_association_objects", overlaps="app_clients"
    )
    app_client = relationship("AppClient", overlaps="roles")

    def __repr__(self):
        return f"<AppClientRole(app_client_id='{self.app_client_id}', role_id='{self.role_id}')>"

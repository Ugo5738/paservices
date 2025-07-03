import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Table,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from auth_service.db import Base

# Define a placeholder for Supabase's auth.users table.
# This makes SQLAlchemy's metadata aware of the table and its schema
# without trying to create or manage it. This resolves the NoReferencedTableError.
auth_users_table = Table(
    "users",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    schema="auth",
    extend_existing=True,
)


class Profile(Base):
    __tablename__ = "profiles"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    email = Column(String, nullable=False, index=True)
    username = Column(String, unique=True, nullable=True, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Add the inverse relationship to the Role model
    # This tells SQLAlchemy how a Profile is related to Roles through the 'user_roles' table.
    # The 'back_populates="users"' matches the relationship defined in the Role model.
    roles = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        overlaps="user_roles,role",
    )
    user_roles = relationship(
        "UserRole",
        back_populates="user_profile",
        cascade="all, delete-orphan",
        overlaps="roles,user_profile",
    )

    # Add foreign key constraint with use_alter and post_create
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"],
            ["auth.users.id"],
            ondelete="CASCADE",
            use_alter=True,  # This creates the constraint after tables are created
            name="fk_profile_auth_user_id",
        ),
    )

    def __repr__(self):
        return f"<Profile(user_id='{self.user_id}', username='{self.username}')>"

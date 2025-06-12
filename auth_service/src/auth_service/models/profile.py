import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, func, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID

from auth_service.db import Base

class Profile(Base):
    __tablename__ = "profiles"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    email = Column(String, nullable=False, index=True) # Added email column
    username = Column(String, unique=True, nullable=True, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Add foreign key constraint with use_alter and post_create
    __table_args__ = (
        ForeignKeyConstraint(
            ['user_id'], ['auth.users.id'],
            ondelete='CASCADE',
            use_alter=True,  # This creates the constraint after tables are created
            name='fk_profile_auth_user_id'
        ),
    )
    
    def __repr__(self):
        return f"<Profile(user_id='{self.user_id}', username='{self.username}')>"

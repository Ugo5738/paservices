import uuid
from sqlalchemy import Column, String, DateTime, func, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID

from auth_service.db import Base

class AppClientRefreshToken(Base):
    __tablename__ = "app_client_refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    app_client_id = Column(UUID(as_uuid=True), ForeignKey("app_clients.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True) # Timestamp when the token was revoked

    def __repr__(self):
        return f"<AppClientRefreshToken(id='{self.id}', app_client_id='{self.app_client_id}', revoked='{bool(self.revoked_at)}')>"

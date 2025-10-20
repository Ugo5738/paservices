# Re-export schemas for backward compatibility
from super_id_service.schemas.auth_schema import TokenData
from super_id_service.schemas.super_id_schema import (
    MessageResponse,
    SuperIdRequest,
    SuperIDResponse,
)

__all__ = [
    "SuperIdRequest",
    "SuperIDResponse",
    "MessageResponse",
    "TokenData",
]

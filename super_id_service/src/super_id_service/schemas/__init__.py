# Re-export schemas for backward compatibility
from super_id_service.schemas.auth_schema import TokenData
from super_id_service.schemas.super_id_schema import (
    BatchSuperIDResponse,
    MessageResponse,
    SingleSuperIDResponse,
    SuperIdRequest,
)

__all__ = [
    "SuperIdRequest",
    "SingleSuperIDResponse",
    "BatchSuperIDResponse",
    "MessageResponse",
    "TokenData",
]

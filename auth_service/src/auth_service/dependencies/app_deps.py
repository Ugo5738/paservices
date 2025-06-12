from functools import lru_cache
from auth_service.config import Settings # Assuming Settings is in auth_service.config

@lru_cache()
def get_app_settings() -> Settings:
    """
    Returns the application settings, cached for efficiency.
    """
    return Settings()

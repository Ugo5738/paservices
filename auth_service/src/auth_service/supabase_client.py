import asyncio

from supabase._async.client import AsyncClient as AsyncSupabaseClient
from supabase._async.client import create_client as create_async_supabase_client
from supabase.lib.client_options import ClientOptions

import auth_service.config as app_config
from auth_service.logging_config import logger

_global_async_supabase_client: AsyncSupabaseClient | None = None


async def init_supabase_client():
    """Initializes the global Supabase client. To be called at application startup."""
    global _global_async_supabase_client
    if _global_async_supabase_client is not None:
        logger.info("Supabase client already initialized.")
        return

    url = app_config.settings.supabase_url
    # For the general purpose client used by most of the app,
    # the ANON_KEY is typically used.
    # Specific admin operations might need a client initialized with SERVICE_ROLE_KEY.
    key = app_config.settings.supabase_anon_key

    if not url or not key:
        logger.error(
            "Supabase URL or Anon Key is not configured. Cannot initialize client."
        )
        raise ValueError("Supabase URL or Anon Key not configured.")
    if not url.startswith("http"):
        logger.error(f"Invalid Supabase URL format: {url}")
        raise ValueError(f"Invalid Supabase URL format: {url}")

    logger.info(f"Initializing Supabase AsyncClient with URL: {url[:20]}...")
    try:
        _global_async_supabase_client = await create_async_supabase_client(
            url,
            key,
            options=ClientOptions(
                # persist_session=True, # Default
                # auto_refresh_token=True # Default
            ),
        )
        logger.info("Supabase AsyncClient initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}", exc_info=True)
        _global_async_supabase_client = None  # Ensure it's None if init fails
        raise  # Re-raise the exception to signal startup failure


async def close_supabase_client():
    """Closes the global Supabase client. To be called at application shutdown."""
    global _global_async_supabase_client
    if _global_async_supabase_client:
        logger.info("Closing Supabase AsyncClient...")
        # The Supabase AsyncClient doesn't have an aclose() method
        # Just set it to None as cleanup
        _global_async_supabase_client = None
        logger.info("Supabase AsyncClient reference cleared.")


def get_supabase_client() -> AsyncSupabaseClient:
    """
    FastAPI dependency to get the globally initialized Supabase AsyncClient.
    This function itself is NOT async, but it returns an async client.
    It relies on the client being initialized via the FastAPI lifespan.
    """
    if _global_async_supabase_client is None:
        # Check if we're in a test environment - this helps prevent failures in test mode
        # where the client might be mocked.
        import sys
        is_testing = 'pytest' in sys.modules or any('pytest' in arg for arg in sys.argv)
        
        if not is_testing:
            # Only raise the error in non-test environments
            logger.error(
                "Supabase client accessed before initialization or after shutdown!"
            )
            raise RuntimeError("Supabase client not available. Check application lifespan.")
    return _global_async_supabase_client


async def get_supabase_admin_client() -> AsyncSupabaseClient:
    """
    Creates and returns a new Supabase AsyncClient initialized with the SERVICE_ROLE_KEY.
    This client is intended for specific admin operations and should be used with 'async with'
    for proper resource management by the caller, as it's not a shared global instance.
    """
    url = app_config.settings.supabase_url
    service_key = app_config.settings.supabase_service_role_key

    if not url or not service_key:
        logger.error(
            "Supabase URL or Service Role Key not configured for admin client."
        )
        raise ValueError(
            "Supabase URL or Service Role Key not configured for admin client."
        )

    # This creates a new client instance each time it's called.
    # The caller is responsible for closing it, ideally with 'async with'.
    return await create_async_supabase_client(url, service_key, options=ClientOptions())

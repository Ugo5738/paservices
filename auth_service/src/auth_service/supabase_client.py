import asyncio

from supabase._async.client import AsyncClient as AsyncSupabaseClient
from supabase._async.client import create_client as create_async_supabase_client
from supabase.lib.client_options import ClientOptions

from auth_service.config import settings
from auth_service.logging_config import logger

# Global instances for both clients
_global_async_supabase_client: AsyncSupabaseClient | None = None
_global_admin_supabase_client: AsyncSupabaseClient | None = None


async def init_supabase_clients():
    """
    Initializes the global Supabase clients.
    This function should be called once at application startup.
    """
    global _global_async_supabase_client, _global_admin_supabase_client

    if _global_async_supabase_client and _global_admin_supabase_client:
        logger.info("Supabase clients already initialized.")
        return

    url = settings.SUPABASE_URL
    anon_key = settings.SUPABASE_ANON_KEY
    service_key = settings.SUPABASE_SERVICE_ROLE_KEY

    if not all([url, anon_key, service_key]):
        logger.error("Supabase URL, Anon Key, or Service Role Key is not configured.")
        raise ValueError("Supabase configuration is incomplete.")

    # --- Initialize Regular Client (with anon key) ---
    logger.info(f"Initializing Supabase AsyncClient with URL: {url[:20]}...")
    try:
        _global_async_supabase_client = await create_async_supabase_client(
            url, anon_key
        )
        logger.info("Supabase AsyncClient initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}", exc_info=True)
        _global_async_supabase_client = None
        raise

    # --- Initialize Admin Client (with service role key) ---
    logger.info("Initializing Supabase Admin Client...")
    try:
        _global_admin_supabase_client = await create_async_supabase_client(
            url, service_key
        )
        logger.info("Supabase Admin Client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase Admin client: {e}", exc_info=True)
        _global_admin_supabase_client = None
        raise


async def close_supabase_clients():
    """
    Closes the global Supabase clients by clearing the references.
    This function should be called once at application shutdown.
    """
    global _global_async_supabase_client, _global_admin_supabase_client
    if _global_async_supabase_client or _global_admin_supabase_client:
        logger.info("Closing Supabase clients...")
        _global_async_supabase_client = None
        _global_admin_supabase_client = None
        logger.info("Supabase client references cleared.")


def get_supabase_client() -> AsyncSupabaseClient:
    """
    FastAPI dependency to get the globally initialized anonymous Supabase client.
    """
    if _global_async_supabase_client is None:
        logger.error("Supabase client accessed before initialization.")
        raise RuntimeError("Supabase client not available. Check application lifespan.")
    return _global_async_supabase_client


def get_supabase_admin_client() -> AsyncSupabaseClient:
    """
    FastAPI dependency to get the globally initialized admin (service_role) Supabase client.
    """
    if _global_admin_supabase_client is None:
        logger.error("Supabase admin client accessed before initialization.")
        raise RuntimeError(
            "Supabase admin client not available. Check application lifespan."
        )
    return _global_admin_supabase_client

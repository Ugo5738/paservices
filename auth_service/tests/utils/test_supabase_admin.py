import asyncio
import os
import socket

import pytest
from dotenv import load_dotenv
from gotrue.errors import AuthApiError
from supabase._async.client import AsyncClient as AsyncSupabaseClient
from supabase._async.client import create_client
from supabase.lib.client_options import ClientOptions


@pytest.mark.asyncio
async def test_list_users():
    env_production_path = os.path.join(os.path.dirname(__file__), ".env.production")
    if os.path.exists(env_production_path):
        print(f"Loading environment variables from: {env_production_path}")
        load_dotenv(dotenv_path=env_production_path, override=True)
    else:
        print(
            f"Warning: {env_production_path} not found. Falling back to default .env or shell variables."
        )
        load_dotenv(override=True)

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not supabase_service_key:
        print("Error: SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY not found.")
        return

    print(f"Attempting to connect to Supabase URL: {supabase_url}")
    print(
        f"Using Service Role Key: {'*' * (len(supabase_service_key) - 4) + supabase_service_key[-4:]}"
    )

    # Create an async session for the client
    async_client: AsyncSupabaseClient = None  # Define it outside try
    try:
        # Explicitly create an AsyncClient using create_async_client
        # The service_role_key is used as the anon_key for admin operations
        async_client = await create_client(supabase_url, supabase_service_key)

        print(f"Supabase client type: {type(async_client)}")
        print(f"Supabase client auth type: {type(async_client.auth)}")
        print(f"Supabase client auth admin type: {type(async_client.auth.admin)}")
        print(
            f"Supabase client auth admin list_users type: {type(async_client.auth.admin.list_users)}"
        )

        print("Attempting to list users (admin action)...")

        list_users_method = async_client.auth.admin.list_users
        is_awaitable = asyncio.iscoroutinefunction(list_users_method)
        print(f"Is list_users_method awaitable? {is_awaitable}")

        if not is_awaitable:
            print(
                "ERROR: list_users method is not awaitable even with AsyncClient. Check Supabase library version/usage."
            )
            return

        response = await list_users_method()

        if response and hasattr(response, "users") and response.users is not None:
            print(f"\nSuccessfully listed users! Found {len(response.users)} user(s).")
            if response.users:
                print("First few users:")
                for i, user_item in enumerate(response.users):
                    if i < 3:
                        print(
                            f"  - ID: {user_item.id}, Email: {user_item.email}, Created At: {user_item.created_at}"
                        )
                    else:
                        print(f"  ... and {len(response.users) - 3} more user(s)")
                        break
            else:
                print("No users found in the project.")
        else:
            print("Received an unexpected response structure from list_users.")
            print(f"Response type: {type(response)}")
            print(f"Response: {response}")

    except AuthApiError as e:
        print(f"\nSupabase AuthApiError occurred:")
        print(f"  Message: {e.message}")
        print(f"  Status Code: {e.status}")
        print(f"  Code: {getattr(e, 'code', 'N/A')}")
        if (
            "403" in str(e.status)
            or "Forbidden" in e.message
            or "User not allowed" in e.message
        ):
            print(
                "  This looks like a PERMISSION DENIED error. Double-check your SERVICE_ROLE_KEY and its permissions."
            )
        elif (
            "401" in str(e.status)
            or "Unauthorized" in e.message
            or "Invalid API key" in e.message
        ):
            print(
                "  This looks like an AUTHENTICATION FAILED error. Ensure the SERVICE_ROLE_KEY is correct and active."
            )
    except TypeError as e:
        print(f"\nTypeError occurred: {e}")
        print(
            "This often means you are awaiting a non-awaitable object or the supabase client/method is not async as expected."
        )
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        print(f"Error type: {type(e)}")
    finally:
        if async_client:
            print("Closing Supabase async client session...")


if __name__ == "__main__":
    asyncio.run(test_list_users())

import asyncio
import os

import httpx
from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

# Load environment variables from mcp_app/.env
load_dotenv(dotenv_path="mcp_app/.env")


async def get_stytch_token() -> str | None:
    """Authenticates with Stytch using Client Credentials to get an M2M token."""
    print("Attempting to get M2M token from Stytch...")
    project_id = os.getenv("STYTCH_PROJECT_ID")
    client_id = os.getenv("STYTCH_CLIENT_ID")
    client_secret = os.getenv("STYTCH_CLIENT_SECRET")

    if not all([project_id, client_id, client_secret]):
        print(
            "Error: STYTCH_PROJECT_ID, STYTCH_CLIENT_ID, or STYTCH_CLIENT_SECRET is not set in mcp_app/.env."
        )
        return None

    # --- THIS IS THE CORRECTED URL STRUCTURE, AS PER STYTCH DOCUMENTATION ---
    # token_url = f"https://test.stytch.com/v1/projects/{project_id}/oauth/token"
    token_url = f"https://test.stytch.com/v1/public/{project_id}/oauth2/token"
    # -----------------------------------------------------------------------

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    try:
        async with httpx.AsyncClient() as client:
            # Stytch expects form-encoded data, so we use `data=payload`
            response = await client.post(token_url, data=payload)
            response.raise_for_status()
            token_data = response.json()
            access_token = token_data.get("access_token")
            if access_token:
                print("Successfully obtained Stytch access token.")
                return access_token
            else:
                print("Error: 'access_token' not found in Stytch response.")
                return None
    except httpx.HTTPStatusError as e:
        print(
            f"Error authenticating with Stytch: {e.response.status_code} - {e.response.text}"
        )
        return None
    except Exception as e:
        print(f"An unexpected error occurred during Stytch authentication: {e}")
        return None


async def call_mcp():
    token = await get_stytch_token()
    if not token:
        print("Could not retrieve token, aborting MCP call.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    transport = StreamableHttpTransport("http://127.0.0.1:8000/mcp", headers=headers)
    client = Client(transport=transport)

    async with client:
        await client.ping()
        print("\nSuccessfully pinged the MCP server.")

        tools = await client.list_tools()
        print("\n===============================Tools===============================\n")
        print("\n".join([tool.name for tool in tools]))

        try:
            result = await client.call_tool("get_my_notes")
            print(
                "\n===============================Get Notes Tool Result===============================\n"
            )
            print(result.content[0].text)

            result = await client.call_tool(
                "add_note",
                {"content": "This is a test note from an authenticated client."},
            )
            print(
                "\n===============================Add Note Tool Result================================\n"
            )
            print(result.content[0].text)

        except Exception as e:
            print(
                "\n===============================Tool Error===============================\n"
            )
            print(e)


if __name__ == "__main__":
    asyncio.run(call_mcp())

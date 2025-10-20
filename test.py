# test.py
import asyncio
from typing import Any, Optional

import httpx
import jwt
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

AUTH_SERVICE_URL = "http://localhost:8001"
CLIENT_ID = "fe2c7655-0860-4d98-9034-cd5e1ac90a41"
CLIENT_SECRET = "dev-rightmove-service-secret"


async def get_auth_token() -> Optional[str]:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{AUTH_SERVICE_URL}/api/v1/auth/token",
            json={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "scope": "super_id:generate",
            },
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def call_mcp():
    token = await get_auth_token()

    transport = StreamableHttpTransport(
        url="http://localhost:8765/mcp",
        headers={"Authorization": f"Bearer {token}"},
    )
    client = Client(transport=transport)

    async with client:
        await client.ping()

        tools = await client.list_tools()
        print("Tools:", [t.name for t in tools])

        result = await client.call_tool("create_super_id", {"prefix": "svc_"})
        print("create_super_id result:", result.content[0].text)


if __name__ == "__main__":
    asyncio.run(call_mcp())

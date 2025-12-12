import contextlib
import json

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import AuthMiddleware
from .config import settings
from .crud import get_analysis_result, upsert_analysis_result
from .db import get_db
from .mcp_metadata import prompts as prompt_templates
from .mcp_metadata import resources as resources_catalog
from .mcp_tools import mcp as mcp_app
from .rate_limiter import rate_limit_middleware
from .schemas import AnalysisCallbackPayload
from .utils.logging_config import logger


# Create a combined lifespan to manage the MCP session manager
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_app.session_manager.run():
        yield


app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your actual origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# # Add rate limiting middleware (simple in-memory implementation)
# app.middleware("http")(rate_limit_middleware)


# MCP well-known endpoint
@app.get("/.well-known/oauth-protected-resource/mcp")
async def oauth_protected_resource_metadata():
    """
    OAuth 2.0 Protected Resource Metadata endpoint for MCP client discovery.
    Required by the MCP specification for authorization server discovery.
    """

    return {
        "authorization_servers": [settings.SCALEKIT_AUTHORIZATION_SERVERS],
        "bearer_methods_supported": ["header"],
        "resource": settings.SCALEKIT_RESOURCE_NAME,
        "resource_documentation": settings.SCALEKIT_RESOURCE_DOCS_URL,
        "scopes_supported": ["users:analyze"],
    }


# Create and mount the MCP server with authentication
mcp_server = mcp_app.streamable_http_app()
app.add_middleware(AuthMiddleware)
app.mount("/", mcp_server)


# @app.get("/mcp/resources")
# async def get_mcp_resources():
#     return resources_catalog()


# @app.get("/mcp/prompts")
# async def get_mcp_prompts():
#     return prompt_templates()


@app.post("/api/analysis/callback")
async def receive_analysis_callback(
    payload: AnalysisCallbackPayload, db=Depends(get_db)
):
    """Endpoint for n8n to post final workflow results."""
    stored = await upsert_analysis_result(
        db, payload.super_id, payload.model_dump(exclude_none=True)
    )
    logger.info(
        "Stored workflow callback",
        extra={"super_id": payload.super_id, "status": stored.status},
    )
    return {"status": "accepted", "super_id": payload.super_id}


@app.get("/api/analysis/results/{super_id}")
async def read_analysis_result(super_id: str, db=Depends(get_db)):
    """Fetch a stored workflow result."""
    result = await get_analysis_result(db, super_id)
    if result:
        return result.to_dict()
    return {"super_id": super_id, "status": "pending"}


def main():
    """Main entry point for the MCP server."""
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")


if __name__ == "__main__":
    main()

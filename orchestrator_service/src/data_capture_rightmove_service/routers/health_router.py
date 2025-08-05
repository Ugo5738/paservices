"""
Health check endpoints for monitoring service status.
"""

import os
import time
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Security
from fastapi.security import HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from supabase._async.client import AsyncClient as AsyncSupabaseClient

from data_capture_rightmove_service.clients.auth_service_client import (
    auth_service_client,
)
from data_capture_rightmove_service.clients.super_id_service_client import (
    super_id_service_client,
)
from data_capture_rightmove_service.config import settings
from data_capture_rightmove_service.db import get_db
from data_capture_rightmove_service.schemas.common import (
    ComponentHealth,
    HealthCheckResponse,
    HealthStatus,
)
from data_capture_rightmove_service.utils.logging_config import logger
from data_capture_rightmove_service.utils.security import validate_token

router = APIRouter(tags=["Health"])

# Track app startup time for uptime monitoring
start_time = time.time()


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HealthCheckResponse:
    """
    Basic health check endpoint for the service.
    Can be used by Kubernetes liveness and readiness probes.
    """
    current_time = datetime.utcnow()
    response = {
        "status": HealthStatus.OK,
        "version": "0.1.0",  # TODO: Get from version file
        "timestamp": current_time,
        "components": {"api": {"status": HealthStatus.OK}},
        "uptime_seconds": time.time() - start_time,
    }

    # Check database connectivity
    try:
        result = await db.execute(text("SELECT 1"))
        row = result.scalar()
        if row == 1:
            response["components"]["database"] = {"status": HealthStatus.OK}
        else:
            response["components"]["database"] = {
                "status": HealthStatus.ERROR,
                "message": "Database query returned unexpected result",
            }
            response["status"] = HealthStatus.ERROR
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        response["components"]["database"] = {
            "status": HealthStatus.ERROR,
            "message": f"Database connection error: {str(e)}",
        }
        response["status"] = HealthStatus.ERROR

    # For Kubernetes probes, we might want to simplify the response
    is_k8s_probe = "kube-probe" in request.headers.get("user-agent", "").lower()

    # If this is a Kubernetes probe and we want to avoid pod restarts during maintenance,
    # we could always return status OK, but log the actual status
    if is_k8s_probe and response["status"] != HealthStatus.OK:
        logger.warning(
            f"Health check failed but reporting OK for K8s probe: {response}"
        )
        # For K8s probes, we still report OK to avoid unnecessary pod restarts
        response["status"] = HealthStatus.OK

    return HealthCheckResponse(**response)


@router.get("/health/detailed", response_model=HealthCheckResponse)
async def detailed_health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HealthCheckResponse:
    """
    Detailed health check that tests connectivity to all dependent services.
    This is more thorough than the basic health check and intended for internal monitoring.
    """
    # Start with basic health check
    response = await health_check(request, db)
    response_dict = response.model_dump()

    # Check auth service connectivity
    try:
        # Log the attempt to access auth service
        logger.debug(
            f"Testing auth service connectivity at: {settings.AUTH_SERVICE_URL}"
        )
        # Just test if we can get a token
        token = await auth_service_client.get_token()
        if token:
            response_dict["components"]["auth_service"] = {"status": HealthStatus.OK}
        else:
            response_dict["components"]["auth_service"] = {
                "status": HealthStatus.ERROR,
                "message": "Failed to acquire token from auth service",
            }
            response_dict["status"] = HealthStatus.ERROR
    except Exception as e:
        logger.error(f"Auth service health check failed: {str(e)}")
        response_dict["components"]["auth_service"] = {
            "status": HealthStatus.ERROR,
            "message": f"Auth service error: {str(e)}",
        }
        response_dict["status"] = HealthStatus.ERROR

    # Check super ID service connectivity (only if auth service is OK)
    if (
        response_dict["components"].get("auth_service", {}).get("status")
        == HealthStatus.OK
    ):
        try:
            # Log the attempt to access super_id service
            logger.debug(
                f"Testing super_id service connectivity at: {settings.SUPER_ID_SERVICE_URL}"
            )
            # Create a test super ID
            super_id = await super_id_service_client.create_super_id(
                description="Health check test"
            )
            if super_id:
                response_dict["components"]["super_id_service"] = {
                    "status": HealthStatus.OK
                }
            else:
                response_dict["components"]["super_id_service"] = {
                    "status": HealthStatus.ERROR,
                    "message": "Failed to generate super ID",
                }
                response_dict["status"] = HealthStatus.ERROR
        except Exception as e:
            logger.error(f"Super ID service health check failed: {str(e)}")
            response_dict["components"]["super_id_service"] = {
                "status": HealthStatus.ERROR,
                "message": f"Super ID service error: {str(e)}",
            }
            response_dict["status"] = HealthStatus.ERROR

    # Include environment information
    response_dict["components"]["environment"] = {
        "status": HealthStatus.OK,
        "message": f"Environment: {settings.ENVIRONMENT}",
    }

    # Include process information
    response_dict["components"]["process"] = {
        "status": HealthStatus.OK,
        "message": f"PID: {os.getpid()}",
    }

    return HealthCheckResponse(**response_dict)

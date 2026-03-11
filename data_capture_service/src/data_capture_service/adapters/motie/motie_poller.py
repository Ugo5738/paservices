"""
Motie polling logic with exponential backoff.

Polls GET /api/v1/agent/session/:id until the session completes or times out.
Default: 5s initial → 1.5x multiplier → 30s cap → 300s total max.
"""

import asyncio
import logging
import time
from typing import Optional

from data_capture_service.config import settings

from .motie_client import MotieClient, MotieSessionResponse

logger = logging.getLogger(__name__)


class MotiePollerTimeout(Exception):
    """Raised when polling exceeds the maximum timeout."""

    pass


class MotiePollerError(Exception):
    """Raised when the Motie session fails."""

    pass


async def poll_session(
    client: MotieClient,
    session_id: str,
    timeout: Optional[float] = None,
    initial_interval: Optional[float] = None,
    backoff: Optional[float] = None,
    max_interval: Optional[float] = None,
) -> MotieSessionResponse:
    """
    Poll a Motie session until it completes, fails, or times out.

    Uses exponential backoff:
    - initial_interval: 5s (default)
    - backoff multiplier: 1.5x (default)
    - max_interval cap: 30s (default)
    - total timeout: 300s (default)

    Returns the final MotieSessionResponse.
    Raises MotiePollerTimeout if the session doesn't complete in time.
    Raises MotiePollerError if the session fails.
    """
    timeout = timeout or settings.MOTIE_POLL_TIMEOUT
    interval = initial_interval or settings.MOTIE_POLL_INTERVAL
    backoff_mult = backoff or settings.MOTIE_POLL_BACKOFF
    max_iv = max_interval or settings.MOTIE_POLL_MAX_INTERVAL

    start_time = time.time()
    poll_count = 0

    logger.info(
        f"Starting poll for Motie session {session_id} "
        f"(timeout={timeout}s, interval={interval}s, backoff={backoff_mult}x, cap={max_iv}s)"
    )

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            logger.error(
                f"Motie session {session_id} timed out after {elapsed:.1f}s ({poll_count} polls)"
            )
            raise MotiePollerTimeout(
                f"Motie session {session_id} did not complete within {timeout}s"
            )

        poll_count += 1
        try:
            session = await client.get_session(session_id)
        except Exception as e:
            logger.warning(
                f"Poll #{poll_count} for session {session_id} failed: {e}. Retrying..."
            )
            await asyncio.sleep(interval)
            interval = min(interval * backoff_mult, max_iv)
            continue

        status = session.status.lower()
        logger.debug(
            f"Poll #{poll_count} for session {session_id}: status={status}, "
            f"elapsed={elapsed:.1f}s, next_interval={interval:.1f}s"
        )

        if status == "completed":
            logger.info(
                f"Motie session {session_id} completed after {elapsed:.1f}s ({poll_count} polls)"
            )
            return session

        if status in ("failed", "error", "cancelled"):
            error_msg = session.error or f"Session ended with status: {status}"
            logger.error(f"Motie session {session_id} failed: {error_msg}")
            raise MotiePollerError(error_msg)

        # Still running — wait and retry with backoff
        await asyncio.sleep(interval)
        interval = min(interval * backoff_mult, max_iv)

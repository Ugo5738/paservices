"""
Fetcher Audit — thin convenience layer over fetcher_run_crud.

Wraps the column-naming for `fetcher_run_crud.record` so routers don't
have to import the model directly.

After chunk 5 of the V2 SuperID implementation, every fetcher run is a
single-shot, immutable row. The previous multi-shot helpers
(`record_loop_attempt`, `promote_winner_in_group`) and the
`draft → final → superseded` status lifecycle are gone. Iteration is
expressed by a new SuperID per pass plus a link record connecting the
new SuperID to the prior one; see
docs/data_capture_v2_id_and_data_flow.md.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.crud import fetcher_run_crud
from data_capture_service.models.fetcher_run import FetcherRun, FetcherRunKind

logger = logging.getLogger(__name__)


async def record_run(
    db: AsyncSession,
    *,
    kind: str,
    vendor: str,
    url: str,
    domain: str,
    super_id: Optional[UUID] = None,
    fetcher_id: Optional[UUID] = None,
    ai_fetcher_id: Optional[UUID] = None,
    motie_build_id: Optional[UUID] = None,
    completeness_score: Optional[float] = None,
    payload_json: Optional[Dict[str, Any]] = None,
    fields_json: Optional[Dict[str, Any]] = None,
    field_presence_json: Optional[Dict[str, Any]] = None,
    missing_fields_json: Optional[List[str]] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
    succeeded: bool = True,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> FetcherRun:
    """
    Persist one V2 primitive call as a single immutable row.

    `succeeded` is a caller hint: when False, the helper ensures an
    `error_message` is populated (using a synthetic placeholder if the
    caller didn't supply one) so the derived `FetcherRun.succeeded`
    property returns the right answer even if the caller forgot to set
    `error_message`.
    """
    if not succeeded and not error_message:
        error_message = "fetcher run reported failure with no detail"
    return await fetcher_run_crud.record(
        db,
        kind=kind,
        vendor=vendor,
        url=url,
        domain=domain,
        super_id=super_id,
        fetcher_id=fetcher_id,
        ai_fetcher_id=ai_fetcher_id,
        motie_build_id=motie_build_id,
        completeness_score=completeness_score,
        payload_json=payload_json,
        fields_json=fields_json,
        field_presence_json=field_presence_json,
        missing_fields_json=missing_fields_json,
        error_message=error_message,
        duration_ms=duration_ms,
        metadata_json=metadata_json,
    )


# Backwards-compatible alias for callers still using the chunk-3-era name.
# Slated for removal once those callers (none remaining at chunk 5 commit
# time within this repo) are updated.
record_single_shot_run = record_run

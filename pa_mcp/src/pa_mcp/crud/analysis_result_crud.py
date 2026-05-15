from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.analysis_result import AnalysisResult


async def upsert_analysis_result(
    db: AsyncSession, super_id: str, payload: Dict[str, Any]
) -> AnalysisResult:
    """
    Upsert an analysis result row keyed by super_id.

    Note on principles compliance (chunk 4 review, 2026-05-15): this upsert
    is NOT a violation of the per-service single-use check
    (docs/superid_principles.md section 4). It exists because the
    analysis_results table aggregates partial callbacks from multiple
    downstream services (data_capture, floorplan_analysis,
    image_condition_analysis) that each contribute a slice of the
    consumer-facing result for ONE analysis run. The upsert represents
    progressive state of pa_mcp's single use of the super_id, not
    multiple uses.

    Fuller principles hygiene would convert this table to append-only
    event sourcing: each callback writes a new (super_id, context, ...)
    row and a view aggregates the latest values per context. That refactor
    is deferred — see docs/data_capture_v2_architecture.md section 8.
    """
    values = {"super_id": super_id, **payload}
    stmt = insert(AnalysisResult).values(values)

    # Only update columns that are present in the incoming payload to avoid
    # overwriting existing data with NULLs from partial callbacks.
    allowed_update_cols = {col.name for col in AnalysisResult.__table__.columns} - {
        "super_id",
        "created_at",
    }
    update_values = {
        key: stmt.excluded[key] for key in payload.keys() if key in allowed_update_cols
    }
    update_values["updated_at"] = func.now()  # Always bump updated_at

    stmt = stmt.on_conflict_do_update(
        index_elements=[AnalysisResult.super_id],
        set_=update_values,
    ).returning(AnalysisResult)

    result = await db.execute(stmt)
    return result.scalar_one()


async def get_analysis_result(
    db: AsyncSession, super_id: str
) -> Optional[AnalysisResult]:
    """Fetch an analysis result by super_id."""
    stmt = select(AnalysisResult).where(AnalysisResult.super_id == super_id).limit(1)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

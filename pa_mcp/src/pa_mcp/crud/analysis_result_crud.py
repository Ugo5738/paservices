from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.analysis_result import AnalysisResult


async def upsert_analysis_result(
    db: AsyncSession, super_id: str, payload: Dict[str, Any]
) -> AnalysisResult:
    """Upsert an analysis result row keyed by super_id."""
    values = {"super_id": super_id, **payload}
    stmt = insert(AnalysisResult).values(values)

    update_values = {
        col.name: stmt.excluded[col.name]
        for col in AnalysisResult.__table__.columns
        if col.name not in ("super_id", "created_at")
    }
    update_values["updated_at"] = func.now()

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

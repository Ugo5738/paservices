"""
DataCapture Pipeline — Core orchestrator for the data_capture workflow.

Pipeline steps:
1. Create DataCaptureRun (status=pending)
2. Run Firecrawl baseline → store raw+parsed in source tables (step_type=baseline)
3. For each adapter: fetch_raw → parse → validate_against_baseline → score
4. If score >= 0.85 and validation passes → canonical_mapper → store → completed
5. If score < 0.7 or validation fails → next adapter
6. Chain exhausted → store best result → completed_with_warnings or failed
"""

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.adapters.base import (
    AdapterStatus,
    BaselineResult,
    CompletenessScore,
    ParsedDataCaptureResult,
    RawDataCaptureResult,
    DataCaptureRequest,
    DataCaptureAdapter,
)
from data_capture_service.adapters.motie import motie_adapter
from data_capture_service.config import settings
from data_capture_service.crud import canonical_crud, data_capture_run_crud, data_capture_step_crud
from data_capture_service.crud import source_record_crud, usage_crud
from data_capture_service.mappers.canonical_mapper import map_to_canonical
from data_capture_service.models.data_capture_run import DataCaptureRun, DataCaptureRunMode, DataCaptureRunStatus
from data_capture_service.models.data_capture_run_step import StepStatus, StepType
from data_capture_service.services.baseline_provider import firecrawl_baseline_provider
from data_capture_service.services.field_registry import compute_completeness_score
from data_capture_service.services.validation_gate import validate_against_baseline
from data_capture_service.utils.url_utils import extract_domain

logger = logging.getLogger(__name__)


class DataCapturePipeline:
    """
    Core pipeline orchestrator.

    Coordinates: baseline → adapter chain → validation → scoring → storage.
    """

    def __init__(self):
        # Adapter registry — order determines fallback chain
        self._adapters: Dict[str, DataCaptureAdapter] = {}
        self._adapter_chain: List[str] = []
        self._register_adapters()

    def _register_adapters(self):
        """Register available adapters in priority order."""
        if settings.motie_enabled():
            self._adapters["motie"] = motie_adapter
            self._adapter_chain.append("motie")
            logger.info("Registered Motie adapter")

    def get_adapter(self, name: str) -> Optional[DataCaptureAdapter]:
        """Get a specific adapter by name."""
        return self._adapters.get(name)

    async def execute(
        self,
        db: AsyncSession,
        url: str,
        super_id: uuid.UUID,
        skip_baseline: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DataCaptureRun:
        """
        Full orchestrated pipeline: baseline → adapter chain → validate → score → store.
        """
        domain = extract_domain(url)

        # Step 1: Create run
        run = await data_capture_run_crud.create_run(
            db=db,
            super_id=super_id,
            target_url=url,
            target_domain=domain,
            mode=DataCaptureRunMode.ORCHESTRATED,
        )
        logger.info(f"Created data_capture run {run.id} for {url}")

        # Step 2: Run baseline
        baseline: Optional[BaselineResult] = None
        step_order = 0

        if not skip_baseline and settings.firecrawl_enabled():
            await data_capture_run_crud.update_run_status(
                db, run.id, DataCaptureRunStatus.BASELINE_RUNNING
            )

            baseline_step = await data_capture_step_crud.create_step(
                db=db,
                run_id=run.id,
                step_order=step_order,
                adapter_name="firecrawl_baseline",
                step_type=StepType.BASELINE,
                provider_type="firecrawl",
            )
            step_order += 1

            try:
                baseline = await firecrawl_baseline_provider.fetch_baseline(url)

                # Store baseline raw record
                raw_rec = await source_record_crud.store_raw_record(
                    db=db,
                    run_id=run.id,
                    step_id=baseline_step.id,
                    adapter_name="firecrawl_baseline",
                    payload_json={"markdown": baseline.markdown} if baseline.markdown else None,
                    source_domain=domain,
                )

                # Store baseline parsed record
                await source_record_crud.store_parsed_record(
                    db=db,
                    run_id=run.id,
                    step_id=baseline_step.id,
                    raw_record_id=raw_rec.id,
                    adapter_name="firecrawl_baseline",
                    field_presence_json=baseline.field_presence,
                )

                # Record usage
                await usage_crud.record_usage(
                    db=db,
                    run_id=run.id,
                    step_id=baseline_step.id,
                    adapter_name="firecrawl_baseline",
                    operation="data_capture_baseline",
                    credits_used=baseline.credits_used,
                    request_count=1,
                )

                await data_capture_step_crud.update_step(
                    db=db,
                    step_id=baseline_step.id,
                    status=StepStatus.COMPLETED if baseline.status == AdapterStatus.SUCCESS else StepStatus.FAILED,
                    duration_ms=baseline.duration_ms,
                    error_message=baseline.error_message,
                )

            except Exception as e:
                logger.error(f"Baseline step failed: {e}", exc_info=True)
                await data_capture_step_crud.update_step(
                    db=db,
                    step_id=baseline_step.id,
                    status=StepStatus.FAILED,
                    error_message=str(e),
                )

        # Step 3: Adapter chain
        await data_capture_run_crud.update_run_status(
            db, run.id, DataCaptureRunStatus.SCRAPING
        )

        best_result: Optional[Tuple[ParsedDataCaptureResult, CompletenessScore, str]] = None
        fallback_count = 0

        for adapter_name in self._adapter_chain:
            adapter = self._adapters[adapter_name]
            request = DataCaptureRequest(
                url=url,
                super_id=str(super_id),
                adapter_name=adapter_name,
            )

            result = await self._run_adapter(
                db=db,
                run=run,
                adapter=adapter,
                adapter_name=adapter_name,
                request=request,
                baseline=baseline,
                step_order=step_order,
            )
            step_order += 1

            if result is None:
                fallback_count += 1
                continue

            parsed, score, validation_passed = result

            # Accept if score >= threshold and validation passes
            if score.overall >= settings.COMPLETENESS_ACCEPT_THRESHOLD and validation_passed:
                await self._store_canonical(
                    db=db,
                    run=run,
                    parsed=parsed,
                    score=score,
                    adapter_name=adapter_name,
                    fallback_count=fallback_count,
                )
                return run

            # Track best result for fallback
            if best_result is None or score.overall > best_result[1].overall:
                best_result = (parsed, score, adapter_name)

            # Fallback if score < threshold
            if score.overall < settings.COMPLETENESS_FALLBACK_THRESHOLD or not validation_passed:
                fallback_count += 1
                continue

            # Score is between fallback and accept — still store but with warnings
            await self._store_canonical(
                db=db,
                run=run,
                parsed=parsed,
                score=score,
                adapter_name=adapter_name,
                fallback_count=fallback_count,
                with_warnings=True,
            )
            return run

        # Step 6: Chain exhausted
        if best_result:
            parsed, score, adapter_name = best_result
            await self._store_canonical(
                db=db,
                run=run,
                parsed=parsed,
                score=score,
                adapter_name=adapter_name,
                fallback_count=fallback_count,
                with_warnings=True,
            )
        else:
            await data_capture_run_crud.update_run_status(
                db=db,
                run_id=run.id,
                status=DataCaptureRunStatus.FAILED,
                error_message="All adapters failed",
                fallback_count=fallback_count,
            )

        return run

    async def execute_single_adapter(
        self,
        db: AsyncSession,
        url: str,
        super_id: uuid.UUID,
        adapter_name: str,
        skip_baseline: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DataCaptureRun:
        """
        Direct adapter call (for per-adapter endpoints).
        Still runs baseline + validation for data quality.
        """
        adapter = self.get_adapter(adapter_name)
        if not adapter:
            raise ValueError(f"Unknown adapter: {adapter_name}")

        domain = extract_domain(url)

        run = await data_capture_run_crud.create_run(
            db=db,
            super_id=super_id,
            target_url=url,
            target_domain=domain,
            mode=DataCaptureRunMode.DIRECT_ADAPTER,
            selected_adapter=adapter_name,
        )

        # Run baseline
        baseline: Optional[BaselineResult] = None
        step_order = 0

        if not skip_baseline and settings.firecrawl_enabled():
            await data_capture_run_crud.update_run_status(
                db, run.id, DataCaptureRunStatus.BASELINE_RUNNING
            )
            baseline_step = await data_capture_step_crud.create_step(
                db=db,
                run_id=run.id,
                step_order=step_order,
                adapter_name="firecrawl_baseline",
                step_type=StepType.BASELINE,
                provider_type="firecrawl",
            )
            step_order += 1

            try:
                baseline = await firecrawl_baseline_provider.fetch_baseline(url)
                raw_rec = await source_record_crud.store_raw_record(
                    db=db,
                    run_id=run.id,
                    step_id=baseline_step.id,
                    adapter_name="firecrawl_baseline",
                    payload_json={"markdown": baseline.markdown} if baseline.markdown else None,
                    source_domain=domain,
                )
                await source_record_crud.store_parsed_record(
                    db=db,
                    run_id=run.id,
                    step_id=baseline_step.id,
                    raw_record_id=raw_rec.id,
                    adapter_name="firecrawl_baseline",
                    field_presence_json=baseline.field_presence,
                )
                await usage_crud.record_usage(
                    db=db,
                    run_id=run.id,
                    step_id=baseline_step.id,
                    adapter_name="firecrawl_baseline",
                    operation="data_capture_baseline",
                    credits_used=baseline.credits_used,
                    request_count=1,
                )
                await data_capture_step_crud.update_step(
                    db=db,
                    step_id=baseline_step.id,
                    status=StepStatus.COMPLETED if baseline.status == AdapterStatus.SUCCESS else StepStatus.FAILED,
                    duration_ms=baseline.duration_ms,
                )
            except Exception as e:
                logger.error(f"Baseline failed: {e}")
                await data_capture_step_crud.update_step(
                    db=db, step_id=baseline_step.id, status=StepStatus.FAILED, error_message=str(e)
                )

        # Run adapter
        await data_capture_run_crud.update_run_status(db, run.id, DataCaptureRunStatus.SCRAPING)

        request = DataCaptureRequest(url=url, super_id=str(super_id), adapter_name=adapter_name)
        result = await self._run_adapter(
            db=db, run=run, adapter=adapter, adapter_name=adapter_name,
            request=request, baseline=baseline, step_order=step_order,
        )

        if result:
            parsed, score, validation_passed = result
            with_warnings = not validation_passed or score.overall < settings.COMPLETENESS_ACCEPT_THRESHOLD
            await self._store_canonical(
                db=db, run=run, parsed=parsed, score=score,
                adapter_name=adapter_name, with_warnings=with_warnings,
            )
        else:
            await data_capture_run_crud.update_run_status(
                db=db, run_id=run.id, status=DataCaptureRunStatus.FAILED,
                error_message=f"Adapter {adapter_name} failed",
            )

        return run

    async def _run_adapter(
        self,
        db: AsyncSession,
        run: DataCaptureRun,
        adapter: DataCaptureAdapter,
        adapter_name: str,
        request: DataCaptureRequest,
        baseline: Optional[BaselineResult],
        step_order: int,
    ) -> Optional[Tuple[ParsedDataCaptureResult, CompletenessScore, bool]]:
        """
        Run a single adapter through: fetch → parse → validate → score.
        Returns (parsed, score, validation_passed) or None on failure.
        """
        # Create data_capture step
        data_capture_step = await data_capture_step_crud.create_step(
            db=db,
            run_id=run.id,
            step_order=step_order,
            adapter_name=adapter_name,
            step_type=StepType.DATA_CAPTURE,
            provider_type=adapter_name,
        )

        try:
            # Fetch raw
            raw = await adapter.fetch_raw(request)

            # Store raw record
            raw_rec = await source_record_crud.store_raw_record(
                db=db,
                run_id=run.id,
                step_id=data_capture_step.id,
                adapter_name=adapter_name,
                payload_json=raw.payload,
                source_domain=run.target_domain,
                http_status_code=raw.http_status_code,
                http_meta_json=raw.http_meta,
                content_hash=raw.content_hash,
            )

            if raw.status != AdapterStatus.SUCCESS:
                await data_capture_step_crud.update_step(
                    db=db,
                    step_id=data_capture_step.id,
                    status=StepStatus.FAILED,
                    error_message=raw.error_message,
                    duration_ms=raw.duration_ms,
                    provider_run_id=raw.provider_run_id,
                )
                return None

            # Parse
            parsed = await adapter.parse(raw)

            # Store parsed record
            await source_record_crud.store_parsed_record(
                db=db,
                run_id=run.id,
                step_id=data_capture_step.id,
                raw_record_id=raw_rec.id,
                adapter_name=adapter_name,
                parsed_json=parsed.fields,
                field_presence_json=parsed.field_presence,
                missing_fields=parsed.missing_fields,
            )

            if parsed.status != AdapterStatus.SUCCESS:
                await data_capture_step_crud.update_step(
                    db=db,
                    step_id=data_capture_step.id,
                    status=StepStatus.FAILED,
                    error_message=parsed.error_message,
                    duration_ms=raw.duration_ms,
                    provider_run_id=raw.provider_run_id,
                )
                return None

            # Validate against baseline
            validation = validate_against_baseline(parsed, baseline)

            # Score
            score = await adapter.score(parsed)

            # Update step
            await data_capture_step_crud.update_step(
                db=db,
                step_id=data_capture_step.id,
                status=StepStatus.COMPLETED,
                completeness_score=score.overall,
                duration_ms=raw.duration_ms,
                provider_run_id=raw.provider_run_id,
                metadata_json={
                    "validation_passed": validation.passed,
                    "validation_summary": validation.summary,
                    "priority_scores": score.priority_scores,
                },
            )

            # Record usage
            await usage_crud.record_usage(
                db=db,
                run_id=run.id,
                step_id=data_capture_step.id,
                adapter_name=adapter_name,
                operation="data_capture",
                request_count=1,
            )

            return parsed, score, validation.passed

        except Exception as e:
            logger.error(f"Adapter {adapter_name} failed: {e}", exc_info=True)
            await data_capture_step_crud.update_step(
                db=db,
                step_id=data_capture_step.id,
                status=StepStatus.FAILED,
                error_message=str(e),
            )
            return None

    async def _store_canonical(
        self,
        db: AsyncSession,
        run: DataCaptureRun,
        parsed: ParsedDataCaptureResult,
        score: CompletenessScore,
        adapter_name: str,
        fallback_count: int = 0,
        with_warnings: bool = False,
    ):
        """Store the canonical snapshot and update run status."""
        column_fields, extras_json, media_items = map_to_canonical(
            parsed, run.target_url, adapter_name
        )

        snapshot = await canonical_crud.create_snapshot(
            db=db,
            run_id=run.id,
            super_id=run.super_id,
            source_adapter=adapter_name,
            source_url=run.target_url,
            completeness_score=score.overall,
            column_fields=column_fields,
            extras_json=extras_json if extras_json else None,
        )

        if media_items:
            await canonical_crud.create_media_records(
                db=db,
                snapshot_id=snapshot.id,
                super_id=run.super_id,
                media_items=media_items,
            )

        status = (
            DataCaptureRunStatus.COMPLETED_WITH_WARNINGS
            if with_warnings
            else DataCaptureRunStatus.COMPLETED
        )

        await data_capture_run_crud.update_run_status(
            db=db,
            run_id=run.id,
            status=status,
            completeness_score=score.overall,
            selected_adapter=adapter_name,
            fallback_count=fallback_count,
            route_decision_json={
                "priority_scores": score.priority_scores,
                "fields_present": score.fields_present,
                "fields_total": score.fields_total,
            },
        )

        logger.info(
            f"Stored canonical snapshot for run {run.id}: "
            f"adapter={adapter_name}, score={score.overall:.4f}, status={status.value}"
        )


# Global instance
data_capture_pipeline = DataCapturePipeline()

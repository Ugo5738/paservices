"""
DataCapture Pipeline — Core orchestrator for the data_capture workflow.

Pipeline steps:
1. Create DataCaptureRun (status=pending)
2. Run Firecrawl baseline → store raw+parsed in source tables (step_type=baseline)
3. For each adapter: fetch_raw → parse → validate_against_baseline → score
4. Auto-retry: if P0/P1 fields missing, retry adapter with targeted prompt
   - Retry results stored separately, then merged with original
   - Max retries per adapter controlled by MAX_RETRIES_PER_ADAPTER config
5. If score >= 0.85 and validation passes → canonical_mapper → store → completed
6. If score < 0.7 or validation fails → next adapter
7. Chain exhausted → store best result → completed_with_warnings or failed
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.adapters.base import (
    AdapterStatus,
    BaselineResult,
    CompletenessScore,
    DataCaptureAdapter,
    DataCaptureRequest,
    ParsedDataCaptureResult,
    RawDataCaptureResult,
)
from data_capture_service.adapters.motie import motie_adapter
from data_capture_service.config import settings
from data_capture_service.crud import (
    canonical_crud,
    data_capture_run_crud,
    data_capture_step_crud,
    source_record_crud,
    usage_crud,
)
from data_capture_service.mappers.canonical_mapper import map_to_canonical
from data_capture_service.models.data_capture_run import (
    DataCaptureRun,
    DataCaptureRunMode,
    DataCaptureRunStatus,
)
from data_capture_service.models.data_capture_run_step import StepStatus, StepType
from data_capture_service.services.baseline_provider import firecrawl_baseline_provider
from data_capture_service.services.field_registry import (
    FIELD_PRIORITIES,
    compute_completeness_score,
    compute_field_presence,
    get_missing_critical_fields,
)
from data_capture_service.services.validation_gate import validate_against_baseline
from data_capture_service.utils.status_notifier import get_status_notifier
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
        existing_run_id: Optional[uuid.UUID] = None,
    ) -> DataCaptureRun:
        """
        Full orchestrated pipeline: baseline → adapter chain → validate → score → store.

        If existing_run_id is provided, reuses that run instead of creating a new one.
        This avoids the double-run problem when the caller has already created a run record.
        """
        domain = extract_domain(url)

        # Step 1: Reuse existing run or create a new one
        if existing_run_id:
            run = await data_capture_run_crud.get_run(db, existing_run_id)
            if not run:
                raise ValueError(f"Run {existing_run_id} not found")
            logger.info(f"Reusing existing data_capture run {run.id} for {url}")
        else:
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
                super_id=super_id,
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
                    payload_json=(
                        {"markdown": baseline.markdown} if baseline.markdown else None
                    ),
                    source_domain=domain,
                    super_id=super_id,
                )

                # Store baseline parsed record
                await source_record_crud.store_parsed_record(
                    db=db,
                    run_id=run.id,
                    step_id=baseline_step.id,
                    raw_record_id=raw_rec.id,
                    adapter_name="firecrawl_baseline",
                    field_presence_json=baseline.field_presence,
                    super_id=super_id,
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
                    super_id=super_id,
                )

                await data_capture_step_crud.update_step(
                    db=db,
                    step_id=baseline_step.id,
                    status=(
                        StepStatus.COMPLETED
                        if baseline.status == AdapterStatus.SUCCESS
                        else StepStatus.FAILED
                    ),
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

        best_result: Optional[
            Tuple[ParsedDataCaptureResult, CompletenessScore, str]
        ] = None
        fallback_count = 0
        adapter_errors: Dict[str, str] = {}

        for adapter_name in self._adapter_chain:
            adapter = self._adapters[adapter_name]
            request = DataCaptureRequest(
                url=url,
                super_id=str(super_id),
                adapter_name=adapter_name,
                metadata={"db": db},
            )

            result, error_reason = await self._run_adapter(
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
                if error_reason:
                    adapter_errors[adapter_name] = error_reason
                    logger.warning(
                        "Adapter %s failed for %s: %s",
                        adapter_name,
                        url,
                        error_reason,
                    )
                continue

            parsed, score, validation_passed = result

            # --- Auto-retry for missing P0/P1 fields ---
            parsed, score, validation_passed, step_order = (
                await self._retry_for_missing_fields(
                    db=db,
                    run=run,
                    adapter=adapter,
                    adapter_name=adapter_name,
                    url=url,
                    super_id=super_id,
                    parsed=parsed,
                    score=score,
                    validation_passed=validation_passed,
                    baseline=baseline,
                    step_order=step_order,
                )
            )

            # Accept if score >= threshold and validation passes
            if (
                score.overall >= settings.COMPLETENESS_ACCEPT_THRESHOLD
                and validation_passed
            ):
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

            # Fallback if score < threshold — attempt quality repair first
            if (
                score.overall < settings.COMPLETENESS_FALLBACK_THRESHOLD
                or not validation_passed
            ):
                # Try a quality repair on this adapter before falling back
                if hasattr(adapter, "build_retry_prompt"):
                    missing = parsed.missing_fields or []
                    # Build baseline-aware repair prompt
                    baseline_info = ""
                    if (
                        baseline
                        and hasattr(baseline, "field_presence")
                        and baseline.field_presence
                    ):
                        baseline_present = [
                            f
                            for f, present in baseline.field_presence.items()
                            if present
                        ]
                        baseline_gaps = [f for f in baseline_present if f in missing]
                        if baseline_gaps:
                            baseline_info = (
                                f"\n\nOur validation system confirmed these fields ARE "
                                f"present on the page but your code missed them: "
                                f"{baseline_gaps}. The page contains: {baseline_present}."
                            )
                    repair_prompt = (
                        f"The data captured from {url} has very low quality "
                        f"(score: {score.overall:.2f}).\n\n"
                        f"Missing or empty fields: {', '.join(missing[:15])}"
                        f"{baseline_info}\n\n"
                        f"Please rebuild the endpoint to correctly extract "
                        f"all property listing data including: price, address, "
                        f"bedrooms, bathrooms, description, images, and floorplans."
                    )
                    logger.warning(
                        f"Score {score.overall:.2f} below threshold "
                        f"({settings.COMPLETENESS_FALLBACK_THRESHOLD}). "
                        f"Attempting quality repair on {adapter_name} before fallback."
                    )
                    try:
                        repair_request = DataCaptureRequest(
                            url=url,
                            super_id=str(super_id),
                            adapter_name=adapter_name,
                            prompt=repair_prompt,
                            metadata={"db": db},
                        )
                        repair_result, _ = await self._run_adapter(
                            db=db,
                            run=run,
                            adapter=adapter,
                            adapter_name=adapter_name,
                            request=repair_request,
                            baseline=baseline,
                            step_order=step_order,
                            is_retry=True,
                            retry_metadata={
                                "reason": "quality_repair",
                                "original_score": score.overall,
                            },
                        )
                        step_order += 1

                        if repair_result:
                            repair_parsed, repair_score, repair_valid = repair_result
                            if repair_score.overall > score.overall:
                                logger.info(
                                    f"Quality repair improved score: "
                                    f"{score.overall:.2f} → {repair_score.overall:.2f}"
                                )
                                parsed, score = repair_parsed, repair_score
                                validation_passed = repair_valid

                                # Update best result
                                best_result = (parsed, score, adapter_name)

                                # Re-check against thresholds
                                if (
                                    score.overall
                                    >= settings.COMPLETENESS_ACCEPT_THRESHOLD
                                    and validation_passed
                                ):
                                    await self._store_canonical(
                                        db=db,
                                        run=run,
                                        parsed=parsed,
                                        score=score,
                                        adapter_name=adapter_name,
                                        fallback_count=fallback_count,
                                    )
                                    return run

                                if (
                                    score.overall
                                    >= settings.COMPLETENESS_FALLBACK_THRESHOLD
                                ):
                                    # Improved enough to store with warnings
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
                            else:
                                logger.info(
                                    f"Quality repair did not improve: "
                                    f"{repair_score.overall:.2f} vs {score.overall:.2f}"
                                )
                    except Exception as e:
                        logger.error(f"Quality repair failed: {e}", exc_info=True)

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

        # Step 6: Chain exhausted — store best result or fail
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
            # Build detailed error message from per-adapter failures
            error_parts = [
                f"{name}: {reason}" for name, reason in adapter_errors.items()
            ]
            detailed_error = (
                "All adapters failed — " + "; ".join(error_parts)
                if error_parts
                else "All adapters failed"
            )
            logger.error(
                "All adapters failed for %s (super_id=%s): %s",
                url,
                super_id,
                detailed_error,
            )
            await data_capture_run_crud.update_run_status(
                db=db,
                run_id=run.id,
                status=DataCaptureRunStatus.FAILED,
                error_message=detailed_error,
                fallback_count=fallback_count,
            )
            await self._notify_callback(
                run=run,
                status_str="failed",
                error_message=detailed_error,
                adapter_errors=adapter_errors,
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
        existing_run_id: Optional[uuid.UUID] = None,
    ) -> DataCaptureRun:
        """
        Direct adapter call (for per-adapter endpoints).
        Still runs baseline + validation for data quality.

        If existing_run_id is provided, reuses that run instead of creating a new one.
        """
        adapter = self.get_adapter(adapter_name)
        if not adapter:
            raise ValueError(f"Unknown adapter: {adapter_name}")

        domain = extract_domain(url)

        if existing_run_id:
            run = await data_capture_run_crud.get_run(db, existing_run_id)
            if not run:
                raise ValueError(f"Run {existing_run_id} not found")
            logger.info(f"Reusing existing run {run.id} for adapter {adapter_name}")
        else:
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
                super_id=super_id,
            )
            step_order += 1

            try:
                baseline = await firecrawl_baseline_provider.fetch_baseline(url)
                raw_rec = await source_record_crud.store_raw_record(
                    db=db,
                    run_id=run.id,
                    step_id=baseline_step.id,
                    adapter_name="firecrawl_baseline",
                    payload_json=(
                        {"markdown": baseline.markdown} if baseline.markdown else None
                    ),
                    source_domain=domain,
                    super_id=super_id,
                )
                await source_record_crud.store_parsed_record(
                    db=db,
                    run_id=run.id,
                    step_id=baseline_step.id,
                    raw_record_id=raw_rec.id,
                    adapter_name="firecrawl_baseline",
                    field_presence_json=baseline.field_presence,
                    super_id=super_id,
                )
                await usage_crud.record_usage(
                    db=db,
                    run_id=run.id,
                    step_id=baseline_step.id,
                    adapter_name="firecrawl_baseline",
                    operation="data_capture_baseline",
                    credits_used=baseline.credits_used,
                    request_count=1,
                    super_id=super_id,
                )
                await data_capture_step_crud.update_step(
                    db=db,
                    step_id=baseline_step.id,
                    status=(
                        StepStatus.COMPLETED
                        if baseline.status == AdapterStatus.SUCCESS
                        else StepStatus.FAILED
                    ),
                    duration_ms=baseline.duration_ms,
                )
            except Exception as e:
                logger.error(f"Baseline failed: {e}")
                await data_capture_step_crud.update_step(
                    db=db,
                    step_id=baseline_step.id,
                    status=StepStatus.FAILED,
                    error_message=str(e),
                )

        # Run adapter
        await data_capture_run_crud.update_run_status(
            db, run.id, DataCaptureRunStatus.SCRAPING
        )

        request = DataCaptureRequest(
            url=url,
            super_id=str(super_id),
            adapter_name=adapter_name,
            metadata={"db": db},
        )
        result, error_reason = await self._run_adapter(
            db=db,
            run=run,
            adapter=adapter,
            adapter_name=adapter_name,
            request=request,
            baseline=baseline,
            step_order=step_order,
        )

        if result:
            parsed, score, validation_passed = result

            # --- Auto-retry for missing P0/P1 fields ---
            parsed, score, validation_passed, _ = await self._retry_for_missing_fields(
                db=db,
                run=run,
                adapter=adapter,
                adapter_name=adapter_name,
                url=url,
                super_id=super_id,
                parsed=parsed,
                score=score,
                validation_passed=validation_passed,
                baseline=baseline,
                step_order=step_order + 1,
            )

            with_warnings = (
                not validation_passed
                or score.overall < settings.COMPLETENESS_ACCEPT_THRESHOLD
            )
            await self._store_canonical(
                db=db,
                run=run,
                parsed=parsed,
                score=score,
                adapter_name=adapter_name,
                with_warnings=with_warnings,
            )
        else:
            detailed_error = (
                f"Adapter {adapter_name} failed: {error_reason}"
                if error_reason
                else f"Adapter {adapter_name} failed"
            )
            await data_capture_run_crud.update_run_status(
                db=db,
                run_id=run.id,
                status=DataCaptureRunStatus.FAILED,
                error_message=detailed_error,
            )
            await self._notify_callback(
                run=run,
                status_str="failed",
                error_message=detailed_error,
                adapter_errors={adapter_name: error_reason} if error_reason else None,
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
        is_retry: bool = False,
        retry_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[
        Optional[Tuple[ParsedDataCaptureResult, CompletenessScore, bool]],
        Optional[str],
    ]:
        """
        Run a single adapter through: fetch → parse → validate → score.
        Returns (result, error_reason) where result is
        (parsed, score, validation_passed) on success, or None on failure.
        error_reason is a human-readable string describing why the adapter failed,
        or None on success.

        For retry attempts, is_retry=True and retry_metadata contains attempt info.
        """
        # Create data_capture step
        data_capture_step = await data_capture_step_crud.create_step(
            db=db,
            run_id=run.id,
            step_order=step_order,
            adapter_name=adapter_name,
            step_type=StepType.DATA_CAPTURE,
            provider_type=adapter_name,
            super_id=run.super_id,
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
                super_id=run.super_id,
            )

            if raw.status != AdapterStatus.SUCCESS:
                reason = f"fetch_raw {raw.status.value}: {raw.error_message or 'unknown error'}"
                await data_capture_step_crud.update_step(
                    db=db,
                    step_id=data_capture_step.id,
                    status=StepStatus.FAILED,
                    error_message=raw.error_message,
                    duration_ms=raw.duration_ms,
                    provider_run_id=raw.provider_run_id,
                )
                return None, reason

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
                super_id=run.super_id,
            )

            if parsed.status != AdapterStatus.SUCCESS:
                reason = f"parse {parsed.status.value}: {parsed.error_message or 'unknown error'}"
                await data_capture_step_crud.update_step(
                    db=db,
                    step_id=data_capture_step.id,
                    status=StepStatus.FAILED,
                    error_message=parsed.error_message,
                    duration_ms=raw.duration_ms,
                    provider_run_id=raw.provider_run_id,
                )
                return None, reason

            # Validate against baseline
            validation = validate_against_baseline(parsed, baseline)

            # Score
            score = await adapter.score(parsed)

            # Build step metadata
            step_metadata: Dict[str, Any] = {
                "validation_passed": validation.passed,
                "validation_summary": validation.summary,
                "priority_scores": score.priority_scores,
            }
            if is_retry and retry_metadata:
                step_metadata["is_retry"] = True
                step_metadata.update(retry_metadata)

            # Update step
            await data_capture_step_crud.update_step(
                db=db,
                step_id=data_capture_step.id,
                status=StepStatus.COMPLETED,
                completeness_score=score.overall,
                duration_ms=raw.duration_ms,
                provider_run_id=raw.provider_run_id,
                metadata_json=step_metadata,
            )

            # Record usage
            await usage_crud.record_usage(
                db=db,
                run_id=run.id,
                step_id=data_capture_step.id,
                adapter_name=adapter_name,
                operation="data_capture",
                request_count=1,
                super_id=run.super_id,
            )

            return (parsed, score, validation.passed), None

        except Exception as e:
            logger.error(f"Adapter {adapter_name} failed: {e}", exc_info=True)
            await data_capture_step_crud.update_step(
                db=db,
                step_id=data_capture_step.id,
                status=StepStatus.FAILED,
                error_message=str(e),
            )
            return None, f"exception: {e}"

    def _merge_parsed_results(
        self,
        original: ParsedDataCaptureResult,
        retry: ParsedDataCaptureResult,
    ) -> ParsedDataCaptureResult:
        """
        Merge retry results into original, filling in missing fields.

        Strategy:
        - Scalar fields: use retry value only if original was missing/empty
        - URL lists (images, floorplans, videos): union with dedup, preserving order
        - Recompute field_presence and missing_fields from merged data
        """
        merged_fields = dict(original.fields)

        for key, value in retry.fields.items():
            if value is None or value == [] or value == "":
                continue

            if key in ("image_urls", "floorplan_urls", "video_urls"):
                # Union URL lists, preserving order and deduplicating
                existing = merged_fields.get(key, [])
                if isinstance(existing, list) and isinstance(value, list):
                    seen = set(existing)
                    merged = list(existing) + [u for u in value if u not in seen]
                    merged_fields[key] = merged
                elif not existing:
                    merged_fields[key] = value
            else:
                # For scalar fields, only fill in if original was missing
                original_value = merged_fields.get(key)
                if (
                    original_value is None
                    or original_value == ""
                    or original_value == []
                ):
                    merged_fields[key] = value

        # Merge media URL lists (top-level attributes on ParsedDataCaptureResult)
        image_seen = set(original.image_urls)
        merged_images = list(original.image_urls) + [
            u for u in retry.image_urls if u not in image_seen
        ]

        fp_seen = set(original.floorplan_urls)
        merged_floorplans = list(original.floorplan_urls) + [
            u for u in retry.floorplan_urls if u not in fp_seen
        ]

        # Recompute field presence from merged fields
        field_presence = compute_field_presence(merged_fields)
        missing = [f for f, present in field_presence.items() if not present]

        logger.info(
            f"Merged results: {len([v for v in merged_fields.values() if v])} fields, "
            f"{len(merged_images)} images, {len(merged_floorplans)} floorplans"
        )

        return ParsedDataCaptureResult(
            adapter_name=original.adapter_name,
            url=original.url,
            status=AdapterStatus.SUCCESS,
            fields=merged_fields,
            field_presence=field_presence,
            image_urls=merged_images,
            floorplan_urls=merged_floorplans,
            missing_fields=missing,
        )

    async def _retry_for_missing_fields(
        self,
        db: AsyncSession,
        run: DataCaptureRun,
        adapter: DataCaptureAdapter,
        adapter_name: str,
        url: str,
        super_id: uuid.UUID,
        parsed: ParsedDataCaptureResult,
        score: CompletenessScore,
        validation_passed: bool,
        baseline: Optional[BaselineResult],
        step_order: int,
    ) -> Tuple[ParsedDataCaptureResult, CompletenessScore, bool, int]:
        """
        Auto-retry adapter for missing P0/P1 fields.

        Builds a targeted prompt for just the missing fields, invokes the adapter
        again, and merges the retry results with the original. Each retry attempt
        is stored as a separate source record for full audit history.

        Returns (merged_parsed, new_score, validation_passed, updated_step_order)
        """
        missing_critical = get_missing_critical_fields(parsed.field_presence)
        retry_count = 0

        while missing_critical and retry_count < settings.MAX_RETRIES_PER_ADAPTER:
            # Check if adapter supports targeted retry prompts
            if not hasattr(adapter, "build_retry_prompt"):
                logger.info(f"Adapter {adapter_name} does not support targeted retry")
                break

            retry_prompt = adapter.build_retry_prompt(
                missing_critical, baseline=baseline
            )
            if not retry_prompt:
                logger.info(f"Could not build retry prompt for: {missing_critical}")
                break

            logger.info(
                f"Auto-retry {retry_count + 1}/{settings.MAX_RETRIES_PER_ADAPTER} "
                f"for {adapter_name}: targeting {len(missing_critical)} missing "
                f"P0/P1 fields: {missing_critical}"
            )

            retry_request = DataCaptureRequest(
                url=url,
                super_id=str(super_id),
                adapter_name=adapter_name,
                prompt=retry_prompt,
                metadata={"db": db},
            )

            retry_result, _ = await self._run_adapter(
                db=db,
                run=run,
                adapter=adapter,
                adapter_name=adapter_name,
                request=retry_request,
                baseline=baseline,
                step_order=step_order,
                is_retry=True,
                retry_metadata={
                    "retry_attempt": retry_count + 1,
                    "targeted_fields": missing_critical,
                    "previous_score": score.overall,
                },
            )
            step_order += 1

            if retry_result:
                retry_parsed, _, _ = retry_result
                parsed = self._merge_parsed_results(parsed, retry_parsed)
                score = await adapter.score(parsed)
                validation = validate_against_baseline(parsed, baseline)
                validation_passed = validation.passed

                new_missing = get_missing_critical_fields(parsed.field_presence)
                logger.info(
                    f"After retry {retry_count + 1}: score={score.overall:.4f}, "
                    f"still missing P0/P1: {new_missing if new_missing else 'none'}"
                )

                # Stop retrying if no improvement
                if set(new_missing) == set(missing_critical):
                    logger.info("No improvement from retry — stopping")
                    break

                missing_critical = new_missing
            else:
                logger.warning(
                    f"Retry {retry_count + 1} failed — adapter returned None"
                )

            retry_count += 1

        return parsed, score, validation_passed, step_order

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

        # --- Detailed capture summary ---
        photo_count = len([m for m in media_items if m["media_type"] == "photo"])
        floorplan_count = len(
            [m for m in media_items if m["media_type"] == "floorplan"]
        )
        video_count = len([m for m in media_items if m["media_type"] == "video"])

        logger.info("=" * 60)
        logger.info("CAPTURE SUMMARY — Source vs Canonical")
        logger.info(
            f"Score: {score.overall:.4f} | Adapter: {adapter_name} | "
            f"Status: {status.value}"
        )
        logger.info(
            f"Fields: {score.fields_present}/{score.fields_total} | "
            f"Media: {photo_count} photos, {floorplan_count} floorplans, "
            f"{video_count} videos"
        )

        # Per-tier breakdown
        for priority in sorted(score.priority_scores.keys()):
            tier_score = score.priority_scores[priority]
            tier_fields = FIELD_PRIORITIES.get(priority, [])
            present = [f for f in tier_fields if parsed.field_presence.get(f, False)]
            missing = [
                f for f in tier_fields if not parsed.field_presence.get(f, False)
            ]
            logger.info(
                f"  P{priority}: {tier_score:.0%} — "
                f"present={present}, missing={missing}"
            )

        # Key field values
        logger.info("--- Key Field Values ---")
        for key_field in [
            "address_road",
            "price",
            "address_town",
            "bedrooms",
            "bathrooms",
            "property_type",
            "estate_agent_name",
        ]:
            value = column_fields.get(key_field, "—")
            if isinstance(value, str) and len(value) > 60:
                value = value[:57] + "..."
            logger.info(f"  {key_field}: {value}")

        # Extras summary
        if extras_json:
            logger.info(f"Extras (P4+): {list(extras_json.keys())}")

        logger.info("=" * 60)

        # Notify callback URL if configured
        await self._notify_callback(
            run=run,
            status_str=status.value,
            column_fields=column_fields,
            media_items=media_items,
            score=score,
        )

    async def _notify_callback(
        self,
        run: DataCaptureRun,
        status_str: str,
        column_fields: Optional[Dict[str, Any]] = None,
        media_items: Optional[List[Dict[str, Any]]] = None,
        score: Optional[CompletenessScore] = None,
        error_message: Optional[str] = None,
        adapter_errors: Optional[Dict[str, str]] = None,
    ) -> None:
        """POST callback notification when a run reaches a terminal state.

        Fire-and-forget — errors are logged but never raised.
        If no callback_url is set on the run, this is a no-op.
        """
        if not run.callback_url:
            return

        summary: Dict[str, Any] = {}
        final_result: Optional[Dict[str, Any]] = None

        if media_items:
            summary["floorplan_urls"] = [
                m["url"] for m in media_items if m.get("media_type") == "floorplan"
            ]
            summary["image_urls"] = [
                m["url"] for m in media_items if m.get("media_type") == "photo"
            ]
            summary["photo_count"] = len(summary["image_urls"])
            summary["floorplan_count"] = len(summary["floorplan_urls"])

        if column_fields:
            summary["address_road"] = column_fields.get("address_road")
            summary["price"] = column_fields.get("price")
            summary["bedrooms"] = column_fields.get("bedrooms")

        if status_str != "failed":
            final_result = {}
            if column_fields:
                final_result["canonical"] = column_fields
            if media_items:
                final_result["media"] = media_items
            if score:
                final_result["quality"] = {
                    "completeness_score": score.overall,
                    "fields_present": score.fields_present,
                    "fields_total": score.fields_total,
                    "priority_scores": score.priority_scores,
                }

        if score:
            summary["completeness_score"] = score.overall

        # Upload snapshot to S3 for data_location (matches floorplan_service pattern)
        data_location: Optional[str] = None
        notifier = get_status_notifier()
        if notifier:
            try:
                snapshot = {
                    "super_id": str(run.super_id),
                    "context": "data_capture",
                    "status": status_str,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "summary": summary,
                    "data": {
                        "final_result": final_result,
                        "error": error_message,
                    },
                }
                data_location = await notifier.upload_snapshot(
                    super_id=run.super_id,
                    context="data_capture",
                    snapshot=snapshot,
                )
                logger.info(
                    "Uploaded status snapshot to %s for super_id=%s",
                    data_location,
                    run.super_id,
                )
            except Exception as exc:
                logger.error(
                    "Failed to upload S3 snapshot for super_id=%s: %s",
                    run.super_id,
                    exc,
                )

        payload = {
            "super_id": str(run.super_id),
            "status": status_str,
            "context": "data_capture",
            "data_location": data_location,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "final_result": final_result,
            "error": (
                {
                    "message": error_message,
                    **({"adapter_errors": adapter_errors} if adapter_errors else {}),
                }
                if error_message
                else None
            ),
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(run.callback_url, json=payload, timeout=10)
                logger.info(
                    "Callback POST to %s returned %s",
                    run.callback_url,
                    resp.status_code,
                )
        except Exception as exc:
            logger.error(
                "Callback POST to %s failed: %s",
                run.callback_url,
                exc,
            )


# Global instance
data_capture_pipeline = DataCapturePipeline()

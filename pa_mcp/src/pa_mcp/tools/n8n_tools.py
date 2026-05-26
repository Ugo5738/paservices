from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.exc import SQLAlchemyError

from ..config import settings
from ..crud import get_analysis_result, list_analysis_updates, upsert_analysis_result
from ..db import AsyncSessionLocal
from ..utils.logging_config import logger


async def start_property_analysis_via_n8n(
    client: httpx.AsyncClient,
    property_url: str,
    workflow_callback_url: Optional[str] = None,
    super_id: Optional[str] = None,
    external_callback_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Kick off the long-running property analysis via n8n."""
    if not property_url:
        raise ValueError("property_url is required")

    callback_url = workflow_callback_url or settings.WORKFLOW_CALLBACK_URL
    normalized_external_callback_url = None
    if isinstance(external_callback_url, str):
        normalized_external_callback_url = external_callback_url.strip() or None
    else:
        normalized_external_callback_url = external_callback_url
    if not normalized_external_callback_url:
        normalized_external_callback_url = callback_url

    payload = {
        "property_url": property_url,
        "workflow_callback_url": callback_url,
    }
    callback_urls: Dict[str, str] = {"workflow_callback_url": callback_url}
    if normalized_external_callback_url:
        callback_urls["external_callback_url"] = normalized_external_callback_url
    payload["callback_urls"] = callback_urls
    if super_id:
        payload["super_id"] = super_id

    logger.info("Triggering n8n workflow", extra={"payload": payload})

    try:
        response = await client.post(
            settings.N8N_SUPERSAMI_TRIGGER_URL,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        try:
            n8n_response: Any = response.json()
        except ValueError:
            n8n_response = {"raw": response.text}
    except httpx.HTTPError as exc:
        logger.error("Failed to trigger n8n workflow: %s", exc, exc_info=True)
        raise

    # --- Extract super_id from the n8n response ---
    response_super_id: Optional[str] = None
    remote_status: str = "started"

    if isinstance(n8n_response, dict):
        response_super_id = n8n_response.get("super_id")
        remote_status = n8n_response.get("status", remote_status)
    elif isinstance(n8n_response, list) and n8n_response:
        # just in case you ever switch to array responses
        item = n8n_response[0]
        if isinstance(item, dict):
            response_super_id = item.get("super_id")
            remote_status = item.get("status", remote_status)

    if response_super_id and super_id and response_super_id != super_id:
        logger.warning(
            "n8n returned a different super_id than requested",
            extra={
                "requested_super_id": super_id,
                "response_super_id": response_super_id,
            },
        )

    final_super_id = response_super_id or super_id
    if not final_super_id:
        # At this point something is wrong with the workflow config,
        # better to fail loudly than silently.
        logger.error("n8n trigger did not return a super_id: %r", n8n_response)
        raise RuntimeError("n8n workflow did not return a super_id")

    # Seed persistence with a pending entry so fetches have immediate feedback
    async with AsyncSessionLocal() as session:
        try:
            await upsert_analysis_result(
                session,
                final_super_id,
                {
                    "status": "pending",  # our internal status
                    "remote_status": remote_status,  # what n8n said ("started")
                    "property_url": property_url,
                    "workflow_callback_url": callback_url,
                    "n8n_triggered": True,
                },
            )
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error("Failed to seed analysis result row: %s", exc, exc_info=True)
            raise

    return {
        "super_id": final_super_id,
        "status": "started",
        "workflow_callback_url": callback_url,
        "requested_super_id": super_id,
        "external_callback_url": normalized_external_callback_url,
        "n8n_response": n8n_response,
    }


def _ts(value: Any) -> Optional[str]:
    try:
        return value.isoformat() if value else None
    except Exception:
        return None


SUCCESS_STATUSES = {"success", "completed", "completed_with_warnings", "pass"}
FAILURE_STATUSES = {"failed", "error", "fail", "cancelled", "timeout"}
SKIPPED_STATUSES = {"skipped", "not_applicable", "not_applicable_no_data"}
PENDING_STATUSES = {
    "accepted",
    "created",
    "in_progress",
    "pending",
    "processing",
    "queued",
    "started",
}


def _normalise_status(status: Any) -> str:
    return str(status or "pending").lower()


def _status_category(status: Any) -> str:
    normalised = _normalise_status(status)
    if normalised in SUCCESS_STATUSES:
        return "success"
    if normalised in FAILURE_STATUSES:
        return "failed"
    if normalised in SKIPPED_STATUSES:
        return "skipped"
    if normalised in PENDING_STATUSES:
        return "pending"
    return "unknown"


def _normalise_error(
    raw_error: Any,
    raw_payload: Optional[Dict[str, Any]] = None,
    *,
    status: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    raw_payload = raw_payload or {}
    error = raw_error
    if error is None and raw_payload.get("error") is not None:
        error = raw_payload["error"]
    if error is None and raw_payload.get("error_message"):
        error = {"message": raw_payload["error_message"]}
    if error is None and status and _status_category(status) == "failed":
        message = raw_payload.get("reason") or raw_payload.get("detail")
        if not message:
            score = raw_payload.get("completeness_score")
            fields = raw_payload.get("fields")
            if score == 0 and not fields:
                message = (
                    "Capture failed: the AI fetcher returned no usable fields "
                    "(completeness_score 0)."
                )
        if message:
            error = {"message": message}
    if error is None:
        return None

    if isinstance(error, str):
        structured: Dict[str, Any] = {"message": error}
    elif isinstance(error, dict):
        structured = {
            key: value
            for key, value in error.items()
            if key != "stack" and value is not None
        }
        if "message" not in structured:
            structured["message"] = (
                structured.get("detail")
                or structured.get("reason")
                or str(error)
            )
    else:
        structured = {"message": str(error)}

    for source, target in (
        ("error_type", "type"),
        ("code", "code"),
        ("status_code", "http_status"),
        ("reason", "reason"),
        ("detail", "detail"),
        ("workflow_status", "workflow_status"),
        ("last_error", "last_error"),
        ("promote_detail", "promote_detail"),
    ):
        value = raw_payload.get(source)
        if value is not None and target not in structured:
            structured[target] = value
    return structured


def _extract_ids(raw_payload: Dict[str, Any], analysis_update_id: str) -> Dict[str, Any]:
    ids: Dict[str, Any] = {"analysis_update_id": analysis_update_id}
    for field in (
        "run_id",
        "parent_run_id",
        "attempt_number",
        "fetcher_id",
        "build_flag_id",
        "build_id",
        "parent_build_id",
        "session_id",
        "deployment_id",
        "workflow_execution_id",
        "n8n_execution_id",
    ):
        if raw_payload.get(field) is not None:
            ids[field] = raw_payload[field]
    metadata = raw_payload.get("metadata")
    if isinstance(metadata, dict):
        for field in ("run_id", "execution_id", "workflow_execution_id"):
            if metadata.get(field) is not None and field not in ids:
                ids[field] = metadata[field]
    return ids


def _urls_from_values(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value] if value.startswith(("http://", "https://")) else []
    if not isinstance(value, list):
        return []
    urls: List[str] = []
    for item in value:
        if isinstance(item, str) and item.startswith(("http://", "https://")):
            urls.append(item)
        elif isinstance(item, dict):
            candidate = item.get("url") or item.get("value") or item.get("src")
            if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                urls.append(candidate)
    return list(dict.fromkeys(urls))


def _capture_media_urls(entry: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    if not entry:
        return {"image_urls": [], "floorplan_urls": []}
    image_urls: List[str] = []
    floorplan_urls: List[str] = []

    def add_from_fields(fields: Any) -> None:
        if not isinstance(fields, dict):
            return
        image_urls.extend(_urls_from_values(fields.get("image_urls")))
        floorplan_urls.extend(_urls_from_values(fields.get("floorplan_urls")))
        media = fields.get("media")
        if isinstance(media, list):
            for item in media:
                if not isinstance(item, dict):
                    continue
                url = item.get("url") or item.get("value") or item.get("src")
                media_type = str(item.get("media_type") or item.get("type") or "")
                if not isinstance(url, str):
                    continue
                if media_type == "floorplan":
                    floorplan_urls.append(url)
                elif media_type in {"photo", "image"}:
                    image_urls.append(url)

    add_from_fields(entry.get("summary"))
    add_from_fields(entry.get("data"))
    final_result = entry.get("final_result")
    add_from_fields(final_result)
    if isinstance(final_result, dict):
        add_from_fields(final_result.get("canonical"))

    return {
        "image_urls": list(dict.fromkeys(image_urls)),
        "floorplan_urls": list(dict.fromkeys(floorplan_urls)),
    }


def _requested_contexts(latest: Dict[str, Dict[str, Any]]) -> List[str]:
    orchestrator = latest.get("orchestrator") or {}
    services = orchestrator.get("requested_services")
    if not isinstance(services, list):
        raw = orchestrator.get("raw_requested_services")
        services = raw if isinstance(raw, list) else []
    contexts: List[str] = []
    for service in services:
        if service in {"data_capture", "data_capture_motie", "data_capture_rightmove"}:
            contexts.append("data_capture")
        elif service in {"floorplan_analysis", "image_condition_analysis"}:
            contexts.append(service)
    return list(dict.fromkeys(contexts))


async def _fetch_s3_data(client: httpx.AsyncClient, url: str) -> Optional[Dict[str, Any]]:
    """Fetch JSON data from an S3 data_location URL. Returns None on any failure."""
    try:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


async def get_property_analysis_result(super_id: str) -> Dict[str, Any]:
    """Fetch the stored analysis result by super_id, plus per-context latest statuses."""
    async with AsyncSessionLocal() as session:
        existing = await get_analysis_result(session, super_id)
        base = (
            existing.to_dict()
            if existing
            else {"super_id": super_id, "status": "pending"}
        )

        # Build latest_status_by_context from the append-only updates log
        # Includes per-context data_location, final_result, and summary
        # so the agent gets progressive results as each service completes
        try:
            updates = await list_analysis_updates(session, super_id, limit=200)
            latest: Dict[str, Dict[str, Any]] = {}
            for upd in updates:
                ctx = upd.context or "unknown"
                ts = upd.event_timestamp or upd.received_at
                # first occurrence is the most recent because list_analysis_updates orders desc
                if ctx not in latest:
                    raw_payload = upd.raw_payload or {}
                    normalised_status = _normalise_status(upd.status)
                    entry: Dict[str, Any] = {
                        "context": ctx,
                        "status": upd.status,
                        "status_category": _status_category(normalised_status),
                        "updated_at": _ts(ts),
                        "ids": _extract_ids(raw_payload, str(upd.id)),
                    }
                    if upd.data_location:
                        entry["data_location"] = upd.data_location
                    if upd.final_result:
                        entry["final_result"] = upd.final_result
                    if upd.summary:
                        entry["summary"] = upd.summary
                    structured_error = _normalise_error(
                        upd.error,
                        raw_payload,
                        status=normalised_status,
                    )
                    if structured_error:
                        entry["error"] = structured_error
                    for field in (
                        "source",
                        "adapter",
                        "fetcher_id",
                        "build_flag_id",
                        "requested_services",
                        "property_url",
                        "workflow_callback_url",
                        "completeness_score",
                        "missing_fields",
                        "missing_critical_fields",
                        "promoted",
                        "canonical_columns_written",
                        "canonical_media_count",
                        "promote_detail",
                    ):
                        if raw_payload.get(field) is not None:
                            entry[field] = raw_payload[field]
                    if raw_payload.get("requested_services") is not None:
                        entry["raw_requested_services"] = raw_payload[
                            "requested_services"
                        ]
                    raw_data = raw_payload.get("data")
                    if raw_data and not entry.get("final_result"):
                        entry["data"] = raw_data
                    elif raw_payload.get("fields") and not entry.get("final_result"):
                        entry["data"] = raw_payload["fields"]
                    if entry["status_category"] == "pending":
                        entry["state_explanation"] = (
                            f"{ctx} has started but has not reported a terminal "
                            "result yet."
                        )
                    elif entry["status_category"] == "failed":
                        message = (entry.get("error") or {}).get("message")
                        entry["state_explanation"] = (
                            f"{ctx} failed"
                            + (f": {message}" if message else ".")
                        )
                    elif entry["status_category"] == "success":
                        entry["state_explanation"] = (
                            f"{ctx} reported a successful terminal result."
                        )
                    latest[ctx] = entry
            if latest:
                requested = _requested_contexts(latest)
                if requested:
                    base["expected_contexts"] = requested
                data_capture = latest.get("data_capture")
                data_capture_category = (
                    data_capture.get("status_category")
                    if isinstance(data_capture, dict)
                    else None
                )
                media = _capture_media_urls(data_capture)
                for ctx in requested:
                    if ctx in latest:
                        continue
                    if ctx == "data_capture":
                        latest[ctx] = {
                            "context": ctx,
                            "status": "pending",
                            "status_category": "pending",
                            "state_explanation": (
                                "The orchestrator has started, but data_capture "
                                "has not called back yet."
                            ),
                        }
                    elif data_capture_category not in {"success", "failed"}:
                        latest[ctx] = {
                            "context": ctx,
                            "status": "pending",
                            "status_category": "pending",
                            "state_explanation": (
                                f"{ctx} is waiting for data_capture to finish."
                            ),
                        }
                    elif ctx == "floorplan_analysis" and not media["floorplan_urls"]:
                        latest[ctx] = {
                            "context": ctx,
                            "status": "skipped",
                            "status_category": "skipped",
                            "reason": "no_floorplans_found",
                            "state_explanation": (
                                "No floorplan URLs were found in data_capture, "
                                "so floorplan_analysis was not applicable."
                            ),
                        }
                    elif ctx == "image_condition_analysis" and not media["image_urls"]:
                        latest[ctx] = {
                            "context": ctx,
                            "status": "skipped",
                            "status_category": "skipped",
                            "reason": "no_images_found",
                            "state_explanation": (
                                "No property image URLs were found in data_capture, "
                                "so image_condition_analysis was not applicable."
                            ),
                        }
                    elif data_capture_category == "success":
                        latest[ctx] = {
                            "context": ctx,
                            "status": "pending",
                            "status_category": "pending",
                            "state_explanation": (
                                f"{ctx} is expected but has not called back yet."
                            ),
                        }
                base["latest_status_by_context"] = latest
        except Exception:
            # best-effort; do not fail the call
            pass

        # Fetch actual data from S3 for contexts that have data_location
        # but no final_result. This includes in-progress contexts so
        # ChatGPT can see progressive results as each service updates.
        contexts_to_fetch = {}
        for ctx, entry in base.get("latest_status_by_context", {}).items():
            if entry.get("data_location") and not entry.get("final_result"):
                contexts_to_fetch[ctx] = entry["data_location"]

        if contexts_to_fetch:
            try:
                async with httpx.AsyncClient() as client:
                    for ctx, url in contexts_to_fetch.items():
                        data = await _fetch_s3_data(client, url)
                        if data:
                            base["latest_status_by_context"][ctx]["data"] = data
            except Exception:
                pass

        # Fallback: expose the latest successful data-capture payload as the
        # top-level result when the workflow never wrote a merged final_result.
        if not base.get("final_result"):
            data_capture = (base.get("latest_status_by_context") or {}).get("data_capture")
            if data_capture:
                if data_capture.get("final_result"):
                    base["final_result"] = data_capture["final_result"]
                elif data_capture.get("data"):
                    base["final_result"] = data_capture["data"]
        if not base.get("error"):
            data_capture = (base.get("latest_status_by_context") or {}).get("data_capture")
            if data_capture and data_capture.get("error"):
                base["error"] = data_capture["error"]

        # Derive overall status from per-context statuses.
        # The DB-stored status can be wrong (e.g. "completed" when only data_capture
        # finished, or "pending" when all contexts actually completed).
        ctx_statuses = base.get("latest_status_by_context", {})
        if ctx_statuses:
            service_statuses = {
                ctx: entry
                for ctx, entry in ctx_statuses.items()
                if ctx != "orchestrator"
            }
            categories = [
                entry.get("status_category") or _status_category(entry.get("status"))
                for entry in service_statuses.values()
            ]
            terminal_categories = {"success", "failed", "skipped"}
            if categories and all(c in terminal_categories for c in categories):
                if any(c == "failed" for c in categories):
                    base["status"] = "failed"
                else:
                    base["status"] = "completed"
            elif any(c in terminal_categories for c in categories):
                base["status"] = "in_progress"
            elif base.get("n8n_triggered") is True:
                base["status"] = "in_progress"
            # else leave as-is (pending)

            if base["status"] == "failed":
                failed_contexts = [
                    ctx
                    for ctx, entry in service_statuses.items()
                    if entry.get("status_category") == "failed"
                ]
                base["state_explanation"] = (
                    "One or more service contexts failed: "
                    + ", ".join(failed_contexts)
                )
            elif base["status"] == "completed":
                skipped_contexts = [
                    ctx
                    for ctx, entry in service_statuses.items()
                    if entry.get("status_category") == "skipped"
                ]
                base["state_explanation"] = (
                    "All expected service contexts reached a terminal state."
                )
                if skipped_contexts:
                    base["state_explanation"] += (
                        " Skipped contexts: " + ", ".join(skipped_contexts) + "."
                    )
            elif base["status"] == "in_progress":
                pending_contexts = [
                    ctx
                    for ctx, entry in service_statuses.items()
                    if entry.get("status_category") == "pending"
                ]
                base["state_explanation"] = (
                    "Workflow has started and is waiting for service callbacks"
                    + (
                        ": " + ", ".join(pending_contexts)
                        if pending_contexts
                        else "."
                    )
                )
        elif base.get("n8n_triggered") is False:
            base["state_explanation"] = (
                "This super_id exists, but PA MCP has not recorded a workflow "
                "trigger for it yet."
            )
        elif base.get("n8n_triggered") is True:
            base["state_explanation"] = (
                "Workflow metadata exists, but no service callback events have "
                "been recorded yet."
            )

        return base

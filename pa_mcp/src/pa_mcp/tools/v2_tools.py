"""
HTTP helper functions for the V2 spec MCP tools.

The V2 architecture exposes primitives at multiple layers:

* Bottom (per-vendor): direct calls to the data-capture service's primitive
  endpoints — `/ai-fetchers/{adapter}/run`, `/fetchers/{lookup,run}`,
  `/fetcher-builds/motie/build/{start,status,score,publish}`.

* Middle (reusable flows): n8n webhooks for the workflow primitives —
  WF1 (coded fetcher chain), WF B (multishot AI fetcher).

* Top (full workflows): n8n Orchestrator V3 which composes WF A + downstream
  services with a callback for asynchronous result delivery.

These helpers wrap each call with consistent auth, error handling, and JSON
parsing so the @mcp.tool() functions in mcp_tools.py stay short and readable.
"""

from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.exc import SQLAlchemyError

from ..config import settings
from ..crud import create_analysis_update, upsert_analysis_result
from ..db import AsyncSessionLocal
from ..utils.logging_config import logger
from .auth_helper import get_m2m_token


# ---------------------------------------------------------------------------
# Generic HTTP helpers
# ---------------------------------------------------------------------------


def _dc_base() -> str:
    base = (settings.DATA_CAPTURE_SERVICE_URL or "").rstrip("/")
    if not base:
        raise ValueError(
            "PA_MCP_DATA_CAPTURE_SERVICE_URL is not configured; cannot reach "
            "the data-capture service."
        )
    return base


async def dc_get(
    client: httpx.AsyncClient,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """GET a path on the data-capture service with M2M Bearer auth."""
    token = await get_m2m_token(client)
    url = f"{_dc_base()}{path}"
    resp = await client.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


async def dc_post(
    client: httpx.AsyncClient,
    path: str,
    body: Optional[Dict[str, Any]] = None,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """POST to the data-capture service with M2M Bearer auth."""
    token = await get_m2m_token(client)
    url = f"{_dc_base()}{path}"
    resp = await client.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=body or {},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


async def n8n_post(
    client: httpx.AsyncClient,
    webhook_url: str,
    body: Dict[str, Any],
    timeout: float = 600.0,
) -> Dict[str, Any]:
    """POST to an n8n webhook (n8n itself is open; auth is per-workflow)."""
    if not webhook_url:
        raise ValueError(
            "n8n webhook URL not configured. Check the corresponding "
            "PA_MCP_N8N_* environment variable."
        )
    resp = await client.post(
        webhook_url,
        headers={"Content-Type": "application/json"},
        json=body,
        timeout=timeout,
    )
    resp.raise_for_status()
    if not resp.content:
        return {}
    try:
        return resp.json()
    except ValueError:
        return {"raw": resp.text}


# ---------------------------------------------------------------------------
# Bottom-layer — per-vendor primitives
# ---------------------------------------------------------------------------


async def firecrawl_fetch(
    client: httpx.AsyncClient,
    url: str,
    super_id: Optional[str] = None,
    prompt: Optional[str] = None,
    schema_hint: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Single-shot Firecrawl fetch via /ai-fetchers/firecrawl/run.

    Returns the AIFetcherRunResponse shape: status, payload, fields,
    field_presence, missing_fields, completeness_score, run_id, etc.
    """
    body: Dict[str, Any] = {"url": url}
    if super_id:
        body["super_id"] = super_id
    if prompt:
        body["prompt"] = prompt
    if schema_hint:
        body["schema_hint"] = schema_hint
    return await dc_post(client, "/ai-fetchers/firecrawl/run", body, timeout=120.0)


async def motie_fetch(
    client: httpx.AsyncClient,
    url: str,
    super_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Call the deployed Motie scraper for the URL's domain.

    Looks up the registered fetcher for the domain; if it is a Motie source,
    runs it via /fetchers/run. Returns a structured dict with `error` set
    when there's no Motie fetcher for the domain so callers can decide how
    to fall back.
    """
    lookup = await dc_post(client, "/fetchers/lookup", {"url": url}, timeout=15.0)
    domain = lookup.get("domain")
    if not lookup.get("found"):
        return {
            "error": "no_fetcher_for_domain",
            "domain": domain,
            "message": (
                "No registered fetcher for this domain. Use motie_build_tool "
                "to create one."
            ),
        }

    fetcher = lookup.get("fetcher") or {}
    if (fetcher.get("source_type") or "") != "motie":
        return {
            "error": "fetcher_not_motie",
            "domain": domain,
            "fetcher_id": fetcher.get("id"),
            "source_type": fetcher.get("source_type"),
            "message": (
                "The registered fetcher for this domain is not a Motie scraper. "
                "Use fetch_with_pre_built_tool for a vendor-agnostic call."
            ),
        }

    body: Dict[str, Any] = {
        "fetcher_id": fetcher["id"],
        "url": url,
        "timeout": 60,
    }
    if super_id:
        body["super_id"] = super_id
    return await dc_post(client, "/fetchers/run", body, timeout=120.0)


async def motie_build_start(
    client: httpx.AsyncClient,
    url: str,
    prompt_kind: str = "build",
    failing_error: Optional[str] = None,
    benchmark_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Trigger Motie's agent to build a new scraper for the URL's domain.

    Returns immediately with `build_id` + `state: "session_running"`. Caller
    polls /build/{id}/status (use get_motie_build_status helper) until it
    reaches a terminal state.
    """
    body: Dict[str, Any] = {"url": url, "prompt_kind": prompt_kind}
    if failing_error:
        body["failing_error"] = failing_error
    if benchmark_fields:
        body["benchmark_fields"] = benchmark_fields
    return await dc_post(
        client, "/fetcher-builds/motie/build/start", body, timeout=60.0
    )


async def get_motie_build_status(
    client: httpx.AsyncClient, build_id: str
) -> Dict[str, Any]:
    """Single status poll for a Motie build by id."""
    return await dc_get(
        client, f"/fetcher-builds/motie/build/{build_id}/status", timeout=30.0
    )


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------


async def list_fetchers(
    client: httpx.AsyncClient,
    domain: Optional[str] = None,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """List registered fetchers, optionally filtered."""
    params: Dict[str, Any] = {"limit": limit}
    if domain:
        params["domain"] = domain
    if source_type:
        params["source_type"] = source_type
    if status:
        params["status"] = status
    return await dc_get(client, "/fetchers", params=params)


# ---------------------------------------------------------------------------
# Middle-layer — reusable flows (delegate to n8n primitive workflows)
# ---------------------------------------------------------------------------


async def fetch_with_pre_built(
    client: httpx.AsyncClient,
    url: str,
    super_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Try registered pre-built fetchers in order via WF1.

    WF1 internally does /fetchers/lookup → /fetchers/run → /fetchers/validate.
    """
    body: Dict[str, Any] = {"url": url}
    if super_id:
        body["super_id"] = super_id
    return await n8n_post(client, settings.N8N_WF1_URL, body, timeout=300.0)


async def fetch_with_ai(
    client: httpx.AsyncClient,
    url: str,
    super_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Try AI fetchers via WF B (multishot).

    WF B does Auth → Attempt 1 (default) → Validate → if not passed, Attempt 2
    (focused) → Pick Best → Promote Winner. Returns the winning attempt's data.
    """
    body: Dict[str, Any] = {"url": url}
    if super_id:
        body["super_id"] = super_id
    return await n8n_post(client, settings.N8N_WFB_URL, body, timeout=300.0)


async def build_fetcher(
    client: httpx.AsyncClient,
    url: str,
    super_id: Optional[str] = None,
    poll_interval: float = 15.0,
    poll_timeout: float = 1800.0,
) -> Dict[str, Any]:
    """
    End-to-end fetcher build: kick off → poll → score → publish → register.

    Calls /build/start, polls /build/{id}/status until terminal, then on
    `deployed` calls /score, /publish, and /fetchers/register so the new
    fetcher is immediately usable from /fetchers/lookup.

    Returns a dict with `build_id`, terminal `state`, `score`, and either
    the registered `fetchers` list (on success) or `error_message`
    (on failure).
    """
    import asyncio

    start = await motie_build_start(client, url=url)
    build_id = start.get("build_id")
    project_uuid = start.get("project_uuid")
    if not build_id:
        return {"error": "build_start_returned_no_build_id", "response": start}

    # Poll status until terminal
    elapsed = 0.0
    state = start.get("state") or "session_running"
    is_terminal = False
    last_status: Dict[str, Any] = start
    while not is_terminal and elapsed < poll_timeout:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        last_status = await get_motie_build_status(client, build_id)
        state = last_status.get("state") or state
        is_terminal = bool(last_status.get("is_terminal"))

    if not is_terminal:
        return {
            "build_id": build_id,
            "project_uuid": project_uuid,
            "state": state,
            "error": "poll_timeout",
            "elapsed_sec": elapsed,
        }
    if state != "deployed":
        return {
            "build_id": build_id,
            "project_uuid": project_uuid,
            "state": state,
            "error_message": last_status.get("error_message"),
        }

    # Score
    super_id_for_score = super_id or last_status.get("super_id")
    score_body = {"build_id": build_id}
    if super_id_for_score:
        score_body["super_id"] = super_id_for_score
    score = await dc_post(
        client,
        f"/fetcher-builds/motie/build/{build_id}/score",
        score_body,
        timeout=300.0,
    )

    # Publish artefact
    artefact = await dc_post(
        client, f"/fetcher-builds/motie/build/{build_id}/publish", {}, timeout=60.0
    )

    # Register in fetcher registry
    register_body = {
        "domain": artefact.get("domain"),
        "motie_project_uuid": artefact.get("project_uuid"),
        "routes": artefact.get("routes", []),
        "is_metered": artefact.get("is_metered", False),
        "build_score": artefact.get("benchmark_score") or 0,
    }
    registered = await dc_post(client, "/fetchers/register", register_body, timeout=30.0)

    return {
        "build_id": build_id,
        "project_uuid": project_uuid,
        "state": state,
        "score": {
            "candidate_score": score.get("candidate_score"),
            "baseline_score": score.get("baseline_score"),
            "passed": score.get("passed"),
            "missing_critical_fields": score.get("missing_critical_fields", []),
        },
        "artefact": artefact,
        "fetchers": registered.get("fetchers", []),
    }


# ---------------------------------------------------------------------------
# Top-layer — full workflows (Orchestrator V3)
# ---------------------------------------------------------------------------


async def full_analysis_primary(
    client: httpx.AsyncClient,
    property_url: str,
    services: List[str],
    super_id: Optional[str] = None,
    callback_url: Optional[str] = None,
    service_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Trigger Orchestrator V3 for a full analysis pipeline.

    V3 calls WF A (which itself does pre-built first, falls through to AI
    single-shot), forwards capture result to callback_url, then fans out
    downstream services. Returns 202 immediately with a super_id; the final
    result reaches `callback_url` asynchronously.
    """
    # Guarantee a super_id up front. If we leave it to the orchestrator to mint
    # one (by omitting super_id from the body), a no-super_id call comes back as
    # an empty {} response: the caller gets no id to poll and may re-trigger
    # duplicate extraction (bug observed 2026-05-30). Minting here — same path
    # as create_super_id_tool — makes this tool ALWAYS return a super_id and
    # always seed a pollable result row, regardless of orchestrator behaviour.
    if not super_id:
        try:
            token = await get_m2m_token(client)
            resp = await client.post(
                f"{settings.SUPER_ID_SERVICE_URL}/super_ids",
                json={"count": 1, "metadata": {}},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            resp.raise_for_status()
            super_id = str(resp.json().get("super_id", "")) or None
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "full_analysis_primary: failed to mint super_id: %s",
                exc,
                exc_info=True,
            )
            return {
                "status": "error",
                "error": f"failed to create super_id: {exc}",
                "super_id": None,
            }
        if not super_id:
            return {
                "status": "error",
                "error": "super id service returned no super_id",
                "super_id": None,
            }
    body: Dict[str, Any] = {
        "property_url": property_url,
        "services": services,
    }
    if super_id:
        body["super_id"] = super_id
    if callback_url:
        body["callback_url"] = callback_url
    else:
        body["callback_url"] = settings.WORKFLOW_CALLBACK_URL
    if service_params:
        body["service_params"] = service_params
    result = await n8n_post(
        client, settings.N8N_ORCHESTRATOR_V3_URL, body, timeout=60.0
    )
    response_super_id = (
        result.get("super_id")
        if isinstance(result, dict)
        else None
    )
    final_super_id = response_super_id or super_id
    if final_super_id:
        remote_status = (
            result.get("status", "accepted")
            if isinstance(result, dict)
            else "accepted"
        )
        async with AsyncSessionLocal() as session:
            try:
                await upsert_analysis_result(
                    session,
                    final_super_id,
                    {
                        "status": "pending",
                        "remote_status": remote_status,
                        "property_url": property_url,
                        "workflow_callback_url": body["callback_url"],
                        "n8n_triggered": True,
                    },
                )
                await create_analysis_update(
                    session,
                    {
                        "super_id": final_super_id,
                        "status": remote_status,
                        "context": "orchestrator",
                        "property_url": property_url,
                        "workflow_callback_url": body["callback_url"],
                        "requested_services": services,
                        "service_params": service_params or {},
                        "n8n_triggered": True,
                        "n8n_response": result,
                    },
                )
                await session.commit()
            except SQLAlchemyError as exc:
                await session.rollback()
                logger.error(
                    "Failed to seed Orchestrator V3 analysis result row: %s",
                    exc,
                    exc_info=True,
                    extra={"super_id": final_super_id},
                )
                raise
    # Bulletproof the tool contract: always surface the super_id to the caller,
    # even if the orchestrator response omitted it.
    if isinstance(result, dict) and not result.get("super_id") and final_super_id:
        result = {**result, "super_id": final_super_id}
    return result


async def full_analysis_fallback(
    client: httpx.AsyncClient,
    property_url: str,
    super_id: Optional[str] = None,
    callback_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    AI-fetcher-first analysis, used when the agent knows there's no pre-built
    fetcher (or wants to force the AI path).

    Implementation: directly invoke WF B (multishot AI), then queue a build
    flag locally so WF C will create a coded fetcher in the background. The
    immediate return is the AI fetcher's result; future requests for the same
    domain pick up the newly-built coded fetcher.

    NOTE: WF A already implements 'try coded then AI'. fallback differs by
    skipping the coded attempt entirely — useful when the caller knows the
    domain is new or when they specifically want multishot quality.
    """
    body: Dict[str, Any] = {"url": property_url}
    if super_id:
        body["super_id"] = super_id
    ai_result = await n8n_post(
        client, settings.N8N_WFB_URL, body, timeout=300.0
    )

    # Fire-and-forget: enqueue a build_flag so WF C builds a coded fetcher
    # for this domain in the background. We swallow errors here because the
    # AI result is what the caller actually needs right now.
    build_flag = None
    build_queue_error = None
    build_super_id = super_id or ai_result.get("super_id")
    try:
        if build_super_id:
            build_flag = await dc_post(
                client,
                "/build-flags",
                {
                    "url": property_url,
                    "reason": "fallback",
                    "super_id": build_super_id,
                },
                timeout=15.0,
            )
        else:
            build_queue_error = (
                "AI fallback returned no super_id, so no build_flag could be queued"
            )
    except Exception as exc:  # noqa: BLE001
        build_queue_error = str(exc)
        logger.warning(
            "fallback: failed to enqueue build_flag for %s: %s", property_url, exc
        )

    return {
        "ai_result": ai_result,
        "build_queued": build_flag is not None,
        "build_flag": build_flag,
        "build_queue_error": build_queue_error,
    }

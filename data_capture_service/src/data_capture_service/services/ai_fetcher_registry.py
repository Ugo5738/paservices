"""
AI Fetcher Registry — DB-driven adapter loader.

Replaces the hardcoded `_AI_ADAPTERS = {"firecrawl": firecrawl_adapter}` dict
that used to live in ai_fetchers_router. Adapter selection is now a registry
lookup: each row in `data_capture.ai_fetchers` carries an importable
`adapter_path` like `module.submodule:attr` that we resolve lazily.

This keeps the V2 architecture's "vendor-agnostic" rule honest: adding a new
AI fetcher (Gemini, BrightData, ChatGPT, ...) is one INSERT, no code edit
in routers, no `if name == "firecrawl"` branches.
"""

import importlib
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.adapters.base import DataCaptureAdapter
from data_capture_service.crud import ai_fetcher_crud
from data_capture_service.models.ai_fetcher import AIFetcher

logger = logging.getLogger(__name__)


class AIFetcherNotRegistered(Exception):
    """Raised when a caller asks for an AI fetcher that has no row."""


class AIFetcherDisabled(Exception):
    """Raised when the AI fetcher row exists but `enabled=false`."""


def _import_adapter(adapter_path: str) -> Any:
    """
    Resolve a 'module.path:attr' string to the actual adapter object.

    The adapter must implement the DataCaptureAdapter protocol (fetch_raw,
    parse, score). Mirrors how setuptools entry points are resolved.
    """
    if ":" not in adapter_path:
        raise ValueError(
            f"adapter_path must be 'module.path:attr', got '{adapter_path}'"
        )
    module_path, attr = adapter_path.split(":", 1)
    module = importlib.import_module(module_path)
    obj = getattr(module, attr, None)
    if obj is None:
        raise ImportError(
            f"adapter_path '{adapter_path}' resolved to no attribute on "
            f"module '{module_path}'"
        )
    return obj


async def load_by_name(
    db: AsyncSession, name: str
) -> tuple[AIFetcher, DataCaptureAdapter]:
    """
    Look up the AIFetcher row and return (row, adapter_object).

    Raises AIFetcherNotRegistered if no row, AIFetcherDisabled if enabled=false.
    """
    row = await ai_fetcher_crud.get_by_name(db, name)
    if row is None:
        raise AIFetcherNotRegistered(
            f"No ai_fetchers row for '{name}'. Available: see SELECT name FROM "
            "data_capture.ai_fetchers."
        )
    if not row.enabled:
        raise AIFetcherDisabled(f"AI fetcher '{name}' is disabled in registry")
    adapter = _import_adapter(row.adapter_path)
    return row, adapter


async def load_default_baseline(
    db: AsyncSession,
) -> tuple[AIFetcher, DataCaptureAdapter]:
    """
    Return the (row, adapter) tuple for the default-baseline AI fetcher.

    Used by W3 scoring as the benchmark source. Vendor-agnostic by design —
    today resolves to Firecrawl; future may resolve to an "AI Council"
    composite adapter without any code change.
    """
    row = await ai_fetcher_crud.get_default_baseline(db)
    if row is None:
        raise AIFetcherNotRegistered(
            "No enabled AI fetcher rows; cannot resolve baseline."
        )
    adapter = _import_adapter(row.adapter_path)
    return row, adapter


async def is_registered(db: AsyncSession, name: str) -> bool:
    """Cheap check used by routers to decide between 404 and 503."""
    row = await ai_fetcher_crud.get_by_name(db, name)
    return row is not None


async def list_enabled_names(db: AsyncSession) -> list[str]:
    rows = await ai_fetcher_crud.list_enabled(db)
    return [r.name for r in rows]

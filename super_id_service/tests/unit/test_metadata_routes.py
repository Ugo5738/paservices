"""
Unit tests for SuperID Metadata store routes (activity_records, link_records).

Tests the route handlers in isolation by mocking the DB session and CRUD
layer. Integration tests (with a real DB) live in tests/integration/.

Covers:
  - permission enforcement (superid_metadata:write / :read)
  - happy-path creation of activity and link records
  - Pydantic-level rejection of self-links on link records
  - bidirectional read shape
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status
from pydantic import ValidationError

from super_id_service.routers.metadata_router import (
    create_activity_record_endpoint,
    create_link_record_endpoint,
    list_activity_endpoint,
    list_links_endpoint,
)
from super_id_service.schemas.auth_schema import TokenData
from super_id_service.schemas.metadata_schema import (
    ActivityRecordCreate,
    LinkRecordCreate,
)


def _token(permissions):
    """Build a TokenData fixture with the given permissions."""
    return TokenData(
        sub="test-client",
        exp=1800000000,
        iss="auth_service",
        permissions=permissions,
    )


def _request():
    """Minimal mock Request object — only `method` and `url.path` are read."""
    req = MagicMock()
    req.method = "POST"
    req.url.path = "/test"
    return req


# ---------------------------------------------------------------------------
# Pydantic-level validation (no DB / route layer)
# ---------------------------------------------------------------------------


def test_link_record_create_rejects_self_link():
    """A SuperID linked to itself is rejected at schema validation."""
    same = uuid.uuid4()
    with pytest.raises(ValidationError) as exc:
        LinkRecordCreate(
            super_id_a=same,
            super_id_b=same,
            created_by="test",
            source="test/self_link",
        )
    assert "cannot be linked to itself" in str(exc.value)


def test_link_record_create_accepts_distinct_super_ids():
    """Distinct super_ids are accepted regardless of order."""
    a = uuid.uuid4()
    b = uuid.uuid4()
    payload = LinkRecordCreate(
        super_id_a=a,
        super_id_b=b,
        created_by="test",
        source="test/distinct",
    )
    assert payload.super_id_a == a
    assert payload.super_id_b == b


def test_activity_record_create_requires_non_empty_fields():
    """Empty used_by or source is rejected."""
    sid = uuid.uuid4()
    with pytest.raises(ValidationError):
        ActivityRecordCreate(super_id=sid, used_by="", source="x")
    with pytest.raises(ValidationError):
        ActivityRecordCreate(super_id=sid, used_by="x", source="")


# ---------------------------------------------------------------------------
# Permission enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_activity_rejects_missing_write_permission():
    body = ActivityRecordCreate(
        super_id=uuid.uuid4(), used_by="svc", source="test/initial"
    )
    with pytest.raises(HTTPException) as exc:
        await create_activity_record_endpoint(
            request_body=body,
            request=_request(),
            token_data=_token(permissions=["something:else"]),
            db=AsyncMock(),
        )
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert "superid_metadata:write" in exc.value.detail


@pytest.mark.asyncio
async def test_create_link_rejects_missing_write_permission():
    body = LinkRecordCreate(
        super_id_a=uuid.uuid4(),
        super_id_b=uuid.uuid4(),
        created_by="svc",
        source="test/link",
    )
    with pytest.raises(HTTPException) as exc:
        await create_link_record_endpoint(
            request_body=body,
            request=_request(),
            token_data=_token(permissions=["superid_metadata:read"]),
            db=AsyncMock(),
        )
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_list_activity_rejects_missing_read_permission():
    with pytest.raises(HTTPException) as exc:
        await list_activity_endpoint(
            super_id=uuid.uuid4(),
            limit=10,
            offset=0,
            token_data=_token(permissions=["superid_metadata:write"]),
            db=AsyncMock(),
        )
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert "superid_metadata:read" in exc.value.detail


# ---------------------------------------------------------------------------
# Happy-path creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_activity_happy_path():
    sid = uuid.uuid4()
    fake_record = MagicMock(
        activity_id=uuid.uuid4(),
        super_id=sid,
        used_by="coded_fetcher_service",
        used_at=datetime.now(timezone.utc),
        source="wf_dc_a_cf/service_invocation",
        activity_metadata={"hint": "x"},
    )
    with patch(
        "super_id_service.routers.metadata_router.create_activity_record",
        new=AsyncMock(return_value=fake_record),
    ) as crud_call:
        result = await create_activity_record_endpoint(
            request_body=ActivityRecordCreate(
                super_id=sid,
                used_by="coded_fetcher_service",
                source="wf_dc_a_cf/service_invocation",
                metadata={"hint": "x"},
            ),
            request=_request(),
            token_data=_token(permissions=["superid_metadata:write"]),
            db=AsyncMock(),
        )
    crud_call.assert_awaited_once()
    assert result.super_id == sid
    assert result.used_by == "coded_fetcher_service"
    assert result.source == "wf_dc_a_cf/service_invocation"
    assert result.metadata == {"hint": "x"}


@pytest.mark.asyncio
async def test_create_link_happy_path():
    a = uuid.uuid4()
    b = uuid.uuid4()
    fake_record = MagicMock(
        link_id=uuid.uuid4(),
        super_id_a=a,
        super_id_b=b,
        created_at=datetime.now(timezone.utc),
        created_by="wf_dc_b2_aif",
        source="ai_fetcher_service/validates_prior_service_run",
        link_metadata={},
    )
    with patch(
        "super_id_service.routers.metadata_router.create_link_record",
        new=AsyncMock(return_value=fake_record),
    ) as crud_call:
        result = await create_link_record_endpoint(
            request_body=LinkRecordCreate(
                super_id_a=a,
                super_id_b=b,
                created_by="wf_dc_b2_aif",
                source="ai_fetcher_service/validates_prior_service_run",
            ),
            request=_request(),
            token_data=_token(permissions=["superid_metadata:write"]),
            db=AsyncMock(),
        )
    crud_call.assert_awaited_once()
    assert result.super_id_a == a
    assert result.super_id_b == b
    assert result.source == "ai_fetcher_service/validates_prior_service_run"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_activity_returns_records_for_super_id():
    sid = uuid.uuid4()
    records = [
        MagicMock(
            activity_id=uuid.uuid4(),
            super_id=sid,
            used_by=name,
            used_at=datetime.now(timezone.utc),
            source=f"test/{name}",
            activity_metadata={},
        )
        for name in ("svc_a", "svc_b")
    ]
    with patch(
        "super_id_service.routers.metadata_router.list_activity_for_super_id",
        new=AsyncMock(return_value=records),
    ):
        result = await list_activity_endpoint(
            super_id=sid,
            limit=100,
            offset=0,
            token_data=_token(permissions=["superid_metadata:read"]),
            db=AsyncMock(),
        )
    assert result.super_id == sid
    assert result.count == 2
    assert [r.used_by for r in result.items] == ["svc_a", "svc_b"]


@pytest.mark.asyncio
async def test_list_links_returns_records_from_both_directions():
    """
    The CRUD layer is responsible for the bidirectional OR query.
    Here we just confirm the route surface returns whatever it gets.
    """
    sid = uuid.uuid4()
    other_1 = uuid.uuid4()
    other_2 = uuid.uuid4()
    records = [
        MagicMock(
            link_id=uuid.uuid4(),
            super_id_a=sid,  # sid in column A
            super_id_b=other_1,
            created_at=datetime.now(timezone.utc),
            created_by="x",
            source="test/a",
            link_metadata={},
        ),
        MagicMock(
            link_id=uuid.uuid4(),
            super_id_a=other_2,
            super_id_b=sid,  # sid in column B
            created_at=datetime.now(timezone.utc),
            created_by="y",
            source="test/b",
            link_metadata={},
        ),
    ]
    with patch(
        "super_id_service.routers.metadata_router.list_links_for_super_id",
        new=AsyncMock(return_value=records),
    ):
        result = await list_links_endpoint(
            super_id=sid,
            limit=100,
            offset=0,
            token_data=_token(permissions=["superid_metadata:read"]),
            db=AsyncMock(),
        )
    assert result.super_id == sid
    assert result.count == 2
    # Both directions returned — caller doesn't need to know which column matched.
    assert any(r.super_id_a == sid for r in result.items)
    assert any(r.super_id_b == sid for r in result.items)

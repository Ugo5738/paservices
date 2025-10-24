import importlib
from types import SimpleNamespace
from typing import Any, Dict, List
from uuid import uuid4

import pytest
from pydantic import HttpUrl, TypeAdapter


class DummyS3Client:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> None:
        # mimic boto3 response signature by returning None
        self.calls.append(kwargs)


def _reload_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_PREFIX", "rightmove/status")
    monkeypatch.setenv("DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_REGION", "us-east-1")
    monkeypatch.delenv("DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("DATA_CAPTURE_RIGHTMOVE_SERVICE_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("DATA_CAPTURE_RIGHTMOVE_SERVICE_SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setenv("DATA_CAPTURE_RIGHTMOVE_SERVICE_SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    monkeypatch.setenv("DATA_CAPTURE_RIGHTMOVE_SERVICE_M2M_JWT_SECRET_KEY", "secret-key")

    # Reload configuration so the global settings reflect the current env values.
    import data_capture_rightmove_service.config as config

    importlib.reload(config)

    # Ensure the status notifier sees the refreshed settings module.
    import data_capture_rightmove_service.utils.status_notifier as status_notifier

    importlib.reload(status_notifier)


@pytest.mark.asyncio
async def test_status_notifier_uploads_and_returns_snapshot_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _reload_settings(monkeypatch)

    import data_capture_rightmove_service.utils.status_notifier as status_notifier

    dummy_client = DummyS3Client()
    monkeypatch.setattr(
        status_notifier,
        "boto3",
        SimpleNamespace(client=lambda *args, **kwargs: dummy_client),
    )

    notifier = status_notifier.StatusNotifier()

    super_id = uuid4()
    snapshot_url = await notifier.notify(
        super_id=super_id,
        status="in_progress",
        context="test_context",
        data={"progress": 10},
        summary={"completed": 1},
        metadata={"info": "initial"},
    )

    assert snapshot_url == f"https://test-bucket.s3.amazonaws.com/rightmove/status/test_context/{super_id}/status.json"
    assert len(dummy_client.calls) == 1

    uploaded_payload = dummy_client.calls[0]
    assert uploaded_payload["Bucket"] == "test-bucket"
    assert uploaded_payload["Key"] == f"rightmove/status/test_context/{super_id}/status.json"


@pytest.mark.asyncio
async def test_status_notifier_overwrites_snapshot_for_subsequent_updates(monkeypatch: pytest.MonkeyPatch) -> None:
    _reload_settings(monkeypatch)

    import data_capture_rightmove_service.utils.status_notifier as status_notifier

    dummy_client = DummyS3Client()
    monkeypatch.setattr(
        status_notifier,
        "boto3",
        SimpleNamespace(client=lambda *args, **kwargs: dummy_client),
    )

    notifier = status_notifier.StatusNotifier()
    super_id = uuid4()

    await notifier.notify(
        super_id=super_id,
        status="in_progress",
        context="test_context",
        data={"progress": 30},
    )
    await notifier.notify(
        super_id=super_id,
        status="completed",
        context="test_context",
        data={"progress": 100},
    )

    assert len(dummy_client.calls) == 2
    first_body = dummy_client.calls[0]["Body"].decode("utf-8")
    second_body = dummy_client.calls[1]["Body"].decode("utf-8")
    assert '"progress": 30' in first_body
    assert '"progress": 100' in second_body


@pytest.mark.asyncio
async def test_status_notifier_accepts_httpurl(monkeypatch: pytest.MonkeyPatch) -> None:
    _reload_settings(monkeypatch)

    import data_capture_rightmove_service.utils.status_notifier as status_notifier

    dummy_client = DummyS3Client()
    monkeypatch.setattr(
        status_notifier,
        "boto3",
        SimpleNamespace(client=lambda *args, **kwargs: dummy_client),
    )

    captured_urls: List[str] = []

    class DummyAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "DummyAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, json: Dict[str, Any], headers: Dict[str, Any]) -> Any:
            captured_urls.append(url)

            class _Response:
                def raise_for_status(self) -> None:
                    return None

            return _Response()

    monkeypatch.setattr(
        status_notifier.httpx,
        "AsyncClient",
        DummyAsyncClient,
    )

    notifier = status_notifier.StatusNotifier()
    url_adapter = TypeAdapter(HttpUrl)
    http_url = url_adapter.validate_python(
        "http://host.docker.internal:5678/webhook/test"
    )
    await notifier.notify(
        super_id=uuid4(),
        status="started",
        context="test_httpurl",
        data={"progress": 0},
        metadata={"callback_url": http_url},
        webhook_url=http_url,
    )

    assert captured_urls == ["http://host.docker.internal:5678/webhook/test"]
    body = dummy_client.calls[0]["Body"].decode("utf-8")
    assert '"callback_url": "http://host.docker.internal:5678/webhook/test"' in body

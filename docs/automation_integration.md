# Paservices Automation Integration Guide

This document consolidates everything an n8n (or any automation) engineer needs to orchestrate workflows across the **Auth**, **Super ID**, **Data Capture Rightmove**, **Floorplan Analysis**, and **Image Condition Analysis** services. Each service exposes asynchronous pipelines with consistent status notifications (webhooks + S3 snapshots) so you can trigger, monitor, and react to progress and final results.

---

## 1. System Overview

| Service | Directory | Framework | Purpose |
|---------|-----------|-----------|---------|
| **Auth Service** | `auth_service` | FastAPI | Issues machine-to-machine (M2M) tokens for internal services. |
| **Super ID Service** | `super_id_service` | FastAPI | Generates workflow-specific UUIDs. |
| **Data Capture Rightmove** | `data_capture_rightmove_service` | FastAPI + Celery | Scrapes Rightmove metadata, handles combined property fetches. |
| **Floorplan Service** | `floorplan_service` | FastAPI + Celery | Fetches Rightmove floorplan snapshots and broadcasts status updates. |
| **Image Condition Analysis** | *(external repo `sanalysis`)* | Django + Celery | Analyses property photos for condition scoring and summary insights. |

All services run inside Docker (see `docker-compose.yml`). The `paservices` stack shares Supabase (Postgres) and S3 credentials via `.env` files. The two analysis services (floorplan + image condition) follow the same notification contract:

1. Client submits an async task (`POST /.../analyze` endpoint).
2. Service immediately returns `202` and enqueues work.
3. Background job updates internal DB tables and emits status notifications to S3 and an optional callback URL.
4. n8n listens to the webhook or pulls the snapshot from S3 to continue the automation.

---

## 2. Authentication + Super IDs

### 2.1 Auth Service
- **Endpoint**: `POST http://<host>:8001/api/v1/auth/token`
- **Body**:
  ```json
  {
    "grant_type": "client_credentials",
    "client_id": "<m2m-client-id>",
    "client_secret": "<m2m-client-secret>"
  }
  ```
- **Response**:
  ```json
  {
    "access_token": "<JWT>",
    "token_type": "bearer",
    "expires_in": 3600
  }
  ```
- Use this token in the `Authorization: Bearer <token>` header for all downstream service calls.

### 2.2 Super ID Service
- **Endpoint**: `POST http://<host>:8002/api/v1/super_ids`
- **Headers**: `Authorization: Bearer <token>`
- **Body**:
  ```json
  {
    "count": 1,
    "metadata": {
      "description": "Workflow run for property XYZ"
    }
  }
  ```
- **Response**:
  ```json
  {
    "super_id": "50151250-6c58-43f6-a03c-00d5452e35b9"
  }
  ```

---

## 3. Data Capture Rightmove Service

### 3.1 Combined Fetch API
- **Endpoint**: `POST http://<host>:8003/api/v1/properties/fetch/combined`
- **Body**:
  ```json
  {
    "super_id": "c2a2f94f-b0d9-4414-99ad-a3e2da1518ab",
    "property_url": "https://www.rightmove.co.uk/properties/154508327#/?channel=RES_LET",
    "callback": {
      "url": "http://host.docker.internal:5678/webhook/rightmove-status",
      "headers": { "X-Workflow": "rightmove-combined" }
    }
  }
  ```
- **Response**: `202 Accepted`, `{"message":"Accepted combined fetch request...", "success":true}`

### 3.2 Status Notification
- S3 key: `rightmove/status/fetch_combined/<super_id>/status.json`
- Webhook payload (example):
  ```json
  {
    "super_id": "c2a2f94f-b0d9-4414-99ad-a3e2da1518ab",
    "status": "completed",
    "context": "fetch_combined",
    "data_location": "https://propertyanalysisstorage.s3.amazonaws.com/rightmove/status/fetch_combined/<super_id>/status.json",
    "summary": {
      "total_endpoints": 2,
      "completed_endpoints": 2
    },
    "metadata": {
      "property_id": 154508327,
      "property_url": "...",
      "client_id": "...",
      "callback_url": "http://host.docker.internal:5678/webhook/rightmove-status"
    },
    "timestamp": "2025-10-23T10:50:57.757583+00:00"
  }
  ```
- Snapshot (`data.results[]`) contains the raw API responses, success flags, and messages.

### 3.3 Environment Variables
```
DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_BUCKET_NAME
DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_PREFIX
DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_WEBHOOK_URL
DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_WEBHOOK_HEADERS
```

---

## 4. Floorplan Service

### 4.1 API Call
- **Endpoint**: `POST http://<host>:8004/api/v1/floorplans/analyze`
- **Headers**: `Authorization: Bearer <token>`
- **Body**:
  ```json
  {
    "super_id": "0eae5db5-2cf3-4e82-b6d3-2104a64837fa",
    "property_id": "rightmove-123",
    "floorplans": {
      "fp1": {
        "url": "https://media.rightmove.co.uk/.../FLP_00_0002.jpeg",
        "notes": "Ground floor"
      }
    },
    "callback": {
      "url": "http://host.docker.internal:5678/webhook/floorplan-status",
      "headers": { "X-Workflow": "floorplan" }
    }
  }
  ```
- **Response**: `202 {"message":"Floorplan analysis initiated."}`

### 4.2 Status Notification
- S3 key: `floorplan/status/floorplan_analyze/<super_id>/status.json`
- Webhook payload:
  ```json
  {
    "super_id": "0eae5db5-2cf3-4e82-b6d3-2104a64837fa",
    "status": "completed",
    "context": "floorplan_analyze",
    "summary": { "processed_floorplans": 1, "total_floorplans": 1 },
    "metadata": { "property_id": "rightmove-123", "callback_url": "...", "notes": {} },
    "data_location": "https://propertyanalysisstorage.s3.amazonaws.com/floorplan/status/...",
    "timestamp": "2025-10-25T07:57:23.616069+00:00"
  }
  ```
- Snapshot `data.floorplans[]` includes `raw_data` from the Rightmove API (analysis results, S3 references, messages).

### 4.3 Environment Variables
```
DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_S3_*   (shared bucket credentials)
DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_WEBHOOK_URL
DATA_CAPTURE_RIGHTMOVE_SERVICE_STATUS_WEBHOOK_HEADERS
```

---

## 5. Image Condition Analysis Service (Django)

> **Location**: `/Users/i/Documents/work/sanalysis` (separate repo but shares credentials).

### 5.1 API Call
- **Endpoint**: `POST http://<host>:800x/api/v1/image-condition/analyze`
- **Headers**: `Authorization: Bearer <token>`
- **Body**:
  ```json
  {
    "super_id": "b6964844-25f8-4721-8d20-bb99450d5402",
    "image_urls": [
      "https://media.rightmove.co.uk/.../IMG_00.jpeg",
      "https://media.rightmove.co.uk/.../IMG_01.jpeg"
    ],
    "notes": {
      "bedrooms": 3,
      "floorplan_urls": ["https://...floorplan.jpeg"]
    },
    "callback": {
      "url": "http://host.docker.internal:5678/webhook/image-condition",
      "headers": { "X-Workflow": "condition" }
    }
  }
  ```
- **Response**: `202 {"super_id": "...", "images": 2, "status": "queued"}`.

### 5.2 Status Notification
- S3 key: `image-condition/status/image_condition_analysis/<super_id>/status.json`
- Webhook payload mirrors Floorplan Service (status/context/data_location/summary/metadata).
- Snapshot `data` includes:
  ```json
  {
    "stage": "complete",
    "message": "Analysis completed",
    "progress": 100.0,
    "stage_progress": {
      "analysis": { "progress": 60.0, ... },
      "overall_analysis": { "progress": 100.0, ... }
    },
    "extra": {
      "final_result": {
        "Condition": {...},
        "Detailed Analysis": {...},
        "Overall Analysis": {...}
      }
    }
  }
  ```

### 5.3 Environment Variables
Set in `analysis_service/settings/base.py` via the `IMAGE_CONDITION_STATUS_*` names:
```
IMAGE_CONDITION_STATUS_S3_BUCKET_NAME
IMAGE_CONDITION_STATUS_S3_REGION
IMAGE_CONDITION_STATUS_S3_PREFIX
IMAGE_CONDITION_STATUS_WEBHOOK_URL
IMAGE_CONDITION_STATUS_WEBHOOK_HEADERS
```

---

## 6. n8n Workflow Patterns

### 6.1 Trigger
1. **HTTP Request Node** for Auth → store `access_token`.
2. **HTTP Request Node** for Super ID (optional; some flows accept a pre-generated super_id).
3. **HTTP Request Node** to the service’s `analyze` endpoint (include `callback`).
4. Capture `super_id` for downstream nodes.

### 6.2 Listen for Updates
1. Create an n8n **Webhook** node (POST).
2. URL: `http://host.docker.internal:5678/webhook/<flow-name>`.
3. Add a condition node:
   ```javascript
   {{ $json["status"] === "completed" }}
   ```
4. Optionally branch on `status === "failed"` for alerting.

### 6.3 Fetch Snapshot
1. HTTP Request (GET) to `{{$json["data_location"]}}`.
2. Set “Response Format → JSON”.
3. Use the JSON in subsequent steps (e.g., Property creation, CRM updates, dashboards).

### 6.4 Error Handling
- `status === "failed"` payload contains `metadata.error` or `data.extra.error`. Route to Slack/Email nodes for troubleshooting.
- For partial results (e.g., some floorplans fail), inspect `data.floorplans[].analysis`.

---

## 7. Testing & Local Development

| Component | Command |
|-----------|---------|
| Paservices APIs | `docker compose up auth_service super_id_service data_capture_rightmove_service floorplan_service` |
| Floorplan system test | `python scripts/test_system/test_floorplan_analysis.py --property-id rightmove-demo --floorplan-urls <url>` |
| Sanalysis server | `python manage.py runserver` *(requires env + database connectivity)* |
| Image condition migrations | `python manage.py migrate image_condition_analysis` |
| Install deps (sanalysis) | `pip install -r requirements.txt` |

**Credentials**  
All services share AWS (S3) and Supabase (Postgres) environment variables. Check `.env.dev`, `.env.prod`, and the Supabase dashboard for them. Update the `.env` files if credentials rotate.

---

## 8. Summary
- Every long-running task emits **consistent** status notifications (S3 + webhook).
- n8n can:
  - Trigger (`POST /analyze`), include a callback.
  - Listen (`Webhook` node) for `started/in_progress/completed/failed`.
  - Pull final data (`data_location` URL) for further processing.
- Environment variables control defaults; per-call `callback` overrides are supported.

With this guide, an automation engineer can confidently orchestrate properties, floorplans, and image-condition analyses end-to-end. For further details, inspect the notifier modules:

- `data_capture_rightmove_service/utils/status_notifier.py`
- `floorplan_service/utils/status_notifier.py`
- `image_condition_analysis/utils/status_notifier.py` (in `sanalysis`)

Feel free to extend the webhook payloads or snapshots if additional metadata is needed in future automation flows.

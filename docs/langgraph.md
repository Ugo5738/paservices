## LangGraph Integration Guide (calls, auth, examples)

### MCP Auth (ScaleKit)

- Resource/audience: `https://mcp.supersami.com/mcp`
- Scope: `users:analyze`
- Obtain token from ScaleKit (client credentials). Use `Authorization: Bearer <token>` on MCP requests.

### MCP Connection Model (Streamable HTTP)

- This MCP server uses Streamable HTTP. Clients must establish a session before calling tools.
- The MCP “handshake” is the JSON-RPC `initialize` call.
- Lifecycle:
  1. Obtain OAuth access token (client credentials)
  2. Initialize MCP session (`initialize`)
  3. Confirm initialization (`notifications/initialized`)
  4. Perform tool calls (reuse `Mcp-Session-Id`)
  5. (Optional) Open SSE stream

### Step 1 — Initialize MCP Session (Required)

- Endpoint: `POST https://mcp.supersami.com/mcp`
- Headers:
  - `Authorization: Bearer <access_token>`
  - `Accept: application/json, text/event-stream`
  - `Content-Type: application/json`
- Body:
  ```json
  {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {},
      "clientInfo": {
        "name": "langgraph-client",
        "version": "1.0.0"
      }
    }
  }
  ```
- Response: HTTP 200. `mcp-session-id` is returned in response headers; reuse it for all subsequent MCP calls.

### Step 2 — Complete Initialization

- Endpoint: `POST https://mcp.supersami.com/mcp`
- Headers:
  - `Authorization: Bearer <access_token>`
  - `Mcp-Session-Id: <session_id>`
  - `Accept: application/json, text/event-stream`
  - `Content-Type: application/json`
- Body:
  ```json
  {
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
    "params": {}
  }
  ```

### MCP HTTP (tools) — requires active MCP session

- All tool calls must include both `Authorization: Bearer <token>` and `Mcp-Session-Id: <session_id>` headers obtained during initialization.

- Base: `https://mcp.supersami.com/mcp`
- Trigger full analysis:
  - Payload (raw HTTP example):
    ```json
    {
      "method": "trigger_full_property_analysis_tool",
      "params": {
        "property_url": "https://www.rightmove.co.uk/properties/163495745#/?channel=RES_BUY",
        "external_callback_url": "https://yourapp.example.com/analysis/updates"
      }
    }
    ```
  - Returns n8n trigger response; callback defaults to `https://mcp.supersami.com/api/analysis/callback`.
- Poll result:
  ```json
  {
    "method": "get_property_analysis_result_tool",
    "params": { "super_id": "<id>" }
  }
  ```

### Callback & Polling APIs

- Callback (public):  
  `POST https://mcp.supersami.com/api/analysis/callback`  
  Body: `{"super_id":"abc","status":"complete|failed|pending","property_url":"...","final_result":{...},"error":{...}}`
- Poll:  
  `GET https://mcp.supersami.com/api/analysis/results/<super_id>`
- Updates (public):  
  `GET https://mcp.supersami.com/api/analysis/updates/<super_id>?limit=50`

### Service Update Payloads (external_callback_url)

Services that honor `callback_urls` (Data Capture, Floorplan, and Image Condition) send status updates
to both `workflow_callback_url` and `external_callback_url`. The update body looks like:

```json
{
  "super_id": "e46209e3-1066-4ec8-ac53-ddf2202b0fc6",
  "status": "started|in_progress|completed|failed",
  "context": "fetch_combined|search|floorplan_analysis|image_condition_analysis",
  "data_location": "https://<bucket>/<prefix>/<context>/<super_id>/status.json",
  "timestamp": "2025-12-20T21:06:56.276459+00:00",
  "summary": {},
  "metadata": {}
}
```

The `data_location` URL points to a richer snapshot with the same envelope plus a `data` field
containing service-specific payloads:

```json
{
  "super_id": "...",
  "context": "...",
  "status": "...",
  "timestamp": "...",
  "summary": { "...": "..." },
  "metadata": { "...": "..." },
  "data": { "...": "..." }
}
```

The final aggregate result is posted by n8n to `workflow_callback_url` only:

```json
{
  "super_id": "...",
  "status": "complete",
  "property_url": "...",
  "final_result": { "...": "..." },
  "error": null
}
```

### n8n Trigger (direct)

- Webhook: `POST https://n8n-automation.supersami.com/webhook/d36312c5-f379-4b22-9f6c-e4d44f50af4c`
- Body: `{"property_url":"<url>","workflow_callback_url":"https://mcp.supersami.com/api/analysis/callback","external_callback_url":"https://yourapp.example.com/analysis/updates"}`
- Expected response: `{"super_id":"...","status":"started"}` (ensure workflow responds early).

### Service Endpoints (direct, if needed)

- Auth service: tokens/JWKS (`/.well-known/jwks.json`), issuer `paservices_auth_service`.
- Super ID service: create super IDs.
- Data capture service: scrapes rightmove property data.
- Floorplan service: floorplan analysis trigger.

### Example curls

- Trigger via n8n:  
  `curl -X POST https://n8n-automation.supersami.com/webhook/d36312c5-f379-4b22-9f6c-e4d44f50af4c -H 'Content-Type: application/json' -d '{"property_url":"<url>","workflow_callback_url":"https://mcp.supersami.com/api/analysis/callback","external_callback_url":"https://yourapp.example.com/analysis/updates"}'`
- Poll via MCP API:  
  `curl https://mcp.supersami.com/api/analysis/results/<super_id>`

### Notes for LangGraph

- Ensure tokens include `aud=https://mcp.supersami.com/mcp` and `scope=users:analyze`.
- Return the `super_id` immediately from the n8n webhook so the agent can poll.
- `external_callback_url` is forwarded to downstream services for status updates, while the final aggregate result posts to `workflow_callback_url`.

### Common MCP Errors

- `401 Unauthorized`: missing or invalid OAuth bearer token.
- `406 Not Acceptable`: missing `Accept: text/event-stream` (or `application/json`) header for Streamable HTTP.
- `400 Missing session ID`: MCP session not initialized or `Mcp-Session-Id` header absent.
- Tool calls fail immediately: `initialize` not called first.

---

## Microservice API Quick Reference

- **Auth Service** (`https://auth.supersami.com/api/v1`)

  - Token: `POST /auth/token` with client credentials; returns bearer token. JWKS: `/.well-known/jwks.json`. Issuer: `paservices_auth_service`.
  - Use `Authorization: Bearer <token>` for downstream services.

- **Super ID Service** (`https://superid.supersami.com/api/v1`)

  - Create super ID: `POST /super_ids` with bearer token. Optional prefix; returns `{super_id: ...}`.

- **Data Capture Rightmove** (`https://data-capture-rightmove.supersami.com/api/v1`)

  - Combined fetch: `POST /properties/fetch/combined` with bearer token, body `{"property_url":"<rightmove-url>","super_id":"<id>"}`.

- **Floorplan Service** (`https://floorplan-v1.supersami.com/api/v1`)

  - Analyze: `POST /floorplans/analyze` with bearer token, body includes `floorplan_url` or storage key plus `super_id`/`property_id`.
  - Status (from Aggregate workflow): `GET /workflow-status/{super_id}`.

- **Image Condition Analysis** (`https://image-condition-analysis.supersami.com/api`)
  - Analyze: `POST /image-condition-analysis/analyze/` with bearer token and image payload.
  - Status: `GET /image-condition-analysis/workflow-status/{super_id}`.

Notes:

- External domains above match the n8n workflow JSONs (`n8n_workflows/*.json`). For internal calls, use service URLs from `pa_mcp/.env.prod` (`PA_MCP_AUTH_SERVICE_URL`, `PA_MCP_SUPER_ID_SERVICE_URL`, etc.).

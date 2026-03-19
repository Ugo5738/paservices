# Orchestration V2 — MCP Tools + n8n Workflow Plan

## Current State

### What already exists and works:
1. **Data capture service** — has `callback_url` support, POSTs `{super_id, status, context: "data_capture", summary, final_result}` to pa_mcp's callback endpoint when done
2. **Orchestrator V2 n8n workflow** (`06_orchestrator_v2.json`) — already handles:
   - Scraper → wait for callback → extract media → fan out to FP + ICA
   - Direct fan-out (no scraper, use `service_params`)
   - Any combination of services
3. **pa_mcp callback endpoint** — receives per-service status updates, tracks via `latest_status_by_context`
4. **`trigger_orchestrated_analysis_tool`** — flexible tool with `services_json` parameter
5. **Individual service tools** — `trigger_data_capture_tool`, `trigger_floorplan_tool`, `trigger_image_condition_tool`, `trigger_rightmove_capture_tool`
6. **Polling tool** — `get_property_analysis_result_tool(super_id)` reads from pa_mcp DB

### What needs to be added/changed:

## Plan

### Step 1: Add new convenience MCP tools in `mcp_tools.py`

Add **one new tool** as a cleaner wrapper for the full analysis:

```python
@mcp.tool()
async def analyze_property_tool(property_url: str = "", super_id: str = "") -> str:
    """Run the complete property analysis pipeline: scrape data → extract floorplans →
    run floorplan analysis + image condition analysis. Returns a super_id to poll for results.
    Use get_property_analysis_result_tool(super_id) to check progress and get final results."""
```

This calls `trigger_orchestrator_via_n8n()` under the hood with `services=["data_capture_motie", "floorplan_analysis", "image_condition_analysis"]`.

The existing tools already cover the other use cases:
- **Custom sequence**: `trigger_orchestrated_analysis_tool(url, services_json)` — already exists
- **Single service**: `trigger_data_capture_tool`, `trigger_floorplan_tool`, `trigger_image_condition_tool` — already exist
- **Polling**: `get_property_analysis_result_tool(super_id)` — already exists

No need to create more tools — just rename/add the convenience one.

### Step 2: Wire up `N8N_ORCHESTRATOR_V2_URL` in pa_mcp config

The config already has `N8N_ORCHESTRATOR_V2_URL` defined. Need to:
- Set the env var `PA_MCP_N8N_ORCHESTRATOR_V2_URL` to point to the v2 orchestrator webhook in n8n
- The v2 orchestrator is `06_orchestrator_v2.json` — once imported into n8n, it will have a webhook path

### Step 3: Deploy the Orchestrator V2 workflow to n8n

Import `06_orchestrator_v2.json` into n8n and configure:
- Set the Auth + Super ID sub-workflow ID reference
- Verify webhook URLs for scraper, floorplan, and ICA match current n8n webhook paths
- Activate the workflow

### Step 4: Create per-service n8n workflows for the new data capture service

The orchestrator v2 calls scraper/floorplan/ICA via their n8n webhook paths. For the new Motie data capture:
- Create an n8n workflow (`02_data_capture_motie`) that:
  1. Receives webhook with `{url, super_id, skip_baseline, callback_url}`
  2. Gets auth token
  3. POSTs to `https://data-capture.supersami.com/api/v1/data_capture/start` with `callback_url` set to the orchestrator's "Wait for Scraper" resume webhook
  4. Returns 202 immediately

The data capture service will POST its callback directly to the orchestrator's wait node when done.

### Step 5: Verify callback format compatibility

The data capture service callback already produces:
```json
{
  "super_id": "...",
  "status": "completed",
  "context": "data_capture",
  "summary": {"floorplan_urls": [...], "image_urls": [...], ...},
  "final_result": {"canonical": {...}, "media": [...], "quality": {...}}
}
```

The orchestrator v2's "Extract Media URLs" node reads:
- `$json.body.final_result.media` for floorplan/photo URLs
- `$json.body.summary.floorplan_urls` and `$json.body.summary.image_urls` as fallback

This is already compatible. No changes needed to the data capture service.

### Step 6: No database migration needed

- pa_mcp already has `analysis_results` and `analysis_updates` tables
- The data capture service has its own tables
- Each service pushes callbacks to pa_mcp's `/api/analysis/callback` which updates `analysis_results`
- No new tables or columns required

## Summary of code changes

| File | Change | Scope |
|------|--------|-------|
| `pa_mcp/src/pa_mcp/mcp_tools.py` | Add `analyze_property_tool` wrapper | ~15 lines |
| `pa_mcp/.env.prod` | Set `PA_MCP_N8N_ORCHESTRATOR_V2_URL` | 1 line |
| n8n UI | Import orchestrator v2 + data capture motie workflows | Config only |

## Architecture flow after changes

```
Agent calls analyze_property_tool(url)
  └→ pa_mcp calls trigger_orchestrator_via_n8n(services=["data_capture_motie", "floorplan_analysis", "image_condition_analysis"])
      └→ POST to n8n Orchestrator V2 webhook
          └→ n8n responds 202 {super_id}
          └→ n8n internally:
              1. Calls Data Capture Motie workflow (with callback_url = orchestrator wait webhook)
              2. Data capture service runs, POSTs callback to orchestrator wait webhook
              3. Orchestrator resumes, forwards callback to pa_mcp /api/analysis/callback
              4. Extracts floorplan URLs + image URLs from callback
              5. Fans out: Call Floorplan + Call ICA in parallel
              6. Floorplan/ICA services POST their callbacks directly to pa_mcp /api/analysis/callback

Agent polls get_property_analysis_result_tool(super_id)
  └→ Reads pa_mcp DB
      └→ Returns {
           latest_status_by_context: {
             data_capture: {status: "completed"},
             floorplan_analysis: {status: "in_progress"},
             image_condition_analysis: {status: "completed"}
           },
           final_result: null  // until all services done
         }
```

## What we are NOT doing
- Not touching old workflows (SuperSami Trigger, Data Capture, Aggregate)
- Not migrating databases
- Not creating new n8n polling loops
- Not adding new DB models or tables

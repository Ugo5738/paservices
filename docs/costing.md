# Costing Outline (Full Property Analysis)

This doc summarizes the calls and cost drivers for one “full property analysis” and for a batch of 100 properties. No pricing data exists in this repo, so fill in vendor rates/token costs where marked `TBD`.

## Workflow components (per property)

- Data Capture Rightmove: `POST https://data-capture-rightmove.supersami.com/api/v1/properties/fetch/combined` (1 call)
- Floorplan Analysis: `POST https://floorplan-v1.supersami.com/api/v1/floorplans/analyze` (1 call) + status poll via `GET /api/v1/workflow-status/{super_id}` (1 call)
- Image Condition Analysis: `POST https://image-condition-analysis.supersami.com/api/image-condition-analysis/analyze/` (1 call) + status poll via `GET /api/image-condition-analysis/workflow-status/{super_id}` (1 call)
- Aggregation (n8n):
  - Fetch DCR snapshot: `GET {data_location}` (1 call)
  - Fetch floorplan snapshot(s): `GET {floorplan_data}` and CSV/JSON URLs (~3 calls)
  - Fetch ICA snapshot: `GET {image_condition_analysis_data}` (1 call)
  - Final callback to MCP/external: `POST {workflow_callback_url}` (1 call)

## Cost placeholders (per property)

- Data Capture Rightmove service: `TBD_service_cost_per_run`
- Floorplan service: `TBD_floorplan_cost_per_run`
- Image Condition Analysis service: `TBD_ica_cost_per_run`
- LLM/token usage (if applicable, e.g., ICA/floorplan post-processing):
  - Estimated input tokens per property: `TBD_tokens_in`
  - Estimated output tokens per property: `TBD_tokens_out`
  - Model rate: `TBD_model_name @ $TBD_input_per_1k / $TBD_output_per_1k`
  - Token cost per property = `((TBD_tokens_in/1000) * input_rate) + ((TBD_tokens_out/1000) * output_rate)`
- Storage/egress (S3 snapshots, CSV/JSON fetches): typically negligible; include if billed separately: `TBD_storage_egress_per_property`

### Per-property total (formula)

```
total_per_property = data_capture + floorplan + ica + token_cost + storage_egress
```

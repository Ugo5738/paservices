# Analysis Result Schema (Observed / Inferred)

The `pa_mcp` service stores workflow outputs in `analysis_results.final_result` as JSONB.
This payload is **not a fixed schema** because it includes upstream provider responses
(e.g. Rightmove) and outputs from ML services that can add/remove fields over time.

For AI agents and client integrations, we generate an **observed schema** by sampling
real payloads and inferring:

- all observed keys (including nested keys)
- observed data types per key

## Generate an observed schema locally

From repo root:

```bash
python3 scripts/schema/infer_json_schema.py
```

Or explicitly (same thing, but lets you choose outputs):

```bash
python3 scripts/schema/infer_json_schema.py \
  output/final_output.json \
  --unwrap-key final_result \
  --output output/final_result.schema.json \
  --paths-output output/final_result.paths.tsv
```

Notes:

- If you have many payloads, you can point the script at a directory and it will scan
  `*.json` recursively.
- The schema is only as “complete” as the sample set: if a key never appears in your
  samples, it won’t appear in the inferred schema.

## What to treat as stable

In practice, clients should treat these as stable:

- Top-level workflow envelope keys in `analysis_results` (`super_id`, `status`, `final_result`, `error`)
- The top-level sections inside `final_result` (e.g. `data_captured`, `floorplan_data`, `image_condition_data`)

Everything under provider-specific payloads like `final_result.data_captured.data.results[].raw_data.data`
should be treated as **best-effort** (allow unknown keys).

# Data Capture V2 — Architecture Reference

**Audience:** Rolf (project owner), Daniel (implementer), future engineer onboarding to V2.
**Purpose:** explain — with file/line references — how Data Capture is intended to work under the SuperID principles, and where today's code deviates.
**Companions:**
- `docs/superid_principles.md` (authoritative SuperID invariants).
- `docs/superid_data_capture_design.md` (how the SuperID system applies to Data Capture).
- `docs/data_capture_v2_id_and_data_flow.md` (an end-to-end walkthrough of one analysis).
- `docs/superid_agents.md` (gate for AI agents working on SuperID-related code).

This document is target-state, aligned with `docs/superid_principles.md`. "Current code state" callouts mark places where today's code differs from the target. If anything in this doc appears to contradict `docs/superid_principles.md`, the principles document wins.

---

## 1. The two-layer split

| Layer | What it owns | Where it lives |
|---|---|---|
| Workflow logic | Routing, sequencing, looping, fallthrough decisions, retries | n8n (`n8n_workflows/*.json`) |
| Granular primitives | Stateless one-job endpoints (look up, run, validate, register, publish) | `data_capture_service` (FastAPI under `/api/v1/`), `data_capture_rightmove_service`, etc. |

n8n calls primitives over HTTP. Primitives never call other workflows or take orchestration decisions. Adding a new workflow = new n8n flow. Adding a new vendor = one row in the `ai_fetchers` registry (vendor-agnostic).

This split is preserved as-is from the prior V2 design; nothing about the SuperID principles changes it.

---

## 2. Identity: the SuperID is the only ID

There is **exactly one identifier type in this system: the SuperID.** This is non-negotiable; see `docs/superid_principles.md` §1.

The rules that follow are summarised here so the architecture document is self-contained. For the authoritative version go to the principles document.

### How SuperIDs flow

- **One SuperID typically carries an entire analysis.** It is minted at the top of the flow (by the MCP tool or the topmost workflow) and is passed downward through workflows and services. Each service and workflow that receives it uses it exactly once, recording an activity entry, before passing it on.
- **New SuperIDs are minted only when a workflow or service that has already consumed the in-scope SuperID needs to run again.** The principles call this "single-use within scope." Each service enforces this against its **own** datastore — there is no shared registry on the hot path.
- **Failure does not mint a new SuperID.** Failure is the outcome of a use; the failure data is captured in the service's own output. A *retry* against a different service mints a new SuperID only if that service has already consumed the prior one.
- **Long-running multi-turn executions are one use of one SuperID.** A Motie build session that takes hours and many turns is a single activity record on a single SuperID. A new SuperID is required only if the executing context resets (process restart, timeout-and-resume against a fresh execution, pivot to a distinct new task).

### What is forbidden

- `RunID`, `WorkflowID`, `JobID`, `StepID`, `parent_id`, `child_id`, `parent_super_id`, `OUTER_SID`, "inner_super_id", `group_id`, `thread_id`, `lineage_id`, `session_id` (as a SuperID-like identifier), `version_id`, `attempt_number` (as a SuperID-equivalent grouping field).
- Mutating a record keyed by SuperID — no UPDATE, no UPSERT, no DELETE in the normal flow. Reruns and corrections are new SuperIDs.
- Hierarchy between SuperIDs. Relationships are recorded as bidirectional **link records** in the SuperID Metadata store, not as parent/child fields.

### The SuperID Metadata store

Two record types — both append-only, both immutable — describe what SuperIDs do and how they relate:

- **Activity record:** `{activity_id, super_id, used_by, used_at, source}`. One row per use of a SuperID by a service or workflow. Indexed on `super_id`.
- **Link record:** `{link_id, super_id_a, super_id_b, created_at, created_by, source}`. One row per claimed relationship between two SuperIDs. **Bidirectional** — indexed on both `super_id_a` and `super_id_b`. Order of the two columns is not semantically meaningful.

Whether the SuperID Metadata store is hosted by the existing `super_id_service` or by a new dedicated service is an open architectural question (see `docs/superid_data_capture_design.md` §3.2). Either option satisfies the principles.

### Current code state — every claim below is verified

The current code is **substantially non-compliant** with the rules above. The deltas:

| Topic | Target (principles) | Current code | Citation |
|---|---|---|---|
| Mint authority | One SuperID flows through a normal pass | Chunk 1 applied: `Auth + Super ID Sub-Workflow` fails on missing/invalid `super_id` (no longer mints); `WF DC 1 Main` passes its `super_id` through to `WF DC B AIF`. Remaining gap: `WF DC B2 AIF` still mints its own `super_id` at entry + per attempt. Upstream callers (Orchestrator V2, pa_mcp) must mint at scope entry — verify before deploying. | `n8n_workflows/Auth + Super ID Sub-Workflow.json`; `n8n_workflows/WF DC 1 Main - Data Capture.json:124`; `n8n_workflows/WF DC B2 AIF - AI Fetcher Multishot.json` |
| Single-use check | Each service enforces `super_id` uniqueness in its own datastore and rejects duplicates | Schema intent partially present: `pa_mcp.analysis_result.super_id` is PRIMARY KEY; `data_capture_rightmove_service.workflow_status` and `floorplan_service.fp_workflow_status` both have `UniqueConstraint("super_id", "context", ...)`. But every application path uses upsert and routes around the constraint instead of rejecting. The V2 `fetcher_runs` table has no constraint at all. | `pa_mcp/src/pa_mcp/models/analysis_result.py:15`; `pa_mcp/src/pa_mcp/crud/analysis_result_crud.py:10-34`; `data_capture_rightmove_service/src/data_capture_rightmove_service/models/workflow_status.py:22-24`; `data_capture_rightmove_service/src/data_capture_rightmove_service/crud/workflow_status_crud.py:35-75`; `floorplan_service/src/floorplan_service/models/workflow_status.py:22-24`; `data_capture_service/src/data_capture_service/models/fetcher_run.py:76` |
| Overlapping IDs | Only `super_id` exists | `run_id` PK, `parent_run_id`, `attempt_number`, `provider_run_id`, etc. in fetcher and motie audit tables | `data_capture_service/src/data_capture_service/models/data_capture_run.py`; `models/fetcher_run.py:67-108`; `models/motie_build.py:92-100`; `models/data_capture_run_step.py:70` |
| Immutability | No UPDATE on SuperID-keyed records | `pa_mcp` `analysis_result_crud.upsert_analysis_result` uses `ON CONFLICT DO UPDATE` lines 10-34; `floorplan_service` `workflow_status_crud.upsert_status` line 35; `fetcher_runs.status` advances `draft → final → superseded` via UPDATE | `pa_mcp/src/pa_mcp/crud/analysis_result_crud.py:10-34`; `floorplan_service/src/floorplan_service/crud/workflow_status_crud.py:35`; `data_capture_service/src/data_capture_service/routers/ai_fetchers_router.py:193-213` |
| SuperID Metadata store | Activity records + link records (append-only, bidirectional) | Does not exist | no tables matching `super_id_activity`, `super_id_link`, `activity_records`, `link_records` |
| Auth-paired SuperID minting | Compatible with principles | Compliant: `super_id_service.POST /api/v1/super_ids` mints UUID SuperIDs; JWT permission-gated; defensive audit log via trigger on `super_ids` table | `super_id_service/src/super_id_service/routers/super_id_router.py:84-151`; `super_id_service/src/super_id_service/crud/super_id_crud.py:32`; `super_id_service/db/schema.sql:9-67` |
| Motie multi-turn handling | One SuperID for the whole long-running execution | Compliant: orchestrator advances `motie_builds.state` across turns without minting new SuperIDs per turn | `data_capture_service/src/data_capture_service/orchestrators/motie_build_orchestrator.py:18-19`; `models/motie_build.py:40-49` |

The "Motie multi-turn" row deserves a note: today the `motie_builds` row mutates its `state` column to track build progress (`session_pending → session_running → session_complete → deployed`). That mutation is **not** a violation of the SuperID principles because `state` is internal to the build's lifecycle, not a field on a SuperID/activity/link record. It is, however, mutation on a row keyed indirectly by `project_uuid` and may be worth converting to append-only for consistency with the broader immutability discipline; that decision is out of scope for this document.

---

## 3. Storage tiers and what writes where

| Table | Tier | What writes to it | Used for |
|---|---|---|---|
| `data_capture.fetcher_runs` (target shape) | Audit (per-call) | every coded-fetcher and AI-fetcher service invocation | one row per use of one SuperID; immutable; `super_id` is `UNIQUE` (the single-use check) |
| `data_capture.fetchers` | Registry | `/fetchers/register` (called by WF DC 2 Build CF after Motie publishes) | which coded fetchers exist for which domains |
| `data_capture.ai_fetchers` | Registry | manual INSERT (one row = one vendor) | vendor-agnostic adapter selection |
| `data_capture.motie_builds` | Audit (per-build) | `/fetcher-builds/motie/build/start` | Motie build lifecycle (one row per build session) |
| `data_capture.build_flags` | Queue | `/build-flags`, WF DC 1 Main's "Write Build Flag" | which URLs need a coded fetcher built |
| `data_capture.canonical_property_snapshots` | **Master / canonical** | the gate-passing primitive only | consumer-facing property data; append-only |
| `data_capture.canonical_media` | Master | as above | consumer-facing image/floorplan list |
| `data_capture.source_raw_records` / `source_parsed_records` | Audit (per-call) | data capture pipeline | raw + parsed payload audit |
| `super_id_metadata.activity_records` (new) | SuperID Metadata | every service/workflow that uses a SuperID | per-use audit in the SuperID system |
| `super_id_metadata.link_records` (new) | SuperID Metadata | every place two SuperIDs become related | bidirectional graph between SuperIDs |

### Invariants

1. **Master is gated.** A master-table row is written only when the validate-and-score gate passes. Coded and AI fetchers behave identically at this layer.
2. **Output tables hold every fetcher run.** Failed validations, iterative passes, build benchmarks — all written. Output tables are immutable.
3. **Audit table tracks one row per use of one SuperID by a fetcher.** `super_id` is `UNIQUE`. There is no `status` lifecycle field that mutates after insertion. Iteration / supersession / fallback chains are expressed via SuperID activity and link records, not status mutation on this table.

### Current code state

- **V2 endpoints do not write to canonical.** `routers/ai_fetchers_router.py:142-174` and `routers/fetchers_router.py:142-169` write only to `fetcher_runs`. The V1 pipeline (`services/data_capture_pipeline.py:_store_canonical()` line 991) is the only writer of `canonical_property_snapshots` and is invoked only by `adapter_router.py` and `data_capture_router.py`. **V2 captures are invisible to consumers reading `canonical_property_snapshots`.** Resolving this needs a decision from Rolf: either V2 promotes-to-canonical when the gate passes, or consumers move to reading `fetcher_runs.fields_json`. Either is internally consistent.
- **`pa_mcp` and `floorplan_service` upsert by `super_id`.** This violates immutability. Re-runs should produce new SuperIDs and new rows, not overwrite existing ones.
- **`fetcher_runs` has `parent_run_id`, `attempt_number`, mutating `status`.** All three need to be removed when this table is brought into compliance.

---

## 4. The three core data paths

These match the walkthrough in `docs/data_capture_v2_id_and_data_flow.md`. Workflow names follow the convention `WF` (workflow) + `DC` (Data Capture domain) + identifier + descriptive suffix. Numbers (`1`, `2`) identify top-level Data Capture workflows; letters (`A`, `B`, `B2`) identify sub-paths called by **WF DC 1 Main**. Suffixes: `CF` = Coded Fetcher, `AIF` = AI Fetcher. The canonical synonyms ("Data Capture parent workflow", "Coded Fetcher workflow", "AI Fetcher workflow") are listed in the walkthrough doc.

Inside every fetcher run, the parser step is handled by `data_capture_service/src/data_capture_service/services/parser_registry.py`, which selects the appropriate parser for the source and converts the raw payload into the fields written to the parsed output table. The parser is internal to the fetcher service; it does not record its own SuperID activity.

### 4a. WF DC A CF — coded fetcher (single-shot)

```
Orchestrator → WF DC 1 Main (S-001 in scope)
            → WF DC A CF
                → /fetchers/lookup (find fetcher for domain)
                → /fetchers/run  (coded fetcher service uses S-001:
                                  fetch → write raw → parser_registry → write parsed → write audit → activity record)
                → /fetchers/validate (returns passed + score)
            → IF passed → write master keyed by (S-001, source_url); respond inline
```

- SuperIDs used: `S-001` throughout (one SuperID, multiple activity records).
- Tables written on success: fetcher output (raw + parsed), fetcher run audit, master, activity records.
- New SuperIDs minted: none.

### 4b. WF DC B AIF — AI fetcher (single-shot, current fallback when 4a fails)

```
WF DC 1 Main IF coded path failed →
            WF DC B AIF (S-001 passed in, not freshly minted)
                → Auth + Super ID (does NOT mint; receives S-001 from caller)
                → Resolve Adapter + Query (defaults to 'firecrawl')
                → POST /ai-fetchers/firecrawl/run (fetch → write raw →
                                                   parser_registry → write parsed →
                                                   write audit → activity record; all keyed by S-001)
                → Respond (data inline)
            → Write Build Flag (queues a coded-fetcher build for this domain)
            → Respond AI Fallback (data inline)
```

- SuperIDs used: `S-001` throughout.
- Tables written on success: fetcher output (raw + parsed), fetcher run audit, master if gate passes, build_flags (one row), activity records.
- New SuperIDs minted: none (the SuperID flows through from WF DC 1 Main).

> **Current code state.** Chunk 1 applied: `WF DC 1 Main` now passes its `super_id` through to `WF DC B AIF` (`n8n_workflows/WF DC 1 Main - Data Capture.json:124`), and the `Auth + Super ID Sub-Workflow` no longer mints when `super_id` is missing — it stops with an error. `WF DC B2 AIF` still has the old pattern (mints at workflow entry, mints per attempt) and will fail when invoked; rework deferred to chunks 5/7.

### 4c. WF DC B2 AIF — iterative AI fetcher (currently not triggered)

WF DC B2 AIF exists as a webhook (`wf-b-ai-fetcher-multishot`) but is not invoked by WF DC 1 Main today; reachable only by direct call.

The principles-compliant flow:

```
External call → WF DC B2 AIF
            → Receive S-001 from caller
            → First pass: fetch → write raw → parser_registry → write parsed → write audit → activity record on S-001
            → /fetchers/validate (scores first pass)
            → IF passed → write master keyed by (S-001, source_url); respond
            → ELSE   → Mint S-002 (WF DC B2 AIF's second run); link S-002 ↔ S-001
                       → WF DC B2 AIF needs to invoke the service again; the service has used S-001
                       → Mint S-003 for the service call; link S-003 ↔ S-001
                       → Service runs under S-003: fetch → write raw → parser_registry →
                                                   write parsed → write audit → activity record on S-003
                       → /fetchers/validate (scores second pass)
                       → Select winning pass (read-time; no status mutation)
                       → IF winner passes → write master keyed by (S-winner, source_url)
                       → Optionally write supersession link record
                       → Respond
```

- SuperIDs used: up to three for a 2-pass iteration (`S-001`, `S-002`, `S-003`).
- Tables written: fetcher output (raw + parsed) for each pass, fetcher run audit for each pass, master for the winning pass if the gate passes, activity records per use, link records per minted SuperID.
- **No** `parent_run_id`, **no** `attempt_number`, **no** `promote-winner` UPDATE on `fetcher_runs.status`.

> **Current code state.** Today `routers/ai_fetchers_router.py:193-213` (`promote-winner`) UPDATES `fetcher_runs.status` from `draft` to `final` (and siblings to `superseded`). `models/fetcher_run.py:67-138` defines `parent_run_id` and `attempt_number`. All of this needs to be replaced by the SuperID Metadata store and read-time interpretation.

---

## 5. WF DC 2 Build CF — Fetcher Build workflow (coded fetcher build, background)

```
Trigger: build_flags table has a 'pending' row
WF DC 2 Build CF polls build_flags
    → /fetcher-builds/motie/build/start (Motie session + deploy)
    → poll /fetcher-builds/motie/build/{id}/status
    → /fetcher-builds/motie/build/{id}/score (runs the newly-built coded fetcher:
                                              fetch → write raw → parser_registry →
                                              write parsed → write audit (fetcher_type=build_benchmark);
                                              compares output vs FireCrawl baseline)
    → IF score < threshold AND attempts < N → repair iteration (continuation of the same Motie session preserves S-001; a fresh session resets context and requires a new SuperID linked to S-001)
    → IF score >= threshold OR attempts exhausted → /fetcher-builds/motie/build/{id}/publish (returns artefact; does NOT write to fetchers registry)
    → /fetchers/register (this is what writes the new coded fetcher to data_capture.fetchers)
    → mark build_flag done
```

- **WF DC 2 Build CF uses the same SuperID as WF DC 1 Main (`S-001`)** for the entire long-running build session.
- Per `docs/superid_data_capture_design.md` §3.1: "The Fetcher Build service is one use of one SuperID for the whole long-running execution. No matter how many turns occur or how much time elapses, this is one activity record."
- The newly-built coded fetcher service has not seen `S-001` and can use it for its benchmark runs without minting a new one.

> **Current code state.** Compliant in shape — the `motie_build_orchestrator` does not mint per-turn SuperIDs (`orchestrators/motie_build_orchestrator.py:18-19`). The `motie_builds.session_id` and `deployment_id` columns are Motie-internal state, not SuperIDs, so they don't violate the "one ID type" rule. The build process is decoupled from `S-001` today (WF DC 2 Build CF has its own SuperID flow rather than receiving WF DC 1 Main's) — that needs to change so the build joins WF DC 1 Main's SuperID rather than minting its own.

---

## 6. Honest gaps and weak spots

Ordered by impact, with the SuperID-related gaps added as Hi-priority items:

| # | Issue | Severity | Status |
|---|---|---|---|
| 1 | SuperID Metadata store does not exist (no activity records, no link records, no append-only store) | **High** | Blocking — needs design decision (host on `super_id_service` vs new service) and implementation |
| 2 | Single-use rejection behaviour doesn't exist anywhere. Three services have schema-level UNIQUE/PK on `super_id` but route around it via upsert; `fetcher_runs` has no constraint at all. | **High** | Required for SuperID compliance; replace upsert with reject-on-collision in `pa_mcp`, rightmove `workflow_status`, floorplan `workflow_status`; add `UNIQUE(super_id)` to `fetcher_runs` and every other consuming service. |
| 3 | `pa_mcp` and `floorplan_service` perform UPSERT on rows keyed by `super_id` | **High** | Violates immutability; switch to append-only |
| 4 | `fetcher_runs` carries `parent_run_id`, `attempt_number`, mutating `status` lifecycle | **High** | Remove all three; replace with SuperID Metadata store + read-time interpretation |
| 5 | n8n workflows explicitly mint a fresh `super_id` at every entry; downstream workflows are passed empty `super_id` to force re-minting | **High** | Invert: pass the SuperID through; mint only where a caller has already used the in-scope one |
| 6 | V2 primitives don't write to `canonical_property_snapshots`; consumers reading canonical see no V2 data | High if consumer expects canonical | Needs decision (gate-promote vs read-from-fetcher_runs) |
| 7 | WF DC 1 Main calls WF DC B AIF directly, not WF DC B2 AIF; iterative logic is dormant | Medium | Needs activation decision |
| 8 | Iteration selection ("best of N") is not implemented in the principles-compliant way (no status mutation, just read-time link records) | Medium | Tied to #4 |
| 9 | No verify-found / verify-missing checks (Rolf's "is what was found actually present?" / "is missing data actually missing?") | Medium | Deferred |
| 10 | No 20-URL ground-truth test pack — output correctness unverified end-to-end | High | About to do |
| 11 | Vendor-agnostic at service layer (registry-driven), but only `firecrawl` is enrolled today | Low | One INSERT per new vendor when needed |
| 12 | Field-level provenance (which pass produced which value) not tracked | Low | Tied to #8 |

---

## 7. What "the system works" actually requires

A 20-URL test pack with hand-verified ground truth. Methodology:

1. **Pick 20 URLs:** 12 Rightmove (covering varied listing formats), 4 Zoopla, 2 OnTheMarket, 2 niche/boutique agency. Mix of sale/rent, varying completeness on the page itself.
2. **Manually capture truth** for each URL into a CSV: price, beds, baths, address_road, address_town, postcode, property_type, tenure, size, agent_name, image_count, floorplan_present (boolean).
3. **Run each URL through three paths:**
   - Coded path (Rightmove only — uses the registered fetcher).
   - AI fallback path (force-fail coded by pointing at a non-Rightmove domain, so it falls through).
   - Iterative AI path (with the same URL, when activated).
4. **Diff field-by-field.** Score:
   - field present and matches truth: +1
   - field present but wrong: 0 (and flag for review)
   - field absent but truth has it: 0 (a miss)
   - field absent and truth has it absent: +1 (correctly null)
5. **Output:** a CSV with one row per (URL, path) and one column per field, plus a summary scorecard.

That artefact, combined with this doc, answers "do we understand the architecture?" and "does the data come out correct?"

---

## 8. Quick reference — file/line index

Code citations for the claims in this document. **Most of these references describe the current state, which is non-compliant with the SuperID principles.** Files marked TARGET describe behaviour that is correct under the principles; everything else is a gap.

| Claim | File:lines | Status vs principles |
|---|---|---|
| SuperID minting endpoint | `super_id_service/src/super_id_service/routers/super_id_router.py:84-151` | TARGET — compliant |
| SuperID UUID generation | `super_id_service/src/super_id_service/crud/super_id_crud.py:32` | TARGET — compliant |
| SuperID record schema (`super_ids` table) | `super_id_service/db/schema.sql:9-19` | TARGET — compliant |
| Defensive audit log on SuperID record mutations | `super_id_service/db/schema.sql:28-67` | TARGET — compliant |
| JWT permission `super_id:generate` enforced | `super_id_service/src/super_id_service/routers/super_id_router.py:122-127` | TARGET — compliant |
| n8n auth sub-workflow reuses passed-in super_id | `n8n_workflows/Auth + Super ID Sub-Workflow.json:48-78, 99-107` | Partially compliant — pass-through works; the "mint if absent" path needs to be removed for downstream workflows |
| WF DC 1 Main passes its `super_id` through to WF DC B AIF | `n8n_workflows/WF DC 1 Main - Data Capture.json:124` | TARGET — chunk 1 applied |
| WF DC B2 AIF still mints its own super_id at the top | `n8n_workflows/WF DC B2 AIF - AI Fetcher Multishot.json` | GAP — chunks 5/7 will receive the caller's SuperID |
| `/ai-fetchers/{adapter}/run` writes audit only (no canonical) | `data_capture_service/src/data_capture_service/routers/ai_fetchers_router.py:142-174` | GAP — V2 path doesn't reach canonical; decision needed |
| `/fetchers/run` writes audit only (no canonical) | `data_capture_service/src/data_capture_service/routers/fetchers_router.py:142-169` | GAP — same as above |
| `promote-winner` UPDATEs `fetcher_runs.status` | `data_capture_service/src/data_capture_service/routers/ai_fetchers_router.py:193-213` | GAP — violates immutability; replace with SuperID Metadata link records |
| `_store_canonical` is the only canonical write path | `data_capture_service/src/data_capture_service/services/data_capture_pipeline.py:991-1023` | TARGET (in shape) — V2 endpoints need to call it once gate passes |
| V1 pipeline used by `adapter_router` + `data_capture_router` only | `data_capture_service/src/data_capture_service/routers/adapter_router.py:26,47`; `data_capture_router.py:35,56` | Mixed — V1 path is compliant; V2 endpoints need a similar canonical-write step |
| `parent_run_id` / `attempt_number` schema | `data_capture_service/src/data_capture_service/models/fetcher_run.py:61-138` | GAP — both fields need to be removed |
| `parent_run_id` navigation CRUD | `data_capture_service/src/data_capture_service/crud/fetcher_run_crud.py:90-99, 113-138` | GAP — replaced by SuperID Metadata link queries |
| FetcherRun status lifecycle (`draft`/`final`/`superseded`) | `data_capture_service/src/data_capture_service/models/fetcher_run.py:54-58` | GAP — remove the lifecycle; one row per SuperID use, immutable |
| `pa_mcp.upsert_analysis_result` (ON CONFLICT DO UPDATE) | `pa_mcp/src/pa_mcp/crud/analysis_result_crud.py:10-34` | GAP — switch to append-only |
| `floorplan_service.upsert_status` | `floorplan_service/src/floorplan_service/crud/workflow_status_crud.py:35` | GAP — switch to append-only |
| Motie build orchestrator (no per-turn super_id minting) | `data_capture_service/src/data_capture_service/orchestrators/motie_build_orchestrator.py:18-19` | TARGET — compliant; the build is one use of one SuperID |
| Motie build state machine | `data_capture_service/src/data_capture_service/models/motie_build.py:40-49` | OK — `state` is build-internal, not a SuperID field; converting to append-only is a separate hygiene question |
| Vendor-agnostic registry loader | `data_capture_service/src/data_capture_service/services/ai_fetcher_registry.py:57-93` | TARGET — compliant |
| Parser registry (selects parser per source) | `data_capture_service/src/data_capture_service/services/parser_registry.py` | TARGET — compliant; invoked inside the fetcher service between the raw and parsed table writes |
| Field tier weights / completeness score | `data_capture_service/src/data_capture_service/services/field_registry.py:21-89` | OK — orthogonal to SuperID |
| `VALIDATE_PASS_THRESHOLD = 0.85` | `data_capture_service/src/data_capture_service/services/thresholds.py:18` | OK — orthogonal to SuperID |
| SuperID Metadata store (activity + link records) | not yet implemented | **MISSING** — blocking new infrastructure |
| Per-service single-use check (`UNIQUE` on `super_id`) | `pa_mcp/src/pa_mcp/models/analysis_result.py:15` (PK); `data_capture_rightmove_service/.../models/workflow_status.py:22-24` (UniqueConstraint); `floorplan_service/.../models/workflow_status.py:22-24` (UniqueConstraint); `data_capture_service/.../models/fetcher_run.py:76` (no constraint) | **PARTIAL** — three services have schema-level constraints but every code path routes around via upsert; `fetcher_runs` has no constraint at all |

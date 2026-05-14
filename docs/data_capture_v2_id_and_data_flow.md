# Data Capture V2 — End-to-End Walkthrough

**Audience:** Rolf (review/signoff), Daniel (implementer).
**Status:** Target architecture — describes how Data Capture should work under the SuperID principles. See "Current code state" callouts for places where today's code still differs from the target.
**Companions:**
- `docs/superid_principles.md` (authoritative SuperID invariants).
- `docs/superid_data_capture_design.md` (how the SuperID system applies to Data Capture; this doc applies that design to a specific worked flow).
- `docs/data_capture_v2_v1_integration_architecture.md` (schema-level integration spec).

If anything in this doc appears to contradict `docs/superid_principles.md`, the principles document wins.

---

## What this doc shows

A concrete walkthrough of one property analysis from URL-in to result-out, naming every table that gets written at each step and every SuperID activity/link record. Designed to make the integration of V2's fetcher-run audit table with V1's output and master tables verifiable by reading top-to-bottom.

The workflows referenced below:

| Workflow | Synonym | Role |
|---|---|---|
| **WF DC 1 Main** | Data Capture parent workflow | Calls **WF DC A CF** first; falls back to **WF DC B AIF** if no coded fetcher exists or the coded run fails the gate. |
| **WF DC A CF** | Coded Fetcher workflow | Coordinates registered coded scrapers (Rightmove proxy, Motie-built). |
| **WF DC B AIF** | AI Fetcher workflow (single-shot) | Coordinates vendor-agnostic AI scrapers (FireCrawl Agent, future Gemini, etc. — selected by `fetcher_name`). |
| **WF DC B2 AIF** | AI Fetcher workflow (iterative) | Iterative variant — multiple AI Fetcher passes that refine or validate prior passes. |
| **WF DC 2 Build CF** | Fetcher Build workflow | Motie build pipeline. Asynchronous, long-running, builds new coded fetchers from FireCrawl benchmarks. |

**Naming convention.** `WF` = workflow; `DC` = Data Capture domain (so the labels don't collide with workflows in other parts of the system). Numbers (`1`, `2`) identify top-level Data Capture workflows. Letters (`A`, `B`, `B2`) identify sub-paths called by **WF DC 1 Main**. The suffix (`Main`, `CF`, `AIF`, `Build CF`) says what the workflow does (`CF` = Coded Fetcher; `AIF` = AI Fetcher).

---

## Plain-language table names

The physical tables sit behind these:

| Plain name | What it really is |
|---|---|
| **fetcher output table (raw)** | the table holding the raw payload returned by a fetcher run; one row per use of a SuperID by a fetcher |
| **fetcher output table (parsed)** | the table holding the structured fields produced by the parser_registry from that raw payload |
| **master table** | the canonical, validated, consumer-facing property data; immutable, append-only |
| **media table** | the canonical image and floorplan list paired with a master row |
| **fetcher run audit table** | per-fetcher-run row recording which SuperID a fetcher service used; immutable; `super_id` is `UNIQUE` (the single-use check) |
| **consumer results table** | per-analysis aggregated state the orchestrator writes for downstream consumers; append-only |
| **event log** | append-only event history for an analysis |
| **fetcher registry** | the single registry of fetchers (one row per fetcher, with `fetcher_type = coded \| ai`) |
| **build queue** | the queue of URLs/domains waiting for a coded fetcher to be built |
| **build tracker** | per-Motie-build row |
| **SuperID Metadata store** | append-only, immutable store of activity records and link records. New infrastructure — see `docs/superid_data_capture_design.md` §3.2. |

---

## Vocabulary

- **Fetcher** = anything that fetches property data from a URL. Coded scrapers (Rightmove, Motie-built) and AI fetchers (FireCrawl Agent, future Gemini, etc.) are all fetchers.
- **Fetcher run** = one execution of a fetcher = one use of one SuperID by that fetcher service.
- **Fetcher type** (`fetcher_type`) = `coded` or `ai`. Same interface, different mechanism.
- **Parser** = code that converts a fetcher's raw payload to structured fields. Selected per source by `parser_registry` (`data_capture_service/src/data_capture_service/services/parser_registry.py`). Lives inside the fetcher service; not a separate service.
- **SuperID** = the single, universal identifier minted by the SuperID service. See `docs/superid_principles.md`. There is no `RunID`, no `WorkflowID`, no `parent_id`, no separate analysis-level vs call-level ID.
- **Activity record** = entry in the SuperID Metadata store recording that a service or workflow used a particular SuperID, with descriptive metadata. One per use.
- **Link record** = bidirectional entry in the SuperID Metadata store connecting two SuperIDs with metadata describing why the relationship is claimed.

---

## Setup: how the SuperID works in Data Capture

**One SuperID typically carries an entire analysis from URL-in to result-out.** Every workflow and service that uses it writes one activity record per use. A new SuperID is minted **only when a workflow or service that has already consumed the in-scope SuperID needs to run again** — for example, when **WF DC B2 AIF**'s second AI Fetcher pass refines the first.

Walking from any SuperID: activity records tell you where it has been; link records tell you which other SuperIDs it relates to and why.

> **What this design refuses:** minting a fresh SuperID at every layer or service boundary. On a normal first pass, **WF DC A CF**, **WF DC B AIF**, and every service inside them use the **same** SuperID as **WF DC 1 Main**. See `docs/superid_principles.md` §9 (Mistake: "minting a new SuperID at every layer or service boundary").

> **Current code state.** Chunk 1 (n8n rename + Auth pass-through) has been applied: `Auth + Super ID Sub-Workflow` now fails on a missing/invalid `super_id` rather than minting (`n8n_workflows/Auth + Super ID Sub-Workflow.json`), and `WF DC 1 Main` now passes its `super_id` through to `WF DC B AIF` (`n8n_workflows/WF DC 1 Main - Data Capture.json:124`). `WF DC B2 AIF` still mints its own `super_id` at workflow entry and on each retry — that rework is deferred to chunk 5/7.
>
> The single-use *infrastructure* is partially present in three services — schema intent is encoded but the rejection behaviour is undermined by upsert patterns:
> - `pa_mcp.analysis_result.super_id` is the PRIMARY KEY, but `analysis_result_crud.upsert_analysis_result` uses `ON CONFLICT DO UPDATE` (`pa_mcp/src/pa_mcp/crud/analysis_result_crud.py:10-34`).
> - `data_capture_rightmove_service.workflow_status` has `UniqueConstraint("super_id", "context", ...)` (`models/workflow_status.py:22-24`), but `workflow_status_crud.upsert_status` does get-then-update-or-insert (`crud/workflow_status_crud.py:35-75`).
> - `floorplan_service.fp_workflow_status` has the same composite UNIQUE, with the same upsert pattern.
>
> So the *schema* in those three places encodes the intent. The *behaviour* in all three silently updates the existing row instead of rejecting. The V2 `fetcher_runs` table has no unique constraint on `super_id` at all (`data_capture_service/src/data_capture_service/models/fetcher_run.py:76` — nullable, no unique). To align with the principles, every consuming service needs a strict `UNIQUE` on `super_id` *and* the application layer needs to reject collisions rather than upsert. The SuperID Metadata store does not exist. All of this needs to change for this walkthrough to be operational.

---

## Step 1 — URL enters the system

The MCP tool receives a property URL, mints **`S-001`** via the SuperID service, and calls Orchestrator V2 with `{url, super_id=S-001, callback_url}`.

> **SuperID Metadata store writes:**
> - **SuperID record:** `{super_id=S-001, created_by="pa_mcp", source="pa_mcp/property_analysis_started"}`.
> - **Activity record:** `{super_id=S-001, used_by="pa_mcp", source="pa_mcp/property_analysis_started"}`.

Orchestrator V2 calls **WF DC 1 Main** with `{url, super_id=S-001}`.

> **Activity record:** `{super_id=S-001, used_by="orchestrator_v2", source="orchestrator_v2/data_capture_invoked"}`.

No persistent storage outside the SuperID Metadata store has been written yet.

---

## Step 2 — WF DC 1 Main

**WF DC 1 Main** receives `S-001`, performs its single-use check (looks up `S-001` in its own datastore; absent → proceeds), writes its activity record, and calls **WF DC A CF**.

> **Activity record:** `{super_id=S-001, used_by="wf_dc_1_main", source="wf_dc_1_main/started_by_orchestrator_v2"}`.

There is no separate `run_id` minted here. The "run" is identified by `S-001` plus its activity records.

---

## Step 3 — WF DC A CF: lookup

**WF DC A CF** performs its single-use check on `S-001`, writes its activity record, then looks up the **fetcher registry** by domain filtered to `fetcher_type='coded'`.

> **Activity record:** `{super_id=S-001, used_by="wf_dc_a_cf", source="wf_dc_a_cf/started_by_wf_dc_1_main"}`.

- **Found** → continue to Step 4.
- **Not found** → returns `no_fetcher` to **WF DC 1 Main**. **WF DC 1 Main** jumps to **Step 5** (AI fallback) and **Step 7** (queue a build for next time).

---

## Step 4 — WF DC A CF: run the coded fetcher

If a coded fetcher exists, **WF DC A CF** invokes the Coded Fetcher service. The service:

1. **Single-use check:** looks up `S-001` in its own datastore. If present, rejects (caller must obtain a new SuperID). If absent, proceeds.
2. Calls the fetcher to retrieve the raw payload.
3. **Writes the fetcher output table (raw)** keyed by `super_id=S-001`.
4. **Invokes `parser_registry`** to select the appropriate parser for the source and produce structured fields, completeness score, missing fields, field presence. The parser is internal to the service; no SuperID activity is recorded for the parser step.
5. **Writes the fetcher output table (parsed)** with the parser's output, keyed by `super_id=S-001`.
6. **Writes the fetcher run audit table** with `{super_id=S-001, fetcher_name='<domain>_coded', fetcher_type='coded'}`. The `super_id` column is `UNIQUE` — single-use is enforced at insertion.
7. **Writes an activity record** to the SuperID Metadata store: `{super_id=S-001, used_by="coded_fetcher_service", source="wf_dc_a_cf/service_invocation"}`.
8. **Validates and scores** (the gate): essential fields present, completeness ≥ threshold.
   - **If pass** → **writes the master table** keyed by `(S-001, source_url)`. Immutable.
   - **If fail** → no master write. Returns to **WF DC 1 Main**, which jumps to Step 5.

> **Failure does not mint a new SuperID.** The fail outcome is captured in the parsed-record fields (`score`, `missing_fields`, error text). Per `docs/superid_principles.md` §3: "A failure is a new SuperID *when retried*. Failure is not the absence of a run; it is a use of a SuperID that produced a different kind of outcome." The retry is the AI fallback (Step 5), not a re-execution of the coded fetcher.

> **Stored on success:**
>
> | Table | Row(s) | Notes |
> |---|---|---|
> | fetcher output table (raw) | 1 row, `super_id=S-001` | immutable |
> | fetcher output table (parsed) | 1 row, `super_id=S-001` | immutable; produced by parser_registry |
> | fetcher run audit table | 1 row, `super_id=S-001`, `fetcher_type=coded` | immutable; `super_id` `UNIQUE` |
> | master table | 1 row, key=`(S-001, source_url)` | immutable, gated |
> | SuperID Metadata store | 1 activity record | |

---

## Step 5 — WF DC B AIF: AI fetcher (single-shot fallback)

**WF DC 1 Main** calls **WF DC B AIF** with `{url, super_id=S-001, fetcher_name='firecrawl'}`. The fetcher is parameterised — any AI fetcher registered in the fetcher registry can be selected by name.

**WF DC B AIF** performs its single-use check, writes its activity record, then invokes the AI Fetcher service.

> **Activity records:**
> - `{super_id=S-001, used_by="wf_dc_b_aif", source="wf_dc_b_aif/started_by_wf_dc_1_main/coded_fetcher_failed"}`.
> - `{super_id=S-001, used_by="ai_fetcher_service", source="wf_dc_b_aif/service_invocation/initial_pass"}` (written by the service after its single-use check).

The AI Fetcher service:

1. Calls FireCrawl (or whichever vendor is selected) to retrieve the raw payload.
2. **Writes the fetcher output table (raw)** keyed by `super_id=S-001`.
3. **Invokes `parser_registry`** to produce structured fields.
4. **Writes the fetcher output table (parsed)** with parsed fields and scores.
5. **Writes the fetcher run audit table** with `{super_id=S-001, fetcher_name='firecrawl', fetcher_type='ai'}`.
6. **Validates and scores** (the gate).
   - **If pass** → **writes the master table**. The user has their data.
   - **If fail** → audit-only; no master. The orchestrator gets back "no usable data."

> **Stored on success:**
>
> | Table | Row(s) |
> |---|---|
> | fetcher output table (raw) | 1 row, `super_id=S-001` |
> | fetcher output table (parsed) | 1 row, `super_id=S-001` |
> | fetcher run audit table | 1 row, `super_id=S-001`, `fetcher_type=ai` |
> | master table | 1 row (gated) |
> | SuperID Metadata store | activity records from **WF DC B AIF** + AI Fetcher service |

---

## Step 6 — WF DC B2 AIF: iterative AI fetcher (deferred — not active today)

Today **WF DC B AIF** runs a single pass. **WF DC B2 AIF**'s iterative pattern, when enabled, mints **a new SuperID per pass** — because **WF DC B2 AIF** (and the AI Fetcher service) has already consumed the in-scope SuperID on the prior pass. Link records connect the new SuperIDs to the prior one.

**First pass:** as Step 5. **WF DC B2 AIF** uses `S-001`, the AI Fetcher service uses `S-001`. Activity records on `S-001` for both. **Master is not written yet** — the gate runs once the iteration is settled.

**Second pass (validation/refinement):**

1. **WF DC B2 AIF** has already used `S-001`. To run again, it mints **`S-002`**.
2. **Link record:** `{super_id_a=S-002, super_id_b=S-001, source="wf_dc_b2_aif/follows_prior_workflow_run"}`.
3. **Activity record on `S-002`:** `{used_by="wf_dc_b2_aif", source="wf_dc_b2_aif/iterative_validation_pass"}`.
4. Inside this second **WF DC B2 AIF** run, the AI Fetcher service must be invoked again. The service has already used `S-001`. The workflow mints **`S-003`** for the service call.
5. **Link record:** `{super_id_a=S-003, super_id_b=S-001, source="ai_fetcher_service/validates_prior_service_run"}`.
6. The service uses `S-003`:
   - Writes fetcher output (raw), invokes parser_registry, writes fetcher output (parsed) — all keyed by `super_id=S-003`.
   - Writes fetcher run audit row with `super_id=S-003`.
   - Writes activity record: `{super_id=S-003, used_by="ai_fetcher_service", source="wf_dc_b2_aif/service_invocation/validation_pass"}`.
7. **Gate runs** on the second pass.
   - **If pass** → writes the master table keyed by `(S-003, source_url)`.
   - **If neither pass meets the gate** → no master row. The orchestrator returns "no usable data."

**Selecting "the answer" without mutation.** There is **no `promote-winner` step that flips a status field.** Both passes exist immutably. If the system needs to express that the second pass supersedes the first, an additional link record is added:

> **Link record (supersession):** `{super_id_a=S-003, super_id_b=S-001, source="ai_fetcher_service/supersedes_prior_pass"}`.

Consumers reading the master table see the row(s) that passed the gate. Consumers reading fetcher output tables see all attempts. Consumers walking the SuperID Metadata store reconstruct which iteration superseded which via link records and their `source` metadata.

> **Stored across a 2-pass iteration (both passes complete):**
>
> | Table | Rows |
> |---|---|
> | fetcher output table (raw) | **2 rows** — `super_id=S-001` and `super_id=S-003` |
> | fetcher output table (parsed) | **2 rows** |
> | fetcher run audit table | **2 rows** — both immutable; no draft/final/superseded status field |
> | master table | **0 or 1 row** — whichever pass passes the gate |
> | SuperID Metadata store: activity records | 4 (workflow + service for each pass) |
> | SuperID Metadata store: link records | 2–3 — `S-002 ↔ S-001`, `S-003 ↔ S-001`, optionally a supersession link |
>
> **Output tables hold every attempt for full audit. Master holds only the chosen, validated capture.** No status mutation; no `parent_run_id`; no `attempt_number`.

> **Current code state.** Today `fetcher_runs.status` advances `draft → final → superseded` via UPDATE in `routers/ai_fetchers_router.py:193-213` (`promote-winner`), and `fetcher_runs` has `parent_run_id` (line 67) and `attempt_number` (line 108) columns, with the `FetcherRunStatus` enum at lines 54–58. All of these have to go to align with the principles. The same information is expressible as activity records, link records, and `source` metadata.

---

## Step 7 — Build flag (queues WF DC 2 Build CF in the background)

When **WF DC A CF** returns `no_fetcher` (or its coded run fails the gate), **WF DC 1 Main** also writes a row to the **build queue** so a coded fetcher can be built for this domain.

> **Stored:** `build_queue: {id, url, domain, reason, status='pending', created_at}`.

The build queue row is a pending request, not an execution; it does not need its own SuperID. **WF DC 1 Main** returns to the orchestrator at this point — the user already has their data from Step 5. The build runs asynchronously.

---

## Step 8 — WF DC 2 Build CF: Motie builds a coded fetcher (background)

**WF DC 2 Build CF** polls the **build queue** and picks the pending row. **It uses the same SuperID as Data Capture (`S-001`)**, per `docs/superid_data_capture_design.md` §3.1: "The asynchronous trigger does not require a new SuperID; Fetcher Build is simply another consumer of `S-001`."

The Fetcher Build service is **one use of one SuperID for the entire long-running, multi-turn build session**, no matter how many turns the Motie session takes or how much time elapses. One activity record covers the whole execution.

> **Activity record:** `{super_id=S-001, used_by="fetcher_build_service", source="wf_dc_2_build_cf/long_running_build_invocation"}`.

**WF DC 2 Build CF**:

1. **Start build:** writes a row to **build tracker** for this build attempt.
2. **Motie generates** a fetcher using the URL + the FireCrawl benchmark fields.
3. **Score:** runs the freshly-built fetcher against the same URL and compares to the FireCrawl benchmark. The score-test is itself a fetcher run, executed by a **newly-built coded fetcher service**. That service has never seen `S-001`, so it can use `S-001` for the benchmark run:
   - Writes 1 row to fetcher output (raw) keyed by `super_id=S-001`.
   - Invokes parser_registry to produce structured fields.
   - Writes 1 row to fetcher output (parsed).
   - Writes 1 row to fetcher run audit table with `fetcher_type='build_benchmark'` and `super_id=S-001`. (`fetcher_type` is descriptive metadata on the audit row, not a SuperID lifecycle field.)
   - Writes activity record on `S-001` from this newly-built fetcher service.
   - **No master write.** The user already has their canonical data from Step 5; benchmarks don't touch master.
4. **If score passes threshold** → publish the fetcher, then add a row to **fetcher registry** (`fetcher_type='coded'`). Future captures on this domain will take the fast coded path.
5. **If below threshold** → repair iteration. **If the Motie session ends and a new session starts for the repair, that's a new SuperID** (context reset; see `docs/superid_principles.md` §9 "Mistake: minting a new SuperID for every turn..."). Link record connects the repair SuperID to `S-001`. **If the repair is a continuation of the same Motie session, no new SuperID.**
6. **If retries exhausted** → mark build queue row `status='failed'`. No fetcher registered. The next user capture for this domain will use FireCrawl again and re-queue another build attempt.

> **Stored across a 3-attempt build (all within one continuous Motie execution):**
>
> | Table | Rows |
> |---|---|
> | build tracker | 1 row tracking the overall build |
> | fetcher output table (raw) | 3 rows (one per benchmark test run), all `super_id=S-001` |
> | fetcher output table (parsed) | 3 rows |
> | fetcher run audit table | 3 rows, `fetcher_type=build_benchmark` |
> | fetcher registry | 1 row added IF a winning iteration passes threshold |
> | build queue | 1 row, status updated to `done` or `failed` |
> | master table | **0 new rows** — benchmarks don't touch master |
> | SuperID Metadata store | 1 activity record for the Fetcher Build service (entire long-running execution = 1 use), plus 1 activity record per benchmark fetcher-service invocation |

---

## Step 9 — The completion path back to the consumer

Back in the user-facing flow:

1. **WF DC 1 Main** returns to Orchestrator V2 with the captured data inline (whatever **WF DC A CF** or **WF DC B AIF** produced).
2. Orchestrator V2 forwards the result via callback to pa_mcp.
3. **pa_mcp writes (append-only, keyed by `S-001`):**
   > | Table | Row |
   > |---|---|
   > | consumer results table | `{super_id=S-001, status, property_url, final_result, ...}` |
   > | event log | `{id, super_id=S-001, context='data_capture', data, ...}` |
4. Orchestrator V2 also kicks off Floorplan Analysis and Image Condition Analysis in parallel, each carrying `S-001`. Their results post back to the same callback and append to the event log.

When the user/agent wants the final result, they call the MCP polling tool with `S-001`. pa_mcp aggregates everything keyed by that SuperID and returns it.

> **Current code state.** `pa_mcp.crud.analysis_result_crud.upsert_analysis_result` uses `ON CONFLICT DO UPDATE` (lines 10–34), which mutates an existing row keyed by `super_id` rather than appending. Under the principles this is forbidden: a re-run produces a new SuperID, not an overwrite. `floorplan_service.crud.workflow_status_crud.upsert_status` (line 35) has the same issue. Both need to switch to append-only writes — and the existing PRIMARY KEY / UNIQUE constraints in those tables should start *rejecting* collisions instead of being routed around by upsert.

---

## Where everything for one analysis can be found

> Start from `S-001`. Activity records tell you every service/workflow that touched it. Link records tell you which other SuperIDs (if any) relate to it.
>
> | Table | Holds |
> |---|---|
> | **consumer results table** | per-analysis aggregated state (the headline answer) |
> | **event log** | full event timeline for this analysis |
> | **master table** | the canonical captured property data |
> | **fetcher output table (raw)** | every raw fetcher run for any SuperID in the analysis |
> | **fetcher output table (parsed)** | every parsed fetcher run for any SuperID in the analysis |
> | **fetcher run audit table** | per-fetcher-run row for any SuperID in the analysis |
> | **SuperID Metadata store: activity records** | every workflow/service that used `S-001` (and `S-002`, `S-003` if iteration happened) |
> | **SuperID Metadata store: link records** | how `S-002`, `S-003`, etc. relate to `S-001` |

---

## At-a-glance "where does data go" cheat sheet

| Step | Fetcher run type | output (raw) | output (parsed) | audit | master | SuperID Metadata |
|---|---|---|---|---|---|---|
| **WF DC A CF** coded fetcher (success) | `coded`, single | 1 row | 1 row | 1 row | **1 row** if gate passes | activity record |
| **WF DC A CF** coded fetcher (fail) | `coded`, single | 1 row | 1 row | 1 row | none | activity record |
| **WF DC B AIF** single-shot AI | `ai`, single | 1 row | 1 row | 1 row | **1 row** if gate passes | activity records (workflow + service) |
| **WF DC B2 AIF** iterative pass N | `ai`, new SuperID per pass | 1 row per pass | 1 row per pass | 1 row per pass | none until selection | activity + link records per pass |
| **WF DC B2 AIF** iteration selection | (no new fetcher run) | — | — | — | **1 row** if gate passes (chosen pass) | optional supersession link |
| **WF DC 2 Build CF** build benchmark | `build_benchmark` | 1 row per attempt | 1 row per attempt | 1 row per attempt | none — benchmarks don't touch master | activity record for the Fetcher Build service (one for whole build) + activity record per benchmark invocation |
| **WF DC 2 Build CF** publish + register | (no fetcher run) | — | — | — | none — fetcher registry gets a new row | — |

---

## The invariants this preserves

1. **One ID type only — SuperID.** No `RunID`, no `WorkflowID`, no `parent_run_id`, no analysis-level vs call-level distinction. See `docs/superid_principles.md` §1.
2. **One SuperID flows through a normal pass.** New SuperIDs appear only where a workflow or service has already consumed the in-scope SuperID and needs to run again.
3. **Every record is immutable, append-only.** Fetcher output tables (raw + parsed), fetcher run audit table, master table, consumer results table, event log, activity records, link records — all write-once. No `UPDATE` on rows keyed by SuperID. See `docs/superid_principles.md` §3.
4. **Each service enforces single-use locally** via a `UNIQUE` constraint on `super_id` in its own datastore *and* application-layer rejection on collision (no upsert). No shared registry on the hot path. See `docs/superid_principles.md` §4.
5. **Relationships are links, not hierarchy.** No parent/child. Iteration, supersession, fallback chains, async triggering — all expressed as bidirectional link records with descriptive `source` metadata. See `docs/superid_principles.md` §5, §7.
6. **The fetcher output tables hold every fetcher run, ever** — full audit. Failed validations. Iterative passes. Build benchmark runs. Same flow regardless of coded vs ai vs benchmark.
7. **The master table holds only the gated, chosen, validated capture per source URL.** One row per `(SuperID-of-winning-pass, source_url)`. Build benchmarks never touch master.

Coded and AI fetchers behave identically at the SuperID layer. The fetcher run audit table is additive metadata; it never replaces or duplicates the output tables or the master table, and it never mutates a status field to express lifecycle.

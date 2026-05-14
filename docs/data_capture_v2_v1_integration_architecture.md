# Data Capture V2 — Integration with V1 Storage Architecture

**Audience:** Rolf (signoff before code), Daniel (implementer).
**Status:** Proposal. No code changes until this is signed off.
**Author:** Daniel.

---

## 0. Vocabulary (locked in 8 May)

- **Fetcher** = anything that fetches property data from a URL. Coded scrapers (Rightmove, Motie-built) and AI fetchers (FireCrawl Agent, future Gemini, etc.) are all fetchers. There is no separate "adapter" concept — that term is dropped.
- **Fetcher run** = one execution of a fetcher.
- **Kind** of fetcher = `coded` or `ai`. Same interface, different mechanism.

Where this document refers to physical tables, plain names are used throughout:

| Plain name (this doc) | Physical table |
|---|---|
| **fetcher output table (raw)** | `data_capture.source_raw_records` |
| **fetcher output table (parsed)** | `data_capture.source_parsed_records` |
| **master table** | `data_capture.canonical_property_snapshots` (+ `canonical_media`) |
| **fetcher run audit table** | `data_capture.fetcher_runs` |
| **fetcher registry** | `data_capture.fetchers` (after merge — see §6f) |
| **build queue** | `data_capture.build_flags` |
| **build tracker** | `data_capture.motie_builds` |
| **run record** | `data_capture.data_capture_runs` |
| **consumer results table** | `pa_mcp.analysis_results` |
| **event log** | `pa_mcp.analysis_updates` |

---

## 1. The principle (Rolf, 8 May)

> *"Each fetcher is a granular fetcher in the scraper service.
> Data from each fetcher run goes into the fetcher output tables (raw + parsed).
> Data from the parsed output goes into the master table (gated by validate + score).
> Only data from the master table is used for analysis etc.
> Same flow applies to coded fetchers (Rightmove / Motie / other) and AI fetchers (FireCrawl Agent / etc.) — consistency is essential."*

(Rolf's wording, restated using the locked vocabulary from §0.)

**This is the single canonical flow. V2 must conform to it, not run alongside it.**

---

## 2. What the system does today (the gap)

The V2 routes were implemented as a parallel system. They write only to the fetcher run audit table and **bypass the V1 storage pipeline entirely**.

| V2 route | Writes fetcher run audit table | Writes fetcher output tables (raw / parsed) | Writes master table |
|---|---|---|---|
| `/fetchers/run` (coded fetchers — Rightmove, Motie, etc.) | ✅ | ❌ | ❌ |
| `/ai-fetchers/{name}/run` (AI fetchers — FireCrawl, future Gemini etc.) | ✅ | ❌ | ❌ |

**Consequence:** every property captured via the n8n V2 workflows (which is everything the MCP tooling currently uses) is invisible to anything that reads from master. Master is dormant for the entire V2 path. Both coded and AI fetchers are affected.

This is the miss. It happened because V2 was written without an architecture document, and the rewrite produced a parallel storage path instead of integrating with the existing one.

---

## 3. Target state — unified flow for every fetcher run

Every fetcher run (coded or AI, single-shot or multishot) goes through this flow:

```
[Fetcher run (V2 route)]
        │
        │  (fetcher-name parameterised — works for Rightmove, Motie, FireCrawl, ...)
        ▼
[fetcher run audit table row]  ← additive audit. Records super_id (per-call),
                                 fetcher_name, run_id, parent_run_id (loop linkage),
                                 status (draft/final/superseded/failed).
        │
        ▼
[fetcher output table (raw) row]     ← raw payload from the fetcher (V1 storage)
[fetcher output table (parsed) row]  ← parsed structured fields (V1 storage)
        │
        ▼
[validate + score gate]              ← V1 gate: validate_against_baseline,
                                       completeness score ≥ threshold (0.85)
        │
        │   gate passes ──────► [master table row written]
        │                        [media rows written]
        │
        │   gate fails ───────► no master write; rows stay as audit only
        ▼
[Response back to caller]
```

**Three rules govern this flow:**

1. **Every fetcher run writes the fetcher output tables (raw and parsed).** Not just legacy V1 calls. V2 routes call the same V1 storage functions.
2. **Master is only written when the validate + score gate passes.** Same gate V1 uses today (`_store_canonical()` after `validate_against_baseline()` + completeness threshold).
3. **The fetcher run audit table is additive, not a replacement.** It carries V2-specific concerns (multishot loop linkage, draft/final lifecycle, fetcher-name selection) that the V1 storage tables don't model. It does not absolve V2 from writing the V1 tables.

---

## 4. The role of the fetcher run audit table (additive)

The fetcher run audit table keeps its existing role. It does NOT replace the fetcher output tables. It carries the V2-specific information they don't have:

- **Multishot loop linkage** via `parent_run_id` — lets a multishot loop's iterations be grouped, promoted, and superseded.
- **Status lifecycle** (`draft` → `final` / `superseded` / `failed`) — lets a multishot loop write multiple attempts to audit and pick the winner.
- **Fetcher-name pointer** (`fetcher_name`, replacing the legacy `vendor` column) — identifies which registered fetcher produced this row.
- **Per-call super_id** — the inner auth super_id used for the granular call (distinct from the outer analysis super_id passed by the orchestrator).

**Every V2 fetcher run writes one fetcher-run-audit row AND its raw and parsed output rows AND (if the gate passes) its master row.** All tiers populated.

---

## 5. The multishot reconciliation (the one tricky bit)

The V1 storage pipeline assumes one row per fetcher run. The V2 multishot pattern (Workflow B) writes N draft rows for one logical "capture this URL" event, then promotes a winner. Reconciling these:

**Single-shot calls (Workflow 1 coded path, single-shot Workflow 2 AI path):**

- One fetcher run → one audit row (`status='final'` directly), one raw output row, one parsed output row.
- Validate + score → if passes, one master row written.
- Identical to the V1 flow. Trivially conformant.

**Multishot calls (Workflow B loop):**

- Each loop iteration writes one audit row (`status='draft'`), one raw output row, one parsed output row. **Output-table writes happen on every iteration** — these are real fetcher runs that produced output. Each one is a real run; each deserves its audit.
- **Master writes happen ONLY when a draft is promoted to `final`.** Drafts and superseded rows never trigger a master write. The validate + score gate is checked at promote time, not at draft time.
- The `promote-winner` primitive is the integration point: when called, it (a) flips the chosen audit row to `final`, (b) marks siblings `superseded`, (c) calls `_store_canonical()` from the V1 pipeline using the winner's parsed fields, gated by validate + score.

The output tables can carry every attempt (full audit). Master only carries the chosen, validated winner.

---

## 6. What changes in code

Concrete integration points — this is the spec for the work. No code yet.

### 6a. `/fetchers/run` (coded, single-shot)

After running the fetcher:

- Write a raw output row (raw payload, fetcher_name, super_id, run_id linkage)
- Write a parsed output row (parsed fields, fetcher_name)
- Run `validate_against_baseline()` against the field set
- If gate passes → call `_store_canonical()` to write the master row + media rows
- Continue writing the fetcher run audit row as today (`status='final'` for single-shot)

### 6b. `/ai-fetchers/{name}/run` (AI, single-shot)

Same as 6a, with `fetcher_name` set from the registered AI fetcher (firecrawl, gemini, ...).

### 6c. `/ai-fetchers/{name}/run` with `loop_start=true` or `parent_run_id` set (multishot draft)

- Write fetcher run audit row as `draft`
- Write raw output row + parsed output row (these are real fetcher runs; they earn their audit)
- **Do NOT call `_store_canonical()` yet.** No master write at draft time.

### 6d. `/ai-fetchers/promote-winner`

At promote time:

- Flip chosen audit row to `final`, siblings to `superseded`
- Run `validate_against_baseline()` on the winner's fields
- If gate passes → call `_store_canonical()` to write the master row using the winner's parsed data
- If gate fails → no master write; promote-winner returns the score so the parent workflow knows

### 6e. The orchestrator → analysis bridge

The consumer results table continues to be written via the orchestrator's `/api/analysis/callback` after Workflow A returns. This is the consumer-facing per-run record (keyed by outer super_id). It is unchanged.

The master table becomes the queryable per-URL property store. Downstream consumers that want "latest known data for URL X" read from master, not from the consumer results table.

### 6f. Schema migration: merge the two registries into one

Current schema has two registry tables: `data_capture.fetchers` (coded fetchers) and `data_capture.ai_fetchers` (AI fetchers). Different shapes, different metadata. Same conceptually.

**Target:** one unified `data_capture.fetchers` table with a `kind` column.

Proposed columns:

| Column | Type | Purpose |
|---|---|---|
| `id` | UUID PK | row id |
| `name` | string, unique | the fetcher's name (e.g., `firecrawl`, `motie_rightmove_v1`) |
| `kind` | enum: `coded` \| `ai` | which mechanism |
| `domain` | string, nullable | the domain this fetcher covers (coded only) |
| `implementation_path` | string | Python module path (`module.path:attr`) for the fetcher's implementation code |
| `route_path` | string, nullable | deployed scraper's route (coded only) |
| `http_method` | string, nullable | GET/POST (coded only) |
| `motie_project_uuid` | UUID, nullable | source Motie project (Motie-built coded only) |
| `param_schema` | JSONB | parameters the fetcher accepts |
| `metadata_json` | JSONB | kind-specific config (parser hints, baselines, etc.) |
| `is_metered` | bool | metering flag |
| `is_default_baseline` | bool | for `kind='ai'` — is this the default benchmark fetcher? |
| `status` | string | `active` / `disabled` |
| `created_at`, `updated_at` | timestamps | |

`fetcher_runs.fetcher_id` becomes a single FK pointing at this unified table (replacing the current pair `fetcher_id` + `ai_fetcher_id`).

### 6g. Schema migration: rename `vendor` → `fetcher_name`

In the fetcher run audit table, rename column `vendor` → `fetcher_name` to match vocabulary throughout the system. Also rename `adapter_name` → `fetcher_name` in the raw/parsed output tables and `source_adapter` → `source_fetcher` in the master table for consistency.

---

## 7. Storage tiers summary

| Tier | Tables (plain name) | Keyed by | Purpose | Who writes it |
|---|---|---|---|---|
| **Audit (V2 additive)** | fetcher run audit table | `id` (run_id) + `parent_run_id` for groups | Per-call audit, multishot lifecycle, drift over time | Every V2 route on every fetcher run |
| **Output tables (V1)** | fetcher output table (raw), fetcher output table (parsed) | `id` + `fetcher_name` + run_record link | Per-call raw + parsed records, one row per fetcher run | Every V2 route on every fetcher run (after this change) |
| **Master (V1)** | master table (+ media table) | `super_id` + `source_url` | The chosen, validated answer per analysis run | Single-shot V2 route on success; multishot only at promote-winner with passing gate |
| **Consumer view** | consumer results table, event log | outer `super_id` | Per-analysis-run aggregated state | Orchestrator callback after Workflow A returns |

---

## 8. Migration plan

Proposed as small chunks for sequential signoff:

| Chunk | Scope | Output | Verifiable by |
|---|---|---|---|
| 0 | This architecture doc | Signoff from Rolf | Rolf says yes |
| 1 | Schema migration: merge the two registries into one (§6f); rename `vendor`/`adapter_name` columns to `fetcher_name` (§6g) | One unified `fetchers` table; consistent column naming | DB inspection: one registry; columns named `fetcher_name` |
| 2 | `/fetchers/run` (coded path) wired into V1 storage pipeline | Coded captures populate the raw/parsed output tables and the master table (gated) | DB query after a Rightmove capture: rows in all three tiers |
| 3 | `/ai-fetchers/{name}/run` single-shot wired in | Single-shot AI captures populate same three tiers | DB query after a single FireCrawl capture |
| 4 | Multishot path — output tables on every draft, master on promote-winner | Multishot loop writes N draft+output rows; master row only after promote | DB query showing N output rows + 1 master row per multishot run |
| 5 | 20-URL test pack — verified ground truth | Field-level scorecard across coded / AI single-shot / multishot paths | CSV scorecard delivered |

Chunks 1–4 are independent in code and can be reviewed separately. Chunk 5 closes the loop with output-quality evidence.

---

## 9. Things that don't change

- Workflow A's external interface (webhook path, request shape, response shape) — unchanged.
- Orchestrator V3's call to Workflow A — unchanged.
- The consumer results table and the callback-based consumer flow — unchanged.
- The fetcher run audit table's role (lifecycle wrapper, parent_run_id linkage, draft/final lifecycle) — unchanged.
- Extensible fetcher registry — unchanged in concept; the AI registry physically merges with the coded registry in chunk 1.

What changes is the **internal storage path inside the V2 endpoints**: they start writing the fetcher output tables and master table in addition to the audit table. The audit is additive; the storage gap is closed.

---

## 10. Open questions for Rolf

Three decisions to confirm before chunk 2 starts:

1. **Multishot drafts and output tables.** Proposal in §5: every loop iteration (including drafts that end up superseded) writes the raw and parsed output rows because each iteration is a real fetcher run that produced output. Master is gated. **OK?** (Alternative: drafts skip output tables entirely; only the winner writes them. Recommended against — loses audit fidelity — but it's a valid choice.)

2. **Per-URL master semantics.** Today the master table is keyed by `super_id` + `source_url`. So each analysis run produces a new master row even for the same URL. **Is that what we want, so we can compare runs over time (drift)?** Or should it be one current row per URL with history elsewhere? Recommended: keep current schema — natural drift detection.

3. **Validate + score thresholds.** The V1 pipeline uses `COMPLETENESS_ACCEPT_THRESHOLD = 0.85` (configurable). Should V2 inherit the same threshold, or use a different one? Recommended: inherit — consistency.

Reply on these three and chunk 1 starts.

---

## 11. What this doc commits to

- V2 will not run as a parallel storage path. Every V2 fetcher run will write the output tables and the master table through the existing V1 pipeline functions, not around them.
- The fetcher run audit table stays as additive audit, not a replacement.
- Multishot loops will respect the master gate: drafts and superseded rows do not pollute master.
- Both coded and AI fetchers follow the same storage flow.
- One unified vocabulary (fetcher) across docs, code, schema, and conversation.
- One unified registry table (with a `kind` column) replaces the two existing registries.
- Column names use `fetcher_name` consistently across the schema.
- No code changes until this is signed off.

The miss happened because there was no architecture document anchoring the V2 work. This doc — and the process of getting it signed off before any code — is the operating change going forward.

# Data Capture — SuperID Design

**Status:** Authoritative. Signed off by Rolf.

> **Required reading.** This document assumes you have read `docs/superid_principles.md` and `docs/superid_reference_convention.md` and understand the rules governing the SuperID system. This document does not restate the principles; it shows how to apply them to the Data Capture feature. If anything in this document appears to contradict `docs/superid_principles.md`, the principles document is authoritative.

---

## Draft assumptions and open questions

The following items were assumed or proposed when drafting this document and should be reviewed before the document is finalised.

1. **Naming and casing of `SuperID` in code is not yet confirmed.** This document uses `SuperID`. The actual code form may differ.
2. **Where the SuperID Metadata store lives is not yet decided.** This document presents two options (hosted by the SuperID service, or a dedicated service). The choice is a real architectural decision and should be made before implementation.
3. **The proposed SuperID record fields are a starting point and open to revision.** This document proposes `super_id`, `created_at`, `created_by`, and `source` as the minimum. Additional fields may be appropriate; existing fields may already be in use.
4. **The proposed activity record fields are a starting point and open to revision.** This document proposes `activity_id`, `super_id`, `used_by`, `used_at`, and `source`.
5. **The proposed link record fields are a starting point and open to revision.** This document proposes `link_id`, `super_id_a`, `super_id_b`, `created_at`, `created_by`, and `source`. Conventions on what `source` should contain are suggested but not enforced at the data layer.
6. **No formal schema or enum is prescribed for `source` values.** This document proposes free-form descriptive strings (e.g. `"data_capture/ai_fetcher/iterative_validation"`) as a starting convention. A formal schema may be introduced later if needed.
7. **Naming of the three sub-workflows** (Coded Fetcher workflow, AI Fetcher workflow, Fetcher Build workflow) follows the names used in conversation. If different names are in use in code or tickets, substitute accordingly.
8. **The AI Council pattern is mentioned in the worked example as a forward-looking illustration.** Today's reality is a single AI Fetcher service that may run multiple times. The AI Council case is included to show how the model accommodates multiple parallel services within a workflow, which the design should support even though it is not yet exercised.
9. **Existing implementation state of Data Capture is assumed to be greenfield for the purposes of this document.** This document specifies the design as it should be built. If portions are already implemented, the relevant sections describe what to add or change.
10. **The auth token mechanism is referenced as a separate concern.** It is assumed to exist alongside the SuperID system and is not specified here.

---

## 1. Purpose and scope

The Data Capture feature is responsible for capturing structured data from a property URL. It coordinates three sub-workflows:

- **Coded Fetcher workflow** — coordinates domain-specific coded scrapers ("Coded Fetchers"). One or more Coded Fetchers may be invoked for a given URL. Tried first.
- **AI Fetcher workflow** — coordinates domain-agnostic AI scrapers ("AI Fetchers"). Today this is typically a single AI Fetcher that may run multiple times (a first pass to capture, a fresh second pass to validate findings and probe for missing data). The design should also accommodate future patterns where multiple AI Fetcher services run in parallel — for example, an AI Council pattern. Tried if no Coded Fetcher exists or if the Coded Fetcher workflow does not produce sufficient data.
- **Fetcher Build workflow** — uses AI to build a new Coded Fetcher when an existing one does not exist or has failed for a given domain. Triggered asynchronously. Long-running, with context accumulating across multiple turns within a single execution.

Data Capture itself sits inside a larger **Property Analysis** workflow that handles a property URL end-to-end (including downstream analysis of images, floorplans, and so on). Property Analysis is out of scope for this document but is mentioned where it explains the outer context.

This document specifies how SuperIDs are minted, used, and linked across Data Capture. The model the engineer should hold in mind: **one SuperID typically carries through an entire end-to-end flow**, being used in turn by each workflow and service. New SuperIDs are introduced only when something needs to run again, or when a context resets.

---

## 2. What the engineer should not build

Before describing what to build, this document is explicit about what not to build. Several conventional moves will look reasonable when modelling Data Capture's multi-layer, multi-service structure. They are anti-patterns in this system.

- **Do not introduce a `RunID`, `WorkflowID`, `JobID`, or any other identifier separate from `SuperID`.** Every use of an identifier of this kind, at every layer and granularity, is a SuperID.
- **Do not mint a new SuperID at every layer or service boundary.** In a normal end-to-end flow, one SuperID typically flows through Data Capture, into the sub-workflow it triggers, into the services that workflow calls. Each use is recorded as an activity entry; new SuperIDs are minted only when work repeats.
- **Do not introduce parent/child relationships between SuperIDs.** Even when new SuperIDs do appear (because something is running again), no SuperID is the "parent" of another. Relationships are recorded as links.
- **Do not introduce "outer" and "inner" SuperIDs.** No SuperID is structurally inside another.
- **Do not introduce a "thread ID," "lineage ID," "session ID," or "group ID" to tie iterative passes together.** Iterative passes are linked.
- **Do not modify or overwrite an existing SuperID record, activity record, or link record.** All records are immutable and append-only. Reruns, retries, corrections, and supersessions are all expressed as new SuperIDs (where appropriate) with new activity and link records.
- **Do not weaken the single-use check on any service** to allow a SuperID to be used twice by the same service. Each service enforces "if I have seen this SuperID before, reject" against its own local datastore.

If any of these moves seem necessary to solve a problem in Data Capture, the problem is being framed wrongly. Stop and surface the conflict rather than implementing it. See `docs/superid_principles.md` section 9 for the corrected framings.

---

## 3. What to build

The design has three components.

### 3.1 SuperID minting (mostly existing)

A SuperID is minted at two moments:

1. **When work begins and no SuperID is yet in scope.** If Data Capture is called without a SuperID — for example, if it is the first step in a Property Analysis flow — Data Capture (or the layer above it) requests a SuperID from the SuperID service.
2. **When something needs to run again.** If a service or workflow has already used the SuperID currently in scope, it cannot use that SuperID again — that's what the single-use check enforces. So if the same service or workflow needs to run a second time, a new SuperID is minted for the new run.

Once a SuperID exists, it is passed downward through workflows and into services. Each one uses it once (and records an activity entry) before passing it on.

#### Proposed SuperID record shape (draft, open to revision)

| Field | Type | Description |
|-------|------|-------------|
| `super_id` | string | The unique identifier itself. |
| `created_at` | timestamp | When the SuperID was minted. Use sub-second precision. |
| `created_by` | string | The service or workflow that requested the mint (e.g. `"data_capture"`, `"ai_fetcher_workflow"`). |
| `source` | string | A descriptive string capturing what triggered this mint (see section 5 on `source` conventions). |

The SuperID record is immutable. Nothing about it changes after the mint.

#### What defines the boundary of a single use

The boundary of a SuperID's use by a long-running service is determined by **the continuity of the executing service's context** (see `docs/superid_principles.md` section 1). This has direct implications in Data Capture:

- A Coded Fetcher invocation is a single, short-lived execution. One use, one activity entry.
- An AI Fetcher invocation is a single execution that may take longer but completes in one continuous context. One use, one activity entry.
- A **second AI Fetcher pass** (a fresh execution that validates or refines the first pass) is **a new use, requiring a new SuperID**, because the first AI Fetcher run has already consumed the original SuperID. The two passes are separate runs, linked.
- A **Fetcher Build execution** is long-running and accumulates context across many turns within a single ongoing execution. This is **one use with one SuperID**, regardless of how many turns occur or how long it takes. A new SuperID is required if Fetcher Build is restarted, times out and is resumed against a fresh execution, ends and is started again with the prior context reloaded as input, or pivots to a distinct new task (such as attempting to fix a previously built fetcher — that's a new task in a new execution, not a continuation).

The rule: continuation of the same internal context preserves the SuperID's use. A fresh execution, even one given prior content as input, is a new use and requires a new SuperID (because the previous use has already been recorded as activity for the prior SuperID).

### 3.2 The SuperID Metadata store (new — needs to be built)

A **SuperID Metadata store** is required. It does not exist yet. It holds two record types: **activity records** and **link records**. Both are append-only and immutable.

#### Proposed activity record shape (draft, open to revision)

| Field | Type | Description |
|-------|------|-------------|
| `activity_id` | string | Unique identifier for the activity record itself. |
| `super_id` | string | The SuperID this activity is about. |
| `used_by` | string | The service or workflow that used the SuperID (e.g. `"data_capture"`, `"coded_fetcher_workflow"`, `"ai_fetcher_service"`). |
| `used_at` | timestamp | When the use occurred. Use sub-second precision. |
| `source` | string | A descriptive string capturing what this use represents (see section 5). |

Every time a service or workflow uses a SuperID, it writes one activity record. The collection of activity records for a given SuperID is the complete history of where that SuperID has been used.

#### Proposed link record shape (draft, open to revision)

| Field | Type | Description |
|-------|------|-------------|
| `link_id` | string | Unique identifier for the link record itself. |
| `super_id_a` | string | One of the two SuperIDs being linked. Order is not semantically meaningful. |
| `super_id_b` | string | The other SuperID being linked. Order is not semantically meaningful. |
| `created_at` | timestamp | When the link was recorded. Use sub-second precision. |
| `created_by` | string | The service or workflow that recorded the link. |
| `source` | string | A descriptive string capturing what kind of relationship this link expresses and what triggered the link to be claimed (see section 5). |

Link records are written when two distinct SuperIDs become related — for example, when a new SuperID is minted because a service needs to run a second time, a link is recorded between the new SuperID and the prior one.

#### Properties the SuperID Metadata store must have

1. **Append-only.** Records can be inserted. They cannot be updated or deleted in the normal operational flow. Any storage technology used must enforce or honour this discipline (e.g. by application-level rules, by database constraints, or both).
2. **Bidirectional access for link queries.** Queries of the form "give me all link records where this SuperID appears" must work efficiently regardless of whether the SuperID is in the `super_id_a` or `super_id_b` position. This typically requires indexing both columns. The order of `super_id_a` and `super_id_b` within a record carries no meaning; it is purely a storage convention.
3. **Per-SuperID activity queries.** Queries of the form "give me all activity records for this SuperID" must work efficiently. This typically requires an index on `super_id`.
4. **Self-describing entries.** The `source` and other metadata fields, together with the timestamp and actor, must give a downstream reader enough context to interpret a record without needing to consult other systems.
5. **Idempotent insertion is acceptable but not required.** If the same activity or link is recorded twice by accident, the system may either reject the duplicate or store both. Both are acceptable; what is not acceptable is *modifying* an existing record. If the existing record is wrong, a new record is added with corrective metadata; the existing record stays.

#### Where the SuperID Metadata store should live (open architectural question)

Two reasonable options. Both are compatible with the principles. The choice is a real decision and should be made before implementation begins.

- **Option A — Hosted by the SuperID service.** The SuperID service already mints SuperIDs; extending it to also store and serve activity and link records keeps the ID-related infrastructure in one place. Pro: one service owns "identity, usage, and relationships." Con: the SuperID service grows in responsibility and complexity; this may bloat the service and couple unrelated concerns.
- **Option B — A dedicated SuperID Metadata service.** Activity and link records live in their own service with their own storage and API, separate from the SuperID service. Pro: each service stays focused on one concern; the SuperID service stays minimal. Con: two services to operate and reason about instead of one.

Whichever option is chosen, the **interface** is the same from a caller's perspective: an API to record an activity entry for a SuperID, an API to record a link between two SuperIDs, and APIs to query each.

### 3.3 Recording call sites (new — needs to be wired in)

#### Activity recording

**Whenever a service or workflow uses a SuperID, it writes an activity record.** This is part of the normal operational flow. In Data Capture, this means:

- When Data Capture itself is invoked with a SuperID (or mints one), Data Capture writes an activity record for that use.
- When Data Capture passes the SuperID to the Coded Fetcher workflow, the Coded Fetcher workflow writes an activity record on receipt.
- When the Coded Fetcher workflow invokes a Coded Fetcher service, the service writes an activity record on receipt (after passing its single-use check).
- And so on, for every workflow and service that uses the SuperID.

The activity record is the structural answer to "where has this SuperID been."

#### Link recording

**Whenever a new SuperID is minted in a context where it relates to an existing SuperID, a link is recorded** between the two SuperIDs. In Data Capture, this typically happens when:

- A service needs to run again (e.g. a second AI Fetcher pass to validate the first). The new SuperID is minted; a link is recorded between the new SuperID and the SuperID used by the prior pass.
- A workflow needs to run again (e.g. a second AI Fetcher workflow run). Same pattern.
- A fresh execution begins after a context reset (e.g. a Fetcher Build run that was previously timed out is restarted fresh). New SuperID, link to the prior SuperID.

Links can also be added after the fact if a relationship between two SuperIDs is discovered later. Either way, the link is immutable once written.

---

## 4. Worked example: a complete Data Capture run

This example walks through a single Data Capture run from start to finish, illustrating all four scenarios the model needs to support:

1. Granular service runs.
2. Workflows of any kind, at any layer.
3. Running the same service again (iterative or sequential passes).
4. A long-running task with context maintained across multiple turns.

It also illustrates how the model would accommodate multiple parallel services within a workflow (the AI Council pattern), even though today's reality is a single AI Fetcher.

### The scenario

Property Analysis receives a property URL and triggers Data Capture with `S-001`, the SuperID it has been working with. The Coded Fetcher workflow runs first, attempts to use an existing Coded Fetcher, and fails (the domain is one this Coded Fetcher does not cover well). Data Capture then triggers the AI Fetcher workflow, which uses a single AI Fetcher service. The AI Fetcher's result is incomplete, so a second AI Fetcher pass is started — a fresh run that takes the first pass's output as input and validates it while probing for the missing fields. Meanwhile, Data Capture asynchronously triggers the Fetcher Build workflow to construct a new Coded Fetcher for this domain. Fetcher Build runs over many hours, accumulating context across many turns within a single ongoing execution.

For comparison, the example also illustrates what would happen in a future AI Council scenario where two AI Fetchers run in parallel under the same workflow.

### The SuperIDs minted

For clarity, the SuperIDs in this example are shown as descriptive names rather than realistic identifiers.

| SuperID | When and why it was minted |
|---------|----------------------------|
| `S-001` | Minted by Property Analysis at the start of the property URL flow. Used by everything downstream until a service or workflow has already consumed it. |
| `S-002` | Minted when the AI Fetcher workflow needs to run a *second* time (the validation pass). The first AI Fetcher workflow run has already used `S-001`, so a new SuperID is required. |
| `S-003` | Minted when the AI Fetcher *service* needs to run a *second* time (within the second workflow run, to perform the validation). The first AI Fetcher service invocation already used `S-001`, so a new SuperID is required. |

Three SuperIDs for this Data Capture run — far fewer than would result from "mint a new SuperID at every layer." `S-001` does the work of carrying the original end-to-end flow through Data Capture, the Coded Fetcher workflow and its service, the AI Fetcher workflow's first invocation, the AI Fetcher service's first invocation, and the Fetcher Build workflow and its service. `S-002` and `S-003` exist purely because those layers needed to run a second time.

### The activity records

For brevity, only the SuperID, the user, and the `source` field are shown per activity record.

| SuperID | `used_by` | `source` (descriptive) |
|---------|-----------|------------------------|
| `S-001` | `property_analysis` | `"property_analysis/flow_started"` |
| `S-001` | `data_capture` | `"data_capture/started_by_property_analysis"` |
| `S-001` | `coded_fetcher_workflow` | `"coded_fetcher_workflow/started_by_data_capture"` |
| `S-001` | `coded_fetcher_service` | `"coded_fetcher_workflow/service_invocation"` |
| `S-001` | `ai_fetcher_workflow` | `"ai_fetcher_workflow/started_by_data_capture/coded_fetcher_failed"` |
| `S-001` | `ai_fetcher_service` | `"ai_fetcher_workflow/service_invocation/initial_pass"` |
| `S-001` | `fetcher_build_workflow` | `"fetcher_build_workflow/triggered_async_by_data_capture"` |
| `S-001` | `fetcher_build_service` | `"fetcher_build_workflow/long_running_build_invocation"` |
| `S-002` | `ai_fetcher_workflow` | `"ai_fetcher_workflow/iterative_validation_pass"` |
| `S-003` | `ai_fetcher_service` | `"ai_fetcher_workflow/service_invocation/validation_pass"` |

The activity records form the structural history: ten uses across three SuperIDs.

### The link records

| Link between | `source` (descriptive) |
|--------------|------------------------|
| `S-002` ↔ `S-001` | `"ai_fetcher_workflow/follows_prior_workflow_run"` |
| `S-003` ↔ `S-001` | `"ai_fetcher_service/validates_prior_service_run"` |

Two link records, both recorded at the moment the new SuperIDs were minted. Each link explains *why* the new SuperID exists in relation to the prior one.

### Things to notice about this example

- **One SuperID does most of the work.** `S-001` is used by eight different services and workflows. This is the normal pattern: a SuperID flows through the flow, recording an activity entry at each use, and is not replaced until something needs to run again.
- **New SuperIDs appear only where work repeats.** `S-002` exists because the AI Fetcher workflow needs to run a second time. `S-003` exists because the AI Fetcher service inside that second workflow run needs to run a second time. Each new SuperID is paired with a link to the prior one.
- **The Coded Fetcher's failure did not produce a new SuperID.** The failure is recorded as the output of the Coded Fetcher service's use of `S-001` (visible in the service's own data). The activity record for `S-001`'s use by the Coded Fetcher service exists; the fact that the use produced a failure is captured in the service's own output, not in a new SuperID.
- **The Fetcher Build workflow uses the same SuperID as Data Capture** (`S-001`), even though it was triggered asynchronously and may outlive Data Capture. The asynchronous trigger does not require a new SuperID; Fetcher Build is simply another consumer of `S-001`. The Fetcher Build service uses `S-001` once, for the entire long-running multi-turn execution.
- **The Fetcher Build service is one use of one SuperID** for the whole long-running execution. No matter how many turns occur or how much time elapses, this is one activity record for `S-001`. A new SuperID would only be required if Fetcher Build were restarted, timed out and resumed against a fresh execution, or pivoted to a distinct new task such as fixing a previously built fetcher.
- **Reconstructing what happened starts from any one SuperID.** Querying activity records on `S-001` returns the full backbone of the flow. Following links from `S-001` reveals `S-002` and `S-003`. Querying activity records on those reveals the validation passes. The complete narrative is reconstructable from immutable records.

### How an AI Council variant would look (forward-looking)

If the AI Fetcher workflow were enhanced to run two AI Fetchers in parallel (an AI Council) on the first pass, the model handles it without modification:

- The two services would both use `S-001` on the first pass (each performing its own single-use check, each recording an activity entry).
- On the validation pass, a new SuperID (`S-003` in the example above, or two new SuperIDs if two services participated in the validation) would be minted with a link back to `S-001`.

No new constructs are needed. The same primitives — activity records for uses, link records for "this exists because that did" — express the parallel-services case as cleanly as the sequential-services case.

---

## 5. Conventions for the `source` field (draft, open to revision)

The `source` field on SuperID records, activity records, and link records is descriptive and free-form at the data layer. This document proposes conventions for what it should contain, but does not enforce them with a schema. The conventions may evolve; the data model accommodates change.

### Proposed conventions

- **Use slash-separated descriptive paths** that read top-down, e.g. `"data_capture/ai_fetcher_workflow_started"`. These look hierarchical but are not enforced as hierarchy — they are just human-readable, prefix-queryable strings.
- **Include contextual detail when relevant.** For example, `"ai_fetcher_workflow/started_by_data_capture/coded_fetcher_failed"` carries more information than `"ai_fetcher_workflow/started_by_data_capture"` alone. The extra component is descriptive metadata, not a typed enum.
- **For activity records, describe what the SuperID is being used *for*.** Example: `"ai_fetcher_workflow/service_invocation/validation_pass"` is more useful than `"service_invocation"`.
- **For link records, describe why the link is being claimed.** Example: `"ai_fetcher_service/validates_prior_service_run"` is more useful than `"related_to_prior"`.

### Why this is deliberately loose

A formal schema or enum would prescribe a fixed vocabulary of relationship types and activity types. This is rejected for the same reason hierarchy is rejected: it creates a typed system that has to be maintained, extended, and reconciled across services. Free-form descriptive strings, with conventions documented but not enforced, give the same expressive power without the maintenance cost. If a formal schema becomes necessary later, it can be introduced over the existing data — but the data layer does not require it now.

---

## 6. What to verify

A working implementation of this design should satisfy the following. These can be enforced by code review, by automated tests, or by both.

1. **Every workflow or service that uses a SuperID writes exactly one activity record per use.** No use occurs without an activity record. No activity record exists without a corresponding use.
2. **No code path modifies or deletes an existing SuperID record, activity record, or link record.** All records are write-once.
3. **Every service (Coded Fetcher, AI Fetcher, Fetcher Build) rejects a SuperID it has previously seen in its own datastore.** The check is local, uniform, and unconditional.
4. **No code references `RunID`, `WorkflowID`, `JobID`, `parent_super_id`, `child_super_id`, `outer_super_id`, `inner_super_id`, `group_id`, `thread_id`, `lineage_id`, `session_id`, or any equivalent.** Only `super_id` appears in code.
5. **Link queries for a given SuperID return the same set regardless of whether that SuperID appears in `super_id_a` or `super_id_b` position.** Bidirectionality is preserved.
6. **A multi-turn Fetcher Build execution preserves a single SuperID and a single activity record across all turns within that execution.** A new SuperID is minted only when Fetcher Build is restarted, resumed against a fresh execution, or pivoted to a distinct new task.
7. **A second AI Fetcher pass mints a new SuperID and records a link to the SuperID used by the prior pass.** It does not reuse the prior SuperID, and it does not modify the prior records.
8. **A new SuperID is not minted at every layer or service boundary as a matter of course.** Code review should check that minting is justified by either (a) no SuperID being in scope yet, or (b) the in-scope SuperID having already been used by this caller.
9. **A SuperID's activity records and any links to it survive the lifetime of the originating workflow.** Fetcher Build's activity record for `S-001` remains queryable after Data Capture has ended.

---

## 7. What this document does not cover

- **The Property Analysis workflow** that sits above Data Capture. Mentioned briefly for context; its design is out of scope.
- **The internal data shape of Fetcher outputs.** What a Coded Fetcher or AI Fetcher actually returns is a separate concern from the SuperID system.
- **The auth token mechanism.** Assumed to exist and to pair with SuperIDs for service authorisation.
- **Storage technology choice.** This document specifies required properties (append-only, immutable, bidirectional indexing for links, per-SuperID indexing for activity) but not the database or storage system.
- **Downstream consumption** of the SuperID and metadata data (dashboards, agent-facing queries, analytics). The design supports these but does not specify them.
- **Testing strategy.** Section 6 lists verifiable properties. A separate testing document may be introduced later to specify how those properties are tested.

---

## 8. Summary

The Data Capture feature uses one ID type — the SuperID — across all its layers. A single SuperID typically carries through an entire end-to-end flow, being used in turn by Data Capture, the sub-workflow it triggers, and the services that workflow calls. Each use is recorded as an immutable activity entry. New SuperIDs appear only where work repeats — a service running again, a workflow running again, a fresh execution after a context reset — and the new SuperID is linked to the prior one by an immutable link record. Both record types live in the SuperID Metadata store, which is append-only and immutable.

The features the engineer was reaching for — a way to express that workflows orchestrate services, that iterative passes belong together, that a fallback chain has a sequence, that a long-running task is one thing rather than many — are all expressible in this model. They are expressed as **activity records describing uses**, **link records describing relationships between different SuperIDs**, and **descriptive metadata on both**. No new ID types, no hierarchies, no privileged SuperIDs, no mutation.

When implementing, the test for any design decision is: *does this preserve the properties listed in `docs/superid_principles.md`?* If yes, proceed. If no, stop and surface the conflict.

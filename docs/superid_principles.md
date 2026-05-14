# SuperID System — Principles

**Status:** Authoritative. Signed off by Rolf.
**Companion:** `docs/superid_reference_convention.md` adds the operating-vs-reference SuperID convention that sits on top of these principles without changing the data model.

---

## Draft assumptions and open questions

The following assumptions were made when drafting this document. They should be reviewed, corrected, and either confirmed or amended before this document is finalised.

1. **Exact casing of `SuperID` in the codebase is not yet confirmed.** This document uses `SuperID` as the conceptual term. The codebase may use `SuperID`, `super_id`, `superId`, or similar. The chosen form should be standardised across code and documentation.
2. **The service responsible for minting SuperIDs is referred to as the "SuperID service."** The actual name in the codebase, if different, should be substituted throughout.
3. **The terms "activity" and "link" describe two distinct record types in the SuperID Metadata store.** Activity records describe a use of a SuperID by a service or workflow. Link records describe a relationship between two distinct SuperIDs. If the codebase uses different terms, reconcile with this document or update this document to match.
4. **The SuperID Metadata store is treated as a single conceptual store holding both record types.** Whether it is physically a single store, two separate stores, or hosted within the SuperID service vs. a dedicated service is an architectural decision documented elsewhere.
5. **The term "metadata" is used as a single, unified concept** covering descriptive information attached to a SuperID at mint, to an activity record, or to a link record. No distinction is drawn between "mint-time metadata" and "after-the-fact metadata." If your implementation distinguishes them, update accordingly.
6. **The format of a SuperID (UUID, ULID, or custom) is not specified in this document.** The principles hold regardless of format. Format should be documented separately if it is not already.
7. **Auth tokens are referenced but considered out of scope.** This document assumes the existence of an auth token mechanism that pairs with SuperIDs to authorise service calls. Its design lives elsewhere.
8. **Storage and persistence choices are out of scope.** This document specifies *what* must be recorded and *what properties* the recording must have (e.g. append-only, immutable). It does not specify the storage technology.

---

## TL;DR — Invariants

These rules are absolute. They apply at every layer of the system, to every service, to every workflow, and to every line of code that touches a SuperID. If you find yourself reasoning your way toward an exception, **stop and surface the conflict** rather than implementing it.

1. **There is exactly one ID type in this system: the SuperID.** There are no RunIDs, no workflow IDs, no parent IDs, no child IDs, no group IDs. Every identifier of this kind, at every layer and granularity, is a SuperID.
2. **A SuperID can be used across multiple services and workflows, but exactly once by each.** A single SuperID flows through the system: a workflow may use it, then a service called by that workflow may use it, and so on. Each service and workflow that uses a SuperID enforces the same rule — if it has seen this SuperID before, it rejects. The same SuperID being used by *another* service is not "seeing it before"; the check is local to each service.
3. **A new SuperID is minted only when something needs to be done again.** If a service must run a second time, that second run requires a new SuperID — because the original SuperID has already been consumed by that service. Same for a workflow that needs to run again. The default expectation is that one SuperID carries through a normal end-to-end flow; new SuperIDs appear when work repeats.
4. **SuperIDs are flat and ignorant of each other.** A SuperID does not know about, reference, or contain any other SuperID. No SuperID is "above" or "below" another. No SuperID is privileged.
5. **SuperIDs are immutable.** Once minted, a SuperID and its mint-time metadata are never modified, never overwritten, never deleted. Reruns, retries, corrections, and supersessions produce new SuperIDs — never edits to existing ones.
6. **Two kinds of records describe what a SuperID does and what it relates to: activity records and link records.** Activity records describe *which services or workflows used a particular SuperID*. Link records describe *relationships between different SuperIDs*. Both live in the SuperID Metadata store, both are append-only, both are immutable.
7. **Relationships between SuperIDs are recorded as links, not encoded in the IDs themselves.** Links are bidirectional. Neither side of a link is privileged. There is no parent and no child.
8. **Hierarchy is the failure mode this system is designed against.** If you find yourself reaching for parent/child, tree, root, or container concepts, you are about to violate the model. Use links instead.
9. **The IDs do identity. Metadata does interpretation.** SuperIDs carry no semantic meaning beyond "this is a unique token." Anything that needs interpretation — what used the SuperID, what it relates to, what came before — lives in metadata (activity records and link records).

---

## 1. What a SuperID is

A SuperID is a unique identifier minted by the SuperID service. It represents a token that flows through the system as work is done. A single SuperID may be used by:

- A single granular service call (for example, one invocation of a coded scraper).
- A workflow that orchestrates other workflows or services.
- A higher-order workflow that orchestrates other workflows.
- An iterative pass in a multi-shot AI process.
- A retry or alternative attempt at a logical operation.

The same SuperID can be used at all of these levels in a single end-to-end flow — for example, minted by an outer workflow, then used by an inner workflow, then used by a granular service called by that inner workflow. Each use is recorded as an activity (see section 6). The SuperID itself is the same kind of object in every case. **There are no sub-types or specialisations.** A SuperID is a SuperID regardless of which layer minted or used it.

### When new SuperIDs are minted

A new SuperID is minted at two moments:

1. **When work begins and no SuperID is yet in scope.** Whatever first introduces a SuperID into a flow mints it. This is often an outermost workflow, but it can also be a service called directly with no prior SuperID context.
2. **When something needs to run again.** If a service has already used a SuperID, it cannot use that SuperID again — that's what the single-use check enforces. So if the same service needs to run a second time (for example, an iterative second pass), a new SuperID must be minted for that second run. The same applies to workflows that run more than once.

The default expectation in a normal flow is that **one SuperID carries through** end-to-end: it is minted once, flows downward through workflows and into services, and is used exactly once by each. **New SuperIDs are introduced specifically to cover repetition.** They are not introduced just because a new layer of work has begun.

### What defines the boundary of a single use

When a SuperID is used by a long-running service, the boundary of that use is determined by **the continuity of the executing service's context**. A continuous, long-running execution — even one spanning many turns, long elapsed time, or human-in-the-loop steps — is a single use, identified by a single SuperID. A context reset is *not* a continuation; it requires a new SuperID.

This distinction has one consequence that is easy to misread and important to get right:

- **Context continuing within a single execution is the same use.** An AI agent that accumulates context turn by turn within an ongoing conversation is executing one continuous use. It keeps the same SuperID throughout, no matter how many turns, how much time passes, or how many human inputs are interleaved.
- **Resubmitting prior context as input to a fresh execution is a new use.** Taking the transcript or accumulated context of a prior conversation and sending it as input to a freshly started service is *not* a continuation. The prior context has become input data to a new execution. The new execution requires a new SuperID. The relationship to the prior use, if relevant, is recorded as a link.

The test is whether the service's own internal context — the state it is accumulating as it runs — is the *same* context that began the use. If it is, the use continues. If the service has been started fresh and is being handed prior context as input, a new use has begun and a new SuperID is required.

Common cases where a new SuperID is needed because the prior context did not continue: process restart, timeout-and-resume, ending and re-starting with the old context reloaded as input, switching from one task to a distinct task (for example, building a coded fetcher vs. fixing a problem with one that was previously built).

### Why this matters

The temptation in most ID-system designs is to introduce different ID types for different scopes — `RunID`, `WorkflowID`, `JobID`, `StepID`, and so on. This is a category error in this system. The moment two ID types exist, three problems follow:

1. Code has to know which type it is dealing with, which means logic branches by type.
2. Relationships between types create implicit hierarchy (a `StepID` belongs to a `WorkflowID`, a `WorkflowID` belongs to a `JobID`, and so on).
3. At any depth beyond two layers, the type system either deforms or proliferates.

The SuperID model rejects all three problems by refusing to have more than one type. Every use of a SuperID, regardless of scope or layer, is a use of the same kind of object. Differences in scope, layer, and history are captured by activity records and links, not by the type of identifier.

---

## 2. Flatness and ignorance

A SuperID does not contain, reference, or know about any other SuperID. There is no field on a SuperID record that says "this is the parent of," "this belongs to," or "this is part of." The ID itself is a flat, opaque identifier with associated metadata describing only **itself**.

This means:

- No SuperID is structurally privileged. There is no "root" SuperID, no "anchor" SuperID, no SuperID whose existence is required for other SuperIDs to make sense.
- A SuperID can be understood entirely on its own. To know what a SuperID represents, you read its metadata. To know what it relates to, you query the links store.
- The system supports arbitrary depth (one layer, ten layers, a hundred layers) without any change to the model, because depth is not represented in the IDs.

### Why this matters

The moment any SuperID is privileged — for instance, by being the "name" of a group or the "anchor" of a sequence — a second category of SuperID exists in practice, even if not in name. This re-introduces the type-system problem from a different angle. Flatness is the property that keeps the model uniform across all scales and depths.

---

## 3. Immutability

Every SuperID, once minted, is permanent. Its metadata as recorded at mint time is permanent. Nothing about a SuperID record is ever modified, overwritten, or deleted in the course of normal operation.

The same applies to both record types in the SuperID Metadata store. Activity records, once written, are never modified or deleted. Link records, once written, are never modified or deleted. If a record is later believed to be wrong, the correction is a new record annotating the situation — not an edit to the original.

### Reruns, failures, and corrections

- **A rerun is a new SuperID.** When a service or workflow needs to run again — for example, an iterative second pass that validates a first pass — a new SuperID is minted for the new run. The prior SuperID and the activity and outputs associated with it remain exactly as they were.
- **A failure is a new SuperID when retried.** Failure is not the absence of a run; it is a use of a SuperID that produced a different kind of outcome. The original use, including any data it produced, is preserved. If the failed operation needs to be retried, the retry takes a new SuperID. There is no concept of "deleting a failed run."
- **A correction is a new SuperID.** If a process produced incorrect output, the correct version is produced by a new use under a new SuperID. The incorrect version is not edited or removed; it is superseded, and the supersession is captured as a link.

### Why this matters

Two reasons.

First, in non-deterministic systems (especially those involving LLMs), the correctness of an output is not knowable at the moment of creation. It must be assumed simultaneously correct and incorrect until validated. Deleting or overwriting prior outputs destroys the ability to compare, audit, and reconstruct. Immutability is the property that preserves the evidence needed to reason about what actually happened.

Second, immutability collapses several normally-separate concerns — versioning, audit logging, history — into the SuperID system itself. There is no separate version field, no audit table, no history log. The SuperIDs *are* the history.

### Extreme exceptions

In rare cases — regulatory compliance requiring data erasure, response to a security incident — administrative intervention outside the normal operational flow may modify or remove records. These are not exceptions to the model; they are operations explicitly outside it, handled by separate processes with separate authority. **No code in the normal operational path should ever modify or delete a SuperID, an activity record, or a link record.**

---

## 4. Single-use within scope

When a service receives a SuperID, it checks its own datastore. If the SuperID is already present in that datastore, the service rejects the call: the caller must obtain a new SuperID.

This check is:

- **Local.** Each service checks only its own datastore. There is no shared registry, no cross-service lookup, no central authority on the hot path.
- **Simple.** The check is "does this SuperID exist here? If yes, reject." There are no exceptions, no carve-outs, no "valid in this context but not that one."
- **Uniform.** Every service implements the same check. There are no services that skip it, and no services that implement variations of it.

### What this means in practice

Because each service's check is local to its own datastore, the same SuperID can — and frequently does — appear in *different* services' datastores within a normal flow. That is not a violation of single-use. Single-use means each individual service uses each SuperID at most once. It does not mean each SuperID is used by only one service overall.

A typical flow:

1. The SuperID `S-001` is minted.
2. Workflow A receives `S-001`, checks its own datastore, finds nothing, records the use, and proceeds.
3. Workflow A passes `S-001` to Service B. Service B checks its own datastore, finds nothing, records the use, and proceeds.
4. Service B returns. Workflow A passes `S-001` to Service C. Service C checks its own datastore, finds nothing, records the use, and proceeds.
5. If, at any point, Service B were called again with `S-001`, Service B would reject — *its own* datastore already shows `S-001`. A new SuperID would need to be minted for the second use of Service B.

### What this protects against

- Replay against any individual service: a SuperID cannot be used twice against the same service.
- Accidental double-execution: if a workflow accidentally invokes the same service twice with the same SuperID, the second call fails fast.
- Quiet drift: because the rule is uniform across services, no service is silently weaker than another.

### Important clarifications

- **Each service has its own datastore.** A SuperID present in Service A's datastore is irrelevant to Service B. They are walled off. The "single-use" rule is scoped to each service's local data.
- **Services have their own internal row IDs.** Each service's tables use whatever row identification scheme is appropriate for that service (typically auto-incrementing or UUID primary keys). These are unrelated to the SuperID system and do not interact with it. The SuperID is a column on those rows, not a replacement for the row's own primary key.
- **The check does not consult any other system.** It does not look at the SuperID Metadata store, a workflow registry, or anywhere else. Just the local datastore.

### Why this matters

The simplicity of the check is doing real work. The moment the rule becomes "this SuperID exists, but it's allowed because X," the door opens to inconsistency between services, subtle authorisation bugs, and a steady accumulation of special cases. A dumb, uniform check is harder to break and easier to audit than a smart one. Combined with the fact that SuperIDs naturally flow across services, this check is also what enables a single SuperID to do the work of tying many services and workflows together without any of them having to coordinate.

---

## 5. The SuperID Metadata store: activity and links

Two kinds of records describe what SuperIDs do and how they relate. Both live in the **SuperID Metadata store**. Both are append-only and immutable.

- **Activity records** describe *which services or workflows used a particular SuperID, and when, and why*. Each activity record is attached to a single SuperID. The collection of activity records for a SuperID tells you everywhere that SuperID has been.
- **Link records** describe *relationships between two distinct SuperIDs*. Each link record connects two SuperIDs and explains why the link is being claimed.

These are different shapes serving different jobs. Activity records track a single SuperID's journey. Link records connect different SuperIDs to each other. Both are needed; conflating them would lose information.

### Activity records

When a service or workflow uses a SuperID, it records an activity entry. The activity entry captures who used the SuperID, when, and in what context.

- **Per-SuperID.** Activity records are about one SuperID at a time.
- **Append-only.** Once written, an activity record is never modified or deleted.
- **Self-describing.** The metadata on the record (the service or workflow name, timestamp, descriptive source string) gives a downstream reader enough context to understand the use.
- **Comprehensive.** Every use of a SuperID by a service or workflow generates an activity record. A SuperID's full set of activity records is its complete usage history.

Activity records are the structural answer to "where has this SuperID been, and what did it do." Combined with the immutable outputs of the services themselves, they let any consumer reconstruct what happened with full fidelity.

### Link records

When two SuperIDs are related — for example, one is a second pass following another, or one was minted because the other failed — that relationship is recorded as a link.

- **Bidirectional.** When a link between SuperID A and SuperID B is recorded, the relationship appears on both A's record and B's record. Neither side "owns" the link. Neither side is privileged. Walking the graph works equally well from either direction.
- **Append-only.** Links can be added at any time, including long after the SuperIDs they connect were minted. Links cannot be modified or deleted. If a link is later believed to be incorrect, the correction is a new link with metadata explaining the situation.
- **Self-describing.** Every link carries its own metadata: when it was created, what created it, why the link is being claimed. The metadata explains the *act of linking*, not just the existence of the relationship.
- **Free of type hierarchy.** Links do not have a fixed schema of "relationship types" with privileged categories. Descriptive metadata on the link (for example, source or trigger information) is used to convey the *nature* of the relationship at read time. No consumer is required to understand any specific descriptive value to use the link.

### When records are written

- **Activity records** are written when a service or workflow uses a SuperID. This is part of the normal operational flow.
- **Link records** are typically written at the moment a new SuperID is minted in a context where it relates to an existing SuperID — for example, when minting a SuperID for a second pass that follows a first pass. Links may also be added after the fact: a downstream process discovering that two SuperIDs are related can record a link describing that relationship at any time.

In both cases, the record is itself an immutable, append-only entry with metadata describing when and why it was created.

### Why links are not hierarchy in disguise

A link is not a "parent" or a "child" reference. It is an undirected statement that two SuperIDs are related, accompanied by metadata describing the relationship. The system has no concept of one SuperID being structurally above another. Sequence, causation, and supersession — when they apply — are expressed in the link's metadata, not in the link's direction or in the structure of the SuperIDs themselves.

---

## 6. Metadata: the only place interpretation lives

SuperIDs carry no semantic meaning beyond "this is a unique token." Anything that has meaning — what services used the SuperID, what triggered each use, what other SuperIDs it relates to, what it superseded, what its purpose was — lives in metadata.

This applies to all three places metadata is recorded:

- The metadata captured at the moment a SuperID is minted.
- The metadata recorded on each activity entry, when a service or workflow uses the SuperID.
- The metadata recorded on each link entry, when a relationship between two SuperIDs is claimed.

### What metadata typically captures

- **Timestamp.** When the SuperID was minted, when the activity occurred, or when the link was claimed.
- **Source / trigger.** What caused this SuperID to be minted, this activity to occur, or this link to be claimed. (For example: a workflow step name, a user action, an upstream service, a refinement of a prior pass.)
- **Actor.** The service or workflow that performed the mint, the activity, or the link recording.
- **Context.** Any contextually relevant information available at the moment of recording.

### Why this matters

The SuperIDs themselves stay simple, flat, and uniform because all the variation and interpretation is pushed into metadata. This means:

- The ID system has very few rules.
- Anything that needs to vary (the kind of activity, the nature of a relationship, the reason for a supersession) varies in metadata.
- Read-time interpretation is where complexity lives. The IDs do not pre-compute or pre-categorise; consumers interpret metadata when they need answers.

---

## 7. Vocabulary

The following terms are used consistently throughout the SuperID system and its documentation. Use these terms. Do not introduce synonyms.

| Term | Meaning |
|------|---------|
| **SuperID** | The single, universal identifier minted by the SuperID service. A SuperID can be used across multiple services and workflows, exactly once by each. |
| **SuperID service** | The service responsible for minting SuperIDs. |
| **Mint / minting** | The act of creating a new SuperID. |
| **Use / using a SuperID** | The act of a service or workflow consuming a SuperID for the work it does. A SuperID may be used by many services or workflows in total, but only once by each. |
| **Activity / activity record** | An immutable entry in the SuperID Metadata store recording that a specific service or workflow used a specific SuperID, with descriptive metadata. |
| **Link / link record** | A bidirectional, immutable, append-only record in the SuperID Metadata store connecting two SuperIDs with descriptive metadata about the relationship. |
| **SuperID Metadata store** | The append-only, immutable store holding activity records and link records. The choice of where this store lives (within the SuperID service or as a dedicated service) is an architectural decision documented elsewhere. |
| **Metadata** | Descriptive information attached to a SuperID at mint time, to an activity record, or to a link record. |

### Terms deliberately not used

The following terms describe concepts that do not exist in this system. If you find yourself reaching for one of them, you are likely about to violate a principle. Stop and surface the conflict.

- **RunID, WorkflowID, JobID, StepID, TaskID** — there is no specialised ID type. Every use of a SuperID, at any layer and granularity, is identified by a SuperID.
- **Parent ID, child ID, parent SuperID, child SuperID** — no SuperID is structurally above or below another.
- **Group ID, group SuperID, root SuperID, anchor SuperID** — no SuperID is privileged. Groupings are expressed as links.
- **Outer SuperID, inner SuperID** — these terms imply containment and hierarchy. No SuperID is "outside" or "inside" another. Relationships between SuperIDs are expressed as links, regardless of how the runs they identify relate operationally.
- **Lineage ID, thread ID, pursuit ID** — sequences of related runs are expressed as links between SuperIDs, not by a separate identifier for the sequence.
- **Version field, version ID** — versioning is achieved by the immutability of SuperIDs and the supersession relationship expressed as a link. There is no separate version concept.
- **Update, modify, overwrite, delete (applied to a SuperID or a link)** — these operations do not exist in the normal flow.

---

## 8. Decision heuristics

When in doubt, ask the following questions. A "yes" to any of them means stop and reconsider.

1. **Am I introducing a new kind of ID?** → Stop. There is only the SuperID.
2. **Am I making one SuperID structurally aware of another?** → Stop. SuperIDs are flat and ignorant of each other. Use a link.
3. **Am I making one SuperID privileged over others** (a root, an anchor, the "name" of a group)? → Stop. No SuperID is privileged.
4. **Am I encoding a relationship inside a SuperID record itself** (a "parent" field, a "belongs_to" field)? → Stop. Relationships are links.
5. **Am I about to modify or delete a SuperID, an activity record, or a link?** → Stop. These records are immutable. Add a new record instead.
6. **Am I about to introduce hierarchy** (tree, parent/child, container, group)? → Stop. The system has no hierarchy. Use links.
7. **Am I writing logic that branches on "what kind of SuperID is this"?** → Stop. There is only one kind. If the behaviour varies, it varies based on metadata, not on the SuperID itself.
8. **Am I about to add a "version" field or a "supersedes" field directly on a SuperID record?** → Stop. Supersession is a link.
9. **Am I implementing a special case in the single-use check** ("this SuperID exists, but it's allowed because…")? → Stop. The check is uniform across services and admits no exceptions.
10. **Am I about to mint a new SuperID when one is already in scope and hasn't been used by this service or workflow?** → Stop. Use the existing SuperID. Mint a new one only when the current SuperID has already been used by this caller, or when there is no SuperID yet.

---

## 9. Common mistakes and what to do instead

The patterns below are the conventional moves an engineer or AI agent will reach for. They are anti-patterns in this system. Each is paired with the correct approach.

### Mistake: introducing a `RunID` separate from a `SuperID`

A workflow needs to identify "this overall execution," and the engineer introduces a `RunID` for the workflow while individual services use SuperIDs.

**What to do instead:** the workflow uses a SuperID. The services within it use the same SuperID, or — only if a service needs to run more than once — additional SuperIDs minted for the repeated uses. There is no `RunID`. There is only the SuperID. The same SuperID flowing through a workflow and the services it calls is the normal, expected pattern.

### Mistake: making the workflow's SuperID the "parent" of the services' SuperIDs

The engineer assumes each layer needs its own SuperID and treats the workflow's SuperID as a container for the services' SuperIDs, storing `parent_super_id = <workflow's SuperID>` on each service's record.

**What to do instead:** in most cases, the workflow and the services it calls use the *same* SuperID. There is no parent and no child because there is only one SuperID. Each use is recorded as an activity entry. Where new SuperIDs do appear — because a service or workflow runs more than once — the relationship between the old and new SuperID is recorded as a link, not as a parent/child reference. Neither SuperID is the "parent" of the other.

### Mistake: introducing hierarchy to represent multi-shot iterations

The engineer notices that a multi-shot process produces several SuperIDs (one per iterative pass) and introduces a "thread ID" or "lineage ID" that all the iterations share.

**What to do instead:** each iterative pass is its own SuperID (because each pass is a separate run of the service). Links connect them. The fact that they belong to the same logical pursuit is captured in the metadata of those links. No separate identifier for the thread is needed.

### Mistake: treating retries or fallbacks as modifications of the prior run

The engineer wants the system to "know" that the LLM fetcher's output replaces the failed scraper's output, and updates a field on the scraper's record to mark it as superseded.

**What to do instead:** the scraper's record is left untouched. The LLM fetcher produces its own output under its own SuperID. A link is recorded between the two SuperIDs, with metadata indicating that one supersedes the other. Both records remain, immutably.

### Mistake: minting a new SuperID at every layer or service boundary

The engineer assumes each workflow and each service should mint its own SuperID, producing many SuperIDs in a normal end-to-end flow even when nothing is repeating. This often goes hand in hand with attempting to express containment between them.

**What to do instead:** the default is that one SuperID is minted at the start of a flow and used by every workflow and service that touches the work, each recording an activity entry. New SuperIDs are introduced only when something needs to run *again* — a service repeating, a workflow repeating, a fresh execution after a context reset. If you are about to mint a SuperID, ask: is there already a SuperID in scope that hasn't been used by this service or workflow yet? If yes, use it. Mint a new one only when the current SuperID has already been used by this caller.

### Mistake: encoding ordering or sequence in a field on the SuperID

The engineer adds a `sequence_number` or `attempt_number` field to the SuperID record itself.

**What to do instead:** if ordering matters, it is captured in the metadata on links. The SuperID itself remains free of sequencing information.

### Mistake: minting a new SuperID for every turn of a long-running, multi-turn interaction

A single service — for example, an AI agent in conversation with a human, or any long-running task with human-in-the-loop steps — produces multiple turns over time. The engineer treats each turn as a separate use and mints a new SuperID per turn.

**What to do instead:** the entire continuous interaction is **one use of one SuperID**. The defining property is the continuity of the service's own context, not the number of turns, the elapsed time, or the presence of human input within it. A multi-turn conversation that builds on its own accumulating context is a single long-running execution of the service. It uses one SuperID, from the moment the service begins until the moment its context ends.

A new SuperID is required only when the service's context is no longer continuous. Common cases:

- The process is restarted.
- The process times out and is resumed against a fresh execution (even if prior context is reloaded as input).
- The process is ended and a new one is started against the prior context.
- A distinct new task is started — for example, attempting to *fix* a previously-built coded fetcher is a new task in a new execution, not a continuation of the original build conversation. New SuperID.

This is a "what counts as a continuous use" question, and the answer is determined by continuity of context, not by external pacing. Long elapsed times, paused-and-resumed sessions (where the execution itself continues), and human turns interleaved with AI turns are all part of the same use as long as the executing service's internal context is continuous. Anything that resets or restarts the executing context begins a new use and requires a new SuperID.

**One subtlety to watch for:** resubmitting prior context as input to a freshly started service is *not* a continuation. If a service is started fresh and the prior conversation's transcript is passed in as input data, this is a new use with a new SuperID — even though the new use "has access to" the same content as the prior one. The test is whether the service's internal, accumulating context is the *same* context that began the use, or a *fresh* context that happens to contain prior material as input. Continuation preserves the SuperID. Resubmission creates a new one. The relationship between the two uses, if relevant, is recorded as a link.

---

## 10. Out of scope

This document does not cover:

- **The auth token mechanism.** SuperIDs are used in combination with auth tokens to authorise service calls. The design of the auth token system is documented separately.
- **The format of SuperIDs** (UUID, ULID, or otherwise). This document specifies properties, not encoding.
- **Storage technology.** This document specifies that the SuperID Metadata store must be append-only and immutable, but does not prescribe the database or storage system.
- **Where the SuperID Metadata store lives.** Whether it is hosted by the SuperID service or as a dedicated service is an architectural decision documented elsewhere.
- **Individual services' internal row IDs.** Services use their own primary keys for their internal tables, separate from SuperIDs. This is normal and unrelated to the SuperID system.
- **Read-time interpretation tools.** Building dashboards, analytics, agent-facing query interfaces, and similar tools is downstream work. This document defines what is recorded; it does not define how it is consumed.

---

## 11. Summary

The SuperID system is deliberately small. It has one kind of identifier, two kinds of records describing what SuperIDs do (activity records) and how they relate (link records), one storage discipline (immutable and append-only), and one place where interpretation lives (metadata). It refuses hierarchy, refuses specialisation, and refuses mutation.

A SuperID is minted at the start of a flow and flows through the work — used by workflows and services in turn, each enforcing the same local single-use check. New SuperIDs appear only when work repeats: a service running again, a workflow running again, a context resetting. Relationships between SuperIDs are recorded as links; uses of each SuperID are recorded as activity entries; both live in the SuperID Metadata store.

The simplicity is the point. Every property of the system compounds with the others: flatness makes uniformity possible; uniformity makes the single-use check trivial; immutability makes history reconstructable; activity and link records make arbitrary structure expressible without deforming the model. Adding complexity to any one of these — a privileged ID, a hierarchy, a mutable field, a typed relationship — would weaken all of them.

When working in this system, the goal is to preserve these properties. When in doubt, choose the option that adds the least.

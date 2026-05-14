# SuperID — The reference SuperID convention

**Status:** Authoritative. Signed off by Rolf. Companion to `docs/superid_principles.md`.

> **A note on phrasing.** Throughout this document, "reference" is used as an adjective describing a role a SuperID plays in a particular scope, never as part of a name. There is no such thing as a "Reference SuperID" as a type or a named entity. There are only SuperIDs, and at any moment one of them is acting as the reference for the current scope of work. The lower-case "reference" is deliberate and important — it signals that this is a role, not a type.

---

## What this convention is, and what it is not

The reference SuperID is a **convention**, not a new type of identifier and not a new field in the data model. Every SuperID is still flat, immutable, and equal in storage. The metadata store is unchanged. No SuperID is privileged at the data layer.

What the convention adds is **operational orientation**: at any moment, the code doing work has *one* SuperID it carries as its default reference. That reference is what the work is "about" from the perspective of the current scope of operation. Other related SuperIDs (from reruns, refinements, fallbacks, neighbouring work) still exist in the metadata store and remain discoverable from the reference, but the work proceeds with the reference as its orientation point and only consults the metadata store when it specifically needs to know about related SuperIDs.

This convention exists to solve a specific operational problem: without it, every node in every workflow would need to consider, at every step, whether other related SuperIDs exist that it should be aware of. That review burden is impractical and would erode in practice — developers would forget to do it, do it inconsistently, or write code that quietly missed related data. With the convention, the default behaviour at every node is simple and predictable: *use the reference SuperID you were given as your orientation point; consult related SuperIDs only when the work genuinely requires it.*

---

## The rule

**Every workflow or process carries a SuperID that serves as the reference for its current scope of work. The reference SuperID is the single SuperID that code in the scope orients to by default. It is chosen at the start of each meaningful scope and remains stable throughout that scope. When work transitions to a new meaningful scope, the new scope chooses its own reference SuperID, and the relationship between the prior and new reference is recorded as a link in the metadata store.**

A reference SuperID is a role that a SuperID plays in a particular operational scope. It is not a property of the SuperID itself. The same SuperID may be the reference in one scope and a peripheral participant in another. No SuperID is permanently labelled as a reference; the role is contextual and assigned per scope.

---

## Two SuperIDs in scope, not one

This is the most important clarification for developers working with the convention. **At any node, there are typically two SuperIDs in scope simultaneously, and they serve different purposes:**

1. **The operating SuperID** — the SuperID the node is currently *doing work under*. This is the SuperID passed to the node as input, the one the node performs its single-use check against, and the one its activity record is written under. The operating SuperID is what the node *operates on*.

2. **The reference SuperID** — the SuperID that orients the scope. This is what the node uses if it needs to walk to related SuperIDs, find prior runs, or understand what the current scope of work is "about." The reference SuperID is what the node *orients to*.

**In most simple cases, these are the same SuperID.** A service being invoked for the first time within a scope is operating under the same SuperID that serves as the scope's reference. The distinction does not matter and the node simply has one SuperID in scope.

**In rerun cases, they are different.** When a service needs to be run a second time within a scope, a new SuperID is minted for the second run (because the original has been consumed by that service's prior invocation). The service is now operating under the new SuperID — it writes its activity record under the new SuperID, its single-use check passes against the new SuperID. But the *reference SuperID for the scope has not changed*: the scope is still oriented to whichever SuperID was chosen as its reference at scope entry. The new SuperID is recorded in the metadata store with a link back to the reference SuperID, and code downstream of the rerun continues to carry the same reference SuperID for the scope.

This split — operating SuperID for execution, reference SuperID for orientation — is what makes the convention work. Without it, the rerun case would force the reference to change every time something repeats, which would defeat the purpose of having a stable orientation point.

---

## How to choose the reference SuperID for a scope

The reference SuperID for a scope is **whichever SuperID is most useful to orient to for the work that scope does**. This is a deliberate choice made at the moment a scope begins, based on what the work in that scope is actually about.

At the current stage of the SuperSami platform, the most likely reference SuperID at any given scope is **the SuperID that starts the property analysis** (or the SuperID that starts any smaller workflow if it has been accessed directly). In practice, this most often means the SuperID generated from a client-side action — for example, a user submitting a property URL or a user-triggered action on an existing analysis. As the platform evolves, the most useful reference SuperID may differ at different scopes, but the current default expectation is the client-initiated SuperID.

---

## When the reference SuperID changes

The reference SuperID changes **at scope transitions, not arbitrarily**. A scope transition is a point at which the work meaningfully moves from one unit of activity to another — for example, from batch processing across many items to per-item processing for a single item.

Inside a scope, the reference SuperID is stable. Code in that scope does not change which SuperID is acting as the reference. The reference is picked at scope entry and held throughout. Reruns within the scope do *not* change the reference — they introduce new operating SuperIDs (see above), but the scope's reference remains stable.

When a scope transitions, the new scope chooses its own reference SuperID based on what is most useful for the new scope's work. The prior reference is not lost — it still exists in the metadata store, still has all its links and activity records, and is still reachable by walking links from the new reference. It simply stops being the default operational orientation point because the work has moved into a different scope where a different SuperID is more useful.

### Example

Super Sami processes a batch of ten property emails. The batch run is a scope; the SuperID that started the batch serves as the reference for that scope. While the batch is being processed, every node in the batch scope carries that batch SuperID as its reference. Most nodes also operate under that SuperID for the first invocation of each service; reruns within the batch scope would operate under newly minted SuperIDs while still carrying the batch SuperID as their reference.

The batch then hands off to per-property processing for five of the ten properties (filtered by some criterion). Per-property processing is a different scope. For each property, the reference SuperID becomes the SuperID associated with that property's analysis, not the batch SuperID — because at the per-property scope, the property's SuperID is what the work is about. The link between the batch SuperID and each property SuperID is recorded in the metadata store at the moment each per-property scope begins.

If any node in per-property processing needs to know which batch the property came from, it walks links from the property's reference SuperID and finds the batch SuperID. The information is available. It just isn't the default orientation point any more, because at the per-property scope it doesn't need to be.

---

## What the convention does and does not allow

It **allows**:
- Every node in every workflow to know unambiguously what SuperID it should orient to, without needing to discover that at runtime.
- Working by exception: nodes consult the metadata store for related SuperIDs only when their work specifically requires it.
- Each scope to pick its own most-useful reference, so that orientation matches the work being done at each layer.
- A node to operate under one SuperID while orienting to a different one (the rerun case), without conflict, because the two roles are kept distinct.
- The metadata store and data model to remain exactly as designed: flat, immutable, append-only, with no privileged SuperIDs in storage.

It **does not allow**:
- The reference SuperID to change mid-scope. Inside a scope, the reference is stable. Reruns within a scope introduce new operating SuperIDs but do not change the scope's reference.
- The reference SuperID to become a permanent property of any SuperID. The role is contextual and per-scope; the same SuperID can be the reference in one scope and a peripheral participant in another.
- The reference SuperID to be treated as privileged in the data model. In storage, it is just a SuperID. The convention exists only at the operational layer.
- Scopes to inherit a reference uncritically. Each scope picks its reference deliberately at scope entry, based on what is most useful for the work in that scope.
- The operating SuperID and the reference SuperID to be conflated in code. A node's activity record is written under its operating SuperID, not its reference SuperID. Confusing the two would break the activity record's meaning.

---

## Implications for development

For most code, the convention is invisible. A node receives an operating SuperID and a reference SuperID (which in simple cases are the same SuperID), does its work under the operating SuperID, writes its activity record under the operating SuperID, and uses the reference SuperID only if it needs to discover related work. Most nodes never need the reference for anything; they just do their work under the operating SuperID and pass both onward.

The places where the convention requires conscious design are:

- **Scope entry points.** The code that starts a new scope chooses the reference SuperID for that scope. This is a deliberate choice. Where there is more than one plausible candidate, the choice should be based on what is most useful for the work the scope will do. At the current stage of the platform, the default expectation is "the SuperID that initiated this scope, typically a client-initiated SuperID."
- **Scope transitions.** When work hands off from one scope to another (for example, from batch processing to per-property analysis), the handing-off code records the link in the metadata store and the receiving scope picks its own reference. This is a small amount of orchestration work, concentrated at transitions rather than distributed across every node.
- **Rerun handling within a scope.** When a service within a scope needs to be run a second time, a new SuperID is minted for the second run (the original has been consumed by that service's prior invocation). The orchestration code passes the new SuperID as the operating SuperID for the rerun, while keeping the scope's reference SuperID unchanged. The link between the new SuperID and the reference SuperID is recorded in the metadata store. Code downstream of the rerun continues to receive the reference SuperID for the scope as its orientation point.

The convention is intended to make the default case (a node doing work under one well-defined SuperID with a clear orientation point) easy and the exceptional case (needing to walk to related SuperIDs, or running a service for a second time) explicit and deliberate. The discipline lives at scope entry points, scope transitions, and rerun handling — concentrated locations where it can be applied carefully — rather than at every node, where it cannot.

---

## Why this is a convention and not a type

The reference SuperID could have been introduced as a new ID type (a "primary" SuperID, or an "ISID," or similar). That approach was considered and rejected. The reason: introducing a second type would have made the data model carry two kinds of SuperIDs with different roles, which conflicts with the flatness principle that the system has been deliberately designed around. The properties of flatness, immutability, and uniformity at the data layer compound to give the system its coherence; introducing a privileged ID type would erode all of them.

The convention achieves the same operational benefit (every node has one obvious SuperID to orient to) without that cost. The data model stays flat. The metadata store stays exactly as designed. The convention lives at the orchestration layer, where it belongs, and is invisible to the data model.

The convention does require some discipline at scope entry points, scope transitions, and rerun handling. That discipline is small, concentrated, and can be enforced through standard orchestration code rather than distributed across every node. This is a much smaller discipline burden than would be required without the convention, where every node would need to consider related SuperIDs at every step.

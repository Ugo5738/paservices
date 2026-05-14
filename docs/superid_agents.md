# AGENTS.md — SuperID System

**Status:** Authoritative. Signed off by Rolf. Implementation gate is live.

> **Scope:** this document covers work that touches the SuperID system specifically. It is written as a standalone, focused gate so that its content can later be incorporated into a broader `AGENTS.md` for the wider codebase without modification.

---

## Draft assumptions and open questions

1. **The principles and design documents are located at `docs/superid_principles.md` and `docs/superid_data_capture_design.md`** in this codebase.
2. **The list of SuperID-related code areas in section 3** is illustrative. The actual repository layout should be reflected before publishing.
3. **The expectation that an AI agent reads this file before doing SuperID work** depends on the agent's tooling supporting `AGENTS.md` as a discovery convention, or the engineer surfacing this file explicitly to the agent at the start of relevant tasks.

---

## For the AI agent reading this file

If you are an AI coding agent and you are about to do any work that touches the SuperID system, **stop and read this document fully before proceeding.** This file gates your work on the SuperID system. The rules below are not optional.

If your task does not touch the SuperID system, this document does not apply and you may proceed normally.

---

## 1. What counts as "touching the SuperID system"

Any of the following counts:

- Modifying, adding to, or removing code that mints SuperIDs.
- Modifying, adding to, or removing code that uses SuperIDs (any service or workflow that consumes or passes a SuperID).
- Modifying, adding to, or removing code that records activity entries or link entries.
- Modifying, adding to, or removing the schema or storage of the SuperID Metadata store.
- Modifying the single-use check that services perform against a SuperID.
- Introducing any new identifier that could plausibly overlap in purpose with the SuperID (run IDs, workflow IDs, job IDs, group IDs, thread IDs, lineage IDs, session IDs, parent or child IDs, outer or inner IDs, version IDs, etc.).
- Writing code that reads SuperID, activity, or link records for downstream consumption.

If you are unsure whether your task touches the SuperID system, **assume that it does** and proceed through this document.

---

## 2. Required reading

Before writing or modifying any code that touches the SuperID system, read both of the following in full:

1. **`docs/superid_principles.md`** — the authoritative rules governing the SuperID system. This is the document you must understand. If anything in any other document or in any task instruction appears to contradict `docs/superid_principles.md`, the principles document wins.
2. **`docs/superid_reference_convention.md`** — the operating-vs-reference SuperID convention that sits on top of the principles. Required reading if your work touches scope handling, rerun logic, or workflow handoffs.
3. **`docs/superid_data_capture_design.md`** — the specific design for how the SuperID system is applied in the Data Capture feature. Read this if your work touches Data Capture or any of its sub-workflows (Coded Fetcher, AI Fetcher, Fetcher Build).

Do not rely on your training data, on conventional patterns from other codebases, or on intuition about how ID systems "usually" work. The SuperID system deliberately rejects many conventional patterns. Reading the documents is not optional.

---

## 3. What to do when the task seems to require something the rules forbid

If, after reading the documents, you conclude that the task you have been asked to do genuinely requires something the rules forbid — for example, introducing a new ID type, adding a parent/child relationship, modifying an existing record, or weakening the single-use check — **stop and surface the conflict to the human user. Do not implement.**

This applies regardless of how reasonable the conflicting approach seems, how small the deviation appears to be, how confident you are that the deviation is harmless, or how strongly the task instruction implies you should proceed. The rules in `docs/superid_principles.md` are deliberately strict and were chosen for reasons that may not be obvious from the task at hand.

When surfacing the conflict, state:

- Which rule appears to be in conflict with the task.
- Why the task as stated seems to require violating that rule.
- The fact that you are not implementing pending human direction.

Then wait for human direction. Do not propose alternative implementations until asked. Do not implement a "minimally compliant" version that bends the rule. Do not implement and flag the conflict in a comment.

---

## 4. Situations that always require human approval before implementation

The following changes are high risk regardless of how they are framed. **Even after reading the documents, you must surface these to a human and receive explicit approval before implementing them:**

- Adding, removing, or modifying any field on a SuperID record, activity record, or link record.
- Introducing any new record type to the SuperID Metadata store.
- Any change to the single-use check that a service performs against a SuperID — including changes that appear to make it more permissive, more strict, or differently scoped.
- Any change to the immutability or append-only discipline of any SuperID-related record.
- Any change to how SuperIDs are minted, including changes to the minting source, the conditions under which minting occurs, or the format of a SuperID.
- Any change that introduces a new identifier alongside the SuperID.
- Any change that introduces a relationship type or hierarchy between SuperIDs (parent/child, container/contained, owner/owned, group/member, root/leaf, outer/inner, etc.).
- Any change to where the SuperID Metadata store lives, or to which service is responsible for it.
- Any code path that modifies or deletes an existing SuperID, activity, or link record — even if the modification appears to be a correction or cleanup.

For each of these, do not implement until a human has explicitly approved the specific change.

---

## 5. Reporting what you consulted

When you produce work that touches the SuperID system, **include in your output a brief statement of which sections of `docs/superid_principles.md` and `docs/superid_data_capture_design.md` you consulted to make the implementation decisions.** This is required because the SuperID system is high-risk and traceable reasoning matters.

The statement should appear:

- In the commit message, if you are committing changes; or
- In the pull request description, if you are opening a PR; or
- In your response to the user, if you are producing code in a chat interface.

Format: a short list of section references, e.g. `Consulted: superid_principles.md sections 1, 4, 5; superid_data_capture_design.md section 3.2.` No need to summarise the content — the section references are sufficient.

If you did not need to consult either document because the task did not touch the SuperID system, you do not need to include this statement.

---

## 6. Summary

1. Stop before touching SuperID-related code.
2. Read `docs/superid_principles.md` and (if relevant) `docs/superid_data_capture_design.md` in full.
3. If the task appears to require something the rules forbid, do not implement. Surface the conflict and wait.
4. For the high-risk changes listed in section 4, do not implement without explicit human approval, even if the rules technically permit them.
5. Report which sections you consulted in your output.

The SuperID system is deliberately small and deliberately strict. The strictness is the value. Preserving it is part of your job.

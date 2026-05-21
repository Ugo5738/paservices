"""One-off: cancel build_flags that pre-date migration `l4d9e7f2g5h6`.

Background
----------
Chunk 9 changed the `Auth + Super ID Sub-Workflow` to STOP minting SuperIDs
and START requiring one (`super_id is required and must be a valid UUID`).
That tightening was correct for the data-capture path — but it silently
broke the Fetcher Build pipeline, because:

  1. `data_capture.build_flags` had no `super_id` column.
  2. `WF DC 1 Main`'s Write Build Flag node sent only `{url, reason}`.
  3. The Trigger workflow's first real node (`Auth + Super ID`) was called
     with an empty super_id and died immediately every time.

Migration `l4d9e7f2g5h6` fixes (1) by adding the column. `WF DC 1 Main`
fixes (2) by passing the orchestrator's super_id. The Trigger workflow
now reads super_id from the LISTEN payload, fixing (3).

But the 17 pending + 9 in_progress flags written BEFORE this fix landed
have `super_id = NULL`. They were architecturally orphaned (chunk 9
severed their connection to a live capture flow) and cannot be retried —
there is no upstream SuperID to attach them to.

This script marks them all `status='failed'` with a clear `error` message
so they stop showing up in the pending queue and so the audit trail is
honest about what happened. No data is deleted.

Idempotent: only touches flags that satisfy
  super_id IS NULL AND status IN ('pending', 'in_progress')

Re-running picks up zero rows the second time.

Run inside the data_capture_service container:

    docker compose run --rm \\
      -v "$(pwd)/data_capture_service/scripts/cancel_legacy_build_flags.py:/app/cancel.py" \\
      data_capture_service python /app/cancel.py
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from data_capture_service.config import settings


SELECT_TARGETS = text(
    """
    SELECT id, domain, reason, status, created_at
    FROM data_capture.build_flags
    WHERE super_id IS NULL
      AND status IN ('pending', 'in_progress')
    ORDER BY created_at
    """
)

CANCEL = text(
    """
    UPDATE data_capture.build_flags
    SET status = 'failed',
        error = 'Legacy flag without super_id; superseded by post-chunk-9 wiring '
                '(migration l4d9e7f2g5h6). Mint a fresh SuperID and re-trigger '
                'capture for this domain if a build is still wanted.',
        completed_at = COALESCE(completed_at, NOW())
    WHERE id = :flag_id
    """
)

REMAINING = text(
    """
    SELECT COUNT(*)
    FROM data_capture.build_flags
    WHERE super_id IS NULL
      AND status IN ('pending', 'in_progress')
    """
)


async def main() -> None:
    engine = create_async_engine(str(settings.DATABASE_URL))
    async with engine.begin() as conn:  # single transaction
        targets = (await conn.execute(SELECT_TARGETS)).mappings().all()

        if not targets:
            print(
                "No legacy build_flags (super_id IS NULL AND status IN "
                "('pending','in_progress')). Nothing to do."
            )
            await engine.dispose()
            return

        print(f"Will cancel {len(targets)} legacy flag(s):\n")
        for t in targets:
            print(
                f"  id={t['id']}  status={t['status']:11s}  "
                f"domain={t['domain']:24s}  reason={t['reason']}  "
                f"created_at={t['created_at']}"
            )
            await conn.execute(CANCEL, {"flag_id": t["id"]})

        remaining = (await conn.execute(REMAINING)).scalar()
        print(f"\nLegacy flags remaining: {remaining}")
        if remaining and remaining > 0:
            raise RuntimeError(
                f"{remaining} legacy flag(s) still present — transaction "
                "rolled back. Investigate before re-running."
            )

        print("\n✅ Clean. Committing.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

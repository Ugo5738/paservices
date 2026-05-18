"""One-off: free UNIQUE(super_id) on fetcher_runs by de-duplicating the
legacy build-benchmark pairs.

Background
----------
Before chunk 4's UNIQUE(super_id) and the chunk 8.5 reference-SuperID fix,
`/fetcher-builds/motie/build/{id}/score` wrote TWO `fetcher_runs` rows
under the SAME `request.super_id`:

  - the AI-fetcher baseline run (vendor = the baseline adapter, e.g.
    'firecrawl'), and
  - the freshly-built Motie scraper candidate run (vendor = 'motie').

That makes those super_ids appear on >1 row, which blocks migration
961cbac71cd5 (the defensive duplicate check fires by design).

Chunk 8.5 fixes this going forward: the candidate run now mints its own
operating super_id and link-records it to the build's reference
super_id. This script resolves the PRE-EXISTING rows so the constraint
can be applied.

What it does
------------
For every super_id that currently appears on more than one
`build_benchmark` row, it keeps the super_id on the AI-fetcher baseline
row and clears it on the Motie candidate row(s) — WITHOUT deleting any
row. The original super_id is preserved in that row's `metadata_json`
(`archived_super_id`), so nothing is lost and the row stays traceable
via `motie_build_id`. PostgreSQL allows multiple NULLs in a UNIQUE
constraint, so the constraint then applies cleanly.

This is an explicit administrative migration (docs/superid_principles.md
§3 "Extreme exceptions" — administrative intervention outside the normal
operational flow). It is idempotent and transactional: it commits only
if zero duplicated super_ids remain afterwards, otherwise it rolls back
and reports.

Run it inside the data_capture_service container:

    docker compose run --rm \\
        -v "$(pwd)/data_capture_service/scripts/dedup_legacy_build_benchmark_super_ids.py:/app/dedup.py" \\
        data_capture_service python /app/dedup.py
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from data_capture_service.config import settings

# Only touch rows that are unambiguously the Motie candidate side of a
# duplicated build_benchmark pair. The AI-fetcher baseline row keeps the
# super_id (it is what the chunk 8.5 code now treats as the reference).
SELECT_TARGETS = text(
    """
    SELECT id, super_id, vendor, kind, motie_build_id
    FROM data_capture.fetcher_runs
    WHERE super_id IS NOT NULL
      AND kind = 'build_benchmark'
      AND vendor = 'motie'
      AND super_id IN (
          SELECT super_id
          FROM data_capture.fetcher_runs
          WHERE super_id IS NOT NULL
          GROUP BY super_id
          HAVING COUNT(*) > 1
      )
    ORDER BY super_id
    """
)

ARCHIVE_AND_NULL = text(
    """
    UPDATE data_capture.fetcher_runs
    SET metadata_json = COALESCE(metadata_json, '{}'::jsonb)
            || jsonb_build_object(
                 'archived_super_id', super_id::text,
                 'archived_reason',
                 'chunk_8.5_dedup_legacy_build_benchmark_candidate'
               ),
        super_id = NULL
    WHERE id = :row_id
    """
)

REMAINING_DUPES = text(
    """
    SELECT COUNT(*) FROM (
        SELECT super_id
        FROM data_capture.fetcher_runs
        WHERE super_id IS NOT NULL
        GROUP BY super_id
        HAVING COUNT(*) > 1
    ) d
    """
)


async def main() -> None:
    engine = create_async_engine(str(settings.DATABASE_URL))
    async with engine.begin() as conn:  # single transaction
        targets = (await conn.execute(SELECT_TARGETS)).mappings().all()

        if not targets:
            print("No legacy build_benchmark candidate duplicates found. "
                  "Nothing to do.")
            await engine.dispose()
            return

        print(f"Will archive+NULL super_id on {len(targets)} Motie "
              f"candidate row(s):\n")
        for t in targets:
            print(f"  row id={t['id']}  super_id={t['super_id']}  "
                  f"vendor={t['vendor']}  motie_build_id={t['motie_build_id']}")
            await conn.execute(ARCHIVE_AND_NULL, {"row_id": t["id"]})

        remaining = (await conn.execute(REMAINING_DUPES)).scalar()
        print(f"\nDuplicated super_ids remaining after update: {remaining}")

        if remaining and remaining > 0:
            # The transaction context manager will roll back on exception.
            raise RuntimeError(
                f"{remaining} duplicated super_id(s) still present after "
                "nulling Motie candidates — there are duplicates that are "
                "NOT build_benchmark Motie candidates. Transaction rolled "
                "back; investigate with the inspection query before re-running."
            )

        print("\n✅ Clean. Committing. You can now re-run:")
        print("   docker compose run --rm data_capture_service "
              "alembic upgrade head")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

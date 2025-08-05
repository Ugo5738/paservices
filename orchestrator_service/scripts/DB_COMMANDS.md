# Database Management Commands (manage_db.py)

This document outlines the usage of the `manage_db.py` script, which is the centralized tool for all database operations for this service.

## Usage

All commands are run from the root of the service directory (e.g., `orchestrator_service/`).

```bash
python scripts/manage_db.py [COMMAND]
```

## Commands

### init

**Command:**

```bash
python scripts/manage_db.py init
```

**Description:** Performs a full, non-destructive setup of the database. It will create the database if it doesn't exist, apply all migrations.

**Use Case:** Run this command when setting up the project for the first time on a new machine or in a new environment. It's safe to run multiple times.

### recreate

**Command:**

```bash
python scripts/manage_db.py recreate
```

**Description:** ⚠️ **(DESTRUCTIVE)** Completely deletes the existing database and then runs the init command to rebuild it from scratch. All data will be lost.

**Use Case:** Use this when you need a perfectly clean slate, for example, if migrations have become corrupted or you want to reset the development environment completely.

### delete-db

**Command:**

```bash
python scripts/manage_db.py delete-db
```

**Description:** ⚠️ **(DESTRUCTIVE)** Drops the entire database for this service.

**Use Case:** Useful for environment cleanup when you no longer need the database.

### create-migration

**Command:**

```bash
python scripts/manage_db.py create-migration -m "Your descriptive message"
```

**Description:** Scans your SQLAlchemy models for changes and automatically generates a new Alembic migration file in the `alembic/versions` directory.

**Use Case:** After you modify any file in the `src/orchestrator_service/models/` directory, run this command to create the corresponding database migration.

### upgrade

**Command:**

```bash
python scripts/manage_db.py upgrade
```

**Description:** Applies all pending (unapplied) migration files to the database, bringing it up to the latest version.

**Use Case:** Run this after pulling new changes from version control that include new migrations, or after creating your own new migration.

### downgrade

**Command:**

```bash
python scripts/manage_db.py downgrade -s <number_of_steps>
```

**Description:** Reverts the most recent migration(s). The `-s` flag specifies how many migration steps to go back (defaults to 1).

**Use Case:** Primarily for development when you need to undo a recent migration to fix it before committing. Do not run this in production.

### verify

**Command:**

```bash
python scripts/manage_db.py verify
```

**Description:** Uses the official `alembic check` command to perform a comprehensive verification. It detects any differences between your SQLAlchemy models and the current database schema, including new/removed tables and changes to columns or constraints.

**Use Case:** Run this as a sanity check or in a CI pipeline to ensure your code and database schema are in sync.

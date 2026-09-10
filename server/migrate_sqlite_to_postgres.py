"""One-time, non-destructive migration of a Let's Fly SQLite database to PostgreSQL.

Usage:
  SOURCE_SQLITE_PATH=/path/to/letsfly_v2.db \
  DATABASE_URL=postgresql+psycopg://... \
  python server/migrate_sqlite_to_postgres.py

The destination must be empty. The script refuses to copy into a populated
PostgreSQL schema, preserving the source database and preventing accidental
merges/overwrites. Primary keys and foreign-key relationships are preserved,
and PostgreSQL sequences are aligned after the copy.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import MetaData, create_engine as sa_create_engine, text

source = Path(os.getenv("SOURCE_SQLITE_PATH", "")).expanduser()
destination = os.getenv("DATABASE_URL", "").strip()
if not source:
    raise SystemExit("SOURCE_SQLITE_PATH is required")
if not source.exists():
    raise SystemExit(f"SQLite source database not found: {source}")
if not destination:
    raise SystemExit("DATABASE_URL is required")
if destination.startswith("postgres://"):
    destination = "postgresql+psycopg://" + destination[len("postgres://"):]
elif destination.startswith("postgresql://"):
    destination = "postgresql+psycopg://" + destination[len("postgresql://"):]
if not destination.startswith("postgresql"):
    raise SystemExit("DATABASE_URL must point to PostgreSQL")

# Import models with an explicitly non-production environment so importing the
# application's database module cannot silently reject this migration process.
os.environ["LETSFLY_ENV"] = "migration"
os.environ["DATABASE_URL"] = destination
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.app.db.database import Base  # noqa: E402

src_engine = sa_create_engine(
    f"sqlite:///{source}",
    connect_args={"check_same_thread": False},
)
dst_engine = sa_create_engine(destination, pool_pre_ping=True)
Base.metadata.create_all(bind=dst_engine)

src_meta = MetaData()
src_meta.reflect(bind=src_engine)
source_tables = [t for t in src_meta.sorted_tables if t.name in Base.metadata.tables]

with dst_engine.connect() as dst:
    # Refuse to merge into an existing dataset. This makes migration repeatable
    # only after an intentional fresh destination is supplied.
    populated = []
    for table in Base.metadata.sorted_tables:
        if dst.execute(text(f'SELECT COUNT(*) FROM "{table.name}"')).scalar_one() > 0:
            populated.append(table.name)
    if populated:
        raise SystemExit(
            "Destination PostgreSQL is not empty; migration aborted without modifying it. "
            f"Populated tables: {', '.join(populated)}"
        )

source_counts = {}
for table in source_tables:
    with src_engine.connect() as src:
        source_counts[table.name] = src.execute(text(f'SELECT COUNT(*) FROM "{table.name}"')).scalar_one()

with src_engine.connect() as src, dst_engine.begin() as dst:
    for src_table in source_tables:
        count = source_counts[src_table.name]
        if count == 0:
            continue
        dst_table = Base.metadata.tables[src_table.name]
        columns = [c.name for c in dst_table.columns if c.name in src_table.c]
        # Stream rows in bounded batches instead of materializing a large history
        # table into one Python list.
        result = src.execute(src_table.select()).mappings()
        batch = []
        for row in result:
            batch.append({name: row[name] for name in columns})
            if len(batch) >= 1000:
                dst.execute(dst_table.insert(), batch)
                batch.clear()
        if batch:
            dst.execute(dst_table.insert(), batch)

    # Preserve integer primary keys and make future INSERTs continue at MAX(id)+1.
    for table in Base.metadata.sorted_tables:
        pk_cols = list(table.primary_key.columns)
        if len(pk_cols) != 1:
            continue
        col = pk_cols[0]
        if col.type.python_type is not int:
            continue
        seq_name = f"{table.name}_{col.name}_seq"
        dst.execute(
            text(
                f'SELECT setval(:seq, COALESCE((SELECT MAX("{col.name}") FROM "{table.name}"), 1), '
                f'(SELECT COUNT(*) > 0 FROM "{table.name}"))'
            ),
            {"seq": seq_name},
        )

# Verify row counts after the committed transaction. Any mismatch is a hard
# failure rather than a false success report.
with dst_engine.connect() as dst:
    mismatches = []
    for table_name, expected in source_counts.items():
        actual = dst.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar_one()
        if actual != expected:
            mismatches.append(f"{table_name}: source={expected}, destination={actual}")
    if mismatches:
        raise SystemExit("Migration verification failed: " + "; ".join(mismatches))

print(f"Migration verified: {source} -> PostgreSQL ({len(source_counts)} tables).")

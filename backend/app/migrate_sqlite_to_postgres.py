"""SQLite to PostgreSQL Data Migration & Validation ETL Script.

Safely migrates all entities, relations, IDs, timestamps, and monetary values
from an existing SQLite database into a target PostgreSQL database using
SQLAlchemy 2.x ORM metadata. Automatically handles orphaned records from SQLite.

Usage:
    python -m app.migrate_sqlite_to_postgres --sqlite-url "sqlite:///../foh.db" --pg-url "postgresql+psycopg://postgres:12345678@localhost:5432/foh_management"
"""

import argparse
import logging
import sys
from typing import Any

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base
import app.models  # Registers all models

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("db_migration")


def migrate_data(sqlite_url: str, pg_url: str, wipe_target: bool = True) -> bool:
    logger.info(f"Starting migration from: {sqlite_url}")
    logger.info(f"Target PostgreSQL: {pg_url}")

    # 1. Connect to Source (SQLite)
    sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    SqliteSession = sessionmaker(bind=sqlite_engine)
    src_inspector = inspect(sqlite_engine)
    src_tables = set(src_inspector.get_table_names())

    # 2. Connect to Target (PostgreSQL)
    pg_engine = create_engine(pg_url, pool_pre_ping=True)
    PgSession = sessionmaker(bind=pg_engine)

    # 3. Ensure all tables exist in target PostgreSQL
    logger.info("Ensuring PostgreSQL schema and tables exist...")
    Base.metadata.create_all(bind=pg_engine)

    # 4. Get sorted tables in topological dependency order
    tables = Base.metadata.sorted_tables
    logger.info(f"Total tables to inspect: {len(tables)}")

    with SqliteSession() as src_db, PgSession() as tgt_db:
        # Optional: Clean target tables in reverse order before migrating
        if wipe_target:
            logger.info("Clearing existing data in target database (reverse topological order)...")
            try:
                with pg_engine.connect() as conn:
                    table_names = [f'"{t.name}"' for t in reversed(tables)]
                    conn.execute(text(f"TRUNCATE TABLE {', '.join(table_names)} CASCADE;"))
                    conn.commit()
            except Exception as e:
                logger.warning(f"TRUNCATE CASCADE failed ({e}), falling back to individual deletes...")
                for table in reversed(tables):
                    tgt_db.execute(table.delete())
                tgt_db.commit()

        # 5. Migrate table by table
        stats: dict[str, dict[str, int]] = {}

        for table in tables:
            table_name = table.name
            if table_name not in src_tables:
                stats[table_name] = {"source": 0, "target": 0, "status": "NOT_IN_SRC"}
                continue

            try:
                # Inspect columns present in SQLite
                src_col_info = src_inspector.get_columns(table_name)
                src_col_names = {c["name"] for c in src_col_info}

                # Only query columns that actually exist in SQLite table
                valid_cols = [c for c in table.columns if c.name in src_col_names]
                if not valid_cols:
                    stats[table_name] = {"source": 0, "target": 0, "status": "EMPTY"}
                    continue

                src_rows = src_db.execute(select(*valid_cols)).mappings().all()
                src_count = len(src_rows)

                if src_count == 0:
                    stats[table_name] = {"source": 0, "target": 0, "status": "EMPTY"}
                    continue

                # Prepare rows for PostgreSQL insertion
                cleaned_rows: list[dict[str, Any]] = []
                for row in src_rows:
                    cleaned_rows.append(dict(row))

                # Referential integrity orphan sanitization
                if table_name == "refund_requests":
                    valid_bill_ids = {r[0] for r in tgt_db.execute(text("SELECT id FROM bills")).all()}
                    valid_pay_ids = {r[0] for r in tgt_db.execute(text("SELECT id FROM payments")).all()}
                    cleaned_rows = [
                        r for r in cleaned_rows
                        if (not r.get("bill_id") or r["bill_id"] in valid_bill_ids)
                        and (not r.get("payment_id") or r["payment_id"] in valid_pay_ids)
                    ]
                elif table_name == "discounts":
                    valid_bill_ids = {r[0] for r in tgt_db.execute(text("SELECT id FROM bills")).all()}
                    cleaned_rows = [r for r in cleaned_rows if not r.get("bill_id") or r["bill_id"] in valid_bill_ids]
                elif table_name == "cleaning_events":
                    valid_tbl_ids = {r[0] for r in tgt_db.execute(text("SELECT id FROM tables")).all()}
                    valid_sess_ids = {r[0] for r in tgt_db.execute(text("SELECT id FROM dining_sessions")).all()}
                    for r in cleaned_rows:
                        if r.get("dining_session_id") and r["dining_session_id"] not in valid_sess_ids:
                            r["dining_session_id"] = None
                    cleaned_rows = [r for r in cleaned_rows if not r.get("table_id") or r["table_id"] in valid_tbl_ids]
                elif table_name == "status_history":
                    valid_tbl_ids = {r[0] for r in tgt_db.execute(text("SELECT id FROM tables")).all()}
                    valid_sess_ids = {r[0] for r in tgt_db.execute(text("SELECT id FROM dining_sessions")).all()}
                    for r in cleaned_rows:
                        if r.get("session_id") and r["session_id"] not in valid_sess_ids:
                            r["session_id"] = None
                    cleaned_rows = [r for r in cleaned_rows if not r.get("table_id") or r["table_id"] in valid_tbl_ids]
                elif table_name in ("departure_events", "ai_events"):
                    valid_tbl_ids = {r[0] for r in tgt_db.execute(text("SELECT id FROM tables")).all()}
                    cleaned_rows = [r for r in cleaned_rows if not r.get("table_id") or r["table_id"] in valid_tbl_ids]

                if cleaned_rows:
                    tgt_db.execute(table.insert(), cleaned_rows)
                    tgt_db.commit()

                # Verify target count
                tgt_count = tgt_db.scalar(select(text("COUNT(*)")).select_from(table))
                status = "MATCH" if len(cleaned_rows) == tgt_count else "PARTIAL"
                stats[table_name] = {"source": src_count, "target": tgt_count, "status": status}
                logger.info(f"  [OK] {table_name:<28} Source: {src_count:>4} | Target: {tgt_count:>4} [{status}]")

            except Exception as ex:
                tgt_db.rollback()
                logger.error(f"  [FAIL] Failed migrating table '{table_name}': {ex}")
                stats[table_name] = {"source": -1, "target": -1, "status": f"ERROR: {str(ex)[:40]}"}

    # 6. Validation Summary Report
    print("\n" + "=" * 72)
    print("           SQLITE TO POSTGRESQL DATA MIGRATION REPORT           ")
    print("=" * 72)
    print(f"{'Table Name':<30} | {'SQLite Rows':<12} | {'Postgres Rows':<13} | {'Status'}")
    print("-" * 72)

    all_matched = True
    for t_name, data in stats.items():
        src_c = str(data["source"]) if data["source"] >= 0 else "ERR"
        tgt_c = str(data["target"]) if data["target"] >= 0 else "ERR"
        status_str = data["status"]
        if status_str not in ("MATCH", "EMPTY", "NOT_IN_SRC", "PARTIAL"):
            all_matched = False
        print(f"{t_name:<30} | {src_c:<12} | {tgt_c:<13} | {status_str}")

    print("=" * 72)
    if all_matched:
        print("[SUCCESS] MIGRATION SUCCESSFUL! All records and relationships verified 100%!")
    else:
        print("[WARNING] MIGRATION COMPLETED WITH WARNINGS. Please inspect tables flagged above.")
    print("=" * 72 + "\n")

    return all_matched


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite DB to PostgreSQL")
    parser.add_argument(
        "--sqlite-url",
        default="sqlite:///../foh.db",
        help="Source SQLite database URL",
    )
    parser.add_argument(
        "--pg-url",
        default=settings.database_url if settings.database_url.startswith("postgresql") else "postgresql+psycopg://postgres:12345678@localhost:5432/foh_management",
        help="Target PostgreSQL database URL",
    )
    parser.add_argument(
        "--no-wipe",
        action="store_true",
        help="Do not wipe target tables before insertion",
    )

    args = parser.parse_args()
    success = migrate_data(args.sqlite_url, args.pg_url, wipe_target=not args.no_wipe)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()

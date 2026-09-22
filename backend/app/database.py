from collections.abc import Generator
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# Configure engine arguments based on database dialect
is_sqlite = settings.database_url.startswith("sqlite")

if is_sqlite:
    engine_kwargs = {
        "connect_args": {"check_same_thread": False},
    }
else:
    # PostgreSQL with psycopg / psycopg2 connection pool
    engine_kwargs = {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_recycle": settings.db_pool_recycle,
        "pool_pre_ping": settings.db_pool_pre_ping,
    }

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


from sqlalchemy import MetaData

naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=naming_convention)


def migrate_schema() -> None:
    """Additive schema migrations for SQLite dev fallback.
    PostgreSQL deployments use Alembic for versioned migrations.
    """
    if not is_sqlite:
        return
    with engine.connect() as conn:
        tenant_tables = {
            "users", "floors", "sections", "tables", "reservations",
            "dining_sessions", "orders", "bills", "payments", "audit_logs",
        }
        for table_name in tenant_tables:
            rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            if not rows:
                continue
            col_names = {row[1] for row in rows}
            if "tenant_id" not in col_names:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN tenant_id VARCHAR(64)"))
            if "branch_id" not in col_names:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN branch_id VARCHAR(64)"))

        user_rows = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        user_cols = {row[1] for row in user_rows}
        if user_rows:
            if "failed_login_attempts" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0"))
            if "locked_until" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN locked_until DATETIME"))
            if "status" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN status VARCHAR(20) DEFAULT 'ACTIVE'"))

        bill_rows = conn.execute(text("PRAGMA table_info(bills)")).fetchall()
        bill_cols = {row[1] for row in bill_rows}
        for name in ("discount_amount", "tax_amount", "service_charge_amount"):
            if bill_rows and name not in bill_cols:
                conn.execute(text(f"ALTER TABLE bills ADD COLUMN {name} NUMERIC(10,2) DEFAULT 0"))
        if bill_rows and "discount_reason" not in bill_cols:
            conn.execute(text("ALTER TABLE bills ADD COLUMN discount_reason VARCHAR(255)"))

        if bill_rows:
            for col, typedef in [
                ("bill_number",  "VARCHAR(32)"),
                ("bill_status",  "VARCHAR(30)"),
                ("created_by",   "VARCHAR(64)"),
                ("order_id",     "VARCHAR(64)"),
                ("customer_id",  "VARCHAR(64)"),
                ("updated_by",   "VARCHAR(64)"),
                ("notes",        "TEXT"),
            ]:
                if col not in bill_cols:
                    conn.execute(text(f"ALTER TABLE bills ADD COLUMN {col} {typedef}"))

        pay_rows = conn.execute(text("PRAGMA table_info(payments)")).fetchall()
        pay_cols = {row[1] for row in pay_rows}
        if pay_rows:
            for col, typedef in [
                ("payment_status", "VARCHAR(20) DEFAULT 'SUCCESS'"),
                ("transaction_id", "VARCHAR(255)"),
                ("created_by",     "VARCHAR(64)"),
                ("completed_at",   "DATETIME"),
                ("shift_id",       "VARCHAR(64)"),
            ]:
                if col not in pay_cols:
                    conn.execute(text(f"ALTER TABLE payments ADD COLUMN {col} {typedef}"))

        ord_rows = conn.execute(text("PRAGMA table_info(orders)")).fetchall()
        ord_cols = {row[1] for row in ord_rows}
        if ord_rows:
            for col, typedef in [
                ("created_by", "VARCHAR(64)"),
                ("notes",      "VARCHAR(500)"),
                ("source",     "VARCHAR(10) DEFAULT 'bot'"),
                ("approval_status", "VARCHAR(10) DEFAULT 'PENDING'"),
            ]:
                if col not in ord_cols:
                    conn.execute(text(f"ALTER TABLE orders ADD COLUMN {col} {typedef}"))

        oi_rows = conn.execute(text("PRAGMA table_info(order_items)")).fetchall()
        oi_cols = {row[1] for row in oi_rows}
        if oi_rows:
            for col, typedef in [
                ("station",      "VARCHAR(32)"),
                ("notes",        "VARCHAR(500)"),
                ("allergy_flag", "BOOLEAN DEFAULT 0"),
                ("item_status",  "VARCHAR(20) DEFAULT 'RECEIVED'"),
            ]:
                if col not in oi_cols:
                    conn.execute(text(f"ALTER TABLE order_items ADD COLUMN {col} {typedef}"))

        mi_rows = conn.execute(text("PRAGMA table_info(menu_items)")).fetchall()
        mi_cols = {row[1] for row in mi_rows}
        if mi_rows and "station" not in mi_cols:
            conn.execute(text("ALTER TABLE menu_items ADD COLUMN station VARCHAR(32)"))

        aiev_rows = conn.execute(text("PRAGMA table_info(ai_events)")).fetchall()
        aiev_cols = {row[1] for row in aiev_rows}
        if aiev_rows:
            if "acknowledged" not in aiev_cols:
                conn.execute(text("ALTER TABLE ai_events ADD COLUMN acknowledged BOOLEAN DEFAULT 0"))
            if "metadata_json" not in aiev_cols:
                conn.execute(text("ALTER TABLE ai_events ADD COLUMN metadata_json TEXT"))

        res_rows = conn.execute(text("PRAGMA table_info(reservations)")).fetchall()
        res_cols = {row[1] for row in res_rows}
        if res_rows:
            for col, typedef in [
                ("customer_email", "VARCHAR(255)"),
                ("payment_status", "VARCHAR(20) DEFAULT 'UNPAID'"),
                ("expires_at",     "DATETIME"),
            ]:
                if col not in res_cols:
                    conn.execute(text(f"ALTER TABLE reservations ADD COLUMN {col} {typedef}"))

        tbl_rows = conn.execute(text("PRAGMA table_info(tables)")).fetchall()
        col_names = {row[1] for row in tbl_rows}
        alters: list[str] = []
        if tbl_rows:
            if "roi_coords" not in col_names:
                alters.append("ALTER TABLE tables ADD COLUMN roi_coords VARCHAR(255)")
            if "consecutive_empty_scans" not in col_names:
                alters.append("ALTER TABLE tables ADD COLUMN consecutive_empty_scans INTEGER DEFAULT 0")
            if "cleaning_started_at" not in col_names:
                alters.append("ALTER TABLE tables ADD COLUMN cleaning_started_at VARCHAR(32)")
            for flag in ("dirty_alert_sent", "dirty_escalated", "departure_alert_sent", "walkout_alert_sent"):
                if flag not in col_names:
                    alters.append(f"ALTER TABLE tables ADD COLUMN {flag} BOOLEAN DEFAULT 0")
            for sql in alters:
                conn.execute(text(sql))

        conn.commit()


def get_db() -> Generator:
    """FastAPI database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_health() -> dict[str, str | bool]:
    """Active connection test for health check."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "ok": True}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "ok": False, "error": "Database connection error"}

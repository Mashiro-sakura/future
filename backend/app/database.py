from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine: Engine
SessionLocal: sessionmaker[Session]


def configure_database(database_url: str | None = None) -> Engine:
    global engine, SessionLocal
    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return engine


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_lightweight_migrations()


def _ensure_lightweight_migrations() -> None:
    inspector = inspect(engine)
    if "futures_prices" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("futures_prices")}
    with engine.begin() as connection:
        if "contract_code" not in columns:
            connection.execute(text("ALTER TABLE futures_prices ADD COLUMN contract_code VARCHAR(32) DEFAULT ''"))
    if "reports" in inspector.get_table_names():
        report_columns = {column["name"] for column in inspector.get_columns("reports")}
        additions = {
            "price_behavior_analysis": "ALTER TABLE reports ADD COLUMN price_behavior_analysis TEXT DEFAULT ''",
            "fundamentals_analysis": "ALTER TABLE reports ADD COLUMN fundamentals_analysis TEXT DEFAULT ''",
            "macro_analysis": "ALTER TABLE reports ADD COLUMN macro_analysis TEXT DEFAULT ''",
            "policy_analysis": "ALTER TABLE reports ADD COLUMN policy_analysis TEXT DEFAULT ''",
            "product_analysis_payload": "ALTER TABLE reports ADD COLUMN product_analysis_payload TEXT DEFAULT '[]'",
        }
        with engine.begin() as connection:
            for column_name, ddl in additions.items():
                if column_name not in report_columns:
                    connection.execute(text(ddl))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


configure_database()

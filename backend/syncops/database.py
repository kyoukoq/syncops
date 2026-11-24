import os
from sqlite3 import Connection

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


def database_url() -> str:
    return os.getenv("SYNCOPS_DATABASE_URL", "sqlite:///./syncops.db")


def build_engine(url: str):
    engine = create_engine(url, pool_pre_ping=True, hide_parameters=True)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def configure_sqlite(connection: Connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


engine = build_engine(database_url())
Session = sessionmaker(engine, expire_on_commit=False)

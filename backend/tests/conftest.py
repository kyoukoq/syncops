import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from syncops import database
from syncops.api import app

TEST_PASSWORD = "tests-only-password"
MOCK_TOKEN = "tests-only-mock-token"


@pytest.fixture
def db_engine(tmp_path, monkeypatch):
    engine = database.build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(database, "engine", engine)
    database.Session.configure(bind=engine)
    command.upgrade(Config("alembic.ini"), "head")
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def api(db_engine, monkeypatch):
    for role in ("ADMIN", "OPERATOR", "VIEWER"):
        monkeypatch.setenv(f"SYNCOPS_{role}_PASSWORD", TEST_PASSWORD)
    monkeypatch.setenv("SYNCOPS_MOCK_TOKEN", MOCK_TOKEN)
    with TestClient(app) as client:
        yield client

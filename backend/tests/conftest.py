import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("GEMINI_MODEL", "gemini-3.1-flash-lite")


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "test_meetings.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("GEMINI_API_KEY", "")

    from backend.app.config import get_settings

    get_settings.cache_clear()

    import app.database.database as database

    database.engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    database.SessionLocal = sessionmaker(bind=database.engine, autocommit=False, autoflush=False)
    database.init_db()

    from backend.app.main import app

    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()

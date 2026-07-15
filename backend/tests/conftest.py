from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("BOOTSTRAP_SAMPLE_DATA", "false")
    monkeypatch.setenv("USE_AKSHARE", "false")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin123")
    monkeypatch.delenv("WECHAT_WORK_WEBHOOK_URL", raising=False)

    from app.config import reset_settings_cache
    from app.database import configure_database

    reset_settings_cache()
    configure_database(os.environ["DATABASE_URL"])

    from app.main import app, bootstrap_database

    bootstrap_database()

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/admin/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

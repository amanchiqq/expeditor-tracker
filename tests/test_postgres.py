"""Opt-in integration tests. TEST_DATABASE_URL must point to a disposable test database."""
import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from uuid import uuid4
import asyncpg
import pytest
from fastapi.testclient import TestClient
import main as m
from app.security import get_password_hash

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL to run real PostgreSQL tests")


@pytest.fixture
def database(monkeypatch):
    dsn = os.environ["TEST_DATABASE_URL"]
    schema = "audit_" + uuid4().hex
    async def setup():
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(f'CREATE SCHEMA "{schema}"')
        finally:
            await conn.close()
    asyncio.run(setup())
    parts = urlsplit(dsn)
    query = dict(parse_qsl(parts.query))
    query["search_path"] = schema
    isolated = urlunsplit(parts._replace(query=urlencode(query)))
    monkeypatch.setenv("DATABASE_URL", isolated)
    monkeypatch.setenv("SECRET_KEY", "integration-only-secret-at-least-32-characters")
    try:
        yield isolated
    finally:
        async def cleanup():
            conn = await asyncpg.connect(dsn)
            try:
                await conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
            finally:
                await conn.close()
        asyncio.run(cleanup())


def migrate():
    result = subprocess.run([sys.executable, "scripts/migrate.py"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_clean_schema_login_crud_and_filters(database):
    migrate()
    migrate()  # Re-running is safe and verifies migration checksums.
    async def seed():
        conn = await asyncpg.connect(database)
        try:
            await conn.execute("INSERT INTO users(username,password) VALUES($1,$2)", "dispatcher", get_password_hash("integration-password"))
        finally:
            await conn.close()
    asyncio.run(seed())
    with TestClient(m.app) as c:
        result = c.post("/token", data={"username": "dispatcher", "password": "integration-password"})
        assert result.status_code == 200
        headers = {"Authorization": "Bearer " + result.json()["access_token"]}
        body = {"expeditor_id": 7, "description": "Integration delivery", "latitude": 51.1, "longitude": 71.4, "eta": "2026-10-28T12:00:00+05:00"}
        created = c.post("/tasks", json=body, headers=headers)
        assert created.status_code == 200
        task_id = created.json()["id"]
        task = c.get(f"/tasks/{task_id}", headers=headers).json()
        assert task["eta"] == "2026-10-28T07:00:00Z"
        created_date = task["created_at"][:10]
        filtered = c.get(f"/tasks?task_id={task_id}&expeditor_id=7&status=in_progress&date={created_date}", headers=headers)
        assert filtered.status_code == 200
        assert filtered.json()["total"] == 1
        assert filtered.json()["expeditor_counts"] == {"7": 1}
        assert c.get("/tasks?expeditor_id=8", headers=headers).json()["total"] == 0
        body["status"] = "completed"
        assert c.put(f"/tasks/{task_id}", json=body, headers=headers).status_code == 200
        assert c.get("/tasks?status=completed", headers=headers).json()["total"] == 1
        assert c.delete(f"/tasks/{task_id}", headers=headers).status_code == 200
        assert c.get(f"/tasks/{task_id}", headers=headers).status_code == 404
        assert c.get("/tasks", headers=headers).json()["total"] == 0


def test_legacy_readme_schema_is_upgraded(database):
    async def legacy():
        conn = await asyncpg.connect(database)
        try:
            await conn.execute("CREATE TABLE users (username VARCHAR(50) PRIMARY KEY, password VARCHAR(255) NOT NULL)")
            await conn.execute("CREATE TABLE tasks (id SERIAL PRIMARY KEY, expeditor_id INTEGER NOT NULL, description VARCHAR(255), latitude FLOAT NOT NULL, longitude FLOAT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            await conn.execute("INSERT INTO tasks(expeditor_id,latitude,longitude,created_at) VALUES(1,51,71,'2025-06-08 10:00:00')")
        finally:
            await conn.close()
    asyncio.run(legacy())
    migrate()
    migrate()
    async def verify():
        conn = await asyncpg.connect(database)
        try:
            row = await conn.fetchrow("SELECT * FROM tasks")
            assert row["status"] == "in_progress"
            assert row["eta"] is None
            assert row["created_at"] == datetime(2025,6,8,10,tzinfo=timezone.utc)
        finally:
            await conn.close()
    asyncio.run(verify())

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest
from fastapi.testclient import TestClient
from jose import jwt
import main as m
from app import repository
from app.security import create_access_token, get_password_hash, verify_password

SECRET = "test-only-secret-with-at-least-32-characters"


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", SECRET)
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")


@pytest.fixture
def environment(monkeypatch):
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=AsyncMock())
    record = {"id": 1, "expeditor_id": 1, "description": "Delivery", "latitude": 51.1,
              "longitude": 71.4, "status": "in_progress", "created_at": datetime.now(timezone.utc), "eta": None}
    async def rows(sql, *args):
        return [{"expeditor_id": 1, "status": "in_progress", "count": 1}] if "GROUP BY" in sql else [record]
    conn.fetch.side_effect = rows
    conn.fetchval.return_value = 1
    conn.fetchrow.return_value = record
    pool = MagicMock()
    pool.close = AsyncMock()
    released = []
    @asynccontextmanager
    async def acquire():
        try:
            yield conn
        finally:
            released.append(True)
    pool.acquire = acquire
    monkeypatch.setattr(m.asyncpg, "create_pool", AsyncMock(return_value=pool))
    monkeypatch.setattr(m.sio, "emit", AsyncMock())
    monkeypatch.setattr(m.sio, "shutdown", AsyncMock())
    m.api.dependency_overrides[m.get_current_user] = lambda: {"username": "dispatcher"}
    try:
        with TestClient(m.app, raise_server_exceptions=False) as client:
            yield client, conn, pool, released
        pool.close.assert_awaited_once()
        m.sio.shutdown.assert_awaited_once()
    finally:
        m.api.dependency_overrides.clear()


def test_list_and_full_filtered_aggregates(environment):
    c, db, *_ = environment
    result = c.get("/tasks").json()
    assert result["total"] == 1
    assert result["expeditor_counts"] == {"1": 1}
    assert result["tasks"][0]["id"] == 1


@pytest.mark.parametrize("query", ["expeditor_id=1", "status=completed", "date=2026-10-28", "task_id=5", "task_id=5&expeditor_id=1&status=completed&date=2026-10-28"])
def test_sql_bindings(environment, query):
    c, db, *_ = environment
    assert c.get("/tasks?" + query).status_code == 200
    import re
    calls = db.fetch.await_args_list + db.fetchval.await_args_list
    for call in calls:
        sql, *args = call.args
        ids = set(map(int, re.findall(r"\$(\d+)", sql)))
        assert ids == set(range(1, len(args)+1)), (sql, args)


@pytest.mark.parametrize("eta", [None, "2026-10-28T12:00:00+05:00"])
def test_create_normalizes_eta_and_publishes(environment, eta):
    c, db, pool, released = environment
    response = c.post("/tasks", json={"expeditor_id": 1, "eta": eta})
    assert response.status_code == 200
    assert len(released) == 1
    sql, *args = db.fetchval.await_args.args
    assert "nextval" not in sql and "created_at" not in sql
    assert args[-1] == (datetime(2026, 10, 28, 7, tzinfo=timezone.utc) if eta else None)
    m.sio.emit.assert_awaited_once_with("tasks_changed", {"action": "created", "task_id": 1}, room="dispatchers")


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_missing_task_is_404_without_event(environment, method):
    c, db, *_ = environment
    db.fetchrow.return_value = None
    db.fetchval.return_value = None
    kwargs = {"json": {"expeditor_id": 1}} if method == "put" else {}
    assert getattr(c, method)("/tasks/99", **kwargs).status_code == 404
    m.sio.emit.assert_not_awaited()


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_existing_task(environment, method):
    c, db, *_ = environment
    kwargs = {"json": {"expeditor_id": 1}} if method == "put" else {}
    assert getattr(c, method)("/tasks/1", **kwargs).status_code == 200


@pytest.mark.parametrize("query", ["page=0", "page=-1", "per_page=0", "per_page=-1", "per_page=101", "expeditor_id=-1", "status=anything", "date=invalid", "task_id=0"])
def test_invalid_query_rejected(environment, query):
    c, db, *_ = environment
    assert c.get("/tasks?" + query).status_code == 422
    db.fetch.assert_not_awaited()


@pytest.mark.parametrize("payload", [
    {"expeditor_id": -1}, {"expeditor_id": 1, "latitude": 100, "longitude": 70},
    {"expeditor_id": 1, "latitude": 51, "longitude": 200},
    {"expeditor_id": 1, "latitude": 51}, {"expeditor_id": 1, "status": "anything"},
    {"expeditor_id": 1, "eta": "bad"}, {"expeditor_id": 1, "eta": "2026-10-28T12:00"},
    {"expeditor_id": 1, "description": "x"*256}, {"expeditor_id": 1, "extra": 1},
])
def test_invalid_body_rejected(environment, payload):
    c, db, *_ = environment
    assert c.post("/tasks", json=payload).status_code == 422
    db.fetchval.assert_not_awaited()


def test_database_error_is_sanitized_and_connection_released(environment):
    c, db, pool, released = environment
    db.fetchval.side_effect = asyncpg.PostgresError("private database detail")
    response = c.post("/tasks", json={"expeditor_id": 1})
    assert response.status_code == 503
    assert "private" not in response.text
    assert len(released) == 1
    m.sio.emit.assert_not_awaited()


def test_notification_failure_does_not_undo_write(environment):
    c, db, *_ = environment
    m.sio.emit.side_effect = RuntimeError("offline")
    assert c.post("/tasks", json={"expeditor_id": 1}).status_code == 200


def test_requires_token(environment):
    c, db, *_ = environment
    m.api.dependency_overrides.clear()
    assert c.get("/tasks").status_code == 401


@pytest.mark.parametrize("kind", ["expired", "forged", "missing_exp", "missing_sub", "deleted_user"])
def test_bad_identity_rejected(environment, kind):
    c, db, *_ = environment
    m.api.dependency_overrides.clear()
    payload = {"sub": "dispatcher", "exp": datetime.now(timezone.utc)+timedelta(minutes=2)}
    key = SECRET
    if kind == "expired": payload["exp"] = datetime.now(timezone.utc)-timedelta(seconds=5)
    if kind == "forged": key = "your-very-secure-secret-key-here"
    if kind == "missing_exp": del payload["exp"]
    if kind == "missing_sub": del payload["sub"]
    if kind == "deleted_user": db.fetchrow.return_value = None
    token = jwt.encode(payload, key, algorithm="HS256")
    assert c.get("/tasks", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_login_and_authenticated_read(environment):
    c, db, *_ = environment
    db.fetchrow.return_value = {"username": "dispatcher", "password": get_password_hash("test-password")}
    m.api.dependency_overrides.clear()
    r = c.post("/token", data={"username": "dispatcher", "password": "test-password"})
    assert r.status_code == 200
    assert c.get("/tasks", headers={"Authorization": "Bearer " + r.json()["access_token"]}).status_code == 200
    assert c.post("/token", data={"username": "dispatcher", "password": "wrong"}).status_code == 401


def test_hash_round_trip():
    hashed = get_password_hash("test-password")
    assert verify_password("test-password", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("test", "invalid hash")


@pytest.mark.parametrize("secret", ["", "short", "your-very-secure-secret-key-here"])
def test_unsafe_settings_fail_startup(monkeypatch, secret):
    monkeypatch.setenv("SECRET_KEY", secret)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        with TestClient(m.app): pass


def test_missing_database_fails_startup(monkeypatch):
    monkeypatch.delenv("DATABASE_URL")
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        with TestClient(m.app): pass


def test_date_filter_uses_utc_range():
    from datetime import date
    where, args = repository.filters(date=date(2026, 10, 28))
    assert args == [datetime(2026, 10, 28, tzinfo=timezone.utc), datetime(2026, 10, 29, tzinfo=timezone.utc)]
    assert "DATE(" not in where


def test_socket_auth_contract(environment, monkeypatch):
    c, db, *_ = environment
    db.fetchrow.return_value = {"username": "dispatcher"}
    monkeypatch.setattr(m.sio, "save_session", AsyncMock())
    monkeypatch.setattr(m.sio, "enter_room", AsyncMock())
    monkeypatch.setattr(m.sio, "start_background_task", MagicMock())
    token = create_access_token({"sub": "dispatcher"})
    assert asyncio.run(m.connect("session", {}, {"token": token})) is not False
    m.sio.enter_room.assert_awaited_once_with("session", "dispatchers")
    assert asyncio.run(m.connect("bad", {}, {"token": "invalid"})) is False
    assert asyncio.run(m.connect("missing", {}, {})) is False


def test_expiration_disconnects(monkeypatch):
    monkeypatch.setattr(m.sio, "sleep", AsyncMock())
    monkeypatch.setattr(m.sio.manager, "is_connected", MagicMock(return_value=True))
    monkeypatch.setattr(m.sio, "disconnect", AsyncMock())
    asyncio.run(m.expire_session("sid", 0))
    m.sio.disconnect.assert_awaited_once_with("sid")


def test_socket_transport_path(environment):
    c, *_ = environment
    r = c.get("/socket.io/?EIO=4&transport=polling")
    assert r.status_code == 200
    assert r.text.startswith('0{')


def test_socket_websocket_auth_and_committed_change(environment, monkeypatch):
    import json
    import socketio
    c, db, *_ = environment
    db.fetchrow.return_value = {"username": "dispatcher"}
    # Restore the real emitter to exercise authenticated room delivery end to end in ASGI.
    monkeypatch.setattr(m.sio, "emit", socketio.AsyncServer.emit.__get__(m.sio))
    with c.websocket_connect("/socket.io/?EIO=4&transport=websocket", headers={"Upgrade": "websocket", "Connection": "Upgrade"}) as ws:
        assert ws.receive_text().startswith('0{')
        ws.send_text('40' + json.dumps({"token": create_access_token({"sub": "dispatcher"})}))
        assert ws.receive_text().startswith('40{')
        assert c.post("/tasks", json={"expeditor_id": 1}).status_code == 200
        packet = ws.receive_text()
        assert packet.startswith('42')
        assert json.loads(packet[2:]) == ["tasks_changed", {"action": "created", "task_id": 1}]


def test_socket_websocket_rejects_invalid_token(environment):
    c, *_ = environment
    with c.websocket_connect("/socket.io/?EIO=4&transport=websocket", headers={"Upgrade": "websocket", "Connection": "Upgrade"}) as ws:
        assert ws.receive_text().startswith('0{')
        ws.send_text('40{"token":"invalid"}')
        assert ws.receive_text().startswith('44')


@pytest.mark.parametrize("query", ["ab", "   ", "x"*201])
def test_address_query_validation(environment, monkeypatch, query):
    c, *_ = environment
    search=AsyncMock()
    monkeypatch.setattr(m.api.state.geocoder,'search',search)
    assert c.get('/geocode',params={'q':query}).status_code==422


def test_address_search_requires_auth(environment):
    c, *_ = environment
    m.api.dependency_overrides.clear()
    assert c.get('/geocode?q=Astana').status_code==401


def test_address_search_results(environment, monkeypatch):
    c, *_ = environment
    result={'label':'Baiterek, Astana','latitude':51.1232,'longitude':71.4288}
    monkeypatch.setattr(m.api.state.geocoder,'search',AsyncMock(return_value=[result]))
    response=c.get('/geocode?q=Baiterek')
    assert response.status_code==200
    assert response.json()['results']==[result]
    m.api.state.geocoder.search.assert_awaited_once_with('Baiterek','dispatcher')


@pytest.mark.parametrize('kind,status', [('busy',429),('offline',503)])
def test_address_search_error_contract(environment, monkeypatch, kind, status):
    c, *_ = environment
    error=m.SearchBusy() if kind=='busy' else m.SearchUnavailable()
    monkeypatch.setattr(m.api.state.geocoder,'search',AsyncMock(side_effect=error))
    result=c.get('/geocode?q=Astana')
    assert result.status_code==status
    assert 'PhotonSearch' not in result.text
    if status==429: assert result.headers['retry-after']=='5'


def test_statistics_group_multiple_statuses_per_expeditor(environment):
    c, db, *_ = environment
    async def rows(sql,*args):
        if 'GROUP BY' in sql:
            return [{'expeditor_id':1,'status':'in_progress','count':2},
                    {'expeditor_id':1,'status':'completed','count':3},
                    {'expeditor_id':2,'status':'completed','count':1}]
        return []
    db.fetch.side_effect=rows
    db.fetchval.return_value=6
    response=c.get('/tasks?expeditor_id=1')
    assert response.status_code==200
    assert response.json()['expeditor_counts']=={'1':5,'2':1}
    assert response.json()['status_counts']=={'in_progress':2,'completed':4}

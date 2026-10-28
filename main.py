"""Shared dispatcher API. Run with: uvicorn main:app --reload."""
from contextlib import asynccontextmanager
from datetime import date as Date
import logging
import asyncio
import time
import os

import asyncpg
import socketio
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from app.config import allowed_origins, validate_settings
from app.schemas import TaskCreate, TaskResponse, TaskPage, TaskStatus, Token
from app.security import create_access_token, decode_username, decode_claims, get_password_hash, verify_password
from app import repository

logger = logging.getLogger(__name__)
session_expiry_tasks = {}
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=allowed_origins())


@asynccontextmanager
async def lifespan(application):
    validate_settings()
    application.state.pool = await asyncpg.create_pool(
        dsn=os.environ["DATABASE_URL"], min_size=1, max_size=10,
        command_timeout=15, server_settings={"timezone": "UTC"},
    )
    try:
        yield
    finally:
        pending = list(session_expiry_tasks.values())
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        session_expiry_tasks.clear()
        await sio.shutdown()
        await application.state.pool.close()


api = FastAPI(title="Expeditor Tracker", lifespan=lifespan)
api.add_middleware(CORSMiddleware, allow_origins=allowed_origins(),
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_connection(request: Request):
    async with request.app.state.pool.acquire() as conn:
        yield conn


@api.exception_handler(asyncpg.PostgresError)
async def database_error(request, exc):
    logger.error("Database operation failed", exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(status_code=503, content={"detail": "Database operation unavailable"})


async def get_current_user(token: str = Depends(oauth2_scheme), conn=Depends(get_connection)):
    username = decode_username(token)
    user = await conn.fetchrow("SELECT username FROM users WHERE username=$1", username)
    if user is None:
        raise HTTPException(status_code=401, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    return dict(user)


@api.post("/token", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends(), conn=Depends(get_connection)):
    user = await conn.fetchrow("SELECT username, password FROM users WHERE username=$1", form.username)
    if not user or not verify_password(form.password, user["password"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
    return {"access_token": create_access_token({"sub": user["username"]}), "token_type": "bearer"}


@api.get("/tasks", response_model=TaskPage)
async def get_tasks(expeditor_id: int | None = Query(None, gt=0),
                    status: TaskStatus | None = None, date: Date | None = None,
                    task_id: int | None = Query(None, gt=0),
                    page: int = Query(1, ge=1), per_page: int = Query(10, ge=1, le=100),
                    current_user: dict = Depends(get_current_user), conn=Depends(get_connection)):
    return await repository.list_tasks(conn, page=page, per_page=per_page,
        expeditor_id=expeditor_id, status=status, date=date, task_id=task_id)


@api.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, current_user: dict = Depends(get_current_user), conn=Depends(get_connection)):
    task = await repository.get_task(conn, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return dict(task)


async def publish_change(action, task_id):
    # A committed database write remains successful if realtime delivery fails.
    # Clients can always resync by fetching /tasks on reconnect.
    try:
        await sio.emit("tasks_changed", {"action": action, "task_id": task_id}, room="dispatchers")
    except Exception:
        logger.exception("Realtime notification failed for task %s", task_id)


@api.post("/tasks")
async def create_task(task: TaskCreate, current_user: dict = Depends(get_current_user), conn=Depends(get_connection)):
    task_id = await repository.create_task(conn, task)
    await publish_change("created", task_id)
    return {"id": task_id, "message": "Task created"}


@api.put("/tasks/{task_id}")
async def update_task(task_id: int, task: TaskCreate, current_user: dict = Depends(get_current_user), conn=Depends(get_connection)):
    result = await repository.update_task(conn, task_id, task)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await publish_change("updated", result)
    return {"id": result, "message": "Task updated"}


@api.delete("/tasks/{task_id}")
async def delete_task(task_id: int, current_user: dict = Depends(get_current_user), conn=Depends(get_connection)):
    result = await repository.delete_task(conn, task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await publish_change("deleted", result)
    return {"message": f"Task {task_id} deleted successfully"}


@sio.event
async def connect(sid, environ, auth=None):
    token = auth.get("token", "") if isinstance(auth, dict) else ""
    try:
        payload = decode_claims(token)
        username = payload["sub"]
        async with api.state.pool.acquire() as conn:
            user = await conn.fetchrow("SELECT username FROM users WHERE username=$1", username)
        if user is None:
            return False
    except HTTPException:
        return False
    except (asyncpg.PostgresError, OSError):
        logger.exception("Socket authentication unavailable")
        return False
    # Dispatcher sessions share all task changes. Expired sessions must reauthenticate.
    await sio.save_session(sid, {"username": username, "expires_at": payload["exp"]})
    await sio.enter_room(sid, "dispatchers")
    task = asyncio.create_task(expire_session(sid, max(0, payload["exp"] - time.time())))
    session_expiry_tasks[sid] = task
    task.add_done_callback(lambda completed: session_expiry_tasks.pop(sid, None))


@sio.event
async def disconnect(sid, reason=None):
    task = session_expiry_tasks.pop(sid, None)
    if task is not None and task is not asyncio.current_task():
        task.cancel()


async def expire_session(sid, delay):
    await sio.sleep(delay)
    if sio.manager.is_connected(sid, "/"):
        await sio.disconnect(sid)


# Wrap the whole FastAPI app so /socket.io resolves once, without nested mounts.
app = socketio.ASGIApp(sio, other_asgi_app=api, socketio_path="socket.io")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

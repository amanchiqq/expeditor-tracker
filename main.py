from fastapi import FastAPI, WebSocket, Query
from databases import Database
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, DateTime
import socketio
from datetime import datetime
import json
    
# Конфигурация базы данных
DATABASE_URL = "postgresql://localhost/expeditor_db"
database = Database(DATABASE_URL)
metadata = MetaData()

# Определение таблицы задач
tasks = Table(
    "tasks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("expeditor_id", Integer),
    Column("description", String),
    Column("latitude", Float),
    Column("longitude", Float),
    Column("created_at", DateTime, default=datetime.utcnow),
)

# Инициализация FastAPI и Socket.IO
app = FastAPI()
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app.mount("/socket.io", socketio.ASGIApp(sio))

# Создание таблиц
engine = create_engine(DATABASE_URL)
metadata.create_all(engine)

# Подключение к базе данных
@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

# API: Получить все задачи
@app.get("/tasks")
async def get_tasks(expeditor_id: int = Query(None)):
    query = tasks.select()
    if expeditor_id is not None:
        query = query.where(tasks.c.expeditor_id == expeditor_id)
    return await database.fetch_all(query)

# API: Создать задачу
@app.post("/tasks")
async def create_task(task: dict):
    query = tasks.insert().values(
        expeditor_id=task["expeditor_id"],
        description=task["description"],
        latitude=task["latitude"],
        longitude=task["longitude"],
    )
    last_id = await database.execute(query)
    return {"id": last_id, **task}

# WebSocket: Обновление геолокации
@sio.event
async def location_update(sid, data):
    query = tasks.update().where(tasks.c.id == data["task_id"]).values(
        latitude=data["latitude"], longitude=data["longitude"]
    )
    await database.execute(query)
    await sio.emit("location_update", data)  # Отправка обновления всем клиентам
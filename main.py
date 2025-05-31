from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from databases import Database
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, DateTime
from datetime import datetime
import socketio

# FastAPI app
app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database configuration
DATABASE_URL = "postgresql://localhost/expeditor_db"
database = Database(DATABASE_URL)
metadata = MetaData()

# Define tasks table
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

# Socket.IO server
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app.mount("/socket.io", socketio.ASGIApp(sio))

# Database connection
@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

# API endpoints
@app.get("/tasks")
async def get_tasks(expeditor_id: int = Query(None)):
    query = tasks.select()
    if expeditor_id is not None:
        query = query.where(tasks.c.expeditor_id == expeditor_id)
    return await database.fetch_all(query)

@app.post("/tasks")
async def create_task(task: dict):
    query = tasks.insert().values(
        expeditor_id=task["expeditor_id"],
        description=task["description"],
        latitude=task["latitude"],
        longitude=task["longitude"],
        created_at=datetime.utcnow(),
    )
    last_record_id = await database.execute(query)
    return {**task, "id": last_record_id}

# WebSocket handler
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

@sio.on("location_update")
async def location_update(sid, data):
    print(f"Location update received: {data}")
    query = tasks.update().where(tasks.c.id == data["task_id"]).values(
        latitude=data["latitude"],
        longitude=data["longitude"]
    )
    await database.execute(query)
    await sio.emit("location_update", data)  # Broadcast to all clients
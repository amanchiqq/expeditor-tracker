from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import socketio
import asyncpg
from pydantic import BaseModel
import uvicorn
from contextlib import asynccontextmanager

# Инициализация FastAPI
app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация Socket.IO
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins=["http://localhost:8080"])
sio_app = socketio.ASGIApp(sio)

# Монтируем Socket.IO на FastAPI
app.mount("/socket.io", sio_app)

# Lifespan для управления подключением Socket.IO
@asynccontextmanager
async def lifespan(app):
    yield
    # Здесь можно добавить очистку, если нужно

app.router.lifespan_context = lifespan

# Модель задачи
class Task(BaseModel):
    expeditor_id: int
    description: str
    latitude: float
    longitude: float

# Подключение к базе
async def get_db_connection():
    try:
        conn = await asyncpg.connect(
            user='aman',  # Замени на твоего пользователя PostgreSQL
            password='5566',  # Замени на актуальный пароль
            database='expeditor_db',
            host='localhost'
        )
        return conn
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

# Получение всех задач
@app.get("/tasks")
async def get_tasks(expeditor_id: int = None):
    conn = await get_db_connection()
    try:
        if expeditor_id is not None:
            tasks = await conn.fetch("SELECT * FROM tasks WHERE expeditor_id = $1", expeditor_id)
        else:
            tasks = await conn.fetch("SELECT * FROM tasks")
        return [dict(task) for task in tasks]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tasks: {str(e)}")
    finally:
        await conn.close()

# Добавление задачи
@app.post("/tasks")
async def add_task(task: Task):
    conn = await get_db_connection()
    try:
        query = """
            INSERT INTO tasks (expeditor_id, description, latitude, longitude)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """
        result = await conn.fetchrow(query, task.expeditor_id, task.description, task.latitude, task.longitude)
        new_task = dict(result)
        await sio.emit("location_update", {"task_id": new_task["id"], "latitude": new_task["latitude"], "longitude": new_task["longitude"]})
        return new_task
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding task: {str(e)}")
    finally:
        await conn.close()

# Обработчик подключения Socket.IO
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

# Запуск сервера
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
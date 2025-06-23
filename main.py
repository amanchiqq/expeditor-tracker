from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
from contextlib import asynccontextmanager
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel
import socketio
from datetime import datetime, timedelta
import uvicorn
import logging
import os

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Инициализация FastAPI
app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройка констант
SECRET_KEY = os.environ.get("SECRET_KEY", "your-very-secure-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Инициализация Socket.IO
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins=["http://localhost:8080", "http://127.0.0.1:8080"])
sio_app = socketio.ASGIApp(sio)

# Монтируем Socket.IO на FastAPI
app.mount("/socket.io", sio_app)

# Lifespan для управления подключением Socket.IO
@asynccontextmanager
async def lifespan(app):
    yield

app.router.lifespan_context = lifespan

# Модель задачи
class TaskCreate(BaseModel):
    expeditor_id: int
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    status: str | None = "in_progress"
    eta: str | None = None

class TaskResponse(BaseModel):
    id: int
    expeditor_id: int
    description: str | None
    latitude: float | None
    longitude: float | None
    created_at: str
    status: str | None
    eta: str | None

# Модель пользователя
class User(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# Функция хеширования пароля
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# Функция создания токена
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Проверка токена
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return {"username": username}

# Подключение к базе
async def get_db_connection():
    try:
        conn = await asyncpg.connect(
            user='aman',
            password='5566',
            database='expeditor_db',
            host='localhost'
        )
        logger.info("Database connection established")
        return conn
    except asyncpg.PostgresError as e:
        logger.error(f"Database connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

# Проверка пользователя в базе
async def authenticate_user(username: str, password: str):
    conn = await get_db_connection()
    try:
        user = await conn.fetchrow("SELECT username, password FROM users WHERE username = $1", username)
        if user and verify_password(password, user['password']):
            logger.info(f"User {username} authenticated")
            return {"username": user['username']}
        logger.warning(f"Authentication failed for {username}")
        return None
    finally:
        await conn.close()

# Эндпоинт для логина
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    logger.info(f"Token generated for {user['username']}")
    return {"access_token": access_token, "token_type": "bearer"}

# Получение всех задач
from datetime import datetime
@app.get("/tasks")
async def get_tasks(expeditor_id: int = None, status: str = None, date: str = None, page: int = 1, per_page: int = 10, current_user: dict = Depends(get_current_user)):
    conn = await get_db_connection()
    try:
        offset = (page - 1) * per_page
        query = "SELECT * FROM tasks"
        params = [per_page, offset]  # $1 - per_page, $2 - offset
        conditions = []
        param_count = 2  # Начало фильтров с $3

        if expeditor_id is not None:
            conditions.append(f"expeditor_id = ${param_count + 1}")
            params.append(expeditor_id)
            param_count += 1
        if status is not None:
            conditions.append(f"status = ${param_count + 1}")
            params.append(status)
            param_count += 1
        if date is not None:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                conditions.append(f"DATE(created_at) = ${param_count + 1}")
                params.append(date_obj)
                param_count += 1
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY id ASC LIMIT $1 OFFSET $2"
        logger.debug(f"Executing query: {query}, params: {params}")
        tasks = await conn.fetch(query, *params)

        total_query = "SELECT COUNT(*) FROM tasks"
        total_params = params[2:]  # Только параметры фильтров
        if conditions:
            total_query += " WHERE " + " AND ".join(conditions)
        logger.debug(f"Executing total_query: {total_query}, total_params: {total_params}")
        total = await conn.fetchval(total_query, *total_params) or 0

        logger.debug(f"Fetched tasks: {tasks}, params: {params}, total_params: {total_params}")
        return {
            "tasks": [dict(task) for task in tasks],
            "total": total,
            "page": page,
            "per_page": per_page
        }
    except asyncpg.PostgresError as e:
        logger.error(f"Database error in get_tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Error in get_tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        await conn.close()
             
# Получение задачи по ID
@app.get("/tasks/{task_id}")
async def get_task(task_id: int, current_user: dict = Depends(get_current_user)):
    conn = await get_db_connection()
    try:
        task = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return dict(task)
    except Exception as e:
        logger.error(f"Error in get_task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        await conn.close()

# Добавление задачи
@app.post("/tasks")
async def create_task(task: TaskCreate, current_user: dict = Depends(get_current_user)):
    conn = await get_db_connection()
    task.eta = datetime.fromisoformat(eta) if eta else None
    try:
        task_id = await conn.fetchval("SELECT nextval('tasks_id_seq')") or uuid.uuid4().int & (1<<31)-1
        created_at = datetime.now().astimezone().isoformat()
        query = """
            INSERT INTO tasks (id, expeditor_id, description, latitude, longitude, status, created_at, eta)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id
        """
        result = await conn.fetchval(query, task_id, task.expeditor_id, task.description, task.latitude, task.longitude, task.status, created_at, task.eta)
        logger.debug(f"Created task with ID: {result}")
        await conn.close()
        return {"id": result, "message": "Task created"}
    except Exception as e:
        logger.error(f"Error in create_task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        await conn.close()

# Обновление задачи
@app.put("/tasks/{task_id}")
async def update_task(task_id: int, task: TaskCreate, current_user: dict = Depends(get_current_user)):
    conn = await get_db_connection()
    try:
        task_exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM tasks WHERE id = $1)", task_id)
        if not task_exists:
            raise HTTPException(status_code=404, detail="Task not found")
        eta_value = task.eta if task.eta else None  # Преобразуем пустую строку в None
        query = """
            UPDATE tasks SET expeditor_id = $2, description = $3, latitude = $4, longitude = $5, status = $6, eta = $7
            WHERE id = $1 RETURNING id
        """
        result = await conn.fetchval(query, task_id, task.expeditor_id, task.description, task.latitude, task.longitude, task.status, eta_value)
        logger.debug(f"Updated task with ID: {result}")
        await conn.close()
        return {"id": result, "message": "Task updated"}
    except Exception as e:
        logger.error(f"Error in update_task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        await conn.close()

# Эндпоинт для удаления
@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int, current_user: dict = Depends(get_current_user)):
    conn = await get_db_connection()
    try:
        task = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await conn.execute("DELETE FROM tasks WHERE id = $1", task_id)
        logger.debug(f"Deleted task with ID: {task_id}")
        return {"message": f"Task {task_id} deleted successfully"}
    except Exception as e:
        logger.error(f"Error in delete_task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        await conn.close()

# Обработчики Socket.IO

        
@asynccontextmanager
async def lifespan(app):
    asyncio.create_task(location_update_emitter())
    yield

async def location_update_emitter():
    while True:
        await sio.emit("location_update", {
            "id": 1,
            "latitude": 51.12 + (0.01 * (datetime.now().second % 10)),
            "longitude": 71.40 + (0.01 * (datetime.now().minute % 10))
        })
        await asyncio.sleep(5)

# Обработчики Socket.IO
@sio.event
async def connect(sid, environ, auth=None):
    token = environ.get('HTTP_AUTHORIZATION', '').replace('Bearer ', '')
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.info(f"Client connected: {sid}")
    except JWTError:
        logger.warning(f"Unauthorized connection attempt: {sid}")
        await sio.disconnect(sid)
        return False

@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
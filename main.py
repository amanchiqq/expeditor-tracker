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

# Инициализация FastAPI
app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],  # Добавлен 127.0.0.1
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройка констант
SECRET_KEY = "amanaman"  # Замени на безопасный ключ
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
class Task(BaseModel):
    expeditor_id: int
    description: str
    latitude: float
    longitude: float

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
        return conn
    except asyncpg.PostgresError as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

# Проверка пользователя в базе
async def authenticate_user(username: str, password: str):
    conn = await get_db_connection()
    try:
        user = await conn.fetchrow("SELECT username, password FROM users WHERE username = $1", username)
        if user and verify_password(password, user['password']):
            return {"username": user['username']}
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
    return {"access_token": access_token, "token_type": "bearer"}

# Получение всех задач
@app.get("/tasks")
async def get_tasks(expeditor_id: int = None, page: int = 1, per_page: int = 10, current_user: dict = Depends(get_current_user)):
    conn = await get_db_connection()
    try:
        offset = (page - 1) * per_page
        query = "SELECT * FROM tasks"
        params = [per_page, offset]
        if expeditor_id:
            query += " WHERE expeditor_id = $1"
            params.insert(0, expeditor_id)
            tasks = await conn.fetch(query + " LIMIT $2 OFFSET $3", *params)
            total = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE expeditor_id = $1", expeditor_id)
        else:
            tasks = await conn.fetch(query + " LIMIT $1 OFFSET $2", *params)
            total = await conn.fetchval("SELECT COUNT(*) FROM tasks")
        return {
            "tasks": [{"id": task["id"], "expeditor_id": task["expeditor_id"], "description": task["description"], "latitude": task["latitude"], "longitude": task["longitude"]} for task in tasks],
            "total": total,
            "page": page,
            "per_page": per_page
        }
    finally:
        await conn.close()

# Добавление задачи
@app.post("/tasks")
async def create_task(task: Task, current_user: dict = Depends(get_current_user)):
    conn = await get_db_connection()
    try:
        result = await conn.fetchval(
            "INSERT INTO tasks (expeditor_id, description, latitude, longitude) VALUES ($1, $2, $3, $4) RETURNING id",
            task.expeditor_id, task.description, task.latitude, task.longitude
        )
        await conn.close()
        return {"id": result, "message": "Task created"}
    finally:
        await conn.close()

# Обработчики Socket.IO
@sio.event
async def connect(sid, environ, auth=None):
    token = environ.get('HTTP_AUTHORIZATION', '').replace('Bearer ', '')
    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"Client connected: {sid}")
    except JWTError:
        await sio.disconnect(sid)
        return False

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
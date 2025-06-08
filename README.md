# Expeditor Tracker
Трекер для экспедиторов в Астане.
## Установка
- Python 3.9+
- PostgreSQL
- Node.js (for Tailwind CSS compilation, optional)
- `pip install -r requirements.txt`.
- `uvicorn main:app --reload`.
- `python -m http.server 8080`.
## Функции
- Карта с маркерами и labels.
- Фильтр по expeditor_id.
- Геокодинг (2GIS).
- WebSocket.

# Отчёт по проекту Expeditor Tracker

## Завершение недели 2
- Маркеры с метками по клику.
- Геокодинг без Suggest API (экономия лимитов 2GIS).
- WebSocket обновляет маркеры.
- Демо готово: [expeditor-tracker-demo-compressed.mp4](expeditor-tracker-demo-compressed.mp4).


# Expeditor Tracker

A web application to track tasks for expeditors in Astana using 2GIS maps.

## Features
- User authentication (login with `user1`/`password`).
- Add, view, and delete tasks with coordinates.
- Display tasks on a map (Astana region only).
- Filter tasks by `expeditor_id`.
- Pagination for task list.
- Chart visualization of tasks by expeditor.

## Notes
- Tasks are loaded automatically on page load if a valid token is present in `localStorage`. Log in to ensure the latest data.
- 
## Setup
1. **Clone the repository:**
   ```bash
   git clone https://github.com/amanchiqq/expeditor-tracker.git
   cd expeditor-tracker

2. **Create a virtual environment and install dependencies::**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt

3. **Set up PostgreSQL database::**
      Create the database:
   ```bash
   psql -U postgres
   CREATE DATABASE expeditor_db;
   \q
   ```
   Connect and create tables:
   ```bash
   psql -U aman -d expeditor_db -h localhost
   ```
   Run the following SQL:
   ```sql
   CREATE TABLE users (
    username VARCHAR(50) PRIMARY KEY,
    password VARCHAR(255) NOT NULL
   );

   CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    expeditor_id INTEGER NOT NULL,
    description VARCHAR(255),
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );

   INSERT INTO users (username, password) VALUES ('user1', '$2b$12$...'); -- Use hashed password (e.g., via bcrypt)

4. **Run the backend:**
   ```bash
   uvicorn main:app --reload

5. **Run the frontend::**
   ```bash
   python -m http.server 8080

6. **Open the app:**
   
   Go to http://localhost:8080/index.html and log in with user1/password.

   

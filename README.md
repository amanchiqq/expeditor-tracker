# Expeditor Tracker

A web application designed to track tasks for expeditors in Astana using 2GIS maps. This project combines a FastAPI backend with a PostgreSQL database and a frontend built with HTML, CSS (Tailwind), and JavaScript, featuring interactive maps and real-time updates via WebSocket.

## Features
- **User Authentication:** Secure login with JWT tokens using `user1`/`password`.
- **Task Management:** Add, view, and delete tasks with coordinates (latitude and longitude).
- **Map Visualization:** Display tasks on a 2GIS map, limited to the Astana region (latitude 51–52, longitude 71–72), with clickable markers and temporary labels.
- **Filtering:** Filter tasks by `expeditor_id` for targeted views.
- **Pagination:** Navigate through tasks with 10 per page using "Previous" and "Next" buttons.
- **Chart Visualization:** Display a bar chart of tasks distributed by expeditor ID using Chart.js.
- **Geocoding:** Convert Astana addresses to coordinates using 2GIS Suggest API.
- **Real-Time Updates:** WebSocket integration for live marker updates (currently basic implementation).

## How It Works
- **Backend (FastAPI):** Handles API requests for authentication (`/token`), task CRUD operations (`/tasks`, `/tasks/{task_id}`), and WebSocket connections. Data is stored in a PostgreSQL database.
- **Frontend:** A single-page application (`index.html`) with a map, task table, form for adding tasks, and a chart. Tasks are fetched after login, and map markers update dynamically.
- **Workflow:**
  1. Log in to obtain a JWT token.
  2. Add tasks with coordinates or use geocoding to find them.
  3. View tasks on the map and table, filter or paginate as needed.
  4. Delete tasks or refresh data manually.
  5. WebSocket updates markers in real-time (pending full implementation).

## Setup

### Prerequisites
- Python 3.9+
- PostgreSQL
- Node.js (optional, for Tailwind CSS compilation)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/amanchiqq/expeditor-tracker.git
   cd expeditor-tracker
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


## Notes
- Tasks are loaded only after login. If a valid token exists in `localStorage`, the app may attempt to load tasks immediately—log in to ensure the latest data.
- The map displays only tasks within Astana coordinates (latitude 51–52, longitude 71–72).
- Use a secure `SECRET_KEY` in production (currently set to "amanaman" for development).
- Geocoding uses 2GIS API with a demo key; replace it with your own for production.

## Project Report: Expeditor Tracker

### Completion of Week 2
- **Achievements:**
  - Implemented markers with clickable labels that display for 3 seconds.
  - Added geocoding without Suggest API to save 2GIS API limits.
  - Integrated WebSocket to update markers in real-time.
  - Created a demo video: [expeditor-tracker-demo-compressed.mp4](expeditor-tracker-demo-compressed.mp4).

### Completion of Week 3
- **Achievements:**
  - Completed task CRUD operations (add, view, delete).
  - Added pagination and filtering by `expeditor_id`.
  - Integrated a chart to visualize task distribution.
  - Ensured tasks load only after login by removing automatic `fetchTasks()` call.
- **Testing (Day 5, 8 June 2025):**
  - Added a task via the form: Works.
  - Deleted a task via the "Delete" button: Works.
  - Switched pages with "Previous/Next": Works.
  - Applied filter by `expeditor_id`: Works.
  - Checked console for errors: None found.

## Problems and Solutions
- **Initial Task Loading:** Tasks loaded automatically on page start due to `fetchTasks()` being called at script end. **Solution:** Removed the automatic call, ensuring tasks load only after login.
- **Pagination Error:** Requests without `expeditor_id` returned a 500 error due to SQL issues. **Solution:** Fixed SQL query logic in `get_tasks` to handle cases with and without filters.
- **WebSocket Disconnects:** Clients disconnected due to token issues. **Solution:** Ensured token is passed correctly via `socket.auth.token`.

## Future Plans
- **Enhance Functionality:** Add task editing and status updates.
- **Geolocation Integration:** Use user geolocation to display their position and calculate routes to tasks.
- **Admin Panel:** Develop an admin interface (optional) to manage users and tasks.
- **WebSocket Improvements:** Fully implement real-time updates for all task changes.

## API Endpoints
- `POST /token` - Login and get a JWT token.
- `GET /tasks` - Get tasks (supports `expeditor_id`, `page`, and `per_page` query params).
- `POST /tasks` - Add a new task.
- `DELETE /tasks/{task_id}` - Delete a task by ID.

   

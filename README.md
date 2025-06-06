# Expeditor Tracker
Трекер для экспедиторов в Астане.
## Установка
- Python 3.11, PostgreSQL.
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
- User authentication (login).
- Add, view, and delete tasks with coordinates.
- Display tasks on a map (Astana only).
- Filter tasks by expeditor ID.
- Pagination for task list.

## Notes
- Tasks are loaded automatically on page load if a valid token is present in `localStorage`. Log in to ensure the latest data.
- 
## Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/amanchiqq/expeditor-tracker.git
   cd expeditor-tracker

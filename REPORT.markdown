# Отчёт по проекту Expeditor Tracker

## Цель
Создать приложение для отслеживания экспедиторов с бэкендом (API, WebSocket, база) и веб-интерфейсом (карта, список задач, график) для Астаны.

## Неделя 1: Бэкенд

### Выполненные задачи
- **Окружение**: Python 3.11, `venv`, PostgreSQL (`expeditor_db`).
- **FastAPI**: `GET /tasks`, `POST /tasks`, Swagger UI.
- **WebSocket**: `location_update`.
- **База**: Таблица `tasks` (20 задач).
- **Git**: Репозиторий `https://github.com/amanchiqq/expeditor-tracker`.

### Проблемы и решения
- `ModuleNotFoundError: asyncpg` → `pip install asyncpg`.
- WebSocket 403 → `?EIO=4`.
- `405 Method Not Allowed` → CORS.

## Неделя 2: Веб-интерфейс

### Выполненные задачи
- **Карта**: 2GIS MapGL, центрирована на Астане (`51.16, 71.47`).
- **Интерфейс**: Форма, фильтр, таблица, график (Chart.js).
- **API**: Фильтр по `expeditor_id`, добавление задач.
- **Геокодинг**: Suggest API для автодополнения.
- **Git**: `REPORT.md`.

### Проблемы и решения
- **Точки**: `TypeError` с Clusterer → Убрана кластеризация, локальная иконка.
- **Геокодинг**: 404 → Проверяется написание адреса, добавлено автодополнение.
- **Blob ошибки**: Локальная иконка, очистка кэша.
- **Координаты**: Фильтр по Астане (`51-52, 71-72`).

### План
- Исправить геокодинг (поддержка 2GIS).
- Отобразить точки на карте.
- Подготовить демо.

# Project Report: Expeditor Tracker

## Summary
The Expeditor Tracker project was successfully completed, implementing a web application for task management with map visualization. The backend was built using FastAPI with PostgreSQL, and the frontend used HTML, CSS (Tailwind), and JavaScript with 2GIS Map API.

## Achievements
- Full CRUD functionality for tasks.
- Interactive map and chart integration.
- Pagination, filtering, and login system.
- Real-time WebSocket updates (basic).

## Challenges
- Resolved SQL errors in pagination.
- Fixed automatic task loading by removing `fetchTasks()` call.
- Managed WebSocket disconnects with proper token handling.

## Future Work
- Add geolocation and route calculation.
- Consider an admin panel for enhanced management.
- Improve WebSocket for full real-time functionality.
    
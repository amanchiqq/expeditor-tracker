# Отчёт по проекту Expeditor Tracker

## Цель
Создать приложение для отслеживания экспедиторов с бэкендом (API, WebSocket, база) и веб-интерфейсом (карта, список задач, график) для Астаны.

## Неделя 1: Бэкенд

### Выполненные задачи
- **Окружение**: Python 3.11, `venv`, PostgreSQL (`expeditor_db`).
- **FastAPI**: `GET /tasks`, `POST /tasks`, Swagger UI.
- **WebSocket**: `location_update` для обновления координат.
- **База**: Таблица `tasks` с тестовыми данными (>10 задач).
- **Git**: Репозиторий `https://github.com/amanchiqq/expeditor-tracker`.

### Проблемы и решения
- `ModuleNotFoundError: asyncpg` → `pip install asyncpg`.
- WebSocket 403 → Добавлено `?EIO=4`.
- `405 Method Not Allowed` → Настроен CORS.

## Неделя 2: Веб-интерфейс

### Выполненные задачи
- **Карта**: 2GIS MapGL, центрирована на Астане (`51.16, 71.47`).
- **Интерфейс**: Форма, фильтр, таблица, график (Chart.js).
- **API**: Фильтр по `expeditor_id`, CORS.
- **Геокодинг**: Запрос к 2GIS Geocoder API с `city_id` (в процессе).
- **Кластеризация**: Добавлена через `@2gis/mapgl-clusterer`.
- **Git**: `REPORT.md` обновлён.

### Проблемы и решения
- **Точки не отображаются**: `TypeError: Attempted to assign to readonly property` → Клонирование задач.
- **Геокодинг**: 403 → Проверяется демо-ключ для Geocoder API.
- **Фильтр**: Отладка через F12.

### План
- Подключить ключ для Geocoding API.
- Исправить отображение маркеров и фильтра.
- Тестировать геокодинг («Кабанбай Батыра, 8»).
- Завершить демо.
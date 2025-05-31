# Отчёт по проекту Expeditor Tracker

## Цель
Создать приложение для отслеживания экспедиторов с бэкендом (API, WebSocket, база) и веб-интерфейсом (карта, список задач, график), адаптированное для Астаны.

## Неделя 1: Бэкенд

### Выполненные задачи
- **Окружение**:
  - Python 3.11, виртуальная среда (`venv`).
  - Зависимости: `fastapi`, `uvicorn`, `databases`, `asyncpg`, `psycopg2-binary`, `python-socketio` (`requirements.txt`).
  - PostgreSQL (`expeditor_db`) через `brew`.
- **FastAPI**:
  - `main.py` с API:
    - `GET /tasks`: Список задач.
    - `POST /tasks`: Создание задачи.
  - Swagger UI: `http://localhost:8000/docs`.
- **WebSocket**:
  - Событие `location_update` обновляет координаты.
  - Тестирование через `wscat`: ошибка 403 исправлена.
- **База**:
  - Таблица `tasks` (`id`, `expeditor_id`, `description`, `latitude`, `longitude`, `created_at`).
  - Тестовые данные для Астаны (например, 51.1667, 71.4667).
- **Git**:
  - Репозиторий: `/Users/aman/expeditor-tracker`.
  - Файлы: `main.py`, `requirements.txt`, `.gitignore`, `.gitattributes`.
  - Удалены: `newfile.txt`, `.DS_Store`.

### Проблемы и решения
- `ModuleNotFoundError: asyncpg` → `pip install asyncpg`.
- WebSocket 403 → Подключение через `?EIO=4`.

### Вывод
Бэкенд готов: API, WebSocket, база работают. Код на GitHub.

## Неделя 2: Веб-интерфейс (начало)

### Выполненные задачи
- **Карта**:
  - Выбрана 2GIS MapGL JS API для детализированных карт Астаны.
  - Создан `index.html`:
    - Карта центрирована на Астане (51.16, 71.47).
    - Маркеры для задач из `/tasks`.
    - WebSocket обновляет координаты.
- **Интерфейс**:
  - Форма для добавления задач.
  - Таблица задач.
  - Бар-чарт (Chart.js) по `expeditor_id`.
  - Фильтр по `expeditor_id`.
- **API**:
  - Добавлен фильтр в `GET /tasks` (`expeditor_id`).

### План
- Тестировать 2GIS интерфейс.
- Добавить стили, кластеризацию маркеров.
- Обновить отчёт.
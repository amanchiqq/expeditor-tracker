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

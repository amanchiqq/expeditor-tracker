# Expeditor Tracker

Общий кабинет диспетчеров: задачи, фильтры, карта Астаны и обновления Socket.IO. Все авторизованные диспетчеры имеют доступ ко всем задачам. Создание пользователей выполняет администратор через CLI.

**[План реализации и критерии готовности](IMPLEMENTATION_PLAN.md).** Исторический отчёт: [REPORT.markdown](REPORT.markdown).

## Требования

Python 3.11, PostgreSQL 16, Node.js 22 для JS-тестов и необязательной сборки CSS. Один процесс API: доставка Socket.IO между несколькими workers пока не реализована.

## Установка (PowerShell)

```powershell
git clone https://github.com/amanchiqq/expeditor-tracker.git
cd expeditor-tracker
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -r requirements-dev.txt
```

Создайте отдельную базу PostgreSQL и пользователя с правами на неё. Приложение не создаёт сервер БД. Затем задайте переменные в текущем терминале:

```powershell
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(48))"
$env:DATABASE_URL = 'postgresql://tracker:YOUR_PASSWORD@localhost:5432/expeditor_db'
$env:CORS_ORIGINS = 'http://localhost:8080,http://127.0.0.1:8080'
python scripts/migrate.py
python scripts/create_user.py
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Пароль вводится скрыто; стандартного аккаунта/пароля нет. Для постоянного окружения сохраните секрет в менеджере секретов или настройках сервиса: новая генерация при каждом запуске аннулирует прежние JWT. Файл .env.example описывает переменные; автоматической загрузки .env нет. Для Bash используйте export вместо синтаксиса PowerShell.

## Интерфейс

В другом терминале из папки проекта:

```powershell
python -m http.server 8080 --bind 127.0.0.1
```

Откройте http://localhost:8080. index.html ведёт на dashboard.html, без токена выполняется переход на login.html. Успешный вход действует 30 минут; истёкшая сессия требует повторного входа.

В frontend-config.js заданы публичный URL API и ключи 2GIS. По умолчанию API использует хост страницы и порт 8000. Для другого сервера измените apiBase и разрешённые CORS origins. Ключи карты/geocoding нужно получить и настроить самостоятельно, ограничив разрешённые домены; это публичные браузерные ключи. Работоспособность внешнего API и лимиты проверяются отдельно. Без ключей доступны таблица, CRUD и ручной ввод координат.

Таблица отображает текущую страницу, диаграмма — все задачи текущего фильтра. Карта пока отображает только задачи в диапазоне Астаны: широта 51–52, долгота 71–72. Реального источника геолокации и расчёта маршрутов пока нет.

## Даты и API

- POST /token — form-urlencoded username/password.
- GET /tasks — task_id, expeditor_id, status, date (YYYY-MM-DD, UTC), page >= 1, per_page 1…100.
- GET /tasks/{id}, POST /tasks, PUT /tasks/{id}, DELETE /tasks/{id} — Bearer JWT.
- status: in_progress или completed; expeditor_id > 0; description до 255 символов.
- latitude/longitude либо обе отсутствуют, либо обе заданы в допустимых диапазонах.
- eta: null или ISO datetime с часовым поясом. Интерфейс переводит локальный ввод в UTC.
- PUT полностью заменяет редактируемые поля; это не PATCH.
- /docs — описание HTTP API.

Socket.IO: path /socket.io, auth: {token: JWT}. Сервер публикует tasks_changed с action и task_id только в комнату авторизованных диспетчеров после успешной записи. Клиент перечитывает /tasks после события и reconnect. Нотификации не имеют гарантии доставки; ошибка отправки не отменяет уже выполненный CRUD. Синтетический location_update удалён. Изменения напрямую в БД уведомлений не создают.

## Миграции существующей базы

До запуска сделайте backup. 001_dispatcher_schema.sql поддерживает пустую БД и схему из прежнего README: добавляет status/eta, ограничения и индексы. Прежний TIMESTAMP без timezone интерпретируется как UTC. Если раньше хранилось местное время, сначала согласуйте преобразование на копии БД. Нестандартные схемы необходимо проверить отдельно.

Миграции транзакционные, применяются один раз под advisory lock, проверяют контрольную сумму. Повторный запуск безопасен. Некорректные старые записи могут нарушить новые ограничения: миграция откатится, данные автоматически не удаляются. Исправьте записи на копии и повторите проверку. Уже применённые миграции не редактируют; добавляют следующую.

## Тесты

```powershell
python -m pytest -q
node --test tests/frontend.test.cjs
```

Для настоящих интеграционных проверок задайте отдельную тестовую БД:

```powershell
$env:TEST_DATABASE_URL = 'postgresql://tracker:TEST_PASSWORD@localhost:5432/tracker_test'
python -m pytest -q
```

Интеграционные тесты создают уникальную временную схему и удаляют её после проверки; пользователь тестовой БД должен иметь право CREATE SCHEMA. Не используйте рабочую БД. Без TEST_DATABASE_URL эти две проверки явно пропускаются. GitHub Actions поднимает PostgreSQL и запускает их вместе с остальными тестами.

Локально проверены API с подменённой БД, валидация, JWT, ошибки, освобождение подключений, handshake/auth/event Socket.IO через ASGI и JS-контракты. В GitHub Actions на PostgreSQL 16 прошли все 54 Python-теста и 8 JS-проверок, включая пустую и прежнюю схемы БД. Браузерный E2E требует отдельной приёмки согласно плану.

Для разработки CSS (не требуется для Python API): npm ci, npm run build:css или npm run watch:css. node_modules не хранится в Git.

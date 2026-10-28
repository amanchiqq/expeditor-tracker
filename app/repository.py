"""Parameterized SQL shared by the HTTP endpoints."""
from datetime import datetime, time, timedelta, timezone

COLUMNS = "id, expeditor_id, description, latitude, longitude, status, created_at, eta"


def filters(expeditor_id=None, status=None, date=None, task_id=None):
    conditions, params = [], []
    for name, value in (("expeditor_id", expeditor_id), ("status", status), ("id", task_id)):
        if value is not None:
            params.append(value)
            conditions.append(f"{name} = ${len(params)}")
    if date is not None:
        start = datetime.combine(date, time.min, tzinfo=timezone.utc)
        params.extend([start, start + timedelta(days=1)])
        conditions.append(f"created_at >= ${len(params)-1} AND created_at < ${len(params)}")
    return (" WHERE " + " AND ".join(conditions) if conditions else ""), params


async def list_tasks(conn, *, page, per_page, **criteria):
    where, params = filters(**criteria)
    # One snapshot keeps total, aggregates and page consistent under concurrent edits.
    async with conn.transaction(isolation="repeatable_read", readonly=True):
        total = await conn.fetchval("SELECT COUNT(*) FROM tasks" + where, *params)
        counts = await conn.fetch("SELECT expeditor_id, COUNT(*) AS count FROM tasks" + where + " GROUP BY expeditor_id ORDER BY expeditor_id", *params)
        tasks = await conn.fetch(f"SELECT {COLUMNS} FROM tasks" + where + f" ORDER BY id ASC LIMIT ${len(params)+1} OFFSET ${len(params)+2}", *params, per_page, (page-1)*per_page)
    return {"tasks": [dict(row) for row in tasks], "total": total, "page": page, "per_page": per_page,
            "expeditor_counts": {str(row["expeditor_id"]): row["count"] for row in counts}}


async def get_task(conn, task_id):
    return await conn.fetchrow(f"SELECT {COLUMNS} FROM tasks WHERE id = $1", task_id)


async def create_task(conn, task):
    return await conn.fetchval("""INSERT INTO tasks
        (expeditor_id, description, latitude, longitude, status, eta)
        VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
        task.expeditor_id, task.description, task.latitude, task.longitude, task.status, task.eta)


async def update_task(conn, task_id, task):
    return await conn.fetchval("""UPDATE tasks SET expeditor_id=$2, description=$3,
        latitude=$4, longitude=$5, status=$6, eta=$7 WHERE id=$1 RETURNING id""",
        task_id, task.expeditor_id, task.description, task.latitude, task.longitude, task.status, task.eta)


async def delete_task(conn, task_id):
    return await conn.fetchval("DELETE FROM tasks WHERE id=$1 RETURNING id", task_id)

"""Create a dispatcher interactively, without a default password."""
import asyncio
from getpass import getpass
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asyncpg
from app.security import get_password_hash


async def create(username, password):
    hashed = get_password_hash(password)
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        await conn.execute("INSERT INTO users(username,password) VALUES($1,$2)", username, hashed)
    finally:
        await conn.close()


if __name__ == "__main__":
    username = input("Dispatcher username: ").strip()
    if not username or len(username)>50:
        raise SystemExit("Username must contain 1 to 50 characters")
    password = getpass("Password: ")
    if password != getpass("Repeat password: "):
        raise SystemExit("Passwords do not match")
    asyncio.run(create(username, password))

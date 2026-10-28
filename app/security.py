from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from app.config import validate_settings

ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain, hashed):
    if len(plain.encode("utf-8")) > 72:
        return False
    try:
        return pwd_context.verify(plain, hashed)
    except (ValueError, UnknownHashError):
        return False


def get_password_hash(password):
    if not password or len(password.encode("utf-8")) > 72:
        raise ValueError("Password must contain 1 to 72 UTF-8 bytes")
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=30))
    return jwt.encode(payload, validate_settings(), algorithm=ALGORITHM)


def decode_claims(token: str):
    try:
        payload = jwt.decode(token, validate_settings(), algorithms=[ALGORITHM], options={"require_exp": True, "require_sub": True})
        username = payload.get("sub")
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Missing subject")
        return payload
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})


def decode_username(token: str):
    return decode_claims(token)["sub"]

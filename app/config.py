"""Environment settings. Secrets are validated at application startup."""
import os


def validate_settings():
    secret = os.environ.get("SECRET_KEY", "")
    if len(secret) < 32 or secret == "your-very-secure-secret-key-here":
        raise RuntimeError("SECRET_KEY must contain at least 32 characters and must not use the example value")
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")
    return secret


def allowed_origins():
    return [value.strip() for value in os.environ.get(
        "CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080"
    ).split(",") if value.strip()]

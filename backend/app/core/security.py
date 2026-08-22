import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


class AuthError(Exception):
    """Raised for any authentication failure — invalid credentials, an
    invalid/expired/malformed token, or missing JWT configuration."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: uuid.UUID) -> str:
    if not settings.jwt_secret_key:
        raise AuthError("JWT_SECRET_KEY is not configured. Set it in your .env file to enable login.")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> uuid.UUID:
    """Returns the user id encoded in a valid, unexpired token. Raises
    AuthError for anything else — expired, malformed, wrong signature, or a
    subject that isn't a real UUID — so callers (app/api/deps.py) only need
    to catch one exception type and turn it into a clean 401."""
    if not settings.jwt_secret_key:
        raise AuthError("JWT_SECRET_KEY is not configured. Set it in your .env file to enable login.")

    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Your session has expired. Please log in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Invalid authentication token.") from exc

    subject = payload.get("sub")
    if not subject:
        raise AuthError("Invalid authentication token.")

    try:
        return uuid.UUID(subject)
    except ValueError as exc:
        raise AuthError("Invalid authentication token.") from exc

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import AuthError, decode_access_token
from app.db import crud
from app.db.models import User
from app.db.session import get_db

# auto_error=False so a missing header produces our own clean 401 message
# below, not FastAPI's default "Not authenticated" detail text.
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    token: str | None = None,
    db: Session = Depends(get_db),
) -> User:
    """`token` (query param) is a fallback for the one place a header isn't
    an option: GET /documents/{id}/file is opened by direct browser
    navigation (a new tab, so citations/downloads work) rather than a JS
    fetch() call, so it can't carry an Authorization header. Every other
    endpoint is called via apiFetch (frontend/src/api/client.js), which
    always sends the header — the query param is unused there."""
    raw_token = credentials.credentials if credentials is not None else token
    if raw_token is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        user_id = decode_access_token(raw_token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user = crud.get_user(db, user_id)
    if user is None:
        # The token is valid but the account it names doesn't exist
        # anymore — same clean 401 as any other invalid-credentials case.
        raise HTTPException(status_code=401, detail="Invalid authentication token.")

    return user

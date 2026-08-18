from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    health = {"status": "ok", "database": "unknown"}
    try:
        db.execute(text("SELECT 1"))
        health["database"] = "connected"
    except Exception as exc:
        health["status"] = "degraded"
        health["database"] = "unavailable"
        health["database_error"] = str(exc)
    return health

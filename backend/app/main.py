from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ask, conversations, documents, health, search
from app.core.config import settings

# Schema is managed by Alembic migrations (backend/alembic/), not
# create_all — run `alembic upgrade head` after pulling schema changes.
app = FastAPI(title="Personal AI Knowledge Assistant", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    # settings.allowed_origins defaults to the local Vite dev server; set
    # ALLOWED_ORIGINS in production to the deployed frontend's real origin
    # only — never "*", since allow_credentials=True is set below.
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(ask.router)
app.include_router(conversations.router)

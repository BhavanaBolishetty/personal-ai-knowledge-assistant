from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ask, auth, conversations, documents, health, search
from app.core.config import settings
from app.core.memory_diagnostics import log_memory


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Baseline for comparison against the jump logged when the embedding
    # model first loads (app/embeddings/local.py) — the embedding model is
    # NOT loaded yet at this point (it's lazy, on first use), so this
    # number is FastAPI/uvicorn/SQLAlchemy/etc. only.
    log_memory("startup")
    yield


# Schema is managed by Alembic migrations (backend/alembic/), not
# create_all — run `alembic upgrade head` after pulling schema changes.
app = FastAPI(title="Personal AI Knowledge Assistant", version="0.1.0", lifespan=lifespan)

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
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(ask.router)
app.include_router(conversations.router)

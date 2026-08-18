FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
# torch (a sentence-transformers dependency) defaults to a multi-GB
# CUDA-enabled build on Linux. This container has no GPU, so install the
# CPU-only build explicitly first — pip then sees torch is already
# satisfied and skips it when installing the rest of requirements.txt.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic

EXPOSE 8000

# Applies any pending Alembic migrations before the API starts, so Alembic
# is the single schema-management mechanism in every environment (a fresh
# `docker compose up` on an empty database works with no manual step) —
# not just for local host-side development.
#
# $PORT is honored (falling back to 8000) because Render assigns the
# listening port dynamically. --reload is dropped when ENVIRONMENT=production
# (unnecessary overhead / file-watching in a container that never changes
# after build) but kept by default so local `docker compose up` still
# live-reloads from the bind-mounted ./backend/app volume, unchanged.
CMD ["sh", "-c", "alembic upgrade head && if [ \"$ENVIRONMENT\" = production ]; then exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}; else exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --reload; fi"]

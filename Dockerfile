# syntax=docker/dockerfile:1

# Stage 1 — build the Next.js static export (frontend/out).
FROM node:20-slim AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY frontend/ ./
RUN npm run build


# Stage 2 — FastAPI runtime serving the API and the exported frontend.
FROM python:3.12-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /usr/local/bin/

# Keep the virtualenv outside /app/backend so copying the source cannot clobber it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend

# Dependencies first so the layer caches independently of application code.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY backend/ ./

# backend/db/connection.py resolves DB_PATH as <parents[2]>/db/finally.db,
# i.e. /app/db/finally.db — that directory is the volume mount target.
RUN mkdir -p /app/db

# main.py mounts backend/static/ when present; the export lands there.
COPY --from=frontend /build/out ./static

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

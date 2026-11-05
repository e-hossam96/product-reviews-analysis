# Build stage: resolve and install dependencies with uv

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_DEV=1
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/.python-version ./backend/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package backend --frozen --no-install-project

COPY backend/ ./backend/

# A Windows checkout can turn LF into CRLF, which breaks `#!/bin/sh` scripts.
RUN sed -i 's/\r$//' /app/backend/entrypoint.sh

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package backend --frozen

# Main image

FROM python:3.14-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

COPY --from=builder --chown=nonroot:nonroot /app /app

RUN mkdir -p /app/backend/logs /app/backend/data \
 && chown nonroot:nonroot /app/backend/logs /app/backend/data

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend

USER nonroot

WORKDIR /app/backend

ENTRYPOINT ["/bin/sh", "/app/backend/entrypoint.sh"]

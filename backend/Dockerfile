# syntax=docker/dockerfile:1.7

# One image per worker type, all from the same code: `app` (API, default worker, beat),
# `media` (adds FFmpeg) and `ml` (local models, with a writable cache at /models).

FROM python:3.13-slim-trixie AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app
WORKDIR /app

FROM base AS deps
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

FROM base AS app
COPY --from=deps /opt/venv /opt/venv
COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

FROM base AS media
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY --from=deps /opt/venv /opt/venv
COPY --chown=app:app . .
USER app

# Résumé parsing, embeddings and transcription dependencies arrive with Phase 3.
FROM base AS ml
ENV HF_HOME=/models/huggingface
RUN mkdir -p /models && chown app:app /models
COPY --from=deps /opt/venv /opt/venv
COPY --chown=app:app . .
USER app

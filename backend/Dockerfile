# syntax=docker/dockerfile:1.7

# One image per worker type, all from the same code: `app` (API, default worker, beat),
# `media` (adds FFmpeg), `ml` (local models, with a writable cache at /models) and
# `test` (app plus the dev tools). Code is owned by root, so the app user cannot modify it.

FROM python:3.13-slim-trixie AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app
WORKDIR /app

FROM base AS uv
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./

FROM uv AS deps
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Local models (entity recognition now; embeddings and transcription later) only go where
# they run: the ml worker and the tests.
FROM uv AS deps-ml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --group ml --no-install-project

FROM uv AS deps-dev
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --group ml --no-install-project

FROM base AS app
COPY --from=deps /opt/venv /opt/venv
COPY . .
# Static files are collected at build time. Settings need these values to load;
# they are placeholders for this one command and never reach the final image's environment.
RUN DJANGO_SECRET_KEY=collectstatic POSTGRES_PASSWORD=unused \
    STORAGE_ACCESS_KEY=unused STORAGE_SECRET_KEY=unused \
    python manage.py collectstatic --noinput --verbosity 0
USER app
EXPOSE 8000
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

FROM app AS test
COPY --from=deps-dev /opt/venv /opt/venv
ENV RUFF_CACHE_DIR=/tmp/ruff-cache
CMD ["pytest"]

FROM base AS media
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY --from=deps /opt/venv /opt/venv
COPY . .
USER app

FROM base AS ml
ENV HF_HOME=/models/huggingface
RUN mkdir -p /models && chown app:app /models
COPY --from=deps-ml /opt/venv /opt/venv
COPY . .
USER app

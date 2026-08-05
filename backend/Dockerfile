FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
RUN uv sync --frozen

RUN useradd --create-home --shell /usr/sbin/nologin kawu \
    && chown -R kawu:kawu /app
USER kawu

CMD ["uv", "run", "celery", "-A", "app.pipeline.celery_app:celery_app", "worker", "--loglevel=info"]

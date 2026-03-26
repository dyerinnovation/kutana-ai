# Stage 1: Build dependencies with uv
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Copy workspace metadata + source (filtered by .dockerignore)
COPY pyproject.toml uv.lock ./
COPY packages/ ./packages/
COPY services/ ./services/

# Install only this service's dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package api-server --no-dev --frozen

# Stage 2: Lean runtime image
FROM python:3.13-slim

WORKDIR /app

# Copy the virtual environment with all installed packages
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy alembic config for migration hook
COPY alembic.ini ./
COPY alembic/ ./alembic/

EXPOSE 8000

CMD ["uvicorn", "api_server.main:app", "--host", "0.0.0.0", "--port", "8000"]

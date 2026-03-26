# Base image for docker-compose development — installs all workspace packages
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Copy workspace metadata + source (filtered by .dockerignore)
COPY pyproject.toml uv.lock ./
COPY packages/ ./packages/
COPY services/ ./services/

# Install all workspace packages from lockfile (no dev deps)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --all-packages --no-dev --frozen

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Copy entire monorepo (uv workspace requires all member pyproject.toml files)
COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package api-server --no-dev --frozen

EXPOSE 8000

CMD ["uvicorn", "api_server.main:app", "--host", "0.0.0.0", "--port", "8000"]

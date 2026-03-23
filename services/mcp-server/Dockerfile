FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Copy entire monorepo (uv workspace requires all member pyproject.toml files)
COPY . .

# Install all workspace packages from lockfile (no dev deps)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --all-packages --no-dev --frozen

EXPOSE 3001

ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=3001

CMD ["python", "-m", "mcp_server.main"]

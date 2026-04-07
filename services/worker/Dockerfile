# Stage 1: Build Python dependencies with uv
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
    uv sync --package worker --no-dev --frozen

# Stage 2: Install channel plugins (bun + official Discord plugin)
FROM oven/bun:1-slim AS plugins

WORKDIR /plugins/discord
COPY plugins/discord/package.json plugins/discord/bun.lock* ./
RUN bun install --frozen-lockfile 2>/dev/null || bun install
COPY plugins/discord/ ./

# Slack (MCP server for OAuth feeds)
WORKDIR /plugins/slack
COPY plugins/slack/package.json plugins/slack/bun.lock* ./
RUN bun install --frozen-lockfile 2>/dev/null || bun install
COPY plugins/slack/ ./

# Stage 3: Lean runtime image
FROM python:3.13-slim

WORKDIR /app

# Install bun runtime for stdio MCP channel plugins
COPY --from=oven/bun:1-slim /usr/local/bin/bun /usr/local/bin/bun

# Copy venv + workspace source (workspace .pth files reference /app/packages/ etc.)
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/packages /app/packages
COPY --from=builder /app/services /app/services

# Copy channel plugins
COPY --from=plugins /plugins /app/plugins

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8004

CMD ["uvicorn", "worker.main:app", "--host", "0.0.0.0", "--port", "8004"]

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
    uv sync --package audio-service --no-dev --frozen

# Stage 2: Lean runtime image
FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001

CMD ["uvicorn", "audio_service.main:app", "--host", "0.0.0.0", "--port", "8001"]

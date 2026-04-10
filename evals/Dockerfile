# Eval runner — thin layer on top of api-server with pytest + eval code.
# Build AFTER api-server:
#   bash scripts/build_and_push.sh api-server eval
FROM localhost:30500/kutana/api-server:latest

WORKDIR /app

# Install test runner (all other deps — anthropic, langfuse, boto3 — already
# present in the api-server venv).
# The api-server base image sets PATH=/app/.venv/bin:$PATH but the uv-created
# venv lacks pip. Install directly into the venv's site-packages.
RUN /usr/local/bin/pip install --no-cache-dir --target=/app/.venv/lib/python3.13/site-packages \
    pytest pytest-asyncio

# Copy eval code + test data
COPY evals/ ./evals/

# System prompts doc — referenced by evals/conftest.py:SYSTEM_PROMPTS_PATH
COPY internal-docs/development/managed-agent-system-prompts.md \
     ./internal-docs/development/managed-agent-system-prompts.md

# Root pyproject.toml carries pytest config (markers, asyncio_mode).
# The job command overrides addopts to remove --ignore=evals.
COPY pyproject.toml ./pyproject.toml

ENV PATH="/app/.venv/bin:$PATH"

# Write a small entrypoint that selects mock vs e2e based on EVAL_MODE env var.
# EVAL_MODE=e2e  → python evals/k8s_runner.py (in-cluster job)
# EVAL_MODE=mock → pytest evals/ -m mock       (default, offline)
RUN printf '#!/bin/sh\nif [ "${EVAL_MODE}" = "e2e" ]; then\n  exec python evals/k8s_runner.py "$@"\nelse\n  exec python -m pytest evals/ -m mock -v --tb=short -o "addopts=--import-mode=importlib"\nfi\n' \
    > /app/eval-entrypoint.sh \
    && chmod +x /app/eval-entrypoint.sh

ENTRYPOINT ["/app/eval-entrypoint.sh"]

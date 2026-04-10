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

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app"

# Entrypoint runs the managed-agent eval runner.
ENTRYPOINT ["python", "evals/k8s_runner.py"]

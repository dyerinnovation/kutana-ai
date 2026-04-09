# Eval runner — thin layer on top of api-server with pytest + eval code.
# Build AFTER api-server:
#   bash scripts/build_and_push.sh api-server eval
FROM localhost:30500/kutana/api-server:latest

WORKDIR /app

# Install test runner (all other deps — anthropic, langfuse, boto3 — already
# present in the api-server venv).
RUN pip install --no-cache-dir pytest pytest-asyncio

# Copy eval code + test data
COPY evals/ ./evals/

# System prompts doc — referenced by evals/conftest.py:SYSTEM_PROMPTS_PATH
COPY internal-docs/development/managed-agent-system-prompts.md \
     ./internal-docs/development/managed-agent-system-prompts.md

# Root pyproject.toml carries pytest config (markers, asyncio_mode).
# The job command overrides addopts to remove --ignore=evals.
COPY pyproject.toml ./pyproject.toml

CMD ["python", "-m", "pytest", "evals/", "-m", "mock", "-v", "--tb=short", \
     "-o", "addopts=--import-mode=importlib"]

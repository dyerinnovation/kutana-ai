FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy only the mcp-server package (no workspace needed)
COPY services/mcp-server/pyproject.toml ./pyproject.toml
COPY services/mcp-server/src/ ./src/

# Install dependencies
RUN uv pip install --system --no-cache .

EXPOSE 3001

ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=3001

CMD ["python", "-m", "mcp_server.main"]

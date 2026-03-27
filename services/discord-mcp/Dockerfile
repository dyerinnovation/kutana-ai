FROM oven/bun:1-slim AS builder
WORKDIR /app
COPY services/discord-mcp/package.json services/discord-mcp/bun.lock* ./
RUN bun install --frozen-lockfile || bun install
COPY services/discord-mcp/tsconfig.json ./
COPY services/discord-mcp/src/ ./src/

FROM oven/bun:1-slim
WORKDIR /app
COPY --from=builder /app /app
ENV NODE_ENV=production
EXPOSE 3002
CMD ["bun", "run", "src/index.ts"]

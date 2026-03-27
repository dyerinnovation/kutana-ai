FROM oven/bun:1-slim AS builder
WORKDIR /app
COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile || bun install
COPY tsconfig.json ./
COPY src/ ./src/

FROM oven/bun:1-slim
WORKDIR /app
COPY --from=builder /app /app
ENV NODE_ENV=production
EXPOSE 3002
CMD ["bun", "run", "src/index.ts"]

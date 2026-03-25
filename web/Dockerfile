# Stage 1: Build the Vite SPA
FROM node:22-slim AS build

# web/ is at /repo/web, so ../../../external-docs resolves to /external-docs
# We replicate this structure: /repo/web/ + /repo/external-docs/
WORKDIR /repo/web
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ .
COPY external-docs/ /repo/external-docs/
RUN pnpm build

# Stage 2: Serve with nginx
FROM nginx:1.27-alpine
COPY --from=build /repo/web/dist /usr/share/nginx/html
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

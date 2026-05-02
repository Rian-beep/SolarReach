# SolarReach Web — Vite dev server (HMR via bind-mount in compose).
FROM node:20-alpine

WORKDIR /app

# pnpm
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

# Manifest first for layer caching
COPY package.json ./
COPY pnpm-lock.yaml* ./
RUN pnpm install --no-frozen-lockfile

# App (bind-mounted in dev)
COPY . .

EXPOSE 5173
# --host so it binds 0.0.0.0; --strictPort fails fast on conflict
CMD ["pnpm", "exec", "vite", "--host", "0.0.0.0", "--port", "5173", "--strictPort"]

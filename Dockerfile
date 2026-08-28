# One Railway service for the React frontend, Express API, and Playwright
# scraper. The repository is a pnpm workspace, so this Dockerfile must be
# built from the repository root.
FROM node:20-bookworm-slim

WORKDIR /app

# Chromium is installed from Debian and selected by run_job.py via `which`.
# This is more reliable here than Playwright's downloaded browser shell.
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    chromium \
    python3 \
    python3-pip \
  && rm -rf /var/lib/apt/lists/*

RUN corepack enable \
  && corepack prepare pnpm@10.26.1 --activate

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml .npmrc ./
COPY artifacts/api-server/package.json artifacts/api-server/package.json
COPY artifacts/ad-intel/package.json artifacts/ad-intel/package.json
COPY artifacts/mockup-sandbox/package.json artifacts/mockup-sandbox/package.json
COPY lib/api-client-react/package.json lib/api-client-react/package.json
COPY lib/api-spec/package.json lib/api-spec/package.json
COPY lib/api-zod/package.json lib/api-zod/package.json
COPY lib/db/package.json lib/db/package.json

RUN pnpm install --frozen-lockfile

COPY . .

RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

# Vite requires these variables even for a production build.
RUN PORT=3000 BASE_PATH=/ pnpm --filter @workspace/ad-intel run build \
  && pnpm --filter @workspace/api-server run build

RUN chmod +x ./docker-entrypoint.sh
RUN chown -R node:node /app

ENV NODE_ENV=production
ENV FRONTEND_DIST_DIR=/app/artifacts/ad-intel/dist/public

USER node

EXPOSE 8080
ENTRYPOINT ["./docker-entrypoint.sh"]
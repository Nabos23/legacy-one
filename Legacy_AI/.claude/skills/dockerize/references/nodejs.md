# Node.js / TypeScript / Bun

## Base image choice

- **Default: `node:20.18.1-slim`** (or whatever LTS is current). Debian-based, glibc, native modules just work.
- **Avoid `node:*-alpine`** unless image size is critical AND you've verified all native deps (`bcrypt`, `sharp`, `node-canvas`, `better-sqlite3`, etc.) work with musl. They often don't.
- **For minimal final stage**: `gcr.io/distroless/nodejs20-debian12`. No shell, much smaller, no apt — but you can't `exec` into it to debug, so use only when you're confident.

Pin the exact patch version. `node:20` floats; `node:20.18.1-slim` doesn't.

## Package manager

Detect from the lockfile:

| Lockfile present       | Use                |
| ---------------------- | ------------------ |
| `package-lock.json`    | `npm ci`           |
| `pnpm-lock.yaml`       | `pnpm install --frozen-lockfile` |
| `yarn.lock`            | `yarn install --frozen-lockfile` (Yarn 1) or `yarn install --immutable` (Yarn 2+) |
| `bun.lockb`            | `bun install --frozen-lockfile` |

Never use `npm install` in a Dockerfile — it can update the lockfile and produce a different tree than the developer has locally. `npm ci` is the reproducible version.

For pnpm/yarn, enable Corepack so the right version is used:

```dockerfile
RUN corepack enable
```

## Dependency layer pattern

```dockerfile
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
```

The cache mount (BuildKit) keeps the npm cache across builds — huge speedup when deps change occasionally.

For pnpm:

```dockerfile
COPY package.json pnpm-lock.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile
```

## Multi-stage example: TypeScript backend

```dockerfile
# syntax=docker/dockerfile:1.7

# ---- deps stage (all deps, for building) ----
FROM node:20.18.1-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# ---- build stage ----
FROM node:20.18.1-slim AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---- prod deps stage (only production deps) ----
FROM node:20.18.1-slim AS prod-deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --omit=dev

# ---- runtime stage ----
FROM node:20.18.1-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production

RUN groupadd --system app && useradd --system --gid app --home /app app

COPY --from=prod-deps --chown=app:app /app/node_modules ./node_modules
COPY --from=build     --chown=app:app /app/dist          ./dist
COPY --chown=app:app package.json ./

USER app
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://localhost:3000/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "dist/server.js"]
```

The "prod deps" stage separately reinstalls without devDependencies, so the runtime image doesn't carry TypeScript, ESLint, vitest, etc.

## Next.js specifics

Next.js has a built-in `output: 'standalone'` mode that produces a minimal self-contained server. Enable it in `next.config.js`:

```js
module.exports = { output: 'standalone' };
```

Then the runtime stage only needs three things:

```dockerfile
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static    ./.next/static
COPY --from=build --chown=app:app /app/public          ./public
CMD ["node", "server.js"]
```

Image goes from ~400 MB to ~150 MB.

## Bun

Bun runs much of the Node ecosystem. Base image: `oven/bun:1.1-slim`. Install with `bun install --frozen-lockfile`. Run with `bun run start` or `bun src/index.ts` directly (no transpile step needed for TS).

## Signal handling

Node handles SIGTERM correctly *if* it's PID 1 (exec-form CMD ensures this). For long-lived connections (websockets, long polling), implement graceful shutdown in your app — catch SIGTERM, stop accepting new connections, drain in-flight requests, then exit.

If your app spawns child processes, add `tini`:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends tini && rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["node", "dist/server.js"]
```

## .dockerignore additions for Node

```
node_modules
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.pnpm-debug.log*
.next
.nuxt
.svelte-kit
.turbo
coverage
.eslintcache
```

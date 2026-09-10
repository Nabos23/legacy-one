# docker-compose.yml — multi-service local dev

Use compose when the app talks to other services (database, redis, queue, search). For a single container, plain `docker run` is fine.

## Modern compose format

- **Skip the `version:` field.** It's been deprecated since Compose v2 — modern compose ignores it. Old templates often still have it; remove it.
- **Use `compose.yaml`** as the filename (or `docker-compose.yml` — both still work). The Compose spec prefers `compose.yaml`.

## A solid baseline: web + Postgres + Redis

```yaml
name: myapp

services:
  web:
    build: .
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgres://app:app@db:5432/app
      REDIS_URL: redis://redis:6379
      NODE_ENV: development
    env_file:
      - .env                    # loaded if it exists, OK if missing
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - .:/app                  # bind mount for live reload (DEV ONLY)
      - /app/node_modules       # anonymous volume so host's empty node_modules doesn't shadow image's
    restart: unless-stopped

  db:
    image: postgres:16.4-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    volumes:
      - db_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"             # expose only if you want to connect from host
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d app"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7.4-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  db_data:
  redis_data:
```

## Key decisions in there

- **`depends_on` with `condition: service_healthy`** — waits for Postgres to actually be ready (`pg_isready` passing), not just for the container to be running. Without this, the web service can start before Postgres accepts connections and crash on its first query.
- **Service names as hostnames** — `db` and `redis` are DNS-resolvable from `web`. Never use `localhost` for service-to-service URLs in compose.
- **Named volumes** — `db_data` persists across `docker compose down`. Bind-mounting `./data:/var/lib/postgresql/data` works but is slower on macOS/Windows and creates ownership headaches.
- **The `node_modules` anonymous volume trick** — when you bind-mount the source dir for live reload, you also hide the image's `node_modules`. Mounting an anonymous volume at `/app/node_modules` re-exposes the image's copy. Without it, you get "module not found" the first time you try to run.

## Dev vs prod separation

Don't bind-mount source code in production compose. The clean pattern is two files:

**`compose.yaml`** (base — prod-safe):
```yaml
services:
  web:
    build: .
    environment:
      NODE_ENV: production
    restart: unless-stopped
```

**`compose.override.yaml`** (dev — auto-loaded by `docker compose up`):
```yaml
services:
  web:
    environment:
      NODE_ENV: development
    volumes:
      - .:/app
      - /app/node_modules
    command: npm run dev
```

`docker compose up` → uses both (dev mode).
`docker compose -f compose.yaml up` → uses only base (prod mode).

## Secrets

Don't put real secrets in `compose.yaml`. Three options:

1. **`.env` file**, gitignored, referenced via `env_file:` or `${VAR}` interpolation. Fine for dev.
2. **Docker secrets** (Swarm) or **external secret managers** (AWS Secrets Manager, Vault) for production. Compose has a `secrets:` section for this.
3. **Pass env vars at the shell level**: `DATABASE_URL=... docker compose up`. Compose picks up env from the calling shell.

## Networks

Compose auto-creates a default network where all services can resolve each other by name. Custom networks only matter when:
- You want to isolate services from each other.
- You want to connect containers from multiple compose files.

Don't add `networks:` blocks if the default works.

## Common patterns

**One-shot tasks** (migrations, seed scripts): use a separate service with `profiles:` so it only runs when requested:

```yaml
  migrate:
    build: .
    command: npm run migrate
    environment:
      DATABASE_URL: postgres://app:app@db:5432/app
    depends_on:
      db:
        condition: service_healthy
    profiles: ["tools"]   # not started by default
```

Run with: `docker compose run --rm migrate` or `docker compose --profile tools up`.

**Mailcatcher / Mailhog** for local email testing:

```yaml
  mail:
    image: axllent/mailpit:latest
    ports:
      - "8025:8025"   # web UI
      - "1025:1025"   # SMTP
```

**MinIO** as an S3 stand-in for dev:

```yaml
  s3:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio123
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - s3_data:/data
```

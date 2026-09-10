# Python

## Base image choice

- **Default: `python:3.12.7-slim-bookworm`** (or current Python patch version on Debian bookworm-slim). glibc, predictable wheel compatibility.
- **Avoid `python:*-alpine`** unless you really need the size. Many Python packages (`numpy`, `pandas`, `cryptography`, `psycopg2`, anything with C extensions) ship glibc wheels — on Alpine they fall back to source builds, which need a C toolchain and take forever. Worse, some don't build cleanly at all.
- **For maximum lockdown**: `gcr.io/distroless/python3-debian12` as the final stage.

Pin the exact patch version (`3.12.7`, not `3.12`).

## Package manager

| Lockfile / config         | Tool   | Install command                                |
| ------------------------- | ------ | ---------------------------------------------- |
| `requirements.txt`        | pip    | `pip install --no-cache-dir -r requirements.txt` |
| `poetry.lock` + `pyproject.toml` | poetry | `poetry install --no-root --without dev` |
| `uv.lock` + `pyproject.toml`     | uv     | `uv sync --frozen --no-dev`            |
| `Pipfile.lock`            | pipenv | `pipenv install --deploy --system`             |

**uv** (`pip install uv` or use the official image) is dramatically faster than pip/poetry. If the project uses it, lean into it.

## The virtual-env-in-a-stage pattern

A clean multi-stage pattern that avoids leaking build tools into the runtime image:

```dockerfile
# syntax=docker/dockerfile:1.7

# ---- build stage ----
FROM python:3.12.7-slim-bookworm AS build

# Native build deps for any wheels that need them (psycopg2, lxml, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a venv we can copy whole into the runtime stage
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# ---- runtime stage ----
FROM python:3.12.7-slim-bookworm AS runtime

# Only the runtime libs the wheels link against (e.g. libpq5 for psycopg2),
# NOT the -dev packages or build-essential.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpq5 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app

# Copy the venv from build stage — all deps come along for the ride
COPY --from=build /opt/venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Sensible Python defaults for containers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY --chown=app:app . .

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "app.wsgi:application"]
```

## Critical env vars

Always set these in any Python container:

- `PYTHONDONTWRITEBYTECODE=1` — no `.pyc` files cluttering the filesystem.
- `PYTHONUNBUFFERED=1` — print/logs flush immediately. Without this, container logs lag and look broken.
- `PIP_NO_CACHE_DIR=1` (build stage) — don't write pip's cache into image layers.

## Framework-specific notes

**Django**: Run `python manage.py collectstatic --noinput` in the build stage. Run migrations as a separate step (init container in Kubernetes, or a `command:` override in compose) — not in CMD, because that runs on every container start and races between replicas.

**FastAPI**: Use `uvicorn` directly for dev, `gunicorn` with the `uvicorn.workers.UvicornWorker` for production. Or `uvicorn` with `--workers N` if you don't need gunicorn's process management.

```dockerfile
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
```

**Flask**: Never use `flask run` in production — it's a dev server. Use gunicorn:

```dockerfile
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "4", "app:app"]
```

**Celery worker**: Separate container (or compose service), same image, different CMD:

```dockerfile
CMD ["celery", "-A", "app.celery", "worker", "--loglevel=info"]
```

## Common native-dep recipes

Map of "what's failing to install" → "apt packages to add in build stage":

- `psycopg2` (Postgres) → build: `libpq-dev` + `build-essential`; runtime: `libpq5`. Or just use `psycopg2-binary` and skip both.
- `lxml`, `xmlsec` → `libxml2-dev libxslt1-dev` (build); `libxml2 libxslt1.1` (runtime).
- `Pillow` → `libjpeg-dev zlib1g-dev` (build); `libjpeg62-turbo zlib1g` (runtime).
- `cryptography` (older versions) → `libssl-dev libffi-dev` + Rust. Modern versions ship wheels.
- `mysqlclient` → `default-libmysqlclient-dev` (build); `default-libmysqlclient21` (runtime).

## .dockerignore additions for Python

```
__pycache__
*.pyc
*.pyo
*.pyd
.Python
.venv
venv
env
.pytest_cache
.mypy_cache
.ruff_cache
.coverage
htmlcov
*.egg-info
.tox
```

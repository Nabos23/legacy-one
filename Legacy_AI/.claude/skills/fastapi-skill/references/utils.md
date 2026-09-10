# Project Setup Reference

## Directory Structure

```
project-root/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── .python-version
├── .env
├── app/
│   ├── main.py                  # App factory + lifespan + router registration
│   ├── db.py                    # DB engine, session factory, get_db dependency
│   ├── dependencies.py          # Shared FastAPI dependencies (auth, current user, etc.)
│   ├── middleware/
│   │   └── rate_limit.py        # slowapi limiter setup
│   └── modules/
│       └── <module_name>/
│           ├── routes.py
│           ├── services.py
│           ├── models.py
│           └── schemas.py
└── utils/
    └── helpers.py
```

---

## pyproject.toml

Required packages: `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `asyncpg` (or `psycopg2-binary` for sync), `pydantic`, `pydantic-settings`, `python-dotenv`, `slowapi`, `alembic`.

Python `>=3.11`. Build backend: `hatchling`.

Dev dependencies (under `[tool.uv]`): `ruff`, `mypy`, `pytest`, `httpx`.

---

## Dockerfile

- Base image: `python:3.11-slim`
- Install `uv` via `COPY --from=ghcr.io/astral-sh/uv:latest`
- Copy `pyproject.toml` and `.python-version` first (layer caching), run `uv sync --no-dev`, then copy source.
- Expose port `8000`.
- CMD: `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`

---

## docker-compose.yml

Two services minimum:

- `api` — builds from local Dockerfile, loads `.env`, mounts source volume for dev, depends on `db`.
- `db` — `postgres:16-alpine`, env vars from `.env`, named volume for data persistence.

---

## .python-version

```
3.11
```

---

## uv Commands (always, never pip)

- Install all deps: `uv sync`
- Add a package: `uv add <package>`
- Add a dev dependency: `uv add --dev <package>`
- Run the server: `uv run uvicorn app.main:app --reload`
- Run migrations: `uv run alembic upgrade head`

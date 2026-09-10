# Database Reference

## app/db.py — connect once, share everywhere

The DB engine and session factory are module-level singletons created at import time.
The actual connection pool is opened during the app `lifespan`, not per-request.

### Key rules

- Use `AsyncSession` + `async_sessionmaker` for async FastAPI (recommended).
- Use `Session` + `sessionmaker` only if the project is fully synchronous.
- `get_db` is the only FastAPI dependency for DB access — inject it everywhere via `Depends(get_db)`.
- Never call `engine.connect()` or `SessionLocal()` directly inside routes or services.
- Connection string is read from environment via `pydantic-settings` — never hardcoded.

### app/main.py lifespan pattern

The `lifespan` async context manager in `main.py` is where the DB connection is opened and closed:
- On startup: run `async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)` (dev only) or run Alembic migrations via subprocess.
- On shutdown: `await engine.dispose()`.
- Pass `lifespan=lifespan` to the `FastAPI()` constructor.

### Session per request

`get_db` is an async generator that yields one `AsyncSession` per request and commits/rolls back automatically:
- `yield session` inside a `try` block.
- `await session.commit()` in the happy path (after yield, before finally).
- `await session.rollback()` in the `except` block.
- `await session.close()` in `finally`.

### Alembic

- `alembic.ini` at project root.
- `alembic/env.py` imports `Base` from `app.db` and sets `target_metadata = Base.metadata`.
- Every schema change is a migration: `uv run alembic revision --autogenerate -m "description"` then `uv run alembic upgrade head`.
- Never use `create_all` in production — always Alembic.

### Settings pattern

Database URL and all config come from a `Settings` class in `app/config.py` using `pydantic-settings`:
- `DATABASE_URL: str` read from environment.
- Import as a singleton: `settings = Settings()`.
- `db.py` imports `settings.DATABASE_URL` to build the engine.

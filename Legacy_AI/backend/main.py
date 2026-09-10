import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Scope, Send
from bson import ObjectId
from fastapi.encoders import ENCODERS_BY_TYPE
from backend.core.config import settings

ENCODERS_BY_TYPE[ObjectId] = str

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("backend.main")

if settings.SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
    )
    logger.info("Sentry initialized (environment=%s)", settings.SENTRY_ENVIRONMENT)
else:
    logger.info("SENTRY_DSN not set — Sentry error tracking disabled")


class SecurityHeadersMiddleware:
    """Attach baseline security headers to every response.

    Pure ASGI (not `BaseHTTPMiddleware`) deliberately: `BaseHTTPMiddleware`
    relays the downstream response through a separate task/stream, and when an
    unhandled exception is converted into a response by our global
    `@app.exception_handler(Exception)` below, that relay re-raises the
    original exception to the middleware *above* it instead of passing the
    handler's response through — which skips CORSMiddleware's header logic and
    makes the browser report a misleading "CORS error" for what is really a
    500. Plain ASGI middleware (like RateLimitMiddleware, just below) doesn't
    have this failure mode, since it never leaves the single ASGI call chain.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "no-referrer")
                # Harmless over plain HTTP; instructs browsers to pin HTTPS once seen.
                headers.setdefault(
                    "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)

from ai.tracing import setup_tracing
from backend.admin import admin
from backend.agent.routes import router as agent_router
from backend.agent_builder.routes import router as agent_builder_router
from backend.auth.routes import router as auth_router
from backend.chat.routes import router as chat_router
from backend.auth.permissions import ensure_default_roles
from backend.direct_agent.routes import router as direct_chat_router
from backend.core.quota import ensure_default_quota
from backend.core.ratelimit import RateLimitMiddleware, ensure_default_config
from backend.db.database import db
from backend.dbconnection.routes import router as db_connection_router
from backend.knowledgebase.routes import router as knowledge_base_router
from backend.organization.routes import router as organization_router
from backend.tool.routes import router as tool_router
from backend.team.routes import router as team_router
from backend.toolregistry.routes import router as tool_registry_router
from backend.mcp_server.routes import oauth_callback_router as mcp_oauth_callback_router
from backend.mcp_server.routes import router as mcp_server_router
from backend.connectors.routes import router as connectors_router, callback_router as connectors_callback_router
from backend.notifications.routes import router as notifications_router
from backend.prompt_generator.routes import router as prompt_generator_router
from backend.tracing.routes import router as tracing_router
from backend.user.routes import router as user_router
from backend.orchestration.routes import router as orchestration_router
from backend.schedule.routes import router as schedule_router
from backend.projects.routes import router as projects_router
from backend.widget.routes import router as widget_router
from backend.widget.public_routes import router as widget_public_router
from backend.widget.cors_middleware import DynamicWidgetCORSMiddleware

API_DESCRIPTION = """
Legacy AI backend API (FastAPI + MongoDB).

### Authentication
Most endpoints require a **Bearer JWT**.
1. Call `POST /auth/login` (or `/auth/signup`) to get an `access_token`.
2. Click the **Authorize** 🔓 button (top right) and paste the token.
3. All protected requests will then include `Authorization: Bearer <token>`.

The token persists across page reloads in this UI.

### Prompt Generator
`POST /generate-prompt` — **requires a Bearer JWT**. Generates an optimized system
prompt for an agent given its `agent_name` and `agent_description` using `gpt-5.4-nano`.
"""

OPENAPI_TAGS = [
    {"name": "auth", "description": "Signup, login, password reset (OTP), and admin user creation."},
    {"name": "organizations", "description": "Organization CRUD (paginated, soft delete)."},
    {"name": "agents", "description": "Agent CRUD (paginated, soft delete)."},
    {"name": "projects", "description": "Projects CRUD, skill & file management, and project chat."},
    {"name": "tools", "description": "Tool CRUD (paginated, soft delete)."},
    {"name": "tool-registry", "description": "Tool registry / catalog CRUD (paginated, soft delete)."},
    {"name": "db-connections", "description": "Database connections — connection strings are encrypted at rest."},
    {"name": "knowledge-bases", "description": "Org-level Knowledge Bases — document upload, auto-classification, and RAG search for agents."},
    {"name": "chat", "description": "Conversational chat — send a message, get a reply from the routed agent."},
    {"name": "direct-chat", "description": "Direct 1:1 chat with a single agent — bypasses the supervisor."},
    {"name": "mcp-servers", "description": "MCP server configs — register stdio/SSE/WebSocket MCP servers and link them to agents."},
    {"name": "prompt-generator", "description": "Generate optimized system prompts for agents using LLM."},
    {"name": "users", "description": "User management — list all users (super admin) and org-scoped user queries."},
    {"name": "tracing", "description": "Langfuse observability — traces, sessions, cost stats per org and agent."},
    {"name": "notifications", "description": "Per-user and org-wide notifications — list, unread count, mark read, dismiss."},
    {"name": "schedules", "description": "Schedule an agent to run automatically, once or recurring, reusing the same execution and chat-persistence flow as interactive chat."},
    {"name": "widget-configs", "description": "Embeddable chatbot widgets — create/configure a public-facing chat widget bound to a single agent or the org supervisor."},
    {"name": "widget-public", "description": "Public, unauthenticated endpoints an embedded widget calls from a third-party site — config, session, and chat. Access is controlled by the widget's origin allowlist / API key, not a JWT."},
    {"name": "health", "description": "Service and database health checks."},
]

app = FastAPI(
    title="Legacy AI API",
    description=API_DESCRIPTION,
    version="0.1.0",
    openapi_tags=OPENAPI_TAGS,
    contact={"name": "Legacy AI", "email": "support@example.com"},
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={"persistAuthorization": True},
)

app.include_router(auth_router)
app.include_router(organization_router)
app.include_router(agent_router)
app.include_router(agent_builder_router)
app.include_router(projects_router)
app.include_router(db_connection_router)
app.include_router(knowledge_base_router)
app.include_router(tool_router)
app.include_router(team_router)
app.include_router(chat_router)
app.include_router(direct_chat_router)
app.include_router(tool_registry_router)
app.include_router(mcp_server_router)
app.include_router(prompt_generator_router)
app.include_router(mcp_oauth_callback_router)
app.include_router(tracing_router)
app.include_router(user_router)
app.include_router(connectors_callback_router)
app.include_router(connectors_router)
app.include_router(notifications_router)
app.include_router(orchestration_router)
app.include_router(schedule_router)
app.include_router(widget_router)
app.include_router(widget_public_router)

Path(settings.MEDIA_ROOT).mkdir(parents=True, exist_ok=True)
app.mount(settings.MEDIA_URL_PATH, StaticFiles(directory=settings.MEDIA_ROOT), name="media")

ALLOWED_ORIGINS = [settings.FRONTEND_URL, "http://localhost:3000", "http://localhost:5173", "http://localhost:3001"]

app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(DynamicWidgetCORSMiddleware)


def _cors_headers_for(request: Request) -> dict:
    """Access-Control-Allow-* headers for a response built outside the normal
    routing path (i.e. from an exception handler).

    `CORSMiddleware` only wraps the app's *routing* — Starlette's built-in
    `ServerErrorMiddleware` sits one layer further out and is where responses
    from `@app.exception_handler` actually get sent from, so they never pass
    back through `CORSMiddleware` no matter what order middleware is added in
    (verified directly: an unhandled exception's response has no CORS header
    regardless of add_middleware ordering). Any handler that can fire on an
    arbitrary request — i.e. this one — has to set these headers itself.
    """
    origin = request.headers.get("origin")
    if origin not in ALLOWED_ORIGINS:
        return {}
    return {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true"}


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all so internal errors never leak stack traces / driver messages
    to clients. The full exception is logged server-side for debugging."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
        headers=_cors_headers_for(request),
    )


@app.on_event("startup")
async def _seed_config() -> None:
    import logging as _logging
    _log = _logging.getLogger("startup")
    setup_tracing()
    _log.info(
        "[startup] ENCRYPTION_KEY explicitly set: %s (falling back to JWT_SECRET_KEY-derived key if not)",
        bool(settings.ENCRYPTION_KEY),
    )
    try:
        await ensure_default_config()
    except Exception as exc:
        _log.warning("Could not seed rate-limit config (MongoDB unreachable?): %s", exc)
    try:
        await ensure_default_quota()
    except Exception as exc:
        _log.warning("Could not seed quota config: %s", exc)
    try:
        await ensure_default_roles()
    except Exception as exc:
        _log.warning("Could not seed roles: %s", exc)
    try:
        from backend.connectors.seed import seed_connector_registry
        await seed_connector_registry()
    except Exception as exc:
        _log.warning("Could not seed connector registry: %s", exc)
    try:
        from backend.widget.seed import ensure_widget_indexes
        await ensure_widget_indexes()
    except Exception as exc:
        _log.warning("Could not create widget-config indexes: %s", exc)
    try:
        from backend.db.database import agent_permissions_collection
        await agent_permissions_collection.create_index("agent_id", unique=True, sparse=True, background=True)
        await agent_permissions_collection.create_index("project_id", unique=True, sparse=True, background=True)
    except Exception as exc:
        _log.warning("Could not create agent_permissions index: %s", exc)
    try:
        from backend.schedule.seed import ensure_schedule_indexes
        await ensure_schedule_indexes()
    except Exception as exc:
        _log.warning("Could not create schedule indexes: %s", exc)
    try:
        from backend.db.indexes import ensure_core_indexes
        _log.info("[startup] core indexes: %s", await ensure_core_indexes())
    except Exception as exc:
        _log.warning("Could not create core indexes: %s", exc)
    await _check_qdrant()


@app.on_event("shutdown")
async def _close_clients() -> None:
    import logging as _logging
    _log = _logging.getLogger("shutdown")
    try:
        from backend.tracing.services import close_langfuse_client
        await close_langfuse_client()
    except Exception as exc:
        _log.warning("Could not close Langfuse client: %s", exc)


async def _check_qdrant() -> None:
    from backend.core.config import settings
    logger = logging.getLogger("startup")
    logger.info("Qdrant URL configured as: %s", settings.QDRANT_URL)
    try:
        from qdrant_client import AsyncQdrantClient
        client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
            check_compatibility=False,
        )
        await client.get_collections()
        logger.info("Qdrant connection OK at %s", settings.QDRANT_URL)
    except Exception as exc:
        logger.error("Qdrant connection FAILED at %s — %s", settings.QDRANT_URL, exc)


admin.mount_to(app)


@app.get("/", tags=["health"], summary="Root health check")
def read_root():
    return {"message": "FastAPI is running 🚀"}


@app.get("/mongo-check", tags=["health"], summary="MongoDB connectivity check")
async def mongo_check():
    try:
        await db.command("ping")
        return {"status": "MongoDB Connected ✅"}
    except Exception:
        # Do not leak raw driver errors (which can include connection strings
        # / host details) to the client. Log server-side instead.
        logger.exception("MongoDB ping failed")
        return JSONResponse(
            status_code=503,
            content={"status": "MongoDB NOT connected ❌"},
        )

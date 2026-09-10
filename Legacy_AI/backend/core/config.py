import os

from pydantic_settings import BaseSettings, SettingsConfigDict

from ai.models import Model

class Settings(BaseSettings):
    """Application settings, loaded from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    OTP_EXPIRE_MINUTES: int = 10
    # SECURITY: must stay false outside local development. When true, the
    # password-reset OTP is echoed in the HTTP response, which defeats the
    # reset flow. In production the OTP should only be delivered out-of-band
    # (email/SMS). Opt in explicitly via env for local testing.
    OTP_RETURN_IN_RESPONSE: bool = os.getenv("OTP_RETURN_IN_RESPONSE", "false").lower() == "true"
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")

    # SMTP email (required for password-reset OTP delivery)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", Model.default().value)
    # Small, cheap model used only to generate short chat-session titles.
    TITLE_MODEL: str = os.getenv("TITLE_MODEL", Model.GPT_5_4_NANO.value)
    # Image Generation Model
    IMAGE_MODEL: str = os.getenv("IMAGE_MODEL", Model.GPT_IMAGE_2.value)

    # Langfuse observability
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST")

    # Sentry error/performance monitoring. Left empty disables it entirely.
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    SENTRY_ENVIRONMENT: str = os.getenv("SENTRY_ENVIRONMENT", "development")
    SENTRY_TRACES_SAMPLE_RATE: float = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

    # Qdrant Cloud vector DB (schema search)
    QDRANT_URL: str = os.getenv("QDRANT_URL", "")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")

    # Embedding model used for schema indexing and query search
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # MCP OAuth — public base URL the OAuth provider redirects back to after the
    # user consents. The callback path is appended (see mcp_server.services). In prod
    # set this to the externally reachable API origin and register that redirect
    # URI with the OAuth provider.
    MCP_OAUTH_REDIRECT_BASE: str = os.getenv("MCP_OAUTH_REDIRECT_BASE")
    # Optional URL to send the browser to after a successful callback (e.g. a
    # frontend "connected" page). When empty, the callback renders a simple page.
    MCP_OAUTH_SUCCESS_REDIRECT: str = os.getenv("MCP_OAUTH_SUCCESS_REDIRECT", "")
    # How long an in-flight OAuth authorization (the pending consent) stays valid.
    MCP_OAUTH_FLOW_TTL_SECONDS: int = int(os.getenv("MCP_OAUTH_FLOW_TTL_SECONDS", "900"))

    AUTH_CACHE_TTL_SECONDS: float = float(os.getenv("AUTH_CACHE_TTL_SECONDS", "5"))

    LANGFUSE_CONNECT_TIMEOUT: float = float(os.getenv("LANGFUSE_CONNECT_TIMEOUT", "5"))
    LANGFUSE_READ_TIMEOUT: float = float(os.getenv("LANGFUSE_READ_TIMEOUT", "60"))
    LANGFUSE_MAX_ATTEMPTS: int = int(os.getenv("LANGFUSE_MAX_ATTEMPTS", "2"))
    LANGFUSE_TOTAL_BUDGET_SECONDS: float = float(os.getenv("LANGFUSE_TOTAL_BUDGET_SECONDS", "70"))
    LANGFUSE_FAILURE_CACHE_SECONDS: float = float(os.getenv("LANGFUSE_FAILURE_CACHE_SECONDS", "10"))
    LANGFUSE_CACHE_TTL_SECONDS: float = float(os.getenv("LANGFUSE_CACHE_TTL_SECONDS", "300"))
    LANGFUSE_STALE_TTL_SECONDS: float = float(os.getenv("LANGFUSE_STALE_TTL_SECONDS", "3600"))

    # Frontend URL for OAuth redirects
    FRONTEND_URL: str = os.getenv("FRONTEND_URL")
    CORS_ALLOWED_ORIGINS: str = os.getenv(
        "CORS_ALLOWED_ORIGINS"
    )

    MEDIA_ROOT: str = os.getenv("MEDIA_ROOT", "media")
    MEDIA_URL_PATH: str = os.getenv("MEDIA_URL_PATH", "/media")
    BACKEND_BASE_URL: str = os.getenv("BACKEND_BASE_URL")
    AVATAR_MAX_SIZE_BYTES: int = int(os.getenv("AVATAR_MAX_SIZE_BYTES", str(5 * 1024 * 1024)))

    # Google Drive OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI")
    GOOGLE_DRIVE_SCOPES: list[str] = ["https://www.googleapis.com/auth/drive"]

    GOOGLE_LOGIN_CLIENT_ID: str = os.getenv("GOOGLE_LOGIN_CLIENT_ID", GOOGLE_CLIENT_ID)
    GOOGLE_LOGIN_CLIENT_SECRET: str = os.getenv("GOOGLE_LOGIN_CLIENT_SECRET", GOOGLE_CLIENT_SECRET)
    GOOGLE_LOGIN_REDIRECT_URI: str = os.getenv(
        "GOOGLE_LOGIN_REDIRECT_URI"
    )
    GITHUB_LOGIN_CLIENT_ID: str = os.getenv("GITHUB_LOGIN_CLIENT_ID", "")
    GITHUB_LOGIN_CLIENT_SECRET: str = os.getenv("GITHUB_LOGIN_CLIENT_SECRET", "")
    GITHUB_LOGIN_REDIRECT_URI: str = os.getenv(
        "GITHUB_LOGIN_REDIRECT_URI"
    )

    # Microsoft OneDrive OAuth
    MS_CLIENT_ID: str = os.getenv("MS_CLIENT_ID", "")
    MS_CLIENT_SECRET: str = os.getenv("MS_CLIENT_SECRET", "")
    MS_TENANT: str = os.getenv("MS_TENANT", "common")
    MS_REDIRECT_URI: str = os.getenv("MS_REDIRECT_URI")

    # Unified connectors module — one callback URL for all providers
    CONNECTORS_CALLBACK_BASE_URI: str = os.getenv("CONNECTORS_CALLBACK_BASE_URI")
    
    RATE_LIMIT_TRUST_FORWARDED: bool = (
        os.getenv("RATE_LIMIT_TRUST_FORWARDED", "false").lower() == "true"
    )

settings = Settings()

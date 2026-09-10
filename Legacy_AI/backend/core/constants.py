"""Constants shared across the `core` package."""

# Identifier of the singleton config documents (rate limit & quota).
GLOBAL_CONFIG_NAME = "global"

# --- Soft delete ---
# Mongo filter for documents that are NOT soft-deleted (absent, null, or False).
NOT_DELETED = {"is_deleted": {"$ne": True}}

# --- Security ---
# bcrypt only hashes the first 72 bytes of a password.
MAX_BCRYPT_BYTES = 72

# --- Database schema introspection ---
DB_INTROSPECT_TIMEOUT_SECONDS = 5
MONGO_SAMPLE_SIZE = 25  # docs sampled per collection when inferring fields

# --- Pagination ---
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# --- Rate limiting ---
DEFAULT_RATE_LIMIT_CONFIG = {
    "name": GLOBAL_CONFIG_NAME,
    # Per-IP, fixed-window. A data-rich dashboard legitimately fires 15-40
    # requests per load (more behind NAT where users share an IP), so 100/min
    # was too tight and tripped under normal use. 600/min keeps abuse bounded
    # while giving the SPA headroom. Admin-tunable live via the dashboard.
    "max_requests": 600,
    "window_seconds": 60,
}
RATE_LIMIT_EXCLUDED_PREFIXES = ("/admin", "/docs", "/redoc", "/openapi.json", "/favicon")
RATE_LIMIT_CONFIG_TTL_SECONDS = 5.0

# --- Quotas ---
DEFAULT_QUOTA = {
    "name": GLOBAL_CONFIG_NAME,
    "enabled": True,
    "max_orgs_per_day": 10,
    "max_tools_per_org": 100,
}

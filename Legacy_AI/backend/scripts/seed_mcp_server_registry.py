"""Seed the `mcp_server_registry` collection — the catalog of connectable MCP servers.

Curated-only by default: a small, hand-picked list of servers we know actually
work (ready-to-use connection templates, no network needed to seed). The
official MCP Registry (registry.modelcontextprotocol.io) is NOT pulled unless
you explicitly ask for it with --with-registry — it's a public, unmoderated
directory of ~500+ third-party listings (most unrelated to this product, of
wildly varying quality), which is exactly the noise this script used to dump
straight into the catalog. Opt in only if you specifically want that breadth.

Agents pick entries from this catalog (Flow A) or bring their own connection
string (Flow B); see backend.mcp_server.services.create_mcp_server.

Usage (from project root):
    uv run python -m backend.scripts.seed_mcp_server_registry
    uv run python -m backend.scripts.seed_mcp_server_registry --with-registry --limit 200
"""

import argparse
import logging
from datetime import datetime, timezone
from typing import List, Optional

from pymongo import MongoClient

from backend.db import constants as c
from backend.db.database import DATABASE_NAME, MONGO_URL

logger = logging.getLogger(__name__)

_REGISTRY_BASE = "https://registry.modelcontextprotocol.io/v0/servers"
_REGISTRY_TIMEOUT = 10.0


# ---------------------------------------------------------------------------
# Curated baseline — popular servers with ready-to-use connection templates.
# `connection_string` is exactly what parse_connection_string expects; ``<TOKEN>``
# placeholders are listed in `requires` and filled at connect time.
# ---------------------------------------------------------------------------
CURATED: List[dict] = [
    {
        "key": "mock",
        "name": "Mock MCP (test)",
        "description": "Self-contained mock MCP server for testing: echo, add, reverse, mock_weather, whoami. No credentials or network needed.",
        "prompt": "Use these mock tools for testing and development — echo inputs back, add two numbers, reverse a string, look up mock weather data, or identify the connected session user.",
        "category": "testing",
        "transport": "stdio",
        "connection_string": "python -m backend.scripts.mock_mcp_server",
        "requires": [],
        "homepage": "",
    },
    {
        "key": "filesystem",
        "name": "Filesystem",
        "description": "Read/write files in an allowed local directory.",
        "prompt": "Use filesystem tools when the user asks to read, write, list, or manage files and directories in the allowed local path.",
        "category": "files",
        "transport": "stdio",
        "connection_string": "npx -y @modelcontextprotocol/server-filesystem <PATH>",
        "requires": ["<PATH>"],
        "homepage": "https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem",
    },
    {
        "key": "git",
        "name": "Git",
        "description": "Inspect and operate on a local git repository.",
        "prompt": "Use git tools when the user asks to inspect commits, branches, diffs, logs, file history, or run git operations on the connected repository.",
        "category": "dev-tools",
        "transport": "stdio",
        "connection_string": "uvx mcp-server-git --repository <PATH>",
        "requires": ["<PATH>"],
        "homepage": "https://github.com/modelcontextprotocol/servers/tree/main/src/git",
    },
    {
        "key": "sqlite",
        "name": "SQLite",
        "description": "Query and inspect a local SQLite database.",
        "prompt": "Use SQLite tools when the user asks to query or inspect data in the connected SQLite database.",
        "category": "database",
        "transport": "stdio",
        "connection_string": "uvx mcp-server-sqlite --db-path <PATH>",
        "requires": ["<PATH>"],
        "homepage": "https://github.com/modelcontextprotocol/servers/tree/main/src/sqlite",
    },
    {
        "key": "fetch",
        "name": "Fetch",
        "description": "Fetch a URL and return its content as markdown.",
        "prompt": "Use the fetch tool when the user asks to retrieve, read, or summarize content from a specific web URL.",
        "category": "web",
        "transport": "stdio",
        "connection_string": "uvx mcp-server-fetch",
        "requires": [],
        "homepage": "https://github.com/modelcontextprotocol/servers/tree/main/src/fetch",
    },
    {
        "key": "memory",
        "name": "Memory",
        "description": "A knowledge-graph based persistent memory store.",
        "prompt": "Use memory tools when the user asks to remember information for later, recall something previously stored, or manage a persistent knowledge base across sessions.",
        "category": "memory",
        "transport": "stdio",
        "connection_string": "npx -y @modelcontextprotocol/server-memory",
        "requires": [],
        "homepage": "https://github.com/modelcontextprotocol/servers/tree/main/src/memory",
    },
    {
        "key": "github",
        "name": "GitHub",
        "description": "Repositories, issues, and pull requests — official hosted server.",
        "prompt": "Use GitHub tools when the user asks about repositories, issues, pull requests, branches, commits, code search, or GitHub workflow automation.",
        "category": "dev-tools",
        "transport": "streamable_http",
        # Official hosted remote server (github/github-mcp-server) — HTTP
        # transport, so the Bearer-token field actually works for it (unlike
        # the old deprecated npm stdio package this used to point at).
        "connection_string": "https://api.githubcopilot.com/mcp/",
        "requires": ["GitHub Personal Access Token — paste it in the Bearer token field below"],
        "homepage": "https://github.com/github/github-mcp-server",
    },
]

# Keys removed from CURATED above because their npm package is now marked
# "no longer supported" by its maintainer AND/OR it needs a credential as a
# stdio process env var — which nothing in this system actually injects (the
# Bearer-token field only applies to HTTP/WebSocket transports, never to a
# spawned local process's environment). Rather than build that plumbing for
# packages the maintainers themselves have sunset, these are deactivated
# below. GitHub itself moved to the entry above (hosted remote, HTTP), so it's
# not in this list even though its old npm stdio package is also deprecated.
DEPRECATED_KEYS = [
    "postgres",     # npm: deprecated, unmaintained
    "slack",        # npm: deprecated; also needs an env-var bot token we can't inject
    "brave-search", # npm: deprecated; also needs an env-var API key we can't inject
    "puppeteer",    # npm: deprecated, unmaintained
    "google-maps",  # npm: deprecated; also needs an env-var API key we can't inject
    "gdrive",       # npm: deprecated; also needs OAuth env credentials we can't inject
]


_REGISTRY_PAGE_MAX = 100  # the API rejects limit > 100 with 422


# registryType -> the stdio launcher we use to run that package (must be one
# of _STDIO_LAUNCHERS in backend/mcp_server/services.py so parse_connection_string
# recognises it). Registry types with no sane local launcher (nuget, oci-without-
# docker, etc.) are left out on purpose — we skip those entries entirely below
# rather than seed something unrunnable.
_PACKAGE_LAUNCHERS = {
    "npm": "npx -y {identifier}",
    "pypi": "uvx {identifier}",
}


def _stdio_connection_string(packages: list) -> Optional[str]:
    """Build a runnable stdio launcher from the registry's `packages` array,
    only for a package that (a) we know how to launch and (b) needs no
    credential — we have no way to inject a required env var into a spawned
    local process (the Bearer-token field only applies to HTTP/WebSocket
    transports), so a package requiring one would silently run unauthenticated.
    """
    for pkg in packages or []:
        if (pkg.get("transport") or {}).get("type", "stdio") != "stdio":
            continue
        if any(v.get("isRequired") for v in pkg.get("environmentVariables", [])):
            continue
        template = _PACKAGE_LAUNCHERS.get(pkg.get("registryType"))
        identifier = pkg.get("identifier")
        if not template or not identifier:
            continue
        return template.format(identifier=identifier)
    return None


def _map_registry_item(item: dict) -> Optional[dict]:
    """Map one official-registry item ({"server": {...}, "_meta": {...}}) to our shape.

    Skips entries the official registry has marked inactive/deleted, and skips
    anything we can't turn into a real, connectable entry (no hosted remote and
    no credential-free stdio package we know how to launch) — better to leave
    it out of the catalog than seed a "server" whose connect button always
    fails with an empty connection string.
    """
    server = item.get("server") or {}
    full_name = server.get("name", "")
    if not full_name:
        return None

    official = (item.get("_meta") or {}).get(
        "io.modelcontextprotocol.registry/official", {}
    )
    if official.get("status") not in (None, "active"):
        return None
    # The registry returns every published version; keep only the latest of each
    # server so we don't overwrite a current entry with an older one.
    if official.get("isLatest") is False:
        return None

    remotes = server.get("remotes") or []
    url = remotes[0].get("url") if remotes else None
    connection_string = url or _stdio_connection_string(server.get("packages"))
    if not connection_string:
        return None

    repo = server.get("repository")
    homepage = repo.get("url") if isinstance(repo, dict) else None

    return {
        "key": full_name,                       # registry names are globally unique
        "name": server.get("title") or full_name.split("/")[-1] or full_name,
        "description": server.get("description", ""),
        "category": "registry",
        "transport": "streamable_http" if url else "stdio",
        "connection_string": connection_string,
        "requires": [],
        "source": "registry",
        "homepage": homepage,
        "repo_url": homepage,
    }


def _fetch_registry(limit: int) -> List[dict]:
    """Best-effort snapshot of the official MCP Registry, cursor-paginated."""
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed — skipping official registry pull.")
        return []

    entries: List[dict] = []
    cursor: Optional[str] = None
    try:
        with httpx.Client(timeout=_REGISTRY_TIMEOUT) as http:
            while len(entries) < limit:
                page = min(_REGISTRY_PAGE_MAX, limit - len(entries))
                params = {"limit": str(page)}
                if cursor:
                    params["cursor"] = cursor
                resp = http.get(_REGISTRY_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()
                for item in data.get("servers", []):
                    mapped = _map_registry_item(item)
                    if mapped:
                        entries.append(mapped)
                cursor = (data.get("metadata") or {}).get("nextCursor")
                if not cursor or not data.get("servers"):
                    break
    except Exception as exc:  # noqa: BLE001 - registry is optional, never hard-fail
        logger.warning("Official MCP registry pull stopped early (%s); using what we have.", exc)

    return entries


def _upsert(collection, entry: dict, now: datetime) -> None:
    collection.update_one(
        {"key": entry["key"]},
        {
            "$set": {
                "name": entry.get("name", entry["key"]),
                "description": entry.get("description", ""),
                "prompt": entry.get("prompt"),
                "category": entry.get("category"),
                "transport": entry.get("transport"),
                "connection_string": entry.get("connection_string", ""),
                "requires": entry.get("requires", []),
                "source": entry.get("source", "curated"),
                "homepage": entry.get("homepage"),
                "repo_url": entry.get("repo_url"),
                "is_active": True,
                "is_deleted": False,
            },
            "$setOnInsert": {"key": entry["key"], "created_at": now},
        },
        upsert=True,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Seed the mcp_server_registry catalog.")
    parser.add_argument(
        "--with-registry", action="store_true",
        help="also pull the live official MCP Registry (~500+ third-party listings, unmoderated). Off by default.",
    )
    parser.add_argument("--limit", type=int, default=100, help="max registry entries to pull (only with --with-registry)")
    args = parser.parse_args()

    collection = MongoClient(MONGO_URL)[DATABASE_NAME][c.MCP_SERVER_REGISTRY_COLLECTION]
    collection.create_index("key", unique=True)
    now = datetime.now(timezone.utc)

    # Deactivate curated entries removed above (deprecated upstream and/or need
    # an env-var credential this system can't inject) — an upsert alone won't
    # touch keys that no longer appear in CURATED, so this has to be explicit.
    deprecated_result = collection.update_many(
        {"key": {"$in": DEPRECATED_KEYS}},
        {"$set": {"is_active": False, "is_deleted": True}},
    )
    if deprecated_result.modified_count:
        logger.info("Deactivated %d deprecated curated entr(y/ies).", deprecated_result.modified_count)

    if not args.with_registry:
        # Curated-only run: deactivate every previously-seeded registry-sourced
        # entry so the catalog doesn't keep showing ~500 unmoderated third-party
        # listings from a prior run that DID pull the registry.
        registry_result = collection.update_many(
            {"source": "registry"},
            {"$set": {"is_active": False, "is_deleted": True}},
        )
        if registry_result.modified_count:
            logger.info(
                "Deactivated %d live-registry entr(y/ies) — re-run with --with-registry to bring them back.",
                registry_result.modified_count,
            )

    seeded = 0
    for entry in CURATED:
        entry.setdefault("source", "curated")
        _upsert(collection, entry, now)
        seeded += 1

    if args.with_registry:
        registry = _fetch_registry(args.limit)
        seen = {e["key"] for e in CURATED}
        for entry in registry:
            if entry["key"] in seen:
                continue
            _upsert(collection, entry, now)
            seeded += 1
        logger.info("Pulled %d entries from the official MCP registry.", len(registry))

    total = collection.count_documents({"is_active": True, "is_deleted": {"$ne": True}})
    logger.info("Seeded %d entries; %d active in mcp_server_registry.", seeded, total)


if __name__ == "__main__":
    main()

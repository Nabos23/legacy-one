"""
MCP server module — service layer.

This single module holds all MCP business logic (the module follows the standard
4-file shape: routes / schemas / models / services). It is organised, top to
bottom, low-level first:

1. OAuth token storage   — encrypted, sync-pymongo token store.
2. OAuth runtime helpers — resolve/refresh bearer headers at connect time.
3. Connection            — parse a connection string into a transport-agnostic config.
4. Low-level client      — connect to any MCP server and call its tools (sync).
5. Discovery             — live handshake: connect, initialise, list tools.
6. Catalog               — browse-and-connect source backed by mcp_server_registry.
7. Agent-runtime tools   — turn stored server docs into (tools, callables) for agents.
8. Interactive OAuth     — the two-step "click Authorize" consent flow.
9. CRUD services         — create / discover / list / update / soft-delete instances.
10. Agent<->tool junction — per-tool attach/detach/list (agent_mcp_tools collection).
"""

import asyncio
import base64
import logging
import re
import secrets
import shlex
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple
from urllib.parse import quote, urlencode, urlparse

import httpx
from bson import ObjectId
from fastapi import HTTPException, status
from mcp.client.auth import PKCEParameters
from mcp.client.auth.utils import (
    build_oauth_authorization_server_metadata_discovery_urls,
    build_protected_resource_metadata_discovery_urls,
    create_client_registration_request,
    create_oauth_metadata_request,
    get_client_metadata_scopes,
    handle_auth_metadata_response,
    handle_protected_resource_response,
    handle_registration_response,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken
from mcp.shared.auth_utils import resource_url_from_server_url
from starlette.concurrency import run_in_threadpool

from backend.core.config import settings
from backend.core.encryption import decrypt, encrypt
from backend.core.softdelete import NOT_DELETED, soft_delete_update
from backend.agent.services import _merge_mcp_into_prompt
from backend.db import constants as c
from backend.db.database import (
    agent_mcp_tools_collection,
    agent_mcp_tools_sync,
    agents_collection,
    mcp_oauth_flows_collection,
    mcp_oauth_tokens_sync,
    mcp_server_registry_collection,
    mcp_servers_collection,
    organizations_collection,
    sync_db,
)
from backend.mcp_server.schemas import (
    McpAgentToolPublic,
    McpCatalogEntry,
    McpServerCreate,
    McpServerPublic,
    McpServerUpdate,
    McpTestConnectionRequest,
    McpTestConnectionResult,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# 1. OAuth token storage — encrypted, sync pymongo (safe from the session loop)
# ===========================================================================

class MongoTokenStorage:
    """Per-server OAuth token + client-registration store (TokenStorage protocol).

    Backed by the SYNC pymongo client so it is safe to call from the MCP session
    thread's private event loop (motor is bound to the loop it was created on).
    Keyed by ``storage_key`` — the ``mcp_servers`` document id. Token blobs and
    client registration are encrypted at rest via backend.core.encryption.
    """

    def __init__(self, storage_key: str):
        self._key = storage_key

    def _doc(self) -> dict:
        return mcp_oauth_tokens_sync.find_one({"storage_key": self._key}) or {}

    def _set(self, fields: dict) -> None:
        fields["updated_at"] = time.time()
        mcp_oauth_tokens_sync.update_one(
            {"storage_key": self._key}, {"$set": fields}, upsert=True
        )

    # --- TokenStorage protocol (async) -------------------------------------

    async def get_tokens(self) -> Optional[OAuthToken]:
        blob = self._doc().get("tokens")
        return OAuthToken.model_validate_json(decrypt(blob)) if blob else None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._set({
            "tokens": encrypt(tokens.model_dump_json()),
            # Plain (non-secret) expiry mirror so the runtime can check staleness
            # without decrypting on every connect.
            "expires_at": (time.time() + tokens.expires_in) if tokens.expires_in else None,
        })

    async def get_client_info(self) -> Optional[OAuthClientInformationFull]:
        blob = self._doc().get("client_info")
        return OAuthClientInformationFull.model_validate_json(decrypt(blob)) if blob else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self._set({"client_info": encrypt(client_info.model_dump_json())})

    # --- Sync helpers used by the runtime refresh path ---------------------

    def read_tokens_sync(self) -> Optional[OAuthToken]:
        blob = self._doc().get("tokens")
        return OAuthToken.model_validate_json(decrypt(blob)) if blob else None

    def read_client_info_sync(self) -> Optional[OAuthClientInformationFull]:
        blob = self._doc().get("client_info")
        return OAuthClientInformationFull.model_validate_json(decrypt(blob)) if blob else None

    def read_meta_sync(self) -> dict:
        """Non-secret refresh metadata: token_endpoint, resource, expires_at."""
        doc = self._doc()
        return {
            "token_endpoint": doc.get("token_endpoint"),
            "resource": doc.get("resource"),
            "expires_at": doc.get("expires_at"),
        }

    def save_runtime_meta(
        self,
        *,
        client_info: OAuthClientInformationFull,
        tokens: OAuthToken,
        token_endpoint: str,
        resource: Optional[str],
    ) -> None:
        """Persist everything the runtime needs in one write (used on completion)."""
        self._set({
            "client_info": encrypt(client_info.model_dump_json()),
            "tokens": encrypt(tokens.model_dump_json()),
            "token_endpoint": token_endpoint,
            "resource": resource,
            "expires_at": (time.time() + tokens.expires_in) if tokens.expires_in else None,
        })

    def write_tokens_sync(self, tokens: OAuthToken) -> None:
        self._set({
            "tokens": encrypt(tokens.model_dump_json()),
            "expires_at": (time.time() + tokens.expires_in) if tokens.expires_in else None,
        })

    def delete(self) -> None:
        mcp_oauth_tokens_sync.delete_one({"storage_key": self._key})


# ===========================================================================
# 2. OAuth runtime helpers — low-level, no service/discovery dependencies
# ===========================================================================

_CALLBACK_PATH = "/mcp-servers/oauth/callback"


class OAuthNotAuthorized(Exception):
    """Raised when an OAuth MCP server has no stored token (not yet authorized)."""


def redirect_uri() -> str:
    """The registered redirect URI the OAuth provider sends the browser back to."""
    return settings.MCP_OAUTH_REDIRECT_BASE.rstrip("/") + _CALLBACK_PATH


def auth_base_url(server_url: str) -> str:
    parsed = urlparse(server_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def build_client_metadata(scope: Optional[str]) -> OAuthClientMetadata:
    """Client metadata used for Dynamic Client Registration."""
    return OAuthClientMetadata(
        client_name="One-AI MCP Connector",
        redirect_uris=[redirect_uri()],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method="client_secret_post",
        scope=scope,
    )


def apply_client_auth(
    client_info: OAuthClientInformationFull, data: dict, headers: dict
) -> None:
    """Attach client credentials to a token request per the registered auth method."""
    method = client_info.token_endpoint_auth_method
    if method == "client_secret_basic" and client_info.client_id and client_info.client_secret:
        creds = f"{quote(client_info.client_id, safe='')}:{quote(client_info.client_secret, safe='')}"
        headers["Authorization"] = "Basic " + base64.b64encode(creds.encode()).decode()
    elif method == "client_secret_post" and client_info.client_secret:
        data["client_secret"] = client_info.client_secret


def _refresh_sync(
    storage: MongoTokenStorage, tokens: OAuthToken, meta: dict
) -> OAuthToken:
    """Exchange the refresh token for a fresh access token (synchronous)."""
    client_info = storage.read_client_info_sync()
    if not client_info or not tokens.refresh_token:
        return tokens

    data = {
        "grant_type": "refresh_token",
        "refresh_token": tokens.refresh_token,
        "client_id": client_info.client_id,
    }
    if meta.get("resource"):
        data["resource"] = meta["resource"]
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    apply_client_auth(client_info, data, headers)

    try:
        with httpx.Client(timeout=20.0) as http:
            resp = http.post(meta["token_endpoint"], data=data, headers=headers)
    except Exception as exc:  # noqa: BLE001 - surface as stale-token, caller will 401
        logger.warning("OAuth refresh request failed: %s", exc)
        return tokens

    if resp.status_code != 200:
        logger.warning("OAuth refresh rejected (%s): %s", resp.status_code, resp.text[:200])
        return tokens

    new = OAuthToken.model_validate_json(resp.content)
    if not new.refresh_token:
        # Many providers omit the refresh_token on refresh — keep the existing one.
        new.refresh_token = tokens.refresh_token
    storage.write_tokens_sync(new)
    logger.info("OAuth token refreshed for MCP server %s", storage._key)
    return new


def resolve_oauth_headers(server_id: str) -> dict:
    """Return ``{Authorization: Bearer <access_token>}`` for an OAuth MCP server,
    refreshing the token first if it is missing/near expiry."""
    storage = MongoTokenStorage(server_id)
    tokens = storage.read_tokens_sync()
    if not tokens or not tokens.access_token:
        raise OAuthNotAuthorized(
            f"MCP server {server_id} has no stored OAuth token — authorization not completed."
        )
    meta = storage.read_meta_sync()
    expires_at = meta.get("expires_at")
    if expires_at and time.time() > (expires_at - 60) and tokens.refresh_token:
        tokens = _refresh_sync(storage, tokens, meta)
    return {"Authorization": f"Bearer {tokens.access_token}"}


# ===========================================================================
# 3. Connection — parse/describe a connection (no I/O, single source of truth)
# ===========================================================================

# Transport identifiers used across the mcp_server module.
STDIO = "stdio"
STREAMABLE_HTTP = "streamable_http"
SSE = "sse"
WEBSOCKET = "websocket"

# Command launchers we recognise as "this is a local stdio server".
_STDIO_LAUNCHERS = {
    "npx", "uvx", "uv", "python", "python3", "node", "deno",
    "bun", "docker", "pipx", "bunx",
}


@dataclass
class MCPServerConfig:
    """Validated, transport-agnostic description of one MCP server connection."""

    # stdio transport — run a local process
    command: Optional[str] = None          # e.g. "npx", "python", "uvx"
    args: List[str] = field(default_factory=list)
    env: Optional[Dict[str, str]] = None   # extra env vars for the subprocess

    # HTTP (streamable_http / sse) or WebSocket transport
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None

    # Explicit transport override. When None, `detect_transport` infers it.
    transport: Optional[str] = None

    timeout: float = 30.0                  # seconds for connection + per-call


def detect_transport(config: MCPServerConfig) -> str:
    """Resolve the transport for a config, honouring an explicit override."""
    if config.transport:
        return config.transport
    if config.url:
        lowered = config.url.lower()
        if lowered.startswith(("ws://", "wss://")):
            return WEBSOCKET
        # Legacy HTTP+SSE servers expose a `/sse` endpoint; everything else
        # on http(s) speaks the current Streamable HTTP transport.
        if lowered.rstrip("/").endswith("/sse"):
            return SSE
        return STREAMABLE_HTTP
    if config.command:
        return STDIO
    raise ValueError(
        "MCPServerConfig requires either 'command' (stdio) or 'url' (HTTP/WebSocket)."
    )


def parse_connection_string(
    raw: str,
    *,
    token: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 30.0,
) -> MCPServerConfig:
    """
    Turn a raw user-supplied connection string into a validated config.

    Accepted shapes
    ---------------
    - ``https://host/mcp``      → Streamable HTTP (current remote standard)
    - ``https://host/sse``      → HTTP+SSE (legacy remote servers)
    - ``wss://host/ws``         → WebSocket
    - ``npx -y @scope/server``  → stdio (any recognised launcher, shlex-split)

    A bearer ``token`` (or explicit ``headers``) is attached for HTTP/WS servers.

    Raises
    ------
    ValueError
        If the string is empty or its shape can't be recognised. The message is
        safe to surface directly to the user.
    """
    if not raw or not raw.strip():
        raise ValueError("Connection string is empty.")

    text = raw.strip()
    merged_headers = dict(headers or {})
    if token:
        merged_headers.setdefault("Authorization", f"Bearer {token}")
    merged_headers = merged_headers or None

    lowered = text.lower()

    # --- URL transports -----------------------------------------------------
    if lowered.startswith(("http://", "https://")):
        transport = SSE if lowered.rstrip("/").endswith("/sse") else STREAMABLE_HTTP
        return MCPServerConfig(
            url=text, headers=merged_headers, transport=transport, timeout=timeout
        )

    if lowered.startswith(("ws://", "wss://")):
        return MCPServerConfig(
            url=text, headers=merged_headers, transport=WEBSOCKET, timeout=timeout
        )

    # --- stdio (local process) ---------------------------------------------
    try:
        parts = shlex.split(text)
    except ValueError as exc:
        raise ValueError(f"Could not parse command: {exc}") from exc

    if parts and parts[0] in _STDIO_LAUNCHERS:
        return MCPServerConfig(
            command=parts[0], args=parts[1:], transport=STDIO, timeout=timeout
        )

    raise ValueError(
        "Unrecognised connection string. Use an http(s):// or ws(s):// URL for a "
        "remote server, or a launcher command (e.g. "
        "'npx -y @modelcontextprotocol/server-filesystem /tmp') for a local one."
    )


def config_from_doc(doc: dict) -> MCPServerConfig:
    """
    Build an ``MCPServerConfig`` from a stored ``mcp_servers`` document.

    Handles both the new shape (``connection_string`` + resolved ``transport``)
    and the legacy shape (explicit ``command``/``url`` fields).
    """
    timeout = doc.get("timeout", 30.0)

    # OAuth-backed remote servers: resolve a fresh Bearer header (refreshing the
    # stored token if needed) and connect over streamable_http.
    if doc.get("auth_type") == "oauth":
        headers = resolve_oauth_headers(str(doc["_id"]))
        return MCPServerConfig(
            url=doc["connection_string"],
            headers=headers,
            transport=doc.get("transport") or STREAMABLE_HTTP,
            timeout=timeout,
        )

    connection_string = doc.get("connection_string")
    if connection_string:
        config = parse_connection_string(
            connection_string,
            headers=doc.get("headers"),
            timeout=timeout,
        )
        # Trust a transport explicitly resolved at create time over re-inference.
        if doc.get("transport"):
            config.transport = doc["transport"]
        if doc.get("env"):
            config.env = doc["env"]
        return config

    return MCPServerConfig(
        command=doc.get("command"),
        args=doc.get("args", []),
        env=doc.get("env"),
        url=doc.get("url"),
        headers=doc.get("headers"),
        transport=doc.get("transport"),
        timeout=timeout,
    )


# ===========================================================================
# 4. Low-level client — connect to any MCP server, expose tools to sync callers
# ===========================================================================

def _mcp_tools_to_specs(mcp_tools) -> List[dict]:
    return [
        {
            "name": t.name,
            "description": t.description or "",
            "input_schema": t.inputSchema,
        }
        for t in mcp_tools
    ]


def specs_to_litellm(specs: List[dict]) -> List[dict]:
    """Convert stored tool specs into LiteLLM-format tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s.get("description", ""),
                "parameters": s.get("input_schema") or {"type": "object", "properties": {}},
            },
        }
        for s in specs
    ]


def _content_to_str(content_list) -> str:
    return "\n".join(
        c.text if hasattr(c, "text") else str(c) for c in content_list
    )


class _MCPSessionThread:
    """Keeps a transport + ClientSession alive on a dedicated daemon-thread loop,
    so the rest of the codebase can drive MCP synchronously."""

    def __init__(self, config: MCPServerConfig):
        self._config = config
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._session = None
        self._ready = threading.Event()
        self._error: Optional[Exception] = None
        self._stop_event: Optional[asyncio.Event] = None  # set in background loop

        thread = threading.Thread(target=self._run_loop, daemon=True, name="mcp-session")
        thread.start()

        if not self._ready.wait(timeout=config.timeout):
            raise TimeoutError(f"MCP server did not respond within {config.timeout}s.")
        if self._error:
            raise self._error

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._lifecycle())

    async def _lifecycle(self):
        self._stop_event = asyncio.Event()
        transport = detect_transport(self._config)

        try:
            from mcp import ClientSession

            if transport == STDIO:
                from mcp import StdioServerParameters
                from mcp.client.stdio import stdio_client

                params = StdioServerParameters(
                    command=self._config.command,
                    args=self._config.args,
                    env=self._config.env,
                )
                ctx = stdio_client(params)

            elif transport == STREAMABLE_HTTP:
                from mcp.client.streamable_http import streamablehttp_client

                ctx = streamablehttp_client(
                    url=self._config.url,
                    headers=self._config.headers or {},
                )

            elif transport == SSE:
                from mcp.client.sse import sse_client

                ctx = sse_client(
                    url=self._config.url,
                    headers=self._config.headers or {},
                )

            elif transport == WEBSOCKET:
                from mcp.client.websocket import websocket_client

                ctx = websocket_client(url=self._config.url)

            else:  # pragma: no cover - detect_transport never returns other values
                raise ValueError(f"Unsupported transport '{transport}'.")

            async with ctx as streams:
                # stdio/sse/websocket yield (read, write);
                # streamable_http yields (read, write, get_session_id).
                read, write = streams[0], streams[1]
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session
                    self._ready.set()
                    await self._stop_event.wait()   # stay open until close()

        except Exception as exc:  # noqa: BLE001 - propagate to the constructing thread
            self._error = exc
            self._ready.set()

    # ------------------------------------------------------------------
    # Public: submit a coroutine from any thread and block for the result
    # ------------------------------------------------------------------

    def run(self, coro: Coroutine) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=self._config.timeout)

    def close(self):
        if self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)

    # ------------------------------------------------------------------
    # MCP operations (async, run via self.run())
    # ------------------------------------------------------------------

    async def _list_tools(self):
        """Fetch every tool, following `nextCursor` — `tools/list` is a paginated
        operation per spec (servers MAY split large tool sets across pages) and
        the SDK's `list_tools()` returns only one page per call.
        """
        tools = []
        cursor: Optional[str] = None
        seen_cursors: set = set()
        while True:
            result = await self._session.list_tools(cursor=cursor)
            tools.extend(result.tools)
            cursor = result.nextCursor
            if not cursor or cursor in seen_cursors:
                break
            seen_cursors.add(cursor)
        return tools

    async def _call_tool(self, name: str, arguments: dict) -> str:
        result = await self._session.call_tool(name, arguments)
        return _content_to_str(result.content)


def list_mcp_tools(config: MCPServerConfig) -> List[dict]:
    """
    Connect, list tools, and disconnect. Returns raw tool specs
    (``{name, description, input_schema}``) for discovery / persistence.

    Raises whatever the connection raises (TimeoutError, auth/protocol errors)
    so callers can surface a precise reason.
    """
    session_thread = _MCPSessionThread(config)
    try:
        mcp_tools = session_thread.run(session_thread._list_tools())
        specs = _mcp_tools_to_specs(mcp_tools)
        logger.info(
            "MCP discovery via %s — %d tool(s): %s",
            detect_transport(config),
            len(specs),
            [s["name"] for s in specs],
        )
        return specs
    finally:
        session_thread.close()


def connect_mcp_server(
    config: MCPServerConfig,
) -> Tuple[List[dict], Dict[str, Callable[[dict], str]]]:
    """
    Connect to any MCP server and return tools ready for an agent.

    Returns
    -------
    tools : List[dict]
        LiteLLM-format tool definitions.
    tool_callables : Dict[str, Callable[[dict], str]]
        Sync callable per tool — accepts an input dict, returns a string result.
    """
    session_thread = _MCPSessionThread(config)
    mcp_tools = session_thread.run(session_thread._list_tools())
    logger.info(
        "MCP server connected via %s — %d tool(s): %s",
        detect_transport(config),
        len(mcp_tools),
        [t.name for t in mcp_tools],
    )

    specs = _mcp_tools_to_specs(mcp_tools)
    litellm_tools = specs_to_litellm(specs)
    tool_callables: Dict[str, Callable[[dict], str]] = {
        s["name"]: (
            lambda inp, _name=s["name"]: session_thread.run(
                session_thread._call_tool(_name, inp)
            )
        )
        for s in specs
    }
    return litellm_tools, tool_callables


# ===========================================================================
# 5. Discovery — the live handshake (connect, initialise, list tools)
# ===========================================================================

class MCPConnectionError(Exception):
    """Raised when a connection string is invalid or the server is unreachable."""


def _describe_exc(exc: BaseException) -> str:
    """
    Produce a human-readable reason from an exception, unwrapping anyio/MCP
    ExceptionGroups (the streamable_http client wraps the real error in a
    TaskGroup, whose str is the useless "unhandled errors in a TaskGroup").
    """
    leaves: List[str] = []

    def _walk(e: BaseException) -> None:
        group = getattr(e, "exceptions", None)
        if group:  # BaseExceptionGroup / ExceptionGroup
            for sub in group:
                _walk(sub)
        else:
            text = str(e).strip() or e.__class__.__name__
            if text not in leaves:
                leaves.append(text)

    _walk(exc)
    return "; ".join(leaves) if leaves else str(exc)


async def probe_connection_string(
    connection_string: str,
    *,
    token: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 30.0,
) -> Tuple[MCPServerConfig, str, List[dict]]:
    """
    Evaluate a connection string end to end: parse → connect → list tools.

    Returns
    -------
    (config, transport, tool_specs)

    Raises
    ------
    MCPConnectionError
        With a user-safe message for both malformed strings (syntactic) and
        unreachable / failing servers (semantic).
    """
    try:
        config = parse_connection_string(
            connection_string, token=token, headers=headers, timeout=timeout
        )
    except ValueError as exc:
        raise MCPConnectionError(str(exc)) from exc

    transport = detect_transport(config)
    try:
        specs = await run_in_threadpool(list_mcp_tools, config)
    except TimeoutError as exc:
        raise MCPConnectionError(
            f"Timed out connecting to the MCP server after {timeout:.0f}s."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - surface a precise reason to the caller
        raise MCPConnectionError(
            f"Could not connect to the MCP server ({transport}): {_describe_exc(exc)}"
        ) from exc

    return config, transport, specs


async def refresh_server_tools(doc: dict) -> List[dict]:
    """Re-probe an already-stored server document and return fresh tool specs."""
    config = config_from_doc(doc)
    transport = detect_transport(config)
    try:
        return await run_in_threadpool(list_mcp_tools, config)
    except TimeoutError as exc:
        raise MCPConnectionError(
            f"Timed out connecting to the MCP server after {config.timeout:.0f}s."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise MCPConnectionError(
            f"Could not connect to the MCP server ({transport}): {exc}"
        ) from exc


# ===========================================================================
# 6. Catalog — browse-and-connect source backed by mcp_server_registry
# ===========================================================================

_PLACEHOLDER_RE = re.compile(r"<([A-Za-z0-9_]+)>")


def resolve_template(
    template: str,
    placeholders: Optional[Dict[str, str]] = None,
    *,
    requires: Optional[List[str]] = None,
) -> str:
    """
    Fill ``<KEY>`` tokens in a connection_string template from `placeholders`.

    `placeholders` keys may be bare (``PATH``) or bracketed (``<PATH>``). Any
    ``<KEY>`` token left unfilled raises ValueError — a registry entry must never
    produce a connection string with a literal placeholder in it.

    `requires` is accepted for symmetry with registry entries but the real check
    is simply "no ``<...>`` token survives".
    """
    values: Dict[str, str] = {}
    for raw_key, val in (placeholders or {}).items():
        key = raw_key.strip("<>")
        values[key] = val

    def _sub(match: "re.Match") -> str:
        key = match.group(1)
        if key not in values:
            raise ValueError(f"Missing value for required placeholder '<{key}>'.")
        return values[key]

    resolved = _PLACEHOLDER_RE.sub(_sub, template or "")
    return resolved


def _to_entry(doc: dict) -> dict:
    return {
        "key": doc.get("key", ""),
        "name": doc.get("name", ""),
        "description": doc.get("description", ""),
        "category": doc.get("category"),
        "transport": doc.get("transport"),
        "connection_string": doc.get("connection_string", ""),
        "requires": doc.get("requires", []),
        "source": doc.get("source", "curated"),
        "homepage": doc.get("homepage"),
    }


async def search_catalog(query: Optional[str] = None, limit: int = 30) -> List[dict]:
    """
    Return catalog entries from `mcp_server_registry` matching `query`.

    `query` is matched case-insensitively against name, description, key, and
    category. With no query, returns the first `limit` active entries by name.
    """
    mongo_query: dict = {"is_active": True, **NOT_DELETED}
    if query:
        rx = {"$regex": re.escape(query), "$options": "i"}
        mongo_query["$or"] = [
            {"name": rx}, {"description": rx}, {"key": rx}, {"category": rx},
        ]

    cursor = mcp_server_registry_collection.find(mongo_query).sort("name", 1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_to_entry(d) for d in docs]


# ===========================================================================
# 7. Agent-runtime tools — stored server docs → (tools, callables) for agents
# ===========================================================================

# Process-level cache of live MCP sessions, keyed by server _id. A session opens
# on the first tool call to that server and is reused for the process lifetime.
# Sessions run on daemon threads, so they are cleaned up at process exit.
_SESSIONS: Dict[str, _MCPSessionThread] = {}


def call_mcp_tool(server_doc: dict, tool_name: str, args: dict) -> str:
    """
    Execute one MCP tool call against the server described by `server_doc`.

    Synchronous and blocking (it drives the server's session thread), so callers
    inside async code should wrap it in run_in_threadpool. Reuses a cached session
    per server id, opening one lazily on first use.
    """
    key = str(server_doc.get("_id") or server_doc.get("name", ""))
    session = _SESSIONS.get(key)
    if session is None:
        session = _MCPSessionThread(config_from_doc(server_doc))
        _SESSIONS[key] = session
    return session.run(session._call_tool(tool_name, args))


def _lazy_callable(
    sessions: Dict[str, _MCPSessionThread],
    server_key: str,
    config: MCPServerConfig,
    tool_name: str,
) -> Callable[[dict], str]:
    """Return a sync callable that connects on first use and routes by name."""

    def call(inp: dict) -> str:
        session = sessions.get(server_key)
        if session is None:
            session = _MCPSessionThread(config)
            sessions[server_key] = session
        return session.run(session._call_tool(tool_name, inp))

    return call


def build_mcp_tools(
    server_docs: List[dict],
) -> Tuple[List[dict], Dict[str, Callable[[dict], str]]]:
    """
    Build LiteLLM tool definitions + lazy callables for a set of MCP servers.

    Parameters
    ----------
    server_docs : list of stored ``mcp_servers`` documents (each may carry a
        cached ``tools`` list of ``{name, description, input_schema}`` specs).

    Returns
    -------
    (tools, callables) ready to merge into a SubAgent.
    """
    tools: List[dict] = []
    callables: Dict[str, Callable[[dict], str]] = {}
    sessions: Dict[str, _MCPSessionThread] = {}  # shared closure: server -> live session

    for doc in server_docs:
        specs = doc.get("tools") or []
        if not specs:
            logger.warning(
                "MCP server '%s' has no discovered tools — skipping (run discovery).",
                doc.get("name", doc.get("_id")),
            )
            continue

        server_key = str(doc.get("_id", doc.get("name", "")))
        config = config_from_doc(doc)

        tools.extend(specs_to_litellm(specs))
        for spec in specs:
            callables[spec["name"]] = _lazy_callable(
                sessions, server_key, config, spec["name"]
            )

    return tools, callables


def _filter_server_docs_to_tools(server_docs: List[dict], links: List[dict]) -> List[dict]:
    """Trim each server doc's cached `tools` list down to only the tool names
    an agent has actually been attached to (per `links`, rows from
    `agent_mcp_tools`). A server with no matching links is dropped entirely.
    """
    wanted: Dict[str, set] = {}
    for link in links:
        wanted.setdefault(link["mcp_server_id"], set()).add(link["tool_name"])

    filtered: List[dict] = []
    for doc in server_docs:
        names = wanted.get(str(doc["_id"]))
        if not names:
            continue
        trimmed = dict(doc)
        trimmed["tools"] = [t for t in doc.get("tools", []) if t["name"] in names]
        filtered.append(trimmed)
    return filtered


async def load_agent_mcp_tools_async(agent_id: str) -> Tuple[List[dict], Dict[str, Callable[[dict], str]]]:
    """Async loader used by the single-agent chat path (`backend/chat/services.py`).

    Reads this agent's per-tool attachments from `agent_mcp_tools` instead of
    the legacy whole-server `agent.mcp_server_ids`, so only the specific tools
    attached to this agent are exposed — never a whole server at once.
    """
    links = await agent_mcp_tools_collection.find({"agent_id": agent_id}).to_list(None)
    if not links:
        return [], {}
    server_ids = [ObjectId(l["mcp_server_id"]) for l in links if ObjectId.is_valid(l["mcp_server_id"])]
    server_docs = await mcp_servers_collection.find(
        {"_id": {"$in": server_ids}, "is_active": True, "is_deleted": {"$ne": True}}
    ).to_list(None)
    return build_mcp_tools(_filter_server_docs_to_tools(server_docs, links))


def load_agent_mcp_tools_sync(
    agent_id: str,
) -> Tuple[List[dict], Dict[str, Callable[[dict], str]], Dict[str, str]]:
    """Sync loader used by the multi-agent orchestration path
    (`ai/multi_orchestration/graph_loader.py`, which runs on pymongo `sync_db`).
    Same per-tool filtering as `load_agent_mcp_tools_async`, just synchronous.

    Also returns ``{tool_name: server_name}``. ``build_mcp_tools`` discards which
    server each tool came from, but supervisor-mode routing needs it: the
    Supervisor should see "this agent can reach Notion", not a list of opaque
    tool names.
    """
    links = list(agent_mcp_tools_sync.find({"agent_id": agent_id}))
    if not links:
        return [], {}, {}
    server_ids = [ObjectId(l["mcp_server_id"]) for l in links if ObjectId.is_valid(l["mcp_server_id"])]
    server_docs = list(sync_db[c.MCP_SERVERS_COLLECTION].find(
        {"_id": {"$in": server_ids}, "is_active": True, "is_deleted": {"$ne": True}}
    ))
    filtered = _filter_server_docs_to_tools(server_docs, links)
    tools, callables = build_mcp_tools(filtered)
    tool_owner = {
        spec["name"]: doc.get("name") or _server_name(doc.get("server_url", ""))
        for doc in filtered
        for spec in (doc.get("tools") or [])
    }
    return tools, callables, tool_owner


# ===========================================================================
# 8. Interactive OAuth — the two-step "click Authorize" consent flow
# ===========================================================================

class OAuthError(Exception):
    """User-safe OAuth flow error."""


def _server_name(server_url: str) -> str:
    return urlparse(server_url).netloc or "MCP Server"


async def start_authorization(
    *,
    connection_string: str,
    organization_id: str,
    agent_id: str | None = None,
    name: str | None = None,
    user_description: str | None = None,
    scope: str | None = None,
) -> dict:
    """Discover + register + build the authorization URL. Returns {authorization_url, state}."""
    server_url = connection_string.strip()
    if not server_url.lower().startswith(("http://", "https://")):
        raise OAuthError("OAuth is only supported for remote http(s) MCP servers.")

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as http:
        # 1. Protected Resource Metadata -> authorization server URL.
        prm = None
        for url in build_protected_resource_metadata_discovery_urls(None, server_url):
            try:
                resp = await http.send(create_oauth_metadata_request(url))
            except Exception:  # noqa: BLE001 - try the next discovery URL
                continue
            prm = await handle_protected_resource_response(resp)
            if prm:
                break
        auth_server_url = (
            str(prm.authorization_servers[0]) if (prm and prm.authorization_servers) else None
        )

        # 2. Authorization Server Metadata -> endpoints.
        asm = None
        for url in build_oauth_authorization_server_metadata_discovery_urls(auth_server_url, server_url):
            try:
                resp = await http.send(create_oauth_metadata_request(url))
            except Exception:  # noqa: BLE001
                continue
            ok, candidate = await handle_auth_metadata_response(resp)
            if candidate:
                asm = candidate
                break
            if not ok:
                break
        if not asm or not asm.authorization_endpoint or not asm.token_endpoint:
            raise OAuthError(
                "Could not discover the OAuth endpoints for this server. It may not "
                "support the MCP authorization spec, or the URL is wrong."
            )

        # 3. Scopes + client metadata, then Dynamic Client Registration.
        chosen_scope = scope or get_client_metadata_scopes(None, prm, asm)
        client_metadata = build_client_metadata(chosen_scope)
        try:
            reg_resp = await http.send(
                create_client_registration_request(asm, client_metadata, auth_base_url(server_url))
            )
            client_info = await handle_registration_response(reg_resp)
        except Exception as exc:  # noqa: BLE001
            raise OAuthError(f"Dynamic client registration failed: {exc}")

    # 4. PKCE + state + authorization URL.
    pkce = PKCEParameters.generate()
    state = secrets.token_urlsafe(32)
    resource = resource_url_from_server_url(server_url)
    params = {
        "response_type": "code",
        "client_id": client_info.client_id,
        "redirect_uri": redirect_uri(),
        "state": state,
        "code_challenge": pkce.code_challenge,
        "code_challenge_method": "S256",
        "resource": resource,
    }
    if chosen_scope:
        params["scope"] = chosen_scope
    authorization_url = f"{asm.authorization_endpoint}?{urlencode(params)}"

    # 5. Persist the in-flight authorization (secrets encrypted).
    now = time.time()
    await mcp_oauth_flows_collection.insert_one({
        "state": state,
        "code_verifier": encrypt(pkce.code_verifier),
        "client_info": encrypt(client_info.model_dump_json()),
        "client_id": client_info.client_id,
        "token_endpoint": str(asm.token_endpoint),
        "server_url": server_url,
        "scope": chosen_scope,
        "resource": resource,
        "redirect_uri": redirect_uri(),
        "organization_id": organization_id,
        "agent_id": agent_id,
        "name": name,
        "user_description": user_description,
        "created_at": now,
        "expires_at": now + settings.MCP_OAUTH_FLOW_TTL_SECONDS,
    })
    logger.info("OAuth authorization started for %s (state=%s)", server_url, state[:8])
    return {"authorization_url": authorization_url, "state": state}


async def complete_authorization(*, code: str, state: str) -> McpServerPublic:
    """Exchange the code for tokens, create the MCP server, discover tools, link the agent."""
    flow = await mcp_oauth_flows_collection.find_one({"state": state})
    if not flow:
        raise OAuthError("Unknown or already-used authorization. Please start again.")
    if flow.get("expires_at", 0) < time.time():
        await mcp_oauth_flows_collection.delete_one({"_id": flow["_id"]})
        raise OAuthError("Authorization expired. Please start again.")

    client_info = OAuthClientInformationFull.model_validate_json(decrypt(flow["client_info"]))
    token_endpoint = flow["token_endpoint"]
    resource = flow.get("resource")

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": flow["redirect_uri"],
        "client_id": client_info.client_id,
        "code_verifier": decrypt(flow["code_verifier"]),
    }
    if resource:
        data["resource"] = resource
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    apply_client_auth(client_info, data, headers)

    async with httpx.AsyncClient(timeout=20.0) as http:
        resp = await http.post(token_endpoint, data=data, headers=headers)
    if resp.status_code != 200:
        raise OAuthError(f"Token exchange failed ({resp.status_code}): {resp.text[:300]}")
    tokens = OAuthToken.model_validate_json(resp.content)

    # Create the mcp_servers instance (auth_type=oauth), then persist creds for runtime.
    server_url = flow["server_url"]
    now_dt = datetime.now(timezone.utc)
    doc = {
        "organization_id": flow["organization_id"],
        "agent_id": flow["agent_id"],
        "registry_key": None,
        "name": (flow.get("name") or "").strip() or _server_name(server_url),
        "user_description": flow.get("user_description"),
        "connection_string": server_url,
        "transport": "streamable_http",
        "auth_type": "oauth",
        "headers": None,
        "tools": [],
        "tool_count": 0,
        "status": "pending",
        "last_error": None,
        "discovered_at": None,
        "timeout": 30.0,
        "is_active": True,
        "created_at": now_dt,
        "is_deleted": False,
    }
    result = await mcp_servers_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    server_id = str(result.inserted_id)

    MongoTokenStorage(server_id).save_runtime_meta(
        client_info=client_info, tokens=tokens, token_endpoint=token_endpoint, resource=resource
    )

    # Discover tools now that we hold a token (config_from_doc resolves the bearer).
    try:
        specs = await refresh_server_tools(doc)
        updates = {
            "tools": specs, "tool_count": len(specs),
            "status": "connected", "discovered_at": datetime.now(timezone.utc),
        }
        doc.update(updates)
        await mcp_servers_collection.update_one({"_id": result.inserted_id}, {"$set": updates})
    except Exception as exc:  # noqa: BLE001 - keep the server, surface the error
        await mcp_servers_collection.update_one(
            {"_id": result.inserted_id}, {"$set": {"status": "error", "last_error": str(exc)}}
        )
        doc.update(status="error", last_error=str(exc))
        logger.warning("OAuth server created but tool discovery failed: %s", exc)

    if flow.get("agent_id"):
        await _attach_to_agent(doc)
    await mcp_oauth_flows_collection.delete_one({"_id": flow["_id"]})
    logger.info("OAuth MCP server %s connected for agent %s", server_id, flow.get("agent_id"))
    return _to_public(doc)


# ===========================================================================
# 9. CRUD services — create / discover / list / update / soft-delete instances
# ===========================================================================

def _to_public(doc: dict) -> McpServerPublic:
    return McpServerPublic(
        id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        agent_id=doc["agent_id"],
        registry_key=doc.get("registry_key"),
        auth_type=doc.get("auth_type", "none"),
        name=doc.get("name"),
        user_description=doc.get("user_description"),
        connection_string=doc.get("connection_string"),
        transport=doc.get("transport"),
        tools=doc.get("tools", []),
        tool_count=doc.get("tool_count", 0),
        status=doc.get("status", "pending"),
        last_error=doc.get("last_error"),
        discovered_at=doc.get("discovered_at"),
        timeout=doc.get("timeout", 30.0),
        is_active=doc.get("is_active", True),
        created_at=doc["created_at"],
    )


def _validate_object_id(server_id: str) -> ObjectId:
    if not ObjectId.is_valid(server_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found.")
    return ObjectId(server_id)


async def _validate_org_exists(org_id: str) -> None:
    """Raise 404 if org_id is not a valid ObjectId or the org doesn't exist."""
    if not ObjectId.is_valid(org_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    doc = await organizations_collection.find_one({"_id": ObjectId(org_id), **NOT_DELETED})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")


async def _resolve_registry_entry(registry_key: str) -> dict:
    """Return the active `mcp_server_registry` entry for `registry_key`, or raise."""
    doc = await mcp_server_registry_collection.find_one(
        {"key": registry_key, "is_active": True, "is_deleted": {"$ne": True}}
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active MCP registry entry with key '{registry_key}'.",
        )
    return doc


def _invalidate_graph_cache(server_doc: dict) -> None:
    """Drop cached graphs for the org/agent so a tool change applies without restart."""
    try:
        from backend.chat.graph import invalidate_org_graph, invalidate_single_agent_graph
        org_id = server_doc.get("organization_id")
        agent_id = server_doc.get("agent_id")
        if org_id:
            invalidate_org_graph(org_id)
            invalidate_single_agent_graph(org_id, agent_id)
    except Exception:  # noqa: BLE001 - cache invalidation must never break the request
        pass


async def _attach_to_agent(server_doc: dict) -> None:
    """
    Register this MCP server on its agent and merge its prompt fragment into
    agent.prompt (the parallel of create_tool's linkage + merge).
    """
    agent_id = server_doc["agent_id"]
    if ObjectId.is_valid(agent_id):
        await agents_collection.update_one(
            {"_id": ObjectId(agent_id), **NOT_DELETED},
            {"$addToSet": {"mcp_server_ids": str(server_doc["_id"])}},
        )
        registry_entry = None
        if server_doc.get("registry_key"):
            registry_entry = await mcp_server_registry_collection.find_one(
                {"key": server_doc["registry_key"], "is_deleted": {"$ne": True}}
            )
        await _merge_mcp_into_prompt(agent_id, server_doc, registry_entry)
    _invalidate_graph_cache(server_doc)


async def _detach_from_agent(server_doc: dict) -> None:
    """Remove this MCP server's id from agent.mcp_server_ids. The agent's
    prompt fragment is intentionally left untouched (same policy as
    delete_tool) -- the agent will just report it doesn't have this
    capability if asked. Revisit if this needs cleanup later.
    """
    agent_id = server_doc["agent_id"]
    if ObjectId.is_valid(agent_id):
        await agents_collection.update_one(
            {"_id": ObjectId(agent_id)},
            {"$pull": {"mcp_server_ids": str(server_doc["_id"])}},
        )
    _invalidate_graph_cache(server_doc)

async def test_connection(payload: McpTestConnectionRequest) -> McpTestConnectionResult:
    """Probe a connection string without saving it (the UI 'Test' button)."""
    try:
        _, transport, specs = await probe_connection_string(
            payload.connection_string,
            token=payload.token,
            headers=payload.headers,
            timeout=payload.timeout,
        )
    except MCPConnectionError as exc:
        return McpTestConnectionResult(ok=False, error=str(exc))

    return McpTestConnectionResult(
        ok=True, transport=transport, tools=specs, tool_count=len(specs)
    )


async def create_mcp_server(payload: McpServerCreate) -> McpServerPublic:
    """
    Connect an MCP server to an agent. Two flows (see McpServerCreate):

    - Flow A (catalog): `registry_key` → resolve the `mcp_server_registry` entry,
      fill its connection_string template from `placeholders`.
    - Flow B (custom): a raw `connection_string` provided directly.

    Either way the connection is probed, its tools discovered + cached in the
    `mcp_servers` collection, and the instance linked to the agent via the MCP
    container doc in the `tools` collection — so MCP tools are used like any other.
    """
    await _validate_org_exists(payload.organization_id)

    # Resolve the connection string + default name from whichever flow applies.
    if payload.registry_key:
        registry_entry = await _resolve_registry_entry(payload.registry_key)
        try:
            connection_string = resolve_template(
                registry_entry.get("connection_string", ""),
                payload.placeholders,
                requires=registry_entry.get("requires", []),
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
        default_name = registry_entry["name"]
    else:
        connection_string = payload.connection_string
        default_name = "Custom MCP"

    try:
        config, transport, specs = await probe_connection_string(
            connection_string,
            token=payload.token,
            headers=payload.headers,
            timeout=payload.timeout,
        )
    except MCPConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    now = datetime.now(timezone.utc)
    doc = {
        "organization_id": payload.organization_id,
        "agent_id": payload.agent_id,
        "registry_key": payload.registry_key,
        "name": payload.name.strip() if payload.name and payload.name.strip() else default_name,
        "user_description": payload.user_description,
        "connection_string": connection_string,
        "transport": transport,
        "headers": config.headers,
        "tools": specs,
        "tool_count": len(specs),
        "status": "connected",
        "last_error": None,
        "discovered_at": now,
        "timeout": payload.timeout,
        "is_active": True,
        "created_at": now,
        "is_deleted": False,
    }
    result = await mcp_servers_collection.insert_one(doc)
    doc["_id"] = result.inserted_id

    # Legacy single-owner attach — only runs if the caller supplied agent_id.
    # Standalone servers (agent_id=None) are attached per-tool afterward via
    # attach_mcp_tools(), not here.
    if payload.agent_id:
        await _attach_to_agent(doc)

    return _to_public(doc)


async def discover_mcp_server(server_id: str) -> McpServerPublic:
    """Re-probe an existing instance and refresh its cached tool list."""
    oid = _validate_object_id(server_id)
    doc = await mcp_servers_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found.")

    try:
        specs = await refresh_server_tools(doc)
    except MCPConnectionError as exc:
        await mcp_servers_collection.update_one(
            {"_id": oid}, {"$set": {"status": "error", "last_error": str(exc)}}
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    updates = {
        "tools": specs,
        "tool_count": len(specs),
        "status": "connected",
        "last_error": None,
        "discovered_at": datetime.now(timezone.utc),
    }
    doc = await mcp_servers_collection.find_one_and_update(
        {"_id": oid}, {"$set": updates}, return_document=True
    )
    # Tools refreshed — rebuild mcp_prompt so it reflects the latest tool list.
    if doc and doc.get("agent_id"):
        registry_entry = None
        if doc.get("registry_key"):
            registry_entry = await mcp_server_registry_collection.find_one(
                {"key": doc["registry_key"], "is_deleted": {"$ne": True}}
            )
        await _merge_mcp_into_prompt(doc["agent_id"], doc, registry_entry)
    return _to_public(doc)


async def list_mcp_servers(
    organization_id: str,
    skip: int = 0,
    limit: int = 20,
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> Tuple[List[McpServerPublic], int]:
    query: dict = {"organization_id": organization_id, **NOT_DELETED}
    if search:
        query["name"] = {"$regex": re.escape(search), "$options": "i"}
    if status_filter:
        query["status"] = status_filter
    if agent_id:
        query["agent_id"] = agent_id
    total = await mcp_servers_collection.count_documents(query)
    cursor = mcp_servers_collection.find(query).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_to_public(doc) for doc in docs], total


async def list_mcp_servers_by_agent(
    agent_id: str, skip: int = 0, limit: int = 20
) -> Tuple[List[McpServerPublic], int]:
    """List MCP instances attached to a specific agent (paginated)."""
    query = {"agent_id": agent_id, **NOT_DELETED}
    total = await mcp_servers_collection.count_documents(query)
    cursor = mcp_servers_collection.find(query).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_to_public(doc) for doc in docs], total


async def get_mcp_server(server_id: str) -> McpServerPublic:
    oid = _validate_object_id(server_id)
    doc = await mcp_servers_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found.")
    return _to_public(doc)


async def update_mcp_server(server_id: str, payload: McpServerUpdate) -> McpServerPublic:
    oid = _validate_object_id(server_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update.")

    # If the connection string changes, re-probe so cached tools stay accurate.
    if updates.get("connection_string"):
        try:
            config, transport, specs = await probe_connection_string(
                updates["connection_string"],
                token=updates.get("token"),
                headers=updates.get("headers"),
                timeout=updates.get("timeout", 30.0),
            )
        except MCPConnectionError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        updates.update(
            transport=transport,
            headers=config.headers,
            tools=specs,
            tool_count=len(specs),
            status="connected",
            last_error=None,
            discovered_at=datetime.now(timezone.utc),
        )
    updates.pop("token", None)  # token is folded into headers, never stored raw

    doc = await mcp_servers_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {"$set": updates},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found.")
    return _to_public(doc)


async def delete_mcp_server(server_id: str) -> None:
    oid = _validate_object_id(server_id)
    doc = await mcp_servers_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found.")

    await mcp_servers_collection.update_one({"_id": oid, **NOT_DELETED}, soft_delete_update())
    # Unlink from the agent (agent.mcp_server_ids) — mirror of removing a tool.
    await _detach_from_agent(doc)
    # Drop any per-tool attachments too, so no agent keeps a dangling reference
    # to a deleted server's tools.
    await agent_mcp_tools_collection.delete_many({"mcp_server_id": str(oid)})
    # Drop any stored OAuth tokens for this server.
    if doc.get("auth_type") == "oauth":
        MongoTokenStorage(str(oid)).delete()


async def list_catalog(query: Optional[str] = None, limit: int = 30) -> List[McpCatalogEntry]:
    """Browse the catalog of connectable MCP servers (curated seed + registry)."""
    entries = await search_catalog(query, limit)
    return [McpCatalogEntry(**e) for e in entries]


# ===========================================================================
# 10. Agent<->tool junction — per-tool attach/detach/list (agent_mcp_tools)
# ===========================================================================
#
# Replaces the all-or-nothing agent.mcp_server_ids attach: a server is
# connected once (standalone or legacy agent-owned, see create_mcp_server),
# and individual tools of that server are then attached to any number of
# agents independently via this section.

_agent_mcp_tools_indexes_ready = False


async def _ensure_agent_mcp_tools_indexes() -> None:
    """Create agent_mcp_tools' indexes on first real use (lazy, idempotent) —
    mirrors backend/memory/conversation_store.py's `_ensure_indexes` pattern
    so any environment self-heals its indexes without a separate admin step.
    """
    global _agent_mcp_tools_indexes_ready
    if _agent_mcp_tools_indexes_ready:
        return
    await agent_mcp_tools_collection.create_index(
        [("agent_id", 1), ("mcp_server_id", 1), ("tool_name", 1)],
        unique=True,
        background=True,
        name="agent_mcp_tool_unique",
    )
    await agent_mcp_tools_collection.create_index(
        [("mcp_server_id", 1), ("tool_name", 1)],
        background=True,
        name="agent_mcp_tool_by_server_tool",
    )
    await agent_mcp_tools_collection.create_index(
        [("agent_id", 1)],
        background=True,
        name="agent_mcp_tool_by_agent",
    )
    _agent_mcp_tools_indexes_ready = True


def _to_agent_tool_public(doc: dict, server_name: Optional[str] = None) -> McpAgentToolPublic:
    return McpAgentToolPublic(
        id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        agent_id=doc["agent_id"],
        mcp_server_id=doc["mcp_server_id"],
        mcp_server_name=server_name,
        tool_name=doc["tool_name"],
        created_at=doc["created_at"],
    )


async def _attach_one_mcp_tool(
    organization_id: str,
    agent_id: str,
    mcp_server_id: str,
    tool_name: str,
    created_by: Optional[str],
) -> dict:
    """Attach a single tool, rejecting a flat-name collision against a
    *different* server already attached to this agent (see build_mcp_tools —
    callables are keyed by flat name, so two same-named tools from different
    servers on one agent would silently shadow each other at execution time).
    """
    existing = await agent_mcp_tools_collection.find_one(
        {"agent_id": agent_id, "tool_name": tool_name, "mcp_server_id": {"$ne": mcp_server_id}}
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Tool '{tool_name}' is already attached to this agent from a "
                "different MCP server. Detach it there first — tool names "
                "must be unique per agent."
            ),
        )

    now = datetime.now(timezone.utc)
    await agent_mcp_tools_collection.update_one(
        {"agent_id": agent_id, "mcp_server_id": mcp_server_id, "tool_name": tool_name},
        {
            "$setOnInsert": {
                "organization_id": organization_id,
                "agent_id": agent_id,
                "mcp_server_id": mcp_server_id,
                "tool_name": tool_name,
                "created_at": now,
                "created_by": created_by,
            }
        },
        upsert=True,
    )
    doc = await agent_mcp_tools_collection.find_one(
        {"agent_id": agent_id, "mcp_server_id": mcp_server_id, "tool_name": tool_name}
    )
    return doc


async def attach_mcp_tools(
    organization_id: str,
    agent_id: str,
    mcp_server_id: str,
    tool_names: List[str],
    created_by: Optional[str] = None,
) -> List[McpAgentToolPublic]:
    """Attach one or more of a connected server's discovered tools to an agent.

    Validates the server belongs to `organization_id` and that every
    requested name is actually one of the server's cached, discovered tools
    (`server_doc["tools"]`) before attaching any of them.
    """
    await _ensure_agent_mcp_tools_indexes()

    oid = _validate_object_id(mcp_server_id)
    server = await mcp_servers_collection.find_one(
        {"_id": oid, "organization_id": organization_id, **NOT_DELETED}
    )
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MCP server not found.")

    available = {t["name"] for t in server.get("tools", [])}
    unknown = [name for name in tool_names if name not in available]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown tool(s) for this server: {', '.join(unknown)}.",
        )

    results = []
    for tool_name in tool_names:
        doc = await _attach_one_mcp_tool(organization_id, agent_id, mcp_server_id, tool_name, created_by)
        results.append(doc)

    _invalidate_graph_cache({"organization_id": organization_id, "agent_id": agent_id})
    return [_to_agent_tool_public(doc, server_name=server.get("name")) for doc in results]


async def detach_mcp_tool(agent_id: str, mcp_server_id: str, tool_name: str) -> bool:
    """Detach a single tool from an agent. No soft delete — a junction row is
    a pure link, same policy as `_detach_from_agent`'s real `$pull`.
    """
    result = await agent_mcp_tools_collection.delete_one(
        {"agent_id": agent_id, "mcp_server_id": mcp_server_id, "tool_name": tool_name}
    )
    if result.deleted_count:
        server = await mcp_servers_collection.find_one({"_id": ObjectId(mcp_server_id)}) if ObjectId.is_valid(mcp_server_id) else None
        org_id = server.get("organization_id") if server else None
        _invalidate_graph_cache({"organization_id": org_id, "agent_id": agent_id})
    return bool(result.deleted_count)


async def list_mcp_tools_by_agent(
    agent_id: str, skip: int = 0, limit: int = 20
) -> Tuple[List[McpAgentToolPublic], int]:
    """List tools attached to a specific agent (paginated) — mirrors
    `list_mcp_servers_by_agent`'s signature/return shape.
    """
    await _ensure_agent_mcp_tools_indexes()
    query = {"agent_id": agent_id}
    total = await agent_mcp_tools_collection.count_documents(query)
    cursor = agent_mcp_tools_collection.find(query).skip(skip).limit(limit)
    links = await cursor.to_list(length=limit)

    server_ids = list({ObjectId(l["mcp_server_id"]) for l in links if ObjectId.is_valid(l["mcp_server_id"])})
    servers = await mcp_servers_collection.find({"_id": {"$in": server_ids}}).to_list(None) if server_ids else []
    names_by_id = {str(s["_id"]): s.get("name") for s in servers}

    items = [_to_agent_tool_public(l, server_name=names_by_id.get(l["mcp_server_id"])) for l in links]
    return items, total


async def list_agents_by_mcp_tool(
    mcp_server_id: str, tool_name: str, skip: int = 0, limit: int = 20
) -> Tuple[List[McpAgentToolPublic], int]:
    """Reverse lookup: which agents have this specific tool attached (paginated)."""
    await _ensure_agent_mcp_tools_indexes()
    query = {"mcp_server_id": mcp_server_id, "tool_name": tool_name}
    total = await agent_mcp_tools_collection.count_documents(query)
    cursor = agent_mcp_tools_collection.find(query).skip(skip).limit(limit)
    links = await cursor.to_list(length=limit)
    return [_to_agent_tool_public(l) for l in links], total
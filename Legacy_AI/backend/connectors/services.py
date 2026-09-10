"""All business logic for the unified connectors module.

Follows the same thin-routes / fat-services split used in backend/mcp_server/.
Every public function corresponds to one or more route handlers; routes only
parse/validate, then delegate here.
"""

import asyncio
import hashlib
import hmac
import inspect
import logging
import math
import random
import secrets
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from bson import ObjectId
from fastapi import HTTPException

from backend.connectors.schemas import (
    AuthUrlResponse,
    ConnectorCredentialsSave,
    ConnectorRegistryItem,
    ConnectorRegistryPage,
    ConnectorSetupInfo,
    ConnectorStatus,
    ConnectorTestConnectionResult,
)
from backend.db.database import tools_permissions_registry_collection
from backend.core.config import settings
from backend.core.encryption import decrypt, decrypt_or_none, encrypt
from backend.db.database import (
    connector_credentials_collection,
    connector_instances_collection,
    connector_registry_collection,
    connector_tokens_collection,
)

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _obj_to_str(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


def _callback_uri() -> str:
    return f"{settings.CONNECTORS_CALLBACK_BASE_URI}/api/auth/connector/callback"


def resolve_owner_id(connector: dict, user_id: str, organization_id: str) -> str:
    """Return user_id or organization_id depending on connector's owner_scope."""
    if connector["owner_scope"] == "organization":
        return organization_id
    return user_id


async def _invalidate_agent_graphs_for_connector(connector_id: str) -> None:
    """Drop any cached chat graph whose agent references this connector.

    Chat/direct-agent graphs are compiled once per org (or per org+agent for
    single-agent chat) and reused across turns — their node closures capture
    the connector tools/callables available at build time. Without this, a
    reconnect never takes effect in an existing session: the graph keeps using
    the stale (missing) token/tools until something unrelated (an agent or
    tool edit) happens to invalidate the cache first.
    """
    try:
        from backend.chat.graph import invalidate_org_graph, invalidate_single_agent_graph
        from backend.db.database import agents_collection

        cursor = agents_collection.find(
            {"connector_ids": connector_id}, {"_id": 1, "organization_id": 1}
        )
        async for doc in cursor:
            org_id = doc.get("organization_id")
            if not org_id:
                continue
            invalidate_org_graph(org_id)
            invalidate_single_agent_graph(org_id, str(doc["_id"]))
    except Exception:
        logger.warning("Failed to invalidate agent graphs for connector=%s", connector_id, exc_info=True)


# ─── Registry ─────────────────────────────────────────────────────────────────

async def get_registry() -> list[ConnectorRegistryItem]:
    """Return connectors that are active AND visible (client-facing)."""
    cursor = connector_registry_collection.find({"is_visible": {"$ne": False}})
    results = []
    async for doc in cursor:
        perm_doc = await tools_permissions_registry_collection.find_one(
            {"$or": [{"connector_id": str(doc["_id"])}, {"provider_id": doc.get("provider_id")}]}
        )
        if perm_doc:
            doc["permissions"] = perm_doc.get("permissions")
        results.append(ConnectorRegistryItem(**_obj_to_str(doc)))
    return results


CONNECTOR_REGISTRY_SORTABLE_FIELDS = {"name", "category"}


async def get_registry_admin(
    page: int = 1,
    page_size: int = 10,
    search: str = "",
    category: str = "",
    sort_by: str | None = None,
    sort_order: str = "asc",
) -> ConnectorRegistryPage:
    """Return all connectors regardless of visibility, paginated (admin-facing)."""
    query: dict = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"category": {"$regex": search, "$options": "i"}},
        ]
    if category:
        query["category"] = category

    total = await connector_registry_collection.count_documents(query)
    skip = (page - 1) * page_size
    field = sort_by if sort_by in CONNECTOR_REGISTRY_SORTABLE_FIELDS else "name"
    direction = -1 if sort_order == "desc" else 1
    cursor = connector_registry_collection.find(query).sort(field, direction).skip(skip).limit(page_size)

    items = []
    async for doc in cursor:
        perm_doc = await tools_permissions_registry_collection.find_one(
            {"$or": [{"connector_id": str(doc["_id"])}, {"provider_id": doc.get("provider_id")}]}
        )
        if perm_doc:
            doc["permissions"] = perm_doc.get("permissions")
        items.append(ConnectorRegistryItem(**_obj_to_str(doc)))

    return ConnectorRegistryPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


async def set_connector_visibility(connector_id: str, is_visible: bool) -> ConnectorRegistryItem:
    try:
        oid = ObjectId(connector_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid connector_id format.")
    doc = await connector_registry_collection.find_one_and_update(
        {"_id": oid},
        {"$set": {"is_visible": is_visible}},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Connector not found in registry.")
    return ConnectorRegistryItem(**_obj_to_str(doc))


async def set_connector_active(connector_id: str, is_active: bool) -> ConnectorRegistryItem:
    try:
        oid = ObjectId(connector_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid connector_id format.")
    doc = await connector_registry_collection.find_one_and_update(
        {"_id": oid},
        {"$set": {"is_active": is_active}},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Connector not found in registry.")
    return ConnectorRegistryItem(**_obj_to_str(doc))


async def get_connector(connector_id: str) -> dict:
    try:
        oid = ObjectId(connector_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid connector_id format.")
    doc = await connector_registry_collection.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Connector not found in registry.")
    return _obj_to_str(doc)


# ─── Credentials ──────────────────────────────────────────────────────────────

async def save_credentials(
    connector_id: str, owner_id: str, data: ConnectorCredentialsSave
) -> None:
    connector = await get_connector(connector_id)
    auth_type = connector["auth_type"]

    if auth_type == "oauth2":
        if not data.client_id or not data.client_secret:
            raise HTTPException(
                status_code=422, detail="client_id and client_secret are required."
            )
        update: dict[str, Any] = {
            "connector_id": connector_id,
            "provider_id": connector["provider_id"],
            "owner_id": owner_id,
            "client_id": data.client_id,
            "client_secret": encrypt(data.client_secret),
        }
        if data.subdomain:
            update["subdomain"] = data.subdomain
        oauth_cfg = connector.get("oauth") or {}
        if oauth_cfg.get("requires_signing_secret"):
            if not data.signing_secret:
                raise HTTPException(
                    status_code=422, detail="signing_secret is required for this connector."
                )
            update["signing_secret"] = encrypt(data.signing_secret)
        if connector["provider_id"] == "discord":
            # Discord's OAuth "bot" scope only handles the invite/consent screen —
            # the resulting access_token can't authenticate actual bot actions.
            # Those require the app's permanent Bot Token (Developer Portal → Bot).
            if not data.bot_token:
                raise HTTPException(
                    status_code=422,
                    detail="bot_token is required for Discord (Developer Portal → Bot → Token).",
                )
            update["bot_token"] = encrypt(data.bot_token)
    elif auth_type == "bot_token":
        if not data.bot_token:
            raise HTTPException(status_code=422, detail="bot_token is required.")
        update = {
            "connector_id": connector_id,
            "provider_id": connector["provider_id"],
            "owner_id": owner_id,
            "bot_token": encrypt(data.bot_token),
        }
    elif auth_type == "api_key":
        if not data.api_key:
            raise HTTPException(status_code=422, detail="api_key is required.")
        update = {
            "connector_id": connector_id,
            "provider_id": connector["provider_id"],
            "owner_id": owner_id,
            "api_key": encrypt(data.api_key),
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported auth_type: {auth_type}")

    await connector_credentials_collection.update_one(
        {"connector_id": connector_id, "owner_id": owner_id},
        {"$set": update},
        upsert=True,
    )

    # For bot_token and api_key connectors, mark as connected immediately (no OAuth redirect).
    if auth_type in ("bot_token", "api_key"):
        await connector_instances_collection.update_one(
            {"connector_id": connector_id, "owner_id": owner_id},
            {
                "$set": {
                    "connector_id": connector_id,
                    "provider_id": connector["provider_id"],
                    "owner_id": owner_id,
                    "owner_scope": connector["owner_scope"],
                    "status": "connected",
                    "connected_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                    "last_checked_at": datetime.now(timezone.utc),
                    "last_error": None,
                    "consecutive_failures": 0,
                    "metadata": {},
                }
            },
            upsert=True,
        )
        await _invalidate_agent_graphs_for_connector(connector_id)


async def get_setup_info(connector_id: str, owner_id: str) -> ConnectorSetupInfo:
    connector = await get_connector(connector_id)
    creds_doc = await connector_credentials_collection.find_one(
        {"connector_id": connector_id, "owner_id": owner_id}
    )
    return ConnectorSetupInfo(
        has_credentials=creds_doc is not None,
        client_id=creds_doc.get("client_id") if creds_doc else None,
        redirect_uri=_callback_uri(),
        provider_id=connector["provider_id"],
        auth_type=connector["auth_type"],
    )


async def delete_credentials(connector_id: str, owner_id: str) -> None:
    await connector_credentials_collection.delete_one(
        {"connector_id": connector_id, "owner_id": owner_id}
    )


async def _load_decrypted_credentials(connector_id: str, owner_id: str) -> dict:
    doc = await connector_credentials_collection.find_one(
        {"connector_id": connector_id, "owner_id": owner_id}
    )
    if not doc:
        raise HTTPException(
            status_code=400,
            detail="Connector credentials not configured. Save client_id and client_secret first.",
        )
    undecryptable = []
    for field in ("client_secret", "signing_secret", "bot_token", "api_key"):
        if doc.get(field):
            plaintext = decrypt_or_none(doc[field])
            if plaintext is None:
                undecryptable.append(field)
            else:
                doc[field] = plaintext
    if undecryptable:
        logger.warning(
            "Connector credentials cannot be decrypted with the current key "
            "[connector=%s owner=%s fields=%s] — reconfigure the connector",
            connector_id, owner_id, ",".join(undecryptable),
        )
        raise HTTPException(
            status_code=400,
            detail=(
                "Stored connector credentials cannot be decrypted with the current "
                "ENCRYPTION_KEY. Re-save the connector's client_id and client_secret."
            ),
        )
    return doc


# ─── OAuth ────────────────────────────────────────────────────────────────────

async def build_auth_url(connector_id: str, owner_id: str) -> str:
    connector = await get_connector(connector_id)
    if connector["auth_type"] != "oauth2":
        raise HTTPException(
            status_code=400, detail="This connector does not use OAuth2 authorization."
        )

    oauth_cfg = connector["oauth"]
    creds = await _load_decrypted_credentials(connector_id, owner_id)
    provider_id = connector["provider_id"]
    state = secrets.token_urlsafe(32)
    redirect_uri = _callback_uri()

    # Store OAuth state temporarily so the callback can resolve connector + owner.
    await connector_tokens_collection.update_one(
        {"state": state},
        {
            "$set": {
                "state": state,
                "connector_id": connector_id,
                "provider_id": provider_id,
                "owner_id": owner_id,
                "pending": True,
            }
        },
        upsert=True,
    )

    params: dict[str, str] = {
        "client_id": creds["client_id"],
        "redirect_uri": redirect_uri,
        "state": state,
    }

    _GOOGLE_PROVIDERS = ("google-drive", "gmail", "google-cloud-storage", "google-calendar", "google-sheets", "google-meet")
    _MICROSOFT_PROVIDERS = ("onedrive", "teams", "outlook", "sharepoint", "word", "excel")
    _META_PROVIDERS = ("facebook", "instagram")

    if provider_id == "slack":
        params["scope"] = ",".join(oauth_cfg["scopes"])
        # Slack v2 does not use response_type=code at the top-level
    elif provider_id in _META_PROVIDERS:
        params["response_type"] = "code"
        params["scope"] = ",".join(oauth_cfg["scopes"])  # Meta uses comma-separated scopes
    elif provider_id == "tiktok":
        params["response_type"] = "code"
        params["scope"] = ",".join(oauth_cfg["scopes"])  # TikTok uses comma-separated scopes
    elif provider_id in _GOOGLE_PROVIDERS:
        params["response_type"] = "code"
        params["scope"] = " ".join(oauth_cfg["scopes"])
        params["access_type"] = "offline"
        params["prompt"] = "consent"
    elif provider_id == "dropbox":
        params["response_type"] = "code"
        params["scope"] = " ".join(oauth_cfg["scopes"])
        params["token_access_type"] = "offline"
    elif provider_id in _MICROSOFT_PROVIDERS:
        params["response_type"] = "code"
        params["scope"] = " ".join(oauth_cfg["scopes"])
        params["response_mode"] = "query"
        params["prompt"] = "consent"
    elif provider_id == "jira":
        params["response_type"] = "code"
        params["scope"] = " ".join(oauth_cfg["scopes"])
        params["audience"] = "api.atlassian.com"
        params["prompt"] = "consent"
    elif provider_id == "shopify":
        params["response_type"] = "code"
        if oauth_cfg.get("scopes"):
            params["scope"] = ",".join(oauth_cfg["scopes"])
    elif provider_id == "notion":
        params["response_type"] = "code"
        # Notion does not use scopes in the auth URL
    else:
        # Generic OAuth2: GitHub, Asana, Monday, QuickBooks, DocuSign, Intercom, Pipedrive, HubSpot, Salesforce, etc.
        params["response_type"] = "code"
        if oauth_cfg.get("scopes"):
            params["scope"] = " ".join(oauth_cfg["scopes"])

    auth_url = oauth_cfg["auth_url"]
    if "{subdomain}" in auth_url:
        subdomain = (creds.get("subdomain") or "").strip()
        if not subdomain:
            raise HTTPException(status_code=400, detail="Store subdomain is required. Please save credentials first.")
        auth_url = auth_url.replace("{subdomain}", subdomain)

    return f"{auth_url}?{urlencode(params)}"


async def exchange_code(state: str, code: str) -> str:
    """Exchange the authorization code for tokens. Returns provider_id for the redirect."""
    pending = await connector_tokens_collection.find_one(
        {"state": state, "pending": True}
    )
    if not pending:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    connector_id: str = pending["connector_id"]
    owner_id: str = pending["owner_id"]
    provider_id: str = pending["provider_id"]

    connector = await get_connector(connector_id)
    oauth_cfg = connector["oauth"]
    creds = await _load_decrypted_credentials(connector_id, owner_id)
    redirect_uri = _callback_uri()

    logger.info("Exchange debug — provider=%s client_id=[%s] owner_id=[%s] conn_id=[%s]",
                provider_id, creds.get("client_id"), owner_id, connector_id)
    token_data = await _exchange_code_for_provider(
        provider_id=provider_id,
        oauth_cfg=oauth_cfg,
        code=code,
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
        redirect_uri=redirect_uri,
        subdomain=creds.get("subdomain", ""),
    )

    raw_access: str = token_data["access_token"]
    raw_refresh: Optional[str] = token_data.get("refresh_token")
    expiry: float = datetime.now(timezone.utc).timestamp() + (
        token_data.get("expires_in") or 3600
    )
    extra = _extract_extra(provider_id, token_data)

    # Delete the pending state doc FIRST so the upsert below cannot match it
    # (both share connector_id + owner_id; deleting first prevents the token
    # record from being overwritten and then immediately deleted).
    await connector_tokens_collection.delete_one({"state": state})

    await connector_tokens_collection.update_one(
        {"connector_id": connector_id, "owner_id": owner_id},
        {
            "$set": {
                "connector_id": connector_id,
                "provider_id": provider_id,
                "owner_id": owner_id,
                "access_token": encrypt(raw_access),
                "refresh_token": encrypt(raw_refresh) if raw_refresh else None,
                "expiry": expiry,
                "scope": token_data.get("scope"),
                "extra": extra,
                "pending": False,
            }
        },
        upsert=True,
    )

    await connector_instances_collection.update_one(
        {"connector_id": connector_id, "owner_id": owner_id},
        {
            "$set": {
                "connector_id": connector_id,
                "provider_id": provider_id,
                "owner_id": owner_id,
                "owner_scope": connector["owner_scope"],
                "status": "connected",
                "connected_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "last_checked_at": datetime.now(timezone.utc),
                "last_error": None,
                "consecutive_failures": 0,
                "metadata": extra,
            }
        },
        upsert=True,
    )

    await _invalidate_agent_graphs_for_connector(connector_id)

    return provider_id


async def _exchange_code_for_provider(
    provider_id: str,
    oauth_cfg: dict,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    **kwargs,
) -> dict:
    payload: dict[str, str] = {
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    headers = {"Accept": "application/json"}

    token_url = oauth_cfg["token_url"]

    # Replace {subdomain} if present in token_url (e.g. Shopify, Zendesk).
    if "{subdomain}" in token_url:
        subdomain = (kwargs.get("subdomain") or "").strip()
        if not subdomain:
            raise HTTPException(status_code=400, detail="Store/Subdomain is required. Please reconfigure credentials.")
        token_url = token_url.replace("{subdomain}", subdomain)

    async with httpx.AsyncClient() as http:
        if provider_id in ("slack", "dropbox", "notion", "tiktok"):
            # These providers expect client credentials as HTTP Basic auth.
            # TikTok uses client_key:client_secret via Basic auth per its v2 spec.
            resp = await http.post(
                token_url,
                data=payload,
                auth=(client_id, client_secret),
                headers=headers,
            )
        else:
            payload["client_id"] = client_id
            payload["client_secret"] = client_secret
            resp = await http.post(token_url, data=payload, headers=headers)

    if resp.status_code != 200:
        logger.error(
            "Token exchange failed [%s]: %s — %s", provider_id, resp.status_code, resp.text
        )
        raise HTTPException(
            status_code=502, detail=f"OAuth token exchange failed for {provider_id}."
        )

    data = resp.json()

    if provider_id == "slack":
        if not data.get("ok"):
            raise HTTPException(
                status_code=502, detail=f"Slack OAuth error: {data.get('error')}"
            )
        return {
            "access_token": data.get("access_token", ""),
            "refresh_token": None,
            "expires_in": None,
            "scope": data.get("scope", ""),
            "_raw": data,
        }

    return data


def _extract_extra(provider_id: str, token_data: dict) -> dict:
    if provider_id == "slack":
        raw = token_data.get("_raw", {})
        team = raw.get("team") or {}
        return {
            "team_id": team.get("id"),
            "team_name": team.get("name"),
            "bot_user_id": raw.get("bot_user_id"),
        }
    if provider_id in ("shopify", "zendesk"):
        return {
            "subdomain": token_data.get("subdomain", ""),
        }
    return {}


# ─── Status & Access Token ────────────────────────────────────────────────────

class RefreshFailure(str, Enum):
    """Distinguishes a token-refresh failure that should permanently disconnect
    the connector from one that's likely to clear up on its own."""

    PERMANENT = "permanent"
    TRANSIENT = "transient"


# OAuth error codes (RFC 6749 §5.2) that mean the refresh token itself is dead.
_PERMANENT_OAUTH_ERRORS = {"invalid_grant", "unauthorized_client", "invalid_client"}
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_REFRESH_MAX_ATTEMPTS = 3
_REFRESH_BACKOFF_BASE_SECONDS = 0.5
_REFRESH_LOCK_STALE_SECONDS = 30
_REFRESH_LOCK_POLL_INTERVAL_SECONDS = 0.3
_REFRESH_LOCK_POLL_TIMEOUT_SECONDS = 3


async def get_connection_status(connector_id: str, owner_id: str) -> ConnectorStatus:
    instance = await connector_instances_collection.find_one(
        {"connector_id": connector_id, "owner_id": owner_id}
    )
    if not instance or instance.get("status") != "connected":
        return ConnectorStatus(
            connected=False,
            connected_at=instance.get("connected_at") if instance else None,
            last_checked_at=instance.get("last_checked_at") if instance else None,
            last_error=instance.get("last_error") if instance else None,
            consecutive_failures=instance.get("consecutive_failures") if instance else None,
        )

    now = datetime.now(timezone.utc)
    token, failure = await _get_access_token_with_failure_reason(connector_id, owner_id)

    if token:
        await connector_instances_collection.update_one(
            {"connector_id": connector_id, "owner_id": owner_id},
            {
                "$set": {"last_checked_at": now, "last_error": None, "consecutive_failures": 0},
            },
        )
        return ConnectorStatus(
            connected=True,
            connection_id=str(instance["_id"]),
            metadata=instance.get("metadata"),
            connected_at=instance.get("connected_at"),
            last_checked_at=now,
            last_error=None,
            consecutive_failures=0,
        )

    if failure == RefreshFailure.PERMANENT:
        await connector_instances_collection.update_one(
            {"connector_id": connector_id, "owner_id": owner_id},
            {
                "$set": {
                    "status": "disconnected",
                    "updated_at": now,
                    "last_checked_at": now,
                    "last_error": failure.value,
                },
            },
        )
        return ConnectorStatus(
            connected=False,
            connected_at=instance.get("connected_at"),
            last_checked_at=now,
            last_error=failure.value,
            consecutive_failures=instance.get("consecutive_failures"),
        )

    # Transient failure (network blip, rate limit, provider hiccup): leave
    # `status` untouched so the connector self-heals on the next successful
    # check instead of forcing the user to reconnect.
    next_consecutive_failures = instance.get("consecutive_failures", 0) + 1
    last_error = failure.value if failure else None
    await connector_instances_collection.update_one(
        {"connector_id": connector_id, "owner_id": owner_id},
        {
            "$set": {"last_checked_at": now, "last_error": last_error},
            "$inc": {"consecutive_failures": 1},
        },
    )
    return ConnectorStatus(
        connected=False,
        connected_at=instance.get("connected_at"),
        last_checked_at=now,
        last_error=last_error,
        consecutive_failures=next_consecutive_failures,
    )


async def get_access_token(connector_id: str, owner_id: str) -> Optional[str]:
    token, _ = await _get_access_token_with_failure_reason(connector_id, owner_id)
    return token


async def test_connection(connector_id: str, owner_id: str) -> ConnectorTestConnectionResult:
    """On-demand probe for the UI's 'Test connection' button. Unlike
    `get_connection_status`, this never writes to Mongo — it just reports
    whether a token is currently obtainable, and why not if it isn't."""
    instance = await connector_instances_collection.find_one(
        {"connector_id": connector_id, "owner_id": owner_id}
    )
    if not instance or instance.get("status") != "connected":
        return ConnectorTestConnectionResult(ok=False, error="not_connected")

    token, failure = await _get_access_token_with_failure_reason(connector_id, owner_id)
    if token:
        return ConnectorTestConnectionResult(ok=True)
    return ConnectorTestConnectionResult(ok=False, error=(failure.value if failure else "unknown"))


async def _get_access_token_with_failure_reason(
    connector_id: str, owner_id: str
) -> tuple[Optional[str], Optional[RefreshFailure]]:
    # For api_key connectors the key lives in credentials, not tokens.
    creds_doc = await connector_credentials_collection.find_one(
        {"connector_id": connector_id, "owner_id": owner_id}
    )
    if creds_doc and creds_doc.get("api_key"):
        api_key = decrypt_or_none(creds_doc["api_key"])
        return (api_key, None) if api_key else (None, RefreshFailure.PERMANENT)

    # Bot-token connectors (Discord's supplemental bot token, Telegram, etc.)
    # authenticate with a permanent credential, not the OAuth access_token.
    if creds_doc and creds_doc.get("bot_token"):
        bot_token = decrypt_or_none(creds_doc["bot_token"])
        return (bot_token, None) if bot_token else (None, RefreshFailure.PERMANENT)

    doc = await connector_tokens_collection.find_one(
        {"connector_id": connector_id, "owner_id": owner_id, "pending": {"$ne": True}}
    )
    if not doc or not doc.get("access_token"):
        return None, RefreshFailure.PERMANENT

    access_token = decrypt_or_none(doc["access_token"])
    if not access_token:
        return None, RefreshFailure.PERMANENT
    provider_id: str = doc.get("provider_id", "")

    # Slack bot tokens, Facebook/Instagram long-lived tokens, Telegram bot tokens, and Shopify offline access tokens do not expire.
    if provider_id in ("slack", "telegram", "facebook", "instagram", "shopify"):
        return access_token, None

    now = datetime.now(timezone.utc).timestamp()
    if doc.get("expiry") and doc["expiry"] > now - 60:
        return access_token, None

    if not doc.get("refresh_token"):
        return None, RefreshFailure.PERMANENT

    refresh_token = decrypt_or_none(doc["refresh_token"])
    if not refresh_token:
        return None, RefreshFailure.PERMANENT

    return await _refresh_access_token(connector_id, owner_id, provider_id, refresh_token)


async def _refresh_access_token(
    connector_id: str, owner_id: str, provider_id: str, refresh_token: str
) -> tuple[Optional[str], Optional[RefreshFailure]]:
    """Refreshes an OAuth access token, coordinating concurrent callers via a
    lock on the token document so two requests never race the same
    (possibly single-use/rotating) refresh_token against the provider."""

    lock_acquired = await _acquire_refresh_lock(connector_id, owner_id)
    if not lock_acquired:
        return await _await_concurrent_refresh(connector_id, owner_id)

    try:
        return await _do_refresh_with_retries(connector_id, owner_id, provider_id, refresh_token)
    finally:
        await connector_tokens_collection.update_one(
            {"connector_id": connector_id, "owner_id": owner_id},
            {"$unset": {"refreshing": "", "refresh_started_at": ""}},
        )


async def _acquire_refresh_lock(connector_id: str, owner_id: str) -> bool:
    now = datetime.now(timezone.utc)
    stale_before = now.timestamp() - _REFRESH_LOCK_STALE_SECONDS

    locked = await connector_tokens_collection.find_one_and_update(
        {
            "connector_id": connector_id,
            "owner_id": owner_id,
            "$or": [
                {"refreshing": {"$ne": True}},
                {"refresh_started_at": {"$lt": stale_before}},
            ],
        },
        {"$set": {"refreshing": True, "refresh_started_at": now.timestamp()}},
    )
    return locked is not None


async def _await_concurrent_refresh(
    connector_id: str, owner_id: str
) -> tuple[Optional[str], Optional[RefreshFailure]]:
    deadline = asyncio.get_event_loop().time() + _REFRESH_LOCK_POLL_TIMEOUT_SECONDS
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(_REFRESH_LOCK_POLL_INTERVAL_SECONDS)
        doc = await connector_tokens_collection.find_one(
            {"connector_id": connector_id, "owner_id": owner_id}
        )
        if not doc:
            return None, RefreshFailure.PERMANENT
        if not doc.get("refreshing"):
            now = datetime.now(timezone.utc).timestamp()
            if doc.get("access_token") and doc.get("expiry") and doc["expiry"] > now:
                access_token = decrypt_or_none(doc["access_token"])
                return (access_token, None) if access_token else (None, RefreshFailure.PERMANENT)
            return None, RefreshFailure.TRANSIENT
    logger.warning(
        "Timed out waiting for concurrent token refresh [connector=%s owner=%s]",
        connector_id, owner_id,
    )
    return None, RefreshFailure.TRANSIENT


async def _do_refresh_with_retries(
    connector_id: str, owner_id: str, provider_id: str, refresh_token: str
) -> tuple[Optional[str], Optional[RefreshFailure]]:
    try:
        connector = await get_connector(connector_id)
        creds = await _load_decrypted_credentials(connector_id, owner_id)
    except HTTPException:
        return None, RefreshFailure.PERMANENT

    oauth_cfg = connector["oauth"]
    payload = {
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    last_failure = RefreshFailure.TRANSIENT
    for attempt in range(1, _REFRESH_MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.post(
                    oauth_cfg["token_url"],
                    data=payload,
                    headers={"Accept": "application/json"},
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning(
                "Token refresh network error [%s] attempt %d/%d: %s",
                provider_id, attempt, _REFRESH_MAX_ATTEMPTS, exc,
            )
            last_failure = RefreshFailure.TRANSIENT
            await _backoff_sleep(attempt)
            continue

        if resp.status_code == 200:
            data = resp.json()
            new_access = data["access_token"]
            new_refresh = data.get("refresh_token", refresh_token)
            expiry = datetime.now(timezone.utc).timestamp() + (data.get("expires_in") or 3600)

            await connector_tokens_collection.update_one(
                {"connector_id": connector_id, "owner_id": owner_id},
                {
                    "$set": {
                        "access_token": encrypt(new_access),
                        "refresh_token": encrypt(new_refresh),
                        "expiry": expiry,
                    }
                },
            )
            return new_access, None

        if resp.status_code in _RETRYABLE_STATUS_CODES:
            logger.warning(
                "Token refresh transient failure [%s] attempt %d/%d: HTTP %d",
                provider_id, attempt, _REFRESH_MAX_ATTEMPTS, resp.status_code,
            )
            last_failure = RefreshFailure.TRANSIENT
            await _backoff_sleep(attempt)
            continue

        # 400/401/403 etc: only a recognized OAuth "the refresh token is dead"
        # error is treated as permanent; anything else we haven't seen before
        # is treated as transient so a novel provider error can't accidentally
        # nuke a still-valid connection.
        oauth_error = None
        try:
            oauth_error = resp.json().get("error")
        except ValueError:
            pass

        if oauth_error in _PERMANENT_OAUTH_ERRORS:
            logger.error(
                "Token refresh permanently failed [%s]: HTTP %d error=%s",
                provider_id, resp.status_code, oauth_error,
            )
            return None, RefreshFailure.PERMANENT

        logger.error(
            "Token refresh failed [%s] with unrecognized error, treating as transient: "
            "HTTP %d error=%s",
            provider_id, resp.status_code, oauth_error,
        )
        return None, RefreshFailure.TRANSIENT

    logger.error(
        "Token refresh exhausted retries [%s] after %d attempts",
        provider_id, _REFRESH_MAX_ATTEMPTS,
    )
    return None, last_failure


async def _backoff_sleep(attempt: int) -> None:
    delay = _REFRESH_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
    await asyncio.sleep(delay + random.uniform(0, delay * 0.25))


# ─── Disconnect ───────────────────────────────────────────────────────────────

async def disconnect(
    connector_id: str, owner_id: str, *, reason: str = "user_disconnected"
) -> None:
    await connector_tokens_collection.delete_many(
        {"connector_id": connector_id, "owner_id": owner_id}
    )
    await connector_instances_collection.update_one(
        {"connector_id": connector_id, "owner_id": owner_id},
        {
            "$set": {
                "status": "disconnected",
                "updated_at": datetime.now(timezone.utc),
                "last_error": reason,
            }
        },
    )
    await _invalidate_agent_graphs_for_connector(connector_id)


# ─── Slack Webhook Signature Verification ─────────────────────────────────────

async def verify_slack_signature(
    raw_body: bytes,
    timestamp: str,
    signature: str,
    connector_id: str,
    owner_id: str,
) -> bool:
    creds = await _load_decrypted_credentials(connector_id, owner_id)
    signing_secret: Optional[str] = creds.get("signing_secret")
    if not signing_secret:
        return False
    base = f"v0:{timestamp}:{raw_body.decode()}"
    expected = "v0=" + hmac.new(
        signing_secret.encode(), base.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ─── Actions ──────────────────────────────────────────────────────────────────

async def perform_action(
    connector_id: str, owner_id: str, action: str, params: dict[str, Any] | None = None
) -> Any:
    """Run a single connector tool by name, using the same connector classes and
    as_tools() callables the agent tool-calling path uses (ai/connectors/registry.py).
    This automatically supports every registered provider, not just a hardcoded subset."""
    from ai.connectors.registry import CONNECTOR_CLASS_MAP

    connector = await get_connector(connector_id)
    provider_id = connector["provider_id"]

    token = await get_access_token(connector_id, owner_id)
    if not token:
        raise HTTPException(
            status_code=401, detail="Connector not connected or token expired."
        )

    cls = CONNECTOR_CLASS_MAP.get(provider_id)
    if not cls:
        raise HTTPException(
            status_code=400, detail=f"No actions implemented for provider: {provider_id}"
        )

    _, callables = cls(token).as_tools()
    callable_fn = callables.get(action)
    if not callable_fn:
        raise HTTPException(
            status_code=400, detail=f"Unknown action '{action}' for provider: {provider_id}"
        )

    result = callable_fn(params or {})
    if inspect.isawaitable(result):
        result = await result
    return result

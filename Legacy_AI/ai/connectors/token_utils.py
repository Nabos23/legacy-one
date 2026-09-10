"""Sync helper for loading a valid (possibly refreshed) OAuth access token.

Used by graph_loader and sub_agent — both run in sync threads.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from bson import ObjectId

logger = logging.getLogger(__name__)

_NEVER_EXPIRE_PROVIDERS = {"slack", "telegram", "shopify"}


def get_valid_token_sync(db, connector_id: str, owner_id: str) -> Optional[str]:
    """Return a valid access token for a connector, refreshing it if expired.

    db: sync PyMongo database handle
    connector_id: string ID of the connector_registry document
    owner_id: user_id or organization_id depending on owner_scope
    """
    from backend.core.encryption import decrypt, encrypt

    token_doc = db.connector_tokens.find_one(
        {"connector_id": connector_id, "owner_id": owner_id, "pending": {"$ne": True}}
    )
    if not token_doc or not token_doc.get("access_token"):
        return None

    access_token = decrypt(token_doc["access_token"])
    provider_id: str = token_doc.get("provider_id", "")

    # Helper function to attach subdomain if provider requires it (shopify, zendesk)
    def _format_token(tok: str) -> str:
        if provider_id in ("shopify", "zendesk") and ":" not in tok:
            subdomain = (token_doc.get("extra") or {}).get("subdomain")
            if not subdomain:
                creds_doc = db.connector_credentials.find_one({"connector_id": connector_id, "owner_id": owner_id})
                if creds_doc and creds_doc.get("subdomain"):
                    subdomain = creds_doc["subdomain"]
            if subdomain:
                return f"{tok}:{subdomain}"
        return tok

    if provider_id in _NEVER_EXPIRE_PROVIDERS:
        return _format_token(access_token)

    now = datetime.now(timezone.utc).timestamp()
    if token_doc.get("expiry") and token_doc["expiry"] > now - 60:
        return _format_token(access_token)

    # Token expired — attempt refresh.
    if not token_doc.get("refresh_token"):
        logger.warning(
            "[token-utils] expired token and no refresh_token for connector %s (provider=%s)",
            connector_id, provider_id,
        )
        return access_token  # return stale so callers surface the 401 properly

    refresh_token = decrypt(token_doc["refresh_token"])
    registry_doc = db.connector_registry.find_one({"_id": ObjectId(connector_id)})
    oauth_cfg = (registry_doc or {}).get("oauth", {})
    token_url = oauth_cfg.get("token_url")
    if not token_url:
        return access_token

    creds_doc = db.connector_credentials.find_one(
        {"connector_id": connector_id, "owner_id": owner_id}
    )
    if not creds_doc:
        return access_token

    client_id = creds_doc.get("client_id", "")
    client_secret = decrypt(creds_doc["client_secret"]) if creds_doc.get("client_secret") else ""

    try:
        resp = httpx.post(
            token_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning(
                "[token-utils] refresh failed for connector %s (provider=%s): HTTP %s",
                connector_id, provider_id, resp.status_code,
            )
            return _format_token(access_token)

        data = resp.json()
        new_access = data["access_token"]
        new_refresh = data.get("refresh_token", refresh_token)
        expiry = now + (data.get("expires_in") or 3600)

        db.connector_tokens.update_one(
            {"connector_id": connector_id, "owner_id": owner_id},
            {"$set": {
                "access_token": encrypt(new_access),
                "refresh_token": encrypt(new_refresh),
                "expiry": expiry,
            }},
        )
        logger.info("[token-utils] refreshed token for connector %s (provider=%s)", connector_id, provider_id)
        return _format_token(new_access)
    except Exception as exc:
        logger.error("[token-utils] refresh error for connector %s: %s", connector_id, exc)
        return _format_token(access_token)

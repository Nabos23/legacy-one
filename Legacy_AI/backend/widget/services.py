import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException, UploadFile, status

from backend.core.config import settings
from backend.core.encryption import encrypt
from backend.core.softdelete import NOT_DELETED, soft_delete_update
from backend.core.uploads import save_image_upload
from backend.db.database import (
    agents_collection,
    organizations_collection,
    users_collection,
    widget_config_versions_collection,
    widget_configs_collection,
    widget_webhook_deliveries_collection,
)
from backend.widget.defaults import (
    DEFAULT_ACCESSIBILITY,
    DEFAULT_BEHAVIOR,
    DEFAULT_BRANDING,
    DEFAULT_DAY_SCHEDULE,
    DEFAULT_LAYOUT,
    DEFAULT_SECURITY,
    DEFAULT_TRIGGERS,
    DEFAULT_WEBHOOK_TARGET,
    WEBHOOK_EVENTS,
    availability_with_defaults,
    webhooks_with_defaults,
    with_defaults,
)
from backend.widget.origins import invalidate_widget_origins_cache
from backend.widget.schemas import (
    WidgetApiKeyResponse,
    WidgetConfigCreate,
    WidgetConfigPublic,
    WidgetConfigUpdate,
    WidgetPreviewTokenResponse,
    WidgetVersionListItem,
    WidgetWebhookDeliveryResult,
)
from backend.widget.webhooks import deliver_once
from .validators import validate_object_id

logger = logging.getLogger("widget.services")

# The sections gated behind draft/publish -- everything a visitor sees in the
# chat surface itself. Security (origins/API key/rate limit), webhooks, and
# is_enabled are deliberately excluded: those are access-control/kill-switch
# settings, not "design," and take effect immediately (see update_widget_config).
DRAFT_SECTION_KEYS = ("branding", "layout", "triggers", "behavior", "availability", "accessibility", "lead_fields")


def _draft_sections(doc: dict) -> dict:
    """Every draft-tracked section, with defaults applied -- the single place
    both `_to_public` and the publish/rollback flows read the widget's current
    design/behavior state from."""
    return {
        "branding": with_defaults(DEFAULT_BRANDING, doc.get("branding")),
        "layout": with_defaults(DEFAULT_LAYOUT, doc.get("layout")),
        "triggers": with_defaults(DEFAULT_TRIGGERS, doc.get("triggers")),
        "behavior": with_defaults(DEFAULT_BEHAVIOR, doc.get("behavior")),
        "availability": availability_with_defaults(doc.get("availability")),
        "accessibility": with_defaults(DEFAULT_ACCESSIBILITY, doc.get("accessibility")),
        "lead_fields": doc.get("lead_fields") or [],
    }


def _merge_section(defaults: dict, existing: Optional[dict], incoming) -> dict:
    """Merge a section update into its stored value.

    exclude_unset (NOT exclude_none): a field the client explicitly sends as
    null clears the stored value, while omitted fields keep their existing
    value -- otherwise nullable fields (logo/avatar URLs, override colors,
    tone, scroll trigger, rate limit) could never be cleared once set.

    Clearing a field whose default is non-null (e.g. secondary_color) reverts
    it to that default instead of storing None, which the public schemas
    (and the embed) treat as always-present."""
    merged = {**with_defaults(defaults, existing), **incoming.model_dump(exclude_unset=True)}
    for key, value in merged.items():
        if value is None and defaults.get(key) is not None:
            merged[key] = defaults[key]
    return merged


def _hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _generate_api_key() -> str:
    return secrets.token_urlsafe(32)


def _merge_availability(existing: Optional[dict], incoming) -> dict:
    merged = availability_with_defaults(existing)
    if incoming is None:
        return merged
    data = incoming.model_dump(exclude_none=True)
    if "schedule" in data:
        merged_schedule = {**merged["schedule"]}
        for day, day_update in data.pop("schedule").items():
            merged_schedule[day] = {**merged_schedule.get(day, DEFAULT_DAY_SCHEDULE), **day_update}
        merged["schedule"] = merged_schedule
    merged.update(data)
    return merged


def _merge_webhook_target(existing: Optional[dict], incoming) -> dict:
    """`secret` is write-only and never returned to the client, so `None`
    means "leave the existing encrypted secret alone" -- distinguished from
    an explicit empty string, which clears it."""
    merged = {**DEFAULT_WEBHOOK_TARGET, **(existing or {})}
    if incoming is None:
        return merged
    if incoming.url is not None:
        merged["url"] = incoming.url
    if incoming.is_active is not None:
        merged["is_active"] = incoming.is_active
    if incoming.secret is not None:
        merged["secret_encrypted"] = encrypt(incoming.secret) if incoming.secret else None
    return merged


def _merge_webhooks(existing: Optional[dict], incoming) -> dict:
    if incoming is None:
        return webhooks_with_defaults(existing)
    existing = existing or {}
    return {
        event: _merge_webhook_target(existing.get(event), getattr(incoming, event))
        for event in WEBHOOK_EVENTS
    }


async def _validate_org_exists(org_id: str) -> None:
    if not ObjectId.is_valid(org_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    doc = await organizations_collection.find_one({"_id": ObjectId(org_id), "is_deleted": {"$ne": True}})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")


async def _validate_agent_in_org(agent_id: str, org_id: str, requesting_user_id: str) -> None:
    """Also enforced at chat-runtime (direct_agent._load_single_agent), but
    checked here too so a widget can't be *configured* with a personal or
    selected_users agent the configuring admin can't see in the first place --
    a clear config-time error instead of every visitor message failing."""
    from backend.agent.services import build_agent_visibility_clauses

    if not ObjectId.is_valid(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    doc = await agents_collection.find_one({
        "_id": ObjectId(agent_id),
        "organization_id": org_id,
        **NOT_DELETED,
        "$or": await build_agent_visibility_clauses(requesting_user_id),
    })
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found in this organization.",
        )


def _validate_source_type(source_type: str, agent_id: Optional[str]) -> None:
    if source_type == "single_agent" and not agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="agent_id is required when source_type is 'single_agent'.",
        )
    if source_type == "supervisor" and agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="agent_id must be omitted when source_type is 'supervisor' "
            "(supervisor mode routes across every active agent in the org).",
        )


def _to_public(doc: dict) -> WidgetConfigPublic:
    sections = _draft_sections(doc)
    webhooks = webhooks_with_defaults(doc.get("webhooks"))
    security = with_defaults(DEFAULT_SECURITY, doc.get("security"))

    published = doc.get("published")
    has_unpublished_changes = bool(published) and any(sections[k] != published.get(k) for k in DRAFT_SECTION_KEYS)

    return WidgetConfigPublic(
        id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        name=doc["name"],
        source_type=doc.get("source_type", "single_agent"),
        agent_id=doc.get("agent_id"),
        is_enabled=doc.get("is_enabled", True),
        branding=sections["branding"],
        layout=sections["layout"],
        triggers=sections["triggers"],
        behavior=sections["behavior"],
        availability=sections["availability"],
        accessibility=sections["accessibility"],
        lead_fields=sections["lead_fields"],
        published_version=published.get("version") if published else None,
        published_at=published.get("published_at") if published else None,
        has_unpublished_changes=has_unpublished_changes,
        webhooks={
            event: {
                "url": webhooks[event]["url"],
                "has_secret": bool(webhooks[event]["secret_encrypted"]),
                "is_active": webhooks[event]["is_active"],
            }
            for event in WEBHOOK_EVENTS
        },
        security={
            "allowed_origins": security["allowed_origins"],
            "require_api_key": security["require_api_key"],
            "has_api_key": bool(security.get("widget_api_key_hash")),
            "rate_limit_per_minute": security.get("rate_limit_per_minute"),
            "retention_days": security.get("retention_days"),
        },
        created_by=doc["created_by"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


async def create_widget_config(payload: WidgetConfigCreate, created_by: str) -> WidgetConfigPublic:
    await _validate_org_exists(payload.organization_id)
    _validate_source_type(payload.source_type, payload.agent_id)
    if payload.agent_id:
        await _validate_agent_in_org(payload.agent_id, payload.organization_id, created_by)

    now = datetime.now(timezone.utc)
    branding = {**DEFAULT_BRANDING, **(payload.branding.model_dump(exclude_none=True) if payload.branding else {})}
    layout = {**DEFAULT_LAYOUT, **(payload.layout.model_dump(exclude_none=True) if payload.layout else {})}
    triggers = {**DEFAULT_TRIGGERS, **(payload.triggers.model_dump(exclude_none=True) if payload.triggers else {})}
    behavior = {**DEFAULT_BEHAVIOR, **(payload.behavior.model_dump(exclude_none=True) if payload.behavior else {})}
    availability = _merge_availability(None, payload.availability)
    accessibility = {**DEFAULT_ACCESSIBILITY, **(payload.accessibility.model_dump(exclude_none=True) if payload.accessibility else {})}
    webhooks = _merge_webhooks(None, payload.webhooks)
    security = {**DEFAULT_SECURITY, **(payload.security.model_dump(exclude_none=True) if payload.security else {})}
    lead_fields = [f.model_dump() for f in payload.lead_fields] if payload.lead_fields is not None else []

    draft_sections = {
        "branding": branding,
        "layout": layout,
        "triggers": triggers,
        "behavior": behavior,
        "availability": availability,
        "accessibility": accessibility,
        "lead_fields": lead_fields,
    }
    # Auto-publish v1 at creation, so "create a widget" keeps meaning
    # "the embed code works immediately" -- every edit after this point goes
    # to the draft only, until an explicit publish.
    published = {**draft_sections, "version": 1, "published_by": created_by, "published_at": now}

    doc = {
        "organization_id": payload.organization_id,
        "name": payload.name,
        "source_type": payload.source_type,
        "agent_id": payload.agent_id,
        **draft_sections,
        "published": published,
        "webhooks": webhooks,
        "security": security,
        "is_enabled": True,
        "is_deleted": False,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }
    result = await widget_configs_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    await widget_config_versions_collection.insert_one({
        "widget_id": str(result.inserted_id),
        **draft_sections,
        "version": 1,
        "published_by": created_by,
        "published_at": now,
        "restored_from_version": None,
    })
    if security.get("allowed_origins"):
        invalidate_widget_origins_cache()
    return _to_public(doc)


async def duplicate_widget_config(widget_id: str, created_by: str) -> WidgetConfigPublic:
    """Copy an existing widget's full DRAFT config (plus allowed_origins/rate
    limit and webhook URLs) into a brand-new widget. Secrets are deliberately
    NOT copied -- the webhook signing secrets and the API key hash stay unique
    to the source widget; the copy starts without any and can mint its own."""
    oid = validate_object_id(widget_id)
    existing = await widget_configs_collection.find_one({"_id": oid, **NOT_DELETED})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")

    suffix = " (copy)"
    base_name = existing["name"]
    new_name = base_name + suffix
    if len(new_name) > 120:
        new_name = base_name[: 120 - len(suffix)] + suffix

    draft_sections = _draft_sections(existing)
    existing_webhooks = webhooks_with_defaults(existing.get("webhooks"))
    webhooks = {
        event: {**target, "secret_encrypted": None}
        for event, target in existing_webhooks.items()
    }
    existing_security = with_defaults(DEFAULT_SECURITY, existing.get("security"))
    security = {**existing_security, "widget_api_key_hash": None}

    now = datetime.now(timezone.utc)
    # Auto-publish v1, same as create_widget_config -- a duplicated widget's
    # embed code works immediately, without a separate first publish.
    published = {**draft_sections, "version": 1, "published_by": created_by, "published_at": now}

    doc = {
        "organization_id": existing["organization_id"],
        "name": new_name,
        "source_type": existing.get("source_type", "single_agent"),
        "agent_id": existing.get("agent_id"),
        **draft_sections,
        "published": published,
        "webhooks": webhooks,
        "security": security,
        "is_enabled": True,
        "is_deleted": False,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }
    result = await widget_configs_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    await widget_config_versions_collection.insert_one({
        "widget_id": str(result.inserted_id),
        **draft_sections,
        "version": 1,
        "published_by": created_by,
        "published_at": now,
        "restored_from_version": None,
    })
    if security.get("allowed_origins"):
        invalidate_widget_origins_cache()
    logger.info("[WIDGET] duplicated widget=%s as widget=%s", widget_id, result.inserted_id)
    return _to_public(doc)


async def list_widget_configs_by_org(
    org_id: str, skip: int = 0, limit: int = 20
) -> tuple[List[WidgetConfigPublic], int]:
    query = {"organization_id": org_id, **NOT_DELETED}
    total = await widget_configs_collection.count_documents(query)
    cursor = widget_configs_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_to_public(doc) for doc in docs], total


async def list_all_widget_configs(skip: int = 0, limit: int = 20) -> tuple[List[WidgetConfigPublic], int]:
    """Super-admin only: every widget across every organization."""
    query = {**NOT_DELETED}
    total = await widget_configs_collection.count_documents(query)
    cursor = widget_configs_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return [_to_public(doc) for doc in docs], total


async def get_widget_config(widget_id: str) -> WidgetConfigPublic:
    oid = validate_object_id(widget_id)
    doc = await widget_configs_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")
    return _to_public(doc)


async def update_widget_config(
    widget_id: str, payload: WidgetConfigUpdate, requesting_user_id: str
) -> WidgetConfigPublic:
    oid = validate_object_id(widget_id)
    existing = await widget_configs_collection.find_one({"_id": oid, **NOT_DELETED})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")

    updates = payload.model_dump(
        exclude_unset=True,
        exclude={"branding", "layout", "triggers", "behavior", "availability", "accessibility", "webhooks", "security"},
    )

    next_source_type = updates.get("source_type", existing.get("source_type", "single_agent"))
    next_agent_id = updates.get("agent_id", existing.get("agent_id"))
    if "source_type" in updates or "agent_id" in updates:
        _validate_source_type(next_source_type, next_agent_id)
        if next_source_type == "single_agent" and next_agent_id:
            await _validate_agent_in_org(next_agent_id, existing["organization_id"], requesting_user_id)

    if payload.branding is not None:
        updates["branding"] = _merge_section(DEFAULT_BRANDING, existing.get("branding"), payload.branding)
    if payload.layout is not None:
        updates["layout"] = _merge_section(DEFAULT_LAYOUT, existing.get("layout"), payload.layout)
    if payload.triggers is not None:
        updates["triggers"] = _merge_section(DEFAULT_TRIGGERS, existing.get("triggers"), payload.triggers)
    if payload.behavior is not None:
        updates["behavior"] = _merge_section(DEFAULT_BEHAVIOR, existing.get("behavior"), payload.behavior)
    if payload.availability is not None:
        updates["availability"] = _merge_availability(existing.get("availability"), payload.availability)
    if payload.accessibility is not None:
        updates["accessibility"] = _merge_section(DEFAULT_ACCESSIBILITY, existing.get("accessibility"), payload.accessibility)
    if payload.webhooks is not None:
        updates["webhooks"] = _merge_webhooks(existing.get("webhooks"), payload.webhooks)
    if payload.lead_fields is not None:
        updates["lead_fields"] = [f.model_dump() for f in payload.lead_fields]
    if payload.security is not None:
        # allowed_origins/require_api_key only -- widget_api_key_hash is never
        # touched here, only via regenerate_widget_api_key.
        updates["security"] = _merge_section(DEFAULT_SECURITY, existing.get("security"), payload.security)

    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update.")

    updates["updated_at"] = datetime.now(timezone.utc)
    doc = await widget_configs_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {"$set": updates},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")
    if "security" in updates:
        invalidate_widget_origins_cache()
    return _to_public(doc)


async def publish_widget_config(widget_id: str, published_by: str) -> WidgetConfigPublic:
    """Snapshot the current draft (branding/layout/triggers/behavior/
    availability/accessibility/lead_fields) as the new live version. Visitors
    only ever see the most recent published snapshot -- this is what actually
    makes it visible to them."""
    oid = validate_object_id(widget_id)
    existing = await widget_configs_collection.find_one({"_id": oid, **NOT_DELETED})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")

    sections = _draft_sections(existing)
    now = datetime.now(timezone.utc)
    next_version = (existing.get("published") or {}).get("version", 0) + 1
    published = {**sections, "version": next_version, "published_by": published_by, "published_at": now}

    doc = await widget_configs_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {"$set": {"published": published}},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")
    await widget_config_versions_collection.insert_one({
        "widget_id": widget_id,
        **sections,
        "version": next_version,
        "published_by": published_by,
        "published_at": now,
        "restored_from_version": None,
    })
    logger.info("[WIDGET] published widget=%s version=%s", widget_id, next_version)
    return _to_public(doc)


async def discard_widget_draft(widget_id: str) -> WidgetConfigPublic:
    """Reset the draft back to the last published snapshot, discarding any
    unpublished edits. No-op target if the widget has never been published."""
    oid = validate_object_id(widget_id)
    existing = await widget_configs_collection.find_one({"_id": oid, **NOT_DELETED})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")

    published = existing.get("published")
    if not published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This widget has never been published, so there's no published version to discard back to.",
        )

    updates = {key: published[key] for key in DRAFT_SECTION_KEYS}
    updates["updated_at"] = datetime.now(timezone.utc)
    doc = await widget_configs_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {"$set": updates},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")
    return _to_public(doc)


async def list_widget_versions(widget_id: str, skip: int = 0, limit: int = 20) -> tuple[List[WidgetVersionListItem], int]:
    query = {"widget_id": widget_id}
    total = await widget_config_versions_collection.count_documents(query)
    # Fetch one doc past the page so the oldest item on the page can still be
    # diffed against its predecessor (versions are sequential, newest first).
    cursor = widget_config_versions_collection.find(query).sort("version", -1).skip(skip).limit(limit + 1)
    docs = await cursor.to_list(length=limit + 1)
    extra = docs[limit] if len(docs) > limit else None
    docs = docs[:limit]

    publisher_ids = {d["published_by"] for d in docs if d.get("published_by")}
    names: dict[str, str] = {}
    if publisher_ids:
        valid_oids = [ObjectId(uid) for uid in publisher_ids if ObjectId.is_valid(uid)]
        async for u in users_collection.find({"_id": {"$in": valid_oids}}, {"name": 1}):
            names[str(u["_id"])] = u.get("name") or ""

    def changed_sections(doc: dict, previous: Optional[dict]) -> List[str]:
        if previous is None:
            return []
        return [key for key in DRAFT_SECTION_KEYS if doc.get(key) != previous.get(key)]

    items = []
    for i, d in enumerate(docs):
        previous = docs[i + 1] if i + 1 < len(docs) else extra
        items.append(
            WidgetVersionListItem(
                version=d["version"],
                published_by=d["published_by"],
                published_by_name=names.get(d["published_by"]) or None,
                published_at=d["published_at"],
                restored_from_version=d.get("restored_from_version"),
                changed_sections=changed_sections(d, previous),
            )
        )
    return items, total


async def rollback_widget_config(widget_id: str, version: int, restored_by: str) -> WidgetConfigPublic:
    """Restore a past published version as both the new draft AND a fresh
    published version -- history stays linear/append-only rather than
    branching, so "rollback" always means "publish this old content again"."""
    oid = validate_object_id(widget_id)
    existing = await widget_configs_collection.find_one({"_id": oid, **NOT_DELETED})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")

    version_doc = await widget_config_versions_collection.find_one({"widget_id": widget_id, "version": version})
    if not version_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Version {version} not found for this widget.")

    sections = {key: version_doc[key] for key in DRAFT_SECTION_KEYS}
    now = datetime.now(timezone.utc)
    next_version = (existing.get("published") or {}).get("version", 0) + 1
    published = {**sections, "version": next_version, "published_by": restored_by, "published_at": now}

    doc = await widget_configs_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {"$set": {**sections, "published": published, "updated_at": now}},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")
    await widget_config_versions_collection.insert_one({
        "widget_id": widget_id,
        **sections,
        "version": next_version,
        "published_by": restored_by,
        "published_at": now,
        "restored_from_version": version,
    })
    logger.info("[WIDGET] rolled back widget=%s to version=%s as new version=%s", widget_id, version, next_version)
    return _to_public(doc)


async def toggle_widget_status(widget_id: str, is_enabled: bool) -> WidgetConfigPublic:
    oid = validate_object_id(widget_id)
    doc = await widget_configs_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {"$set": {"is_enabled": is_enabled, "updated_at": datetime.now(timezone.utc)}},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")
    invalidate_widget_origins_cache()
    return _to_public(doc)


async def regenerate_widget_api_key(widget_id: str) -> WidgetApiKeyResponse:
    oid = validate_object_id(widget_id)
    plaintext = _generate_api_key()
    doc = await widget_configs_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED},
        {
            "$set": {
                "security.widget_api_key_hash": _hash_api_key(plaintext),
                "updated_at": datetime.now(timezone.utc),
            }
        },
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")
    logger.info("[WIDGET] regenerated API key for widget=%s", widget_id)
    return WidgetApiKeyResponse(widget_id=widget_id, api_key=plaintext)


# Draft-preview tokens are stateless: nothing is persisted, the signature
# (keyed with the same JWT_SECRET_KEY the auth layer signs tokens with) plus
# the embedded expiry are the whole story. TTL is short because the token
# grants read access to the widget's unpublished draft.
PREVIEW_TOKEN_TTL_SECONDS = 15 * 60


def _sign_preview_token(widget_id: str, expiry_epoch: int) -> str:
    return hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        f"{widget_id}:{expiry_epoch}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def create_widget_preview_token(widget_id: str) -> WidgetPreviewTokenResponse:
    oid = validate_object_id(widget_id)
    existing = await widget_configs_collection.find_one({"_id": oid, **NOT_DELETED})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")

    expiry_epoch = int(datetime.now(timezone.utc).timestamp()) + PREVIEW_TOKEN_TTL_SECONDS
    token = f"{expiry_epoch}.{_sign_preview_token(widget_id, expiry_epoch)}"
    return WidgetPreviewTokenResponse(
        preview_token=token,
        expires_at=datetime.fromtimestamp(expiry_epoch, tz=timezone.utc),
    )


def verify_preview_token(widget_id: str, token: str) -> bool:
    """True only if the token's signature matches this widget AND it hasn't
    expired. Never raises -- the caller decides the HTTP semantics."""
    try:
        expiry_part, signature = token.split(".", 1)
        expiry_epoch = int(expiry_part)
    except (ValueError, AttributeError):
        return False
    if datetime.now(timezone.utc).timestamp() > expiry_epoch:
        return False
    return hmac.compare_digest(signature, _sign_preview_token(widget_id, expiry_epoch))


async def upload_widget_image(widget_id: str, file: UploadFile) -> str:
    """Upload a branding image (logo/avatar/launcher icon) for this widget.

    Doesn't write the URL onto the widget document itself -- the caller
    (WidgetConfigUpdate) decides which field the returned URL belongs in,
    since one widget can hold up to four independent images.
    """
    oid = validate_object_id(widget_id)
    existing = await widget_configs_collection.find_one({"_id": oid, **NOT_DELETED})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")

    url_path = await save_image_upload(file, subdir=f"widgets/{widget_id}")
    return f"{settings.BACKEND_BASE_URL}{url_path}"


async def delete_widget_config(widget_id: str) -> None:
    """Soft delete: mark as deleted instead of removing the document."""
    oid = validate_object_id(widget_id)
    result = await widget_configs_collection.update_one({"_id": oid, **NOT_DELETED}, soft_delete_update())
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")
    invalidate_widget_origins_cache()


_SAMPLE_WEBHOOK_DATA = {
    "conversation_started": {"visitor_session_id": "test-session", "origin": "https://example.com"},
    "lead_captured": {"visitor_session_id": "test-session", "values": {"name": "Test Visitor", "email": "test@example.com"}},
    "message_sent": {"visitor_session_id": "test-session", "message": "This is a test message from the widget builder.", "attachment_count": 0},
    "feedback_submitted": {"visitor_session_id": "test-session", "message_id": "test-message", "rating": "up", "message_excerpt": "Test excerpt"},
}


async def test_widget_webhook(widget_id: str, event: str) -> WidgetWebhookDeliveryResult:
    """One synchronous, sample-payload delivery to the event's configured URL,
    so admins can verify their endpoint + signature handling from the builder."""
    if event not in WEBHOOK_EVENTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown webhook event '{event}'.")
    oid = validate_object_id(widget_id)
    doc = await widget_configs_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")
    target = webhooks_with_defaults(doc.get("webhooks"))[event]
    if not target.get("url"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No URL configured for this event.")

    payload = {
        "event": event,
        "widget_id": widget_id,
        "organization_id": doc.get("organization_id"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test": True,
        "data": _SAMPLE_WEBHOOK_DATA[event],
    }
    result = await deliver_once(widget_id, event, target["url"], target.get("secret_encrypted"), payload, kind="test")
    return WidgetWebhookDeliveryResult(**result)


async def replay_widget_webhook_delivery(widget_id: str, delivery_id: str) -> WidgetWebhookDeliveryResult:
    """Re-deliver a logged payload to the event's CURRENT URL/secret -- the
    dead-letter escape hatch for deliveries that exhausted their retries."""
    oid = validate_object_id(widget_id)
    doc = await widget_configs_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")
    if not ObjectId.is_valid(delivery_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found.")
    row = await widget_webhook_deliveries_collection.find_one({"_id": ObjectId(delivery_id), "widget_id": widget_id})
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found.")
    payload = row.get("payload")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This delivery predates payload logging and cannot be replayed.",
        )
    target = webhooks_with_defaults(doc.get("webhooks"))[row["event"]]
    if not target.get("url"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No URL is currently configured for this event.")
    result = await deliver_once(widget_id, row["event"], target["url"], target.get("secret_encrypted"), payload, kind="replay")
    return WidgetWebhookDeliveryResult(**result)

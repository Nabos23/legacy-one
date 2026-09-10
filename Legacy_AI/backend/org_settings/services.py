from datetime import datetime, timezone

from backend.db.database import organization_settings_collection
from backend.org_settings.schemas import OrgSettingsPublic, OrgSettingsUpdate

# Defaults applied when an organization has no stored settings yet, or when a
# stored document predates a newly added field.
_DEFAULTS = {
    "maintenance_mode": False,
    "require_2fa": False,
    "session_timeout_enabled": True,
    "session_duration": "30m",
    "audit_logging": True,
    "default_model": "gpt-4o",
}


def _to_public(organization_id: str, doc: dict | None) -> OrgSettingsPublic:
    data = {**_DEFAULTS, **(doc or {})}
    return OrgSettingsPublic(
        organization_id=organization_id,
        maintenance_mode=data["maintenance_mode"],
        require_2fa=data["require_2fa"],
        session_timeout_enabled=data["session_timeout_enabled"],
        session_duration=data["session_duration"],
        audit_logging=data["audit_logging"],
        default_model=data["default_model"],
        updated_at=data.get("updated_at"),
    )


async def get_settings(organization_id: str) -> OrgSettingsPublic:
    """Return stored settings for an org, falling back to defaults."""
    doc = await organization_settings_collection.find_one(
        {"organization_id": organization_id}
    )
    return _to_public(organization_id, doc)


async def update_settings(
    organization_id: str, payload: OrgSettingsUpdate
) -> OrgSettingsPublic:
    """Upsert the provided fields and return the full, merged settings."""
    updates = {
        k: v
        for k, v in payload.model_dump(exclude_unset=True).items()
        if v is not None
    }
    updates["updated_at"] = datetime.now(timezone.utc)
    doc = await organization_settings_collection.find_one_and_update(
        {"organization_id": organization_id},
        {"$set": updates, "$setOnInsert": {"organization_id": organization_id}},
        upsert=True,
        return_document=True,
    )
    return _to_public(organization_id, doc)

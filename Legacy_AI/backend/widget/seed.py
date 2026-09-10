from pymongo import ASCENDING, DESCENDING, IndexModel

from backend.db.database import (
    widget_config_versions_collection,
    widget_configs_collection,
    widget_message_feedback_collection,
    widget_sessions_collection,
    widget_webhook_deliveries_collection,
)


async def ensure_widget_indexes() -> None:
    """Create the indexes widget lookups need.

    `organization_id` + `created_at` backs the management list view
    (list_widget_configs_by_org); `agent_id` backs the reverse lookup used
    when an agent is deleted/deactivated (so we can find/flag any widgets
    still pointing at it). `widget_id` + `visitor_session_id` is the hot path
    on every public message -- unique since a visitor_session_id is only ever
    minted once, by create_widget_session. `widget_id` + `version` backs the
    publish-history list/rollback lookups -- unique since versions are
    minted sequentially, never rewritten.
    """
    await widget_configs_collection.create_indexes([
        IndexModel([("organization_id", ASCENDING), ("created_at", DESCENDING)], name="org_created_at"),
        IndexModel([("agent_id", ASCENDING)], name="agent_id_lookup", sparse=True),
    ])
    await widget_sessions_collection.create_indexes([
        IndexModel(
            [("widget_id", ASCENDING), ("visitor_session_id", ASCENDING)],
            unique=True,
            name="widget_visitor_session_unique",
        ),
        IndexModel([("organization_id", ASCENDING), ("created_at", DESCENDING)], name="org_created_at"),
        # Retention: docs carry expires_at only when the widget has a
        # retention_days policy; TTL ignores docs without the field.
        IndexModel([("expires_at", ASCENDING)], name="retention_ttl", expireAfterSeconds=0),
    ])
    await widget_config_versions_collection.create_indexes([
        IndexModel([("widget_id", ASCENDING), ("version", DESCENDING)], unique=True, name="widget_version_unique"),
    ])
    await widget_message_feedback_collection.create_indexes([
        IndexModel(
            [("widget_id", ASCENDING), ("visitor_session_id", ASCENDING), ("message_id", ASCENDING)],
            unique=True,
            name="widget_session_message_unique",
        ),
        IndexModel([("expires_at", ASCENDING)], name="retention_ttl", expireAfterSeconds=0),
    ])
    # Delivery log is an operational aid, not chat data -- expire rows after
    # 30 days so the collection is self-pruning.
    await widget_webhook_deliveries_collection.create_indexes([
        IndexModel([("widget_id", ASCENDING), ("created_at", DESCENDING)], name="widget_created_at"),
        IndexModel([("created_at", ASCENDING)], name="ttl_30d", expireAfterSeconds=30 * 24 * 3600),
    ])

"""Constants for the database layer: connection defaults and collection names."""

# Defaults used when the corresponding env vars are not set.
DEFAULT_MONGO_URL = "mongodb://localhost:27017"
DEFAULT_DATABASE_NAME = "aiddb"

# Collection names.
USERS_COLLECTION = "users"
ORGANIZATIONS_COLLECTION = "organizations"
AGENTS_COLLECTION = "agents"
PROJECTS_COLLECTION = "projects"
PROJECT_CHATS_COLLECTION = "project_chats"
TOOL_REGISTRY_COLLECTION = "tool_registry"
RAG_SOURCES_COLLECTION = "rag_sources"
# Documents belonging to a rag_sources (Knowledge Base) entry. Raw bytes live
# in GridFS; this collection holds metadata + the AI-generated description
# used for fast document-level routing before the detailed chunk search.
KB_DOCUMENTS_COLLECTION = "kb_documents"
CHAT_SESSIONS_COLLECTION = "chat_sessions"
MESSAGES_COLLECTION = "messages"
DB_CONNECTIONS_COLLECTION = "db_connections"
TOOLS_COLLECTION = "tools"
TEAMS_COLLECTION = "teams"
ORG_ROLE_PERMISSIONS_COLLECTION = "org_role_permissions"
PASSWORD_RESETS_COLLECTION = "password_resets"
RATE_LIMIT_CONFIG_COLLECTION = "rate_limit_config"
QUOTA_CONFIG_COLLECTION = "quota_config"
ROLES_COLLECTION = "roles"
MCP_SERVERS_COLLECTION = "mcp_servers"
MCP_SERVER_REGISTRY_COLLECTION = "mcp_server_registry"
# Junction: which individual MCP tools (not whole servers) are attached to which agent.
AGENT_MCP_TOOLS_COLLECTION = "agent_mcp_tools"
# OAuth: in-flight authorizations (pending consent) and stored tokens/client info.
MCP_OAUTH_FLOWS_COLLECTION = "mcp_oauth_flows"
MCP_OAUTH_TOKENS_COLLECTION = "mcp_oauth_tokens"
CONVERSATION_LOGS_COLLECTION = "conversation_logs"
PERMISSIONS_COLLECTION = "permissions"
ROLE_PERMISSIONS_COLLECTION = "role_permissions"
QUERY_AUDIT_LOGS_COLLECTION = "query_audit_logs"
NOTIFICATIONS_COLLECTION = "notifications"
ORGANIZATION_SETTINGS_COLLECTION = "organization_settings"

AGENT_ORCHESTRATIONS_COLLECTION = "agent_orchestrations"
AGENT_PERMISSIONS_COLLECTION = "agent_permissions"
ORCHESTRATION_RUNS_COLLECTION = "orchestration_runs"
ORCHESTRATION_CONVERSATIONS_COLLECTION = "orchestration_conversations"

# Recurring/one-off scheduled agent runs (single-agent direct_chat, triggered
# by Celery Beat instead of a user message).
SCHEDULES_COLLECTION = "schedules"
SCHEDULE_RUNS_COLLECTION = "schedule_runs"

# Unified connectors module
CONNECTOR_REGISTRY_COLLECTION = "connector_registry"
CONNECTOR_CREDENTIALS_COLLECTION = "connector_credentials"
CONNECTOR_TOKENS_COLLECTION = "connector_tokens"
CONNECTOR_INSTANCES_COLLECTION = "connector_instances"
TOOLS_PERMISSIONS_REGISTRY_COLLECTION = "tools_permissions_registry"

# Embeddable chatbot widgets.
WIDGET_CONFIGS_COLLECTION = "widget_configs"
# Phase 2: anonymous visitor sessions for the public widget endpoints.
WIDGET_SESSIONS_COLLECTION = "widget_sessions"
# Draft/publish history: one append-only snapshot per publish/rollback action.
WIDGET_CONFIG_VERSIONS_COLLECTION = "widget_config_versions"
# Visitor thumbs up/down on individual assistant messages.
WIDGET_MESSAGE_FEEDBACK_COLLECTION = "widget_message_feedback"
# Outcome log for outbound widget webhook deliveries (TTL-expired after 30 days).
WIDGET_WEBHOOK_DELIVERIES_COLLECTION = "widget_webhook_deliveries"

# backend/connector_apps/slack — inbound: a Slack workspace installs our own
# single, marketplace-listed Slack App and chats with a bound One-AI agent.
# One installation doc per Slack workspace (team_id unique).
SLACK_APP_INSTALLATIONS_COLLECTION = "slack_app_installations"
# One doc per (team_id, channel_id) -- maps a Slack conversation to the
# backend chat/direct_agent session carrying its history, same shape as
# widget_sessions.
SLACK_APP_SESSIONS_COLLECTION = "slack_app_sessions"
# Event-id dedup so a Slack Events API retry (their 3-second ack window is
# often shorter than an agent turn) never causes a duplicate reply. TTL'd.
SLACK_APP_PROCESSED_EVENTS_COLLECTION = "slack_app_processed_events"

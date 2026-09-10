import logging
import os
import re

import dns.resolver
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

from backend.db import constants as c

load_dotenv()

logger = logging.getLogger(__name__)


def _redact_mongo_url(url: str) -> str:
    """Strip credentials from a Mongo URI so it's safe to log (host/db only)."""
    return re.sub(r"//[^@/]+@", "//****@", url)

dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ["8.8.8.8", "8.8.4.4", "1.1.1.1"]

MONGO_URL = os.getenv("MONGO_URL", c.DEFAULT_MONGO_URL)
DATABASE_NAME = os.getenv("DATABASE_NAME", c.DEFAULT_DATABASE_NAME)

logger.info(
    "[db] connecting to mongo url=%s database=%s",
    _redact_mongo_url(MONGO_URL), DATABASE_NAME,
)

client = AsyncIOMotorClient(MONGO_URL)

sync_client = MongoClient(MONGO_URL)
sync_db = sync_client[DATABASE_NAME]

db = client[DATABASE_NAME]
users_collection = db[c.USERS_COLLECTION]
organizations_collection = db[c.ORGANIZATIONS_COLLECTION]
agents_collection = db[c.AGENTS_COLLECTION]
projects_collection = db[c.PROJECTS_COLLECTION]
project_chats_collection = db[c.PROJECT_CHATS_COLLECTION]
tool_registry_collection = db[c.TOOL_REGISTRY_COLLECTION]
rag_sources_collection = db[c.RAG_SOURCES_COLLECTION]
kb_documents_collection = db[c.KB_DOCUMENTS_COLLECTION]
chat_sessions_collection = db[c.CHAT_SESSIONS_COLLECTION]
messages_collection = db[c.MESSAGES_COLLECTION]
db_connections_collection = db[c.DB_CONNECTIONS_COLLECTION]
tools_collection = db[c.TOOLS_COLLECTION]
teams_collection = db[c.TEAMS_COLLECTION]
org_role_permissions_collection = db[c.ORG_ROLE_PERMISSIONS_COLLECTION]
password_resets_collection = db[c.PASSWORD_RESETS_COLLECTION]
rate_limit_config_collection = db[c.RATE_LIMIT_CONFIG_COLLECTION]
quota_config_collection = db[c.QUOTA_CONFIG_COLLECTION]
roles_collection = db[c.ROLES_COLLECTION]
mcp_servers_collection = db[c.MCP_SERVERS_COLLECTION]
mcp_server_registry_collection = db[c.MCP_SERVER_REGISTRY_COLLECTION]
mcp_oauth_flows_collection = db[c.MCP_OAUTH_FLOWS_COLLECTION]
agent_mcp_tools_collection = db[c.AGENT_MCP_TOOLS_COLLECTION]
# Read by ai/multi_orchestration's sync graph-loader, which runs on sync_db.
agent_mcp_tools_sync = sync_db[c.AGENT_MCP_TOOLS_COLLECTION]
mcp_oauth_tokens_sync = sync_db[c.MCP_OAUTH_TOKENS_COLLECTION]
conversation_logs_collection = db[c.CONVERSATION_LOGS_COLLECTION]
permissions_collection = db[c.PERMISSIONS_COLLECTION]
role_permissions_collection = db[c.ROLE_PERMISSIONS_COLLECTION]
query_audit_logs_collection = db[c.QUERY_AUDIT_LOGS_COLLECTION]
notifications_collection = db[c.NOTIFICATIONS_COLLECTION]
organization_settings_collection = db[c.ORGANIZATION_SETTINGS_COLLECTION]
agent_orchestrations_collection = db[c.AGENT_ORCHESTRATIONS_COLLECTION]
agent_permissions_collection = db[c.AGENT_PERMISSIONS_COLLECTION]

schedules_collection = db[c.SCHEDULES_COLLECTION]
schedule_runs_collection = db[c.SCHEDULE_RUNS_COLLECTION]
schedules_sync = sync_db[c.SCHEDULES_COLLECTION]
schedule_runs_sync = sync_db[c.SCHEDULE_RUNS_COLLECTION]

connector_registry_collection = db[c.CONNECTOR_REGISTRY_COLLECTION]
connector_credentials_collection = db[c.CONNECTOR_CREDENTIALS_COLLECTION]
connector_tokens_collection = db[c.CONNECTOR_TOKENS_COLLECTION]
connector_instances_collection = db[c.CONNECTOR_INSTANCES_COLLECTION]
tools_permissions_registry_collection = db[c.TOOLS_PERMISSIONS_REGISTRY_COLLECTION]
sync_tools_permissions_registry_collection = sync_db[c.TOOLS_PERMISSIONS_REGISTRY_COLLECTION]

widget_configs_collection = db[c.WIDGET_CONFIGS_COLLECTION]
widget_sessions_collection = db[c.WIDGET_SESSIONS_COLLECTION]
widget_config_versions_collection = db[c.WIDGET_CONFIG_VERSIONS_COLLECTION]
widget_message_feedback_collection = db[c.WIDGET_MESSAGE_FEEDBACK_COLLECTION]
widget_webhook_deliveries_collection = db[c.WIDGET_WEBHOOK_DELIVERIES_COLLECTION]
slack_app_installations_collection = db[c.SLACK_APP_INSTALLATIONS_COLLECTION]
slack_app_sessions_collection = db[c.SLACK_APP_SESSIONS_COLLECTION]
slack_app_processed_events_collection = db[c.SLACK_APP_PROCESSED_EVENTS_COLLECTION]

async def ping_db():
    """Test database connection"""
    try:
        await client.admin.command('ping')
        print("✅ Connected to MongoDB")
        return True
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return False
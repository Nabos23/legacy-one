import logging
from abc import ABC, abstractmethod
from backend.db.database import sync_db

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """Base class for all connector tool providers."""

    PROVIDER_ID: str = ""
    FUNCTION_TO_ACTION: dict[str, str] = {}

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        self._token = access_token
        self.agent_id = agent_id
        self._auth_headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    @staticmethod
    def check_permission(
        agent_id: str,
        function_name: str,
        provider_id: str = None,
        function_to_action: dict[str, str] = None,
    ) -> tuple[bool, str]:
        """Query the agent_permissions collection to verify connector permission dynamically."""
        if not agent_id:
            return True, ""

        effective_provider_id = provider_id or ""
        func_action_map = function_to_action or {}

        action = None
        try:
            reg_doc = sync_db.tools_permissions_registry.find_one(
                {"$or": [{"provider_id": effective_provider_id}, {"connector_id": effective_provider_id}]}
            )
            if reg_doc and "permissions" in reg_doc:
                for act, funcs in reg_doc["permissions"].items():
                    if isinstance(funcs, list) and function_name in funcs:
                        action = act
                        break
        except Exception as exc:
            logger.warning("[connector-permission] Failed to query tools_permissions_registry: %s", exc)

        if not action:
            action = func_action_map.get(function_name, "read")

        try:
            doc = sync_db.agent_permissions.find_one(
                {"$or": [{"agent_id": str(agent_id)}, {"project_id": str(agent_id)}]}
            )
            if not doc:
                logger.info("[connector-permission] target=%s provider=%s func=%s action=%s — no permissions doc, allowing", agent_id, effective_provider_id, function_name, action)
                return True, action

            connectors = doc.get("permissions", {}).get("connectors", {})
            conn_perms = connectors.get(effective_provider_id)
            if conn_perms is None and reg_doc:
                conn_id = str(reg_doc.get("connector_id") or reg_doc.get("_id", ""))
                if conn_id and conn_id in connectors:
                    conn_perms = connectors[conn_id]

            allowed = True if conn_perms is None else bool(conn_perms.get(action, False))

            logger.info("[connector-permission] agent=%s provider=%s func=%s action=%s allowed=%s", agent_id, effective_provider_id, function_name, action, allowed)
            return allowed, action
        except Exception as exc:
            logger.warning("[connector-permission] agent=%s provider=%s func=%s action=%s — error checking: %s, allowing", agent_id, effective_provider_id, function_name, action, exc)
            return True, action

    @staticmethod
    def _check(agent_id: str, provider_id: str, tool_name: str, inp: dict, *required_fields: str):
        permission_allowed, permission_action = BaseConnector.check_permission(
            agent_id, tool_name, provider_id
        )
        if not permission_allowed:
            provider_name = provider_id.replace("_", " ").title() if provider_id else "connector"
            permission_error = f"Permission denied: Agent is not allowed to use {provider_name} '{permission_action}' actions."
            return permission_error, *[""] * len(required_fields)

        missing_fields = [field for field in required_fields if field not in inp or inp[field] is None or inp[field] == ""]
        if missing_fields:
            joined_fields = ", ".join(f"'{field}'" for field in missing_fields)
            permission_error = f"Error: missing required field(s): {joined_fields}."
            return permission_error, *[""] * len(required_fields)

        extracted_values = [inp.get(field, "") for field in required_fields]
        return None, *extracted_values

    @abstractmethod
    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        """Return (tool_defs, callables) in OpenAI function schema format."""

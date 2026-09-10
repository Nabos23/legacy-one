import json
import httpx
from ai.connectors.base import BaseConnector

_BASE = "https://api.datadoghq.com"


def _handle_error(tool_name, e):
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class DatadogConnector(BaseConnector):
    """Datadog connector for metrics, monitors, events, logs, dashboards, hosts, and service checks."""

    PROVIDER_ID = "datadog"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id=agent_id)
        parts = access_token.split(":", 1)
        self._api_key = parts[0]
        self._app_key = parts[1] if len(parts) > 1 else ""
        self._token = self._api_key

    @property
    def _auth_headers(self):
        return {
            "DD-API-KEY": self._api_key,
            "DD-APPLICATION-KEY": self._app_key,
            "Accept": "application/json",
        }

    @_auth_headers.setter
    def _auth_headers(self, value: dict) -> None:
        pass

    def _base(self, inp: dict) -> str:
        region = inp.get("region", "us1").lower()
        mapping = {
            "us1": "https://api.datadoghq.com",
            "us3": "https://api.us3.datadoghq.com",
            "us5": "https://api.us5.datadoghq.com",
            "eu1": "https://api.datadoghq.eu",
            "ap1": "https://api.ap1.datadoghq.com",
        }
        return mapping.get(region, _BASE)

    def datadog_list_metrics(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "datadog_list_metrics", inp)
        if permission_error: return permission_error
        base = self._base(inp)
        params = {}
        if inp.get("from"):
            params["from"] = inp["from"]
        if inp.get("host"):
            params["host"] = inp["host"]
        if inp.get("tag_filter"):
            params["tag_filter"] = inp["tag_filter"]
        try:
            r = httpx.get(f"{base}/api/v1/metrics", headers=self._auth_headers, params=params, timeout=30)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("datadog_list_metrics", e)

    def datadog_query_metrics(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "datadog_query_metrics", inp)
        if permission_error: return permission_error
        base = self._base(inp)
        params = {
            "query": inp.get("query", ""),
            "from": inp.get("from", 0),
            "to": inp.get("to", 0),
        }
        try:
            r = httpx.get(f"{base}/api/v1/query", headers=self._auth_headers, params=params, timeout=30)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("datadog_query_metrics", e)

    def datadog_list_monitors(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "datadog_list_monitors", inp)
        if permission_error: return permission_error
        base = self._base(inp)
        params = {}
        if inp.get("tags"):
            params["monitor_tags"] = inp["tags"]
        if inp.get("name"):
            params["name"] = inp["name"]
        if inp.get("page_size"):
            params["page_size"] = inp["page_size"]
        try:
            r = httpx.get(f"{base}/api/v1/monitor", headers=self._auth_headers, params=params, timeout=30)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("datadog_list_monitors", e)

    def datadog_list_events(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "datadog_list_events", inp)
        if permission_error: return permission_error
        base = self._base(inp)
        params = {
            "start": inp.get("start", 0),
            "end": inp.get("end", 0),
        }
        if inp.get("priority"):
            params["priority"] = inp["priority"]
        if inp.get("tags"):
            params["tags"] = inp["tags"]
        try:
            r = httpx.get(f"{base}/api/v1/events", headers=self._auth_headers, params=params, timeout=30)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("datadog_list_events", e)

    def datadog_list_dashboards(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "datadog_list_dashboards", inp)
        if permission_error: return permission_error
        base = self._base(inp)
        params = {}
        if inp.get("filter_shared") is not None:
            params["filter[shared]"] = inp["filter_shared"]
        if inp.get("filter_deleted") is not None:
            params["filter[deleted]"] = inp["filter_deleted"]
        try:
            r = httpx.get(f"{base}/api/v1/dashboard", headers=self._auth_headers, params=params, timeout=30)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("datadog_list_dashboards", e)

    def datadog_list_hosts(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "datadog_list_hosts", inp)
        if permission_error: return permission_error
        base = self._base(inp)
        params = {}
        if inp.get("filter"):
            params["filter"] = inp["filter"]
        if inp.get("count"):
            params["count"] = inp["count"]
        if inp.get("start"):
            params["start"] = inp["start"]
        try:
            r = httpx.get(f"{base}/api/v1/hosts", headers=self._auth_headers, params=params, timeout=30)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("datadog_list_hosts", e)

    def datadog_search_logs(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "datadog_search_logs", inp)
        if permission_error: return permission_error
        base = self._base(inp)
        body = {
            "filter": {
                "query": inp.get("query", "*"),
                "from": inp.get("from", "now-15m"),
                "to": inp.get("to", "now"),
            },
            "page": {
                "limit": inp.get("limit", 25),
            },
            "sort": inp.get("sort", "-timestamp"),
        }
        headers = {**self._auth_headers, "Content-Type": "application/json"}
        try:
            r = httpx.post(f"{base}/api/v2/logs/events/search", headers=headers, json=body, timeout=30)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("datadog_search_logs", e)

    def datadog_list_service_checks(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "datadog_list_service_checks", inp)
        if permission_error: return permission_error
        base = self._base(inp)
        try:
            r = httpx.get(f"{base}/api/v1/service_checks", headers=self._auth_headers, timeout=30)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("datadog_list_service_checks", e)

    def datadog_create_monitor(self, inp: dict) -> str:
        permission_error, name, monitor_type, query = self._check(self.agent_id, self.PROVIDER_ID, "datadog_create_monitor", inp, "name", "type", "query")
        if permission_error: return permission_error
        message = inp.get("message")
        tags = inp.get("tags") or []
        body = {
            "name": name,
            "type": monitor_type,
            "query": query,
            "message": message,
            "tags": tags,
        }
        base = self._base(inp)
        headers = {**self._auth_headers, "Content-Type": "application/json"}
        try:
            r = httpx.post(f"{base}/api/v1/monitor", headers=headers, json=body, timeout=30)
            r.raise_for_status()
            data = r.json()
            return json.dumps({
                "id": data.get("id"),
                "name": data.get("name"),
                "type": data.get("type"),
                "status": data.get("overall_state"),
            })
        except Exception as e:
            return _handle_error("datadog_create_monitor", e)

    def datadog_mute_monitor(self, inp: dict) -> str:
        permission_error, monitor_id = self._check(self.agent_id, self.PROVIDER_ID, "datadog_mute_monitor", inp, "monitor_id")
        if permission_error: return permission_error
        base = self._base(inp)
        headers = {**self._auth_headers, "Content-Type": "application/json"}
        body = {}
        if inp.get("end") is not None:
            body["end"] = inp["end"]
        try:
            r = httpx.post(f"{base}/api/v1/monitor/{monitor_id}/mute", headers=headers, json=body, timeout=30)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("datadog_mute_monitor", e)

    def datadog_unmute_monitor(self, inp: dict) -> str:
        permission_error, monitor_id = self._check(self.agent_id, self.PROVIDER_ID, "datadog_unmute_monitor", inp, "monitor_id")
        if permission_error: return permission_error
        base = self._base(inp)
        headers = {**self._auth_headers, "Content-Type": "application/json"}
        try:
            r = httpx.post(f"{base}/api/v1/monitor/{monitor_id}/unmute", headers=headers, json={}, timeout=30)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("datadog_unmute_monitor", e)

    def datadog_post_event(self, inp: dict) -> str:
        permission_error, title, text = self._check(self.agent_id, self.PROVIDER_ID, "datadog_post_event", inp, "title", "text")
        if permission_error: return permission_error
        tags = inp.get("tags") or []
        alert_type = inp.get("alert_type", "info")
        body = {
            "title": title,
            "text": text,
            "tags": tags,
            "alert_type": alert_type,
        }
        base = self._base(inp)
        headers = {**self._auth_headers, "Content-Type": "application/json"}
        try:
            r = httpx.post(f"{base}/api/v1/events", headers=headers, json=body, timeout=30)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("datadog_post_event", e)

    def datadog_get_dashboard(self, inp: dict) -> str:
        permission_error, dashboard_id = self._check(self.agent_id, self.PROVIDER_ID, "datadog_get_dashboard", inp, "dashboard_id")
        if permission_error: return permission_error
        base = self._base(inp)
        try:
            r = httpx.get(f"{base}/api/v1/dashboard/{dashboard_id}", headers=self._auth_headers, timeout=30)
            r.raise_for_status()
            data = r.json()
            return json.dumps({
                "id": data.get("id"),
                "title": data.get("title"),
                "description": data.get("description"),
                "url": data.get("url"),
                "graphs_count": len(data.get("widgets", [])),
            })
        except Exception as e:
            return _handle_error("datadog_get_dashboard", e)

    def datadog_delete_monitor(self, inp: dict) -> str:
        permission_error, monitor_id = self._check(self.agent_id, self.PROVIDER_ID, "datadog_delete_monitor", inp, "monitor_id")
        if permission_error: return permission_error
        base = self._base(inp)
        try:
            r = httpx.delete(f"{base}/api/v1/monitor/{monitor_id}", headers=self._auth_headers, timeout=30)
            r.raise_for_status()
            return json.dumps({"monitor_id": monitor_id, "status": "deleted"})
        except Exception as e:
            return _handle_error("datadog_delete_monitor", e)

    def datadog_list_slos(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "datadog_list_slos", inp)
        if permission_error: return permission_error
        base = self._base(inp)
        params = {}
        if inp.get("query"):
            params["query"] = inp["query"]
        if inp.get("tags_query"):
            params["tags_query"] = inp["tags_query"]
        try:
            r = httpx.get(f"{base}/api/v1/slo", headers=self._auth_headers, params=params, timeout=30)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("datadog_list_slos", e)

    def as_tools(self):
        tool_defs = [
            {
                "type": "function",
                "function": {
                    "name": "datadog_list_metrics",
                    "description": "List active metrics from Datadog, optionally filtered by host or tag.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "integer", "description": "Unix timestamp for the start of the time window."},
                            "host": {"type": "string", "description": "Filter metrics by host name."},
                            "tag_filter": {"type": "string", "description": "Filter metrics by tag (e.g. 'env:prod')."},
                            "region": {"type": "string", "description": "Datadog region: us1, us3, us5, eu1, ap1. Defaults to us1."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "datadog_query_metrics",
                    "description": "Query time-series metric data from Datadog for a given time range and metric expression.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Datadog metrics query string (e.g. 'avg:system.cpu.user{*}')."},
                            "from": {"type": "integer", "description": "Unix timestamp for the start of the query window."},
                            "to": {"type": "integer", "description": "Unix timestamp for the end of the query window."},
                            "region": {"type": "string", "description": "Datadog region: us1, us3, us5, eu1, ap1. Defaults to us1."},
                        },
                        "required": ["query", "from", "to"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "datadog_list_monitors",
                    "description": "List Datadog monitors, optionally filtered by tags or name.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tags": {"type": "string", "description": "Comma-separated monitor tags to filter by."},
                            "name": {"type": "string", "description": "Filter monitors by name substring."},
                            "page_size": {"type": "integer", "description": "Number of monitors to return per page."},
                            "region": {"type": "string", "description": "Datadog region: us1, us3, us5, eu1, ap1. Defaults to us1."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "datadog_list_events",
                    "description": "List Datadog events within a Unix timestamp range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "integer", "description": "Unix timestamp for the start of the event window."},
                            "end": {"type": "integer", "description": "Unix timestamp for the end of the event window."},
                            "priority": {"type": "string", "description": "Filter by event priority: normal or low."},
                            "tags": {"type": "string", "description": "Comma-separated tags to filter events."},
                            "region": {"type": "string", "description": "Datadog region: us1, us3, us5, eu1, ap1. Defaults to us1."},
                        },
                        "required": ["start", "end"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "datadog_list_dashboards",
                    "description": "List all Datadog dashboards for the organization.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filter_shared": {"type": "boolean", "description": "Filter to only shared dashboards."},
                            "filter_deleted": {"type": "boolean", "description": "Include deleted dashboards."},
                            "region": {"type": "string", "description": "Datadog region: us1, us3, us5, eu1, ap1. Defaults to us1."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "datadog_list_hosts",
                    "description": "List hosts reporting to Datadog, optionally filtered by a search expression.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filter": {"type": "string", "description": "Filter string to search hosts (e.g. 'env:production')."},
                            "count": {"type": "integer", "description": "Number of hosts to return."},
                            "start": {"type": "integer", "description": "Offset for pagination."},
                            "region": {"type": "string", "description": "Datadog region: us1, us3, us5, eu1, ap1. Defaults to us1."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "datadog_search_logs",
                    "description": "Search Datadog logs using a filter query over a time range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Log search query string (e.g. 'service:web status:error')."},
                            "from": {"type": "string", "description": "Start of the time range (ISO 8601 or relative like 'now-1h')."},
                            "to": {"type": "string", "description": "End of the time range (ISO 8601 or relative like 'now')."},
                            "limit": {"type": "integer", "description": "Maximum number of log events to return (default 25)."},
                            "sort": {"type": "string", "description": "Sort order: -timestamp (newest first) or timestamp (oldest first)."},
                            "region": {"type": "string", "description": "Datadog region: us1, us3, us5, eu1, ap1. Defaults to us1."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "datadog_list_service_checks",
                    "description": "List the most recent service check results submitted to Datadog.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "region": {"type": "string", "description": "Datadog region: us1, us3, us5, eu1, ap1. Defaults to us1."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "datadog_create_monitor",
                    "description": "Create a new Datadog monitor to alert on a metric, service check, or event condition.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Name of the monitor."},
                            "type": {"type": "string", "description": "Monitor type: metric alert, service check, event alert, or composite."},
                            "query": {"type": "string", "description": "The monitor query expression."},
                            "message": {"type": "string", "description": "Notification message when the monitor triggers (optional)."},
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of tags to associate with the monitor (optional).",
                            },
                            "region": {"type": "string", "description": "Datadog region: us1, us3, us5, eu1, ap1. Defaults to us1."},
                        },
                        "required": ["name", "type", "query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "datadog_mute_monitor",
                    "description": "Mute a Datadog monitor to suppress notifications.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "monitor_id": {"type": "integer", "description": "The ID of the monitor to mute."},
                            "end": {"type": "integer", "description": "Unix timestamp when the mute expires (optional, mutes indefinitely if omitted)."},
                            "region": {"type": "string", "description": "Datadog region: us1, us3, us5, eu1, ap1. Defaults to us1."},
                        },
                        "required": ["monitor_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "datadog_unmute_monitor",
                    "description": "Unmute a previously muted Datadog monitor.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "monitor_id": {"type": "integer", "description": "The ID of the monitor to unmute."},
                            "region": {"type": "string", "description": "Datadog region: us1, us3, us5, eu1, ap1. Defaults to us1."},
                        },
                        "required": ["monitor_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "datadog_post_event",
                    "description": "Post a custom event to the Datadog event stream.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Title of the event."},
                            "text": {"type": "string", "description": "Body/description of the event."},
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of tags to associate with the event (optional).",
                            },
                            "alert_type": {"type": "string", "description": "Alert type: info, warning, error, or success (default info)."},
                            "region": {"type": "string", "description": "Datadog region: us1, us3, us5, eu1, ap1. Defaults to us1."},
                        },
                        "required": ["title", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "datadog_get_dashboard",
                    "description": "Get details of a specific Datadog dashboard by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dashboard_id": {"type": "string", "description": "The ID of the Datadog dashboard."},
                            "region": {"type": "string", "description": "Datadog region: us1, us3, us5, eu1, ap1. Defaults to us1."},
                        },
                        "required": ["dashboard_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "datadog_delete_monitor",
                    "description": "Permanently delete a Datadog monitor.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "monitor_id": {"type": "integer", "description": "The ID of the monitor to delete."},
                            "region": {"type": "string", "description": "Datadog region: us1, us3, us5, eu1, ap1. Defaults to us1."},
                        },
                        "required": ["monitor_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "datadog_list_slos",
                    "description": "List Service Level Objectives (SLOs) configured in Datadog.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Filter query for SLO names or descriptions (optional)."},
                            "tags_query": {"type": "string", "description": "Filter SLOs by tags (optional)."},
                            "region": {"type": "string", "description": "Datadog region: us1, us3, us5, eu1, ap1. Defaults to us1."},
                        },
                        "required": [],
                    },
                },
            },
        ]

        callables = {
            "datadog_list_metrics": self.datadog_list_metrics,
            "datadog_query_metrics": self.datadog_query_metrics,
            "datadog_list_monitors": self.datadog_list_monitors,
            "datadog_list_events": self.datadog_list_events,
            "datadog_list_dashboards": self.datadog_list_dashboards,
            "datadog_list_hosts": self.datadog_list_hosts,
            "datadog_search_logs": self.datadog_search_logs,
            "datadog_list_service_checks": self.datadog_list_service_checks,
            "datadog_create_monitor": self.datadog_create_monitor,
            "datadog_mute_monitor": self.datadog_mute_monitor,
            "datadog_unmute_monitor": self.datadog_unmute_monitor,
            "datadog_post_event": self.datadog_post_event,
            "datadog_get_dashboard": self.datadog_get_dashboard,
            "datadog_delete_monitor": self.datadog_delete_monitor,
            "datadog_list_slos": self.datadog_list_slos,
        }

        return tool_defs, callables

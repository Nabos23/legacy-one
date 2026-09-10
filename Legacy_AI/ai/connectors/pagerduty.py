import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.pagerduty.com"


def _handle_error(tool_name, e):
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class PagerdutyConnector(BaseConnector):
    """PagerDuty ITSM connector for incidents, services, schedules, on-calls, and users."""

    PROVIDER_ID = "pagerduty"

    def __init__(self, access_token: str, agent_id: str = "") -> None:
        super().__init__(access_token, agent_id=agent_id)
        self._token = access_token
        self._auth_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.pagerduty+json;version=2",
        }

    def list_incidents(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "pagerduty_list_incidents", inp)
        if permission_error: return permission_error
        try:
            params = {
                "limit": inp.get("limit", 25),
                "offset": inp.get("offset", 0),
            }
            if inp.get("status"):
                params["statuses[]"] = inp["status"]
            if inp.get("urgency"):
                params["urgencies[]"] = inp["urgency"]
            if inp.get("service_ids"):
                params["service_ids[]"] = inp["service_ids"]
            resp = httpx.get(
                f"{_BASE}/incidents",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            incidents = [
                {
                    "id": i.get("id"),
                    "incident_number": i.get("incident_number"),
                    "title": i.get("title"),
                    "status": i.get("status"),
                    "urgency": i.get("urgency"),
                    "created_at": i.get("created_at"),
                    "service": i.get("service", {}).get("summary"),
                    "assigned_to": [a.get("assignee", {}).get("summary") for a in i.get("assignments", [])],
                    "html_url": i.get("html_url"),
                }
                for i in data.get("incidents", [])
            ]
            return json.dumps({"incidents": incidents, "count": len(incidents), "total": data.get("total")})
        except Exception as e:
            return _handle_error("pagerduty_list_incidents", e)

    def get_incident(self, inp: dict) -> str:
        permission_error, incident_id = self._check(self.agent_id, self.PROVIDER_ID, "pagerduty_get_incident", inp, "incident_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/incidents/{incident_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            i = resp.json().get("incident", {})
            return json.dumps({
                "id": i.get("id"),
                "incident_number": i.get("incident_number"),
                "title": i.get("title"),
                "description": i.get("description"),
                "status": i.get("status"),
                "urgency": i.get("urgency"),
                "created_at": i.get("created_at"),
                "resolved_at": i.get("resolved_at"),
                "service": i.get("service", {}).get("summary"),
                "escalation_policy": i.get("escalation_policy", {}).get("summary"),
                "assigned_to": [a.get("assignee", {}).get("summary") for a in i.get("assignments", [])],
                "acknowledgements": [a.get("acknowledger", {}).get("summary") for a in i.get("acknowledgements", [])],
                "last_status_change_at": i.get("last_status_change_at"),
                "html_url": i.get("html_url"),
            })
        except Exception as e:
            return _handle_error("pagerduty_get_incident", e)

    def list_services(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "pagerduty_list_services", inp)
        if permission_error: return permission_error
        try:
            params = {
                "limit": inp.get("limit", 25),
                "offset": inp.get("offset", 0),
            }
            if inp.get("query"):
                params["query"] = inp["query"]
            resp = httpx.get(
                f"{_BASE}/services",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            services = [
                {
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "description": s.get("description"),
                    "status": s.get("status"),
                    "escalation_policy": s.get("escalation_policy", {}).get("summary"),
                    "incident_urgency_rule": s.get("incident_urgency_rule", {}).get("type"),
                    "html_url": s.get("html_url"),
                }
                for s in data.get("services", [])
            ]
            return json.dumps({"services": services, "count": len(services), "total": data.get("total")})
        except Exception as e:
            return _handle_error("pagerduty_list_services", e)

    def get_service(self, inp: dict) -> str:
        permission_error, service_id = self._check(self.agent_id, self.PROVIDER_ID, "pagerduty_get_service", inp, "service_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/services/{service_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            s = resp.json().get("service", {})
            return json.dumps({
                "id": s.get("id"),
                "name": s.get("name"),
                "description": s.get("description"),
                "status": s.get("status"),
                "escalation_policy": s.get("escalation_policy", {}).get("summary"),
                "integrations": [i.get("summary") for i in s.get("integrations", [])],
                "created_at": s.get("created_at"),
                "last_incident_timestamp": s.get("last_incident_timestamp"),
                "html_url": s.get("html_url"),
            })
        except Exception as e:
            return _handle_error("pagerduty_get_service", e)

    def list_schedules(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "pagerduty_list_schedules", inp)
        if permission_error: return permission_error
        try:
            params = {
                "limit": inp.get("limit", 25),
                "offset": inp.get("offset", 0),
            }
            if inp.get("query"):
                params["query"] = inp["query"]
            resp = httpx.get(
                f"{_BASE}/schedules",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            schedules = [
                {
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "description": s.get("description"),
                    "time_zone": s.get("time_zone"),
                    "teams": [t.get("summary") for t in s.get("teams", [])],
                    "html_url": s.get("html_url"),
                }
                for s in data.get("schedules", [])
            ]
            return json.dumps({"schedules": schedules, "count": len(schedules), "total": data.get("total")})
        except Exception as e:
            return _handle_error("pagerduty_list_schedules", e)

    def list_oncalls(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "pagerduty_list_oncalls", inp)
        if permission_error: return permission_error
        try:
            params = {}
            if inp.get("schedule_ids"):
                params["schedule_ids[]"] = inp["schedule_ids"]
            if inp.get("user_ids"):
                params["user_ids[]"] = inp["user_ids"]
            if inp.get("escalation_policy_ids"):
                params["escalation_policy_ids[]"] = inp["escalation_policy_ids"]
            resp = httpx.get(
                f"{_BASE}/oncalls",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            oncalls = [
                {
                    "escalation_policy": o.get("escalation_policy", {}).get("summary"),
                    "escalation_level": o.get("escalation_level"),
                    "user": o.get("user", {}).get("summary"),
                    "schedule": o.get("schedule", {}).get("summary") if o.get("schedule") else None,
                    "start": o.get("start"),
                    "end": o.get("end"),
                }
                for o in data.get("oncalls", [])
            ]
            return json.dumps({"oncalls": oncalls, "count": len(oncalls)})
        except Exception as e:
            return _handle_error("pagerduty_list_oncalls", e)

    def list_users(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "pagerduty_list_users", inp)
        if permission_error: return permission_error
        try:
            params = {
                "limit": inp.get("limit", 25),
                "offset": inp.get("offset", 0),
            }
            if inp.get("query"):
                params["query"] = inp["query"]
            resp = httpx.get(
                f"{_BASE}/users",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            users = [
                {
                    "id": u.get("id"),
                    "name": u.get("name"),
                    "email": u.get("email"),
                    "role": u.get("role"),
                    "job_title": u.get("job_title"),
                    "time_zone": u.get("time_zone"),
                    "html_url": u.get("html_url"),
                }
                for u in data.get("users", [])
            ]
            return json.dumps({"users": users, "count": len(users), "total": data.get("total")})
        except Exception as e:
            return _handle_error("pagerduty_list_users", e)

    def acknowledge_incident(self, inp: dict) -> str:
        permission_error, incident_id, from_email = self._check(self.agent_id, self.PROVIDER_ID, "pagerduty_acknowledge_incident", inp, "id", "from_email")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "From": from_email, "Content-Type": "application/json"}
            body = {
                "incidents": [
                    {"id": incident_id, "type": "incident_reference", "status": "acknowledged"}
                ]
            }
            resp = httpx.put(f"{_BASE}/incidents", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            incidents = data.get("incidents", [])
            if incidents:
                i = incidents[0]
                return json.dumps({
                    "id": i.get("id"),
                    "status": i.get("status"),
                    "incident_number": i.get("incident_number"),
                    "title": i.get("title"),
                })
            return json.dumps({"success": True})
        except Exception as e:
            return _handle_error("pagerduty_acknowledge_incident", e)

    def resolve_incident(self, inp: dict) -> str:
        permission_error, incident_id, from_email = self._check(self.agent_id, self.PROVIDER_ID, "pagerduty_resolve_incident", inp, "id", "from_email")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "From": from_email, "Content-Type": "application/json"}
            body = {
                "incidents": [
                    {"id": incident_id, "type": "incident_reference", "status": "resolved"}
                ]
            }
            resp = httpx.put(f"{_BASE}/incidents", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            incidents = data.get("incidents", [])
            if incidents:
                i = incidents[0]
                return json.dumps({
                    "id": i.get("id"),
                    "status": i.get("status"),
                    "incident_number": i.get("incident_number"),
                    "title": i.get("title"),
                    "resolved_at": i.get("resolved_at"),
                })
            return json.dumps({"success": True})
        except Exception as e:
            return _handle_error("pagerduty_resolve_incident", e)

    def create_incident(self, inp: dict) -> str:
        permission_error, title, service_id, from_email = self._check(self.agent_id, self.PROVIDER_ID, "pagerduty_create_incident", inp, "title", "service_id", "from_email")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "From": from_email, "Content-Type": "application/json"}
            incident_body: dict = {
                "type": "incident",
                "title": title,
                "service": {"id": service_id, "type": "service_reference"},
            }
            if inp.get("body"):
                incident_body["body"] = {"type": "incident_body", "details": inp["body"]}
            body = {"incident": incident_body}
            resp = httpx.post(f"{_BASE}/incidents", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            i = resp.json().get("incident", {})
            return json.dumps({
                "id": i.get("id"),
                "incident_number": i.get("incident_number"),
                "title": i.get("title"),
                "status": i.get("status"),
                "urgency": i.get("urgency"),
                "created_at": i.get("created_at"),
                "html_url": i.get("html_url"),
            })
        except Exception as e:
            return _handle_error("pagerduty_create_incident", e)

    def list_escalation_policies(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "pagerduty_list_escalation_policies", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 25)}
            if inp.get("query"):
                params["query"] = inp["query"]
            resp = httpx.get(
                f"{_BASE}/escalation_policies",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            policies = [
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "description": p.get("description"),
                    "num_loops": p.get("num_loops"),
                    "teams": [t.get("summary") for t in p.get("teams", [])],
                    "services": [s.get("summary") for s in p.get("services", [])],
                    "html_url": p.get("html_url"),
                }
                for p in data.get("escalation_policies", [])
            ]
            return json.dumps({"escalation_policies": policies, "count": len(policies), "total": data.get("total")})
        except Exception as e:
            return _handle_error("pagerduty_list_escalation_policies", e)

    def get_user(self, inp: dict) -> str:
        permission_error, user_id = self._check(self.agent_id, self.PROVIDER_ID, "pagerduty_get_user", inp, "user_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/users/{user_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            u = resp.json().get("user", {})
            return json.dumps({
                "id": u.get("id"),
                "name": u.get("name"),
                "email": u.get("email"),
                "role": u.get("role"),
                "job_title": u.get("job_title"),
                "time_zone": u.get("time_zone"),
                "description": u.get("description"),
                "avatar_url": u.get("avatar_url"),
                "html_url": u.get("html_url"),
                "teams": [t.get("summary") for t in u.get("teams", [])],
            })
        except Exception as e:
            return _handle_error("pagerduty_get_user", e)

    def list_teams(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "pagerduty_list_teams", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 25)}
            if inp.get("query"):
                params["query"] = inp["query"]
            resp = httpx.get(f"{_BASE}/teams", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            teams = [
                {"id": t.get("id"), "name": t.get("name"), "description": t.get("description"), "html_url": t.get("html_url")}
                for t in data.get("teams", [])
            ]
            return json.dumps({"teams": teams, "count": len(teams), "total": data.get("total")})
        except Exception as e:
            return _handle_error("pagerduty_list_teams", e)

    def add_note_to_incident(self, inp: dict) -> str:
        permission_error, incident_id, content, from_email = self._check(self.agent_id, self.PROVIDER_ID, "pagerduty_add_note_to_incident", inp, "id", "content", "from_email")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "From": from_email, "Content-Type": "application/json"}
            body = {"note": {"content": content}}
            resp = httpx.post(f"{_BASE}/incidents/{incident_id}/notes", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            n = resp.json().get("note", {})
            return json.dumps({"id": n.get("id"), "content": n.get("content"), "status": "note_added"})
        except Exception as e:
            return _handle_error("pagerduty_add_note_to_incident", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "pagerduty_list_incidents",
                    "description": "List PagerDuty incidents with optional filtering by status, urgency, or service.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by status: triggered, acknowledged, or resolved."},
                            "urgency": {"type": "string", "description": "Filter by urgency: high or low."},
                            "service_ids": {"type": "array", "items": {"type": "string"}, "description": "List of service IDs to filter by."},
                            "limit": {"type": "integer", "description": "Max incidents to return (default 25)."},
                            "offset": {"type": "integer", "description": "Pagination offset (default 0)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pagerduty_get_incident",
                    "description": "Get full details of a specific PagerDuty incident by its ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "incident_id": {"type": "string", "description": "The PagerDuty incident ID (e.g. 'P1234AB')."},
                        },
                        "required": ["incident_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pagerduty_list_services",
                    "description": "List PagerDuty services, optionally filtered by name query.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Filter services by name substring."},
                            "limit": {"type": "integer", "description": "Max services to return (default 25)."},
                            "offset": {"type": "integer", "description": "Pagination offset (default 0)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pagerduty_get_service",
                    "description": "Get full details of a specific PagerDuty service by its ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service_id": {"type": "string", "description": "The PagerDuty service ID (e.g. 'PABC123')."},
                        },
                        "required": ["service_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pagerduty_list_schedules",
                    "description": "List PagerDuty on-call schedules, optionally filtered by name query.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Filter schedules by name substring."},
                            "limit": {"type": "integer", "description": "Max schedules to return (default 25)."},
                            "offset": {"type": "integer", "description": "Pagination offset (default 0)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pagerduty_list_oncalls",
                    "description": "List who is currently on-call in PagerDuty, optionally filtered by schedule, user, or escalation policy.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "schedule_ids": {"type": "array", "items": {"type": "string"}, "description": "Filter by schedule IDs."},
                            "user_ids": {"type": "array", "items": {"type": "string"}, "description": "Filter by user IDs."},
                            "escalation_policy_ids": {"type": "array", "items": {"type": "string"}, "description": "Filter by escalation policy IDs."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pagerduty_list_users",
                    "description": "List PagerDuty users, optionally filtered by name or email query.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Filter users by name or email substring."},
                            "limit": {"type": "integer", "description": "Max users to return (default 25)."},
                            "offset": {"type": "integer", "description": "Pagination offset (default 0)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pagerduty_acknowledge_incident",
                    "description": "Acknowledge a PagerDuty incident by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "The PagerDuty incident ID to acknowledge. Required."},
                            "from_email": {"type": "string", "description": "Email address of the user acknowledging the incident (required by PagerDuty API). Required."},
                        },
                        "required": ["id", "from_email"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pagerduty_resolve_incident",
                    "description": "Resolve a PagerDuty incident by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "The PagerDuty incident ID to resolve. Required."},
                            "from_email": {"type": "string", "description": "Email address of the user resolving the incident (required by PagerDuty API). Required."},
                        },
                        "required": ["id", "from_email"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pagerduty_create_incident",
                    "description": "Create a new PagerDuty incident for a given service.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Incident title/summary. Required."},
                            "service_id": {"type": "string", "description": "PagerDuty service ID to attach the incident to. Required."},
                            "from_email": {"type": "string", "description": "Email address of the user creating the incident (required by PagerDuty API). Required."},
                            "body": {"type": "string", "description": "Optional incident body/description with more detail."},
                        },
                        "required": ["title", "service_id", "from_email"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pagerduty_list_escalation_policies",
                    "description": "List PagerDuty escalation policies, optionally filtered by name query.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Filter escalation policies by name substring."},
                            "limit": {"type": "integer", "description": "Max policies to return (default 25)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pagerduty_get_user",
                    "description": "Get full details of a specific PagerDuty user by their ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "The PagerDuty user ID. Required."},
                        },
                        "required": ["user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pagerduty_list_teams",
                    "description": "List teams in the PagerDuty account.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Filter teams by name substring."},
                            "limit": {"type": "integer", "description": "Max teams to return (default 25)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pagerduty_add_note_to_incident",
                    "description": "Add a note/comment to a PagerDuty incident.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "The PagerDuty incident ID. Required."},
                            "content": {"type": "string", "description": "Note text content. Required."},
                            "from_email": {"type": "string", "description": "Email address of the user adding the note (required by PagerDuty API). Required."},
                        },
                        "required": ["id", "content", "from_email"],
                    },
                },
            },
        ]
        callables = {
            "pagerduty_list_incidents": self.list_incidents,
            "pagerduty_get_incident": self.get_incident,
            "pagerduty_list_services": self.list_services,
            "pagerduty_get_service": self.get_service,
            "pagerduty_list_schedules": self.list_schedules,
            "pagerduty_list_oncalls": self.list_oncalls,
            "pagerduty_list_users": self.list_users,
            "pagerduty_acknowledge_incident": self.acknowledge_incident,
            "pagerduty_resolve_incident": self.resolve_incident,
            "pagerduty_create_incident": self.create_incident,
            "pagerduty_list_escalation_policies": self.list_escalation_policies,
            "pagerduty_get_user": self.get_user,
            "pagerduty_list_teams": self.list_teams,
            "pagerduty_add_note_to_incident": self.add_note_to_incident,
        }
        return tools, callables

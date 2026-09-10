import json
import httpx

from ai.connectors.base import BaseConnector


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected ServiceNow account lacks permission "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their ServiceNow connector."
            )
        if e.response.status_code == 404:
            return f"Not found in {tool_name}: the requested resource does not exist."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class ServiceNowConnector(BaseConnector):
    """
    ServiceNow connector.
    access_token format: "USERNAME:PASSWORD:INSTANCE"
    where INSTANCE is the ServiceNow instance name (e.g. "mycompany" → mycompany.service-now.com)
    """

    PROVIDER_ID = "servicenow"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id=agent_id)
        parts = access_token.split(":", 2)
        self._token = access_token
        self._username = parts[0] if len(parts) > 0 else ""
        self._password = parts[1] if len(parts) > 1 else ""
        self._instance = parts[2] if len(parts) > 2 else ""
        self._token = access_token
        self._base = f"https://{self._instance}.service-now.com/api/now"

    @property
    def _auth_headers(self) -> dict:
        return {"Accept": "application/json", "Content-Type": "application/json"}

    @property
    def _auth(self) -> tuple:
        return (self._username, self._password)

    def list_incidents(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "servicenow_list_incidents", inp)
        if permission_error: return permission_error
        try:
            params = {
                "sysparm_limit": inp.get("limit", 20),
                "sysparm_fields": "number,short_description,state,priority,assigned_to,opened_at,updated_at,caller_id",
                "sysparm_query": inp.get("query", "active=true^ORDERBYDESCopened_at"),
            }
            resp = httpx.get(
                f"{self._base}/table/incident",
                headers=self._auth_headers,
                auth=self._auth,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            records = resp.json().get("result", [])
            incidents = [
                {
                    "number": r.get("number"),
                    "short_description": r.get("short_description"),
                    "state": r.get("state"),
                    "priority": r.get("priority"),
                    "assigned_to": r.get("assigned_to", {}).get("display_value") if isinstance(r.get("assigned_to"), dict) else r.get("assigned_to"),
                    "opened_at": r.get("opened_at"),
                    "caller": r.get("caller_id", {}).get("display_value") if isinstance(r.get("caller_id"), dict) else r.get("caller_id"),
                }
                for r in records
            ]
            return json.dumps({"incidents": incidents, "count": len(incidents)})
        except Exception as e:
            return _handle_error("servicenow_list_incidents", e)

    def get_incident(self, inp: dict) -> str:
        permission_error, number = self._check(self.agent_id, self.PROVIDER_ID, "servicenow_get_incident", inp, "number")
        if permission_error: return permission_error
        try:
            params = {
                "sysparm_query": f"number={number}",
                "sysparm_fields": "number,short_description,description,state,priority,urgency,impact,assigned_to,opened_at,updated_at,resolved_at,close_notes,caller_id,category,subcategory",
                "sysparm_limit": 1,
            }
            resp = httpx.get(
                f"{self._base}/table/incident",
                headers=self._auth_headers,
                auth=self._auth,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json().get("result", [])
            if not results:
                return json.dumps({"error": f"Incident {number} not found."})
            r = results[0]
            return json.dumps({
                "number": r.get("number"),
                "short_description": r.get("short_description"),
                "description": r.get("description"),
                "state": r.get("state"),
                "priority": r.get("priority"),
                "urgency": r.get("urgency"),
                "impact": r.get("impact"),
                "assigned_to": r.get("assigned_to", {}).get("display_value") if isinstance(r.get("assigned_to"), dict) else r.get("assigned_to"),
                "caller": r.get("caller_id", {}).get("display_value") if isinstance(r.get("caller_id"), dict) else r.get("caller_id"),
                "category": r.get("category"),
                "opened_at": r.get("opened_at"),
                "resolved_at": r.get("resolved_at"),
                "close_notes": r.get("close_notes"),
            })
        except Exception as e:
            return _handle_error("servicenow_get_incident", e)

    def create_incident(self, inp: dict) -> str:
        permission_error, short_description = self._check(self.agent_id, self.PROVIDER_ID, "servicenow_create_incident", inp, "short_description")
        if permission_error: return permission_error
        try:
            body = {
                "short_description": short_description,
                "description": inp.get("description", ""),
                "urgency": inp.get("urgency", "3"),
                "impact": inp.get("impact", "3"),
                "category": inp.get("category", ""),
            }
            if inp.get("caller_id"):
                body["caller_id"] = inp["caller_id"]
            if inp.get("assigned_to"):
                body["assigned_to"] = inp["assigned_to"]
            resp = httpx.post(
                f"{self._base}/table/incident",
                headers=self._auth_headers,
                auth=self._auth,
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            r = resp.json().get("result", {})
            return json.dumps({"number": r.get("number"), "sys_id": r.get("sys_id"), "status": "created"})
        except Exception as e:
            return _handle_error("servicenow_create_incident", e)

    def update_incident(self, inp: dict) -> str:
        permission_error, number = self._check(self.agent_id, self.PROVIDER_ID, "servicenow_update_incident", inp, "number")
        if permission_error: return permission_error
        try:
            # First get sys_id
            params = {"sysparm_query": f"number={number}", "sysparm_fields": "sys_id", "sysparm_limit": 1}
            resp = httpx.get(f"{self._base}/table/incident", headers=self._auth_headers, auth=self._auth, params=params, timeout=15)
            resp.raise_for_status()
            results = resp.json().get("result", [])
            if not results:
                return json.dumps({"error": f"Incident {number} not found."})
            sys_id = results[0]["sys_id"]

            body = {}
            if inp.get("state"):
                body["state"] = inp["state"]
            if inp.get("assigned_to"):
                body["assigned_to"] = inp["assigned_to"]
            if inp.get("close_notes"):
                body["close_notes"] = inp["close_notes"]
            if inp.get("work_notes"):
                body["work_notes"] = inp["work_notes"]
            if inp.get("priority"):
                body["priority"] = inp["priority"]

            resp2 = httpx.patch(
                f"{self._base}/table/incident/{sys_id}",
                headers=self._auth_headers,
                auth=self._auth,
                json=body,
                timeout=15,
            )
            resp2.raise_for_status()
            return json.dumps({"number": number, "status": "updated"})
        except Exception as e:
            return _handle_error("servicenow_update_incident", e)

    def list_requests(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "servicenow_list_requests", inp)
        if permission_error: return permission_error
        try:
            params = {
                "sysparm_limit": inp.get("limit", 20),
                "sysparm_fields": "number,short_description,state,priority,opened_at,requested_for",
                "sysparm_query": inp.get("query", "active=true^ORDERBYDESCopened_at"),
            }
            resp = httpx.get(
                f"{self._base}/table/sc_request",
                headers=self._auth_headers,
                auth=self._auth,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            records = resp.json().get("result", [])
            requests = [
                {
                    "number": r.get("number"),
                    "short_description": r.get("short_description"),
                    "state": r.get("state"),
                    "priority": r.get("priority"),
                    "opened_at": r.get("opened_at"),
                    "requested_for": r.get("requested_for", {}).get("display_value") if isinstance(r.get("requested_for"), dict) else r.get("requested_for"),
                }
                for r in records
            ]
            return json.dumps({"requests": requests, "count": len(requests)})
        except Exception as e:
            return _handle_error("servicenow_list_requests", e)

    def search_knowledge(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "servicenow_search_knowledge", inp, "query")
        if permission_error: return permission_error
        try:
            params = {
                "sysparm_limit": inp.get("limit", 10),
                "sysparm_fields": "number,short_description,text,category,kb_knowledge_base",
                "sysparm_query": f"short_descriptionLIKE{query}^ORtextLIKE{query}^workflow_state=published",
            }
            resp = httpx.get(
                f"{self._base}/table/kb_knowledge",
                headers=self._auth_headers,
                auth=self._auth,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            articles = [
                {
                    "number": r.get("number"),
                    "title": r.get("short_description"),
                    "category": r.get("category"),
                    "text": r.get("text", "")[:500],
                }
                for r in resp.json().get("result", [])
            ]
            return json.dumps({"articles": articles, "count": len(articles)})
        except Exception as e:
            return _handle_error("servicenow_search_knowledge", e)

    def get_request(self, inp: dict) -> str:
        permission_error, sys_id = self._check(self.agent_id, self.PROVIDER_ID, "servicenow_get_request", inp, "sys_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{self._base}/table/sc_request/{sys_id}",
                headers=self._auth_headers,
                auth=self._auth,
                timeout=15,
            )
            resp.raise_for_status()
            r = resp.json().get("result", {})
            return json.dumps({
                "sys_id": r.get("sys_id"),
                "number": r.get("number"),
                "short_description": r.get("short_description"),
                "state": r.get("state"),
                "priority": r.get("priority"),
                "opened_at": r.get("opened_at"),
                "requested_for": r.get("requested_for", {}).get("display_value") if isinstance(r.get("requested_for"), dict) else r.get("requested_for"),
                "description": r.get("description"),
            })
        except Exception as e:
            return _handle_error("servicenow_get_request", e)

    def create_problem(self, inp: dict) -> str:
        permission_error, short_description = self._check(self.agent_id, self.PROVIDER_ID, "servicenow_create_problem", inp, "short_description")
        if permission_error: return permission_error
        try:
            body: dict = {"short_description": short_description}
            if inp.get("description"):
                body["description"] = inp["description"]
            if inp.get("assignment_group"):
                body["assignment_group"] = inp["assignment_group"]
            resp = httpx.post(
                f"{self._base}/table/problem",
                headers=self._auth_headers,
                auth=self._auth,
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            r = resp.json().get("result", {})
            return json.dumps({
                "sys_id": r.get("sys_id"),
                "number": r.get("number"),
                "short_description": r.get("short_description"),
                "state": r.get("state"),
                "status": "created",
            })
        except Exception as e:
            return _handle_error("servicenow_create_problem", e)

    def list_users(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "servicenow_list_users", inp)
        if permission_error: return permission_error
        try:
            params = {
                "sysparm_limit": inp.get("limit", 20),
                "sysparm_fields": "sys_id,name,email,title,department",
            }
            if inp.get("query"):
                q = inp["query"]
                params["sysparm_query"] = f"nameLIKE{q}^ORemailLIKE{q}"
            resp = httpx.get(
                f"{self._base}/table/sys_user",
                headers=self._auth_headers,
                auth=self._auth,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            records = resp.json().get("result", [])
            users = [
                {
                    "sys_id": r.get("sys_id"),
                    "name": r.get("name"),
                    "email": r.get("email"),
                    "title": r.get("title"),
                    "department": r.get("department", {}).get("display_value") if isinstance(r.get("department"), dict) else r.get("department"),
                }
                for r in records
            ]
            return json.dumps({"users": users, "count": len(users)})
        except Exception as e:
            return _handle_error("servicenow_list_users", e)

    def list_change_requests(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "servicenow_list_change_requests", inp)
        if permission_error: return permission_error
        try:
            params = {
                "sysparm_limit": inp.get("limit", 20),
                "sysparm_fields": "number,short_description,state,priority,type,requested_by,start_date,end_date",
                "sysparm_query": inp.get("query", "ORDERBYDESCsys_created_on"),
            }
            resp = httpx.get(
                f"{self._base}/table/change_request",
                headers=self._auth_headers,
                auth=self._auth,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            records = resp.json().get("result", [])
            changes = [
                {
                    "number": r.get("number"),
                    "short_description": r.get("short_description"),
                    "state": r.get("state"),
                    "priority": r.get("priority"),
                    "type": r.get("type"),
                    "requested_by": r.get("requested_by", {}).get("display_value") if isinstance(r.get("requested_by"), dict) else r.get("requested_by"),
                    "start_date": r.get("start_date"),
                    "end_date": r.get("end_date"),
                }
                for r in records
            ]
            return json.dumps({"change_requests": changes, "count": len(changes)})
        except Exception as e:
            return _handle_error("servicenow_list_change_requests", e)

    def create_change_request(self, inp: dict) -> str:
        permission_error, short_description = self._check(self.agent_id, self.PROVIDER_ID, "servicenow_create_change_request", inp, "short_description")
        if permission_error: return permission_error
        try:
            body: dict = {"short_description": short_description}
            if inp.get("description"):
                body["description"] = inp["description"]
            if inp.get("type"):
                body["type"] = inp["type"]
            if inp.get("assignment_group"):
                body["assignment_group"] = inp["assignment_group"]
            if inp.get("start_date"):
                body["start_date"] = inp["start_date"]
            if inp.get("end_date"):
                body["end_date"] = inp["end_date"]
            resp = httpx.post(
                f"{self._base}/table/change_request",
                headers=self._auth_headers,
                auth=self._auth,
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            r = resp.json().get("result", {})
            return json.dumps({
                "sys_id": r.get("sys_id"),
                "number": r.get("number"),
                "short_description": r.get("short_description"),
                "state": r.get("state"),
                "status": "created",
            })
        except Exception as e:
            return _handle_error("servicenow_create_change_request", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "servicenow_list_incidents",
                    "description": "List ServiceNow incidents with optional filtering.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "ServiceNow encoded query (default: active incidents ordered by opened_at desc)."},
                            "limit": {"type": "integer", "description": "Max incidents to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "servicenow_get_incident",
                    "description": "Get full details of a specific ServiceNow incident.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "number": {"type": "string", "description": "Incident number (e.g. 'INC0010001')."},
                        },
                        "required": ["number"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "servicenow_create_incident",
                    "description": "Create a new ServiceNow incident.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "short_description": {"type": "string", "description": "Brief incident summary."},
                            "description": {"type": "string", "description": "Detailed incident description."},
                            "urgency": {"type": "string", "description": "Urgency: 1 (High), 2 (Medium), 3 (Low). Default 3."},
                            "impact": {"type": "string", "description": "Impact: 1 (High), 2 (Medium), 3 (Low). Default 3."},
                            "category": {"type": "string", "description": "Incident category (e.g. 'network', 'software', 'hardware')."},
                            "caller_id": {"type": "string", "description": "Username of the caller/reporter."},
                            "assigned_to": {"type": "string", "description": "Username to assign the incident to."},
                        },
                        "required": ["short_description"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "servicenow_update_incident",
                    "description": "Update an existing ServiceNow incident.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "number": {"type": "string", "description": "Incident number (e.g. 'INC0010001')."},
                            "state": {"type": "string", "description": "New state: 1=New, 2=In Progress, 3=On Hold, 6=Resolved, 7=Closed."},
                            "assigned_to": {"type": "string", "description": "Username to reassign to."},
                            "work_notes": {"type": "string", "description": "Internal work notes to add."},
                            "close_notes": {"type": "string", "description": "Resolution notes (required when resolving)."},
                            "priority": {"type": "string", "description": "New priority: 1=Critical, 2=High, 3=Moderate, 4=Low."},
                        },
                        "required": ["number"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "servicenow_list_requests",
                    "description": "List ServiceNow service requests.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "ServiceNow encoded query filter."},
                            "limit": {"type": "integer", "description": "Max requests to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "servicenow_search_knowledge",
                    "description": "Search ServiceNow knowledge base articles.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search term to find relevant knowledge articles."},
                            "limit": {"type": "integer", "description": "Max articles to return (default 10)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "servicenow_get_request",
                    "description": "Get full details of a specific ServiceNow service request by sys_id.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sys_id": {"type": "string", "description": "The sys_id of the service request record."},
                        },
                        "required": ["sys_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "servicenow_create_problem",
                    "description": "Create a new Problem record in ServiceNow.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "short_description": {"type": "string", "description": "Brief description of the problem."},
                            "description": {"type": "string", "description": "Detailed problem description."},
                            "assignment_group": {"type": "string", "description": "Group to assign the problem to."},
                        },
                        "required": ["short_description"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "servicenow_list_users",
                    "description": "List ServiceNow users, optionally filtered by name or email.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Optional name or email filter."},
                            "limit": {"type": "integer", "description": "Max users to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "servicenow_list_change_requests",
                    "description": "List ServiceNow change requests.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "ServiceNow encoded query filter (default: ordered by creation date desc)."},
                            "limit": {"type": "integer", "description": "Max change requests to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "servicenow_create_change_request",
                    "description": "Create a new change request in ServiceNow.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "short_description": {"type": "string", "description": "Brief description of the change."},
                            "description": {"type": "string", "description": "Detailed change description."},
                            "type": {"type": "string", "description": "Change type: standard, normal, or emergency."},
                            "assignment_group": {"type": "string", "description": "Group to assign the change to."},
                            "start_date": {"type": "string", "description": "Planned start date/time (YYYY-MM-DD HH:MM:SS)."},
                            "end_date": {"type": "string", "description": "Planned end date/time (YYYY-MM-DD HH:MM:SS)."},
                        },
                        "required": ["short_description"],
                    },
                },
            },
        ]
        callables = {
            "servicenow_list_incidents": self.list_incidents,
            "servicenow_get_incident": self.get_incident,
            "servicenow_create_incident": self.create_incident,
            "servicenow_update_incident": self.update_incident,
            "servicenow_list_requests": self.list_requests,
            "servicenow_search_knowledge": self.search_knowledge,
            "servicenow_get_request": self.get_request,
            "servicenow_create_problem": self.create_problem,
            "servicenow_list_users": self.list_users,
            "servicenow_list_change_requests": self.list_change_requests,
            "servicenow_create_change_request": self.create_change_request,
        }
        return tools, callables

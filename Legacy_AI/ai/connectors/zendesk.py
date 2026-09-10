import json
import httpx

from ai.connectors.base import BaseConnector


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Zendesk account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Zendesk connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class ZendeskConnector(BaseConnector):

    PROVIDER_ID = "zendesk"

    def __init__(self, access_token: str, subdomain: str = "", agent_id: str = None) -> None:
        super().__init__(access_token, agent_id=agent_id)
        self._token = access_token
        self._subdomain = subdomain
        self._base = f"https://{subdomain}.zendesk.com/api/v2" if subdomain else "https://api.zendesk.com/api/v2"

    def list_tickets(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_list_tickets", inp)
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("per_page", 20)}
            if inp.get("status"):
                params["status"] = inp["status"]
            resp = httpx.get(f"{self._base}/tickets", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            tickets = [
                {
                    "id": t["id"],
                    "subject": t.get("subject", ""),
                    "status": t.get("status"),
                    "priority": t.get("priority"),
                    "requester_id": t.get("requester_id"),
                    "assignee_id": t.get("assignee_id"),
                    "created_at": t.get("created_at"),
                    "updated_at": t.get("updated_at"),
                }
                for t in data.get("tickets", [])
            ]
            return json.dumps({"tickets": tickets, "count": data.get("count")})
        except Exception as e:
            return _handle_error("zendesk_list_tickets", e)

    def get_ticket(self, inp: dict) -> str:
        permission_error, ticket_id = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_get_ticket", inp, "ticket_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/tickets/{ticket_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            t = resp.json().get("ticket", {})
            return json.dumps({
                "id": t["id"],
                "subject": t.get("subject"),
                "description": t.get("description"),
                "status": t.get("status"),
                "priority": t.get("priority"),
                "created_at": t.get("created_at"),
                "updated_at": t.get("updated_at"),
            })
        except Exception as e:
            return _handle_error("zendesk_get_ticket", e)

    def search_tickets(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_search_tickets", inp, "query")
        if permission_error: return permission_error
        try:
            params = {"query": f"type:ticket {query}", "per_page": inp.get("per_page", 10)}
            resp = httpx.get(f"{self._base}/search", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            tickets = [{"id": t["id"], "subject": t.get("subject"), "status": t.get("status"), "priority": t.get("priority")} for t in data.get("results", [])]
            return json.dumps(tickets)
        except Exception as e:
            return _handle_error("zendesk_search_tickets", e)

    def create_ticket(self, inp: dict) -> str:
        permission_error, subject, body = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_create_ticket", inp, "subject", "body")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            payload = {"ticket": {"subject": subject, "comment": {"body": body}}}
            if inp.get("priority"):
                payload["ticket"]["priority"] = inp["priority"]
            if inp.get("requester_email"):
                payload["ticket"]["requester"] = {"email": inp["requester_email"]}
            resp = httpx.post(f"{self._base}/tickets", headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            t = resp.json().get("ticket", {})
            return json.dumps({"id": t["id"], "subject": t.get("subject"), "status": t.get("status")})
        except Exception as e:
            return _handle_error("zendesk_create_ticket", e)

    def update_ticket(self, inp: dict) -> str:
        permission_error, ticket_id = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_update_ticket", inp, "ticket_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            update: dict = {}
            if inp.get("status"):
                update["status"] = inp["status"]
            if inp.get("priority"):
                update["priority"] = inp["priority"]
            if inp.get("comment"):
                update["comment"] = {"body": inp["comment"]}
            resp = httpx.put(f"{self._base}/tickets/{ticket_id}", headers=headers, json={"ticket": update}, timeout=15)
            resp.raise_for_status()
            t = resp.json().get("ticket", {})
            return json.dumps({"id": t["id"], "status": t.get("status"), "updated_at": t.get("updated_at")})
        except Exception as e:
            return _handle_error("zendesk_update_ticket", e)

    def delete_ticket(self, inp: dict) -> str:
        permission_error, ticket_id = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_delete_ticket", inp, "ticket_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{self._base}/tickets/{ticket_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"deleted": True, "id": ticket_id})
        except Exception as e:
            return _handle_error("zendesk_delete_ticket", e)

    def list_users(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_list_users", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"per_page": inp.get("limit", 25)}
            if inp.get("role"):
                params["role"] = inp["role"]
            resp = httpx.get(f"{self._base}/users", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            users = [
                {
                    "id": u["id"],
                    "name": u.get("name"),
                    "email": u.get("email"),
                    "role": u.get("role"),
                    "active": u.get("active"),
                }
                for u in data.get("users", [])
            ]
            return json.dumps(users)
        except Exception as e:
            return _handle_error("zendesk_list_users", e)

    def get_user(self, inp: dict) -> str:
        permission_error, user_id = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_get_user", inp, "user_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/users/{user_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json().get("user", {}))
        except Exception as e:
            return _handle_error("zendesk_get_user", e)

    def add_comment(self, inp: dict) -> str:
        permission_error, ticket_id, comment = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_add_comment", inp, "ticket_id", "comment")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            public = inp.get("public", True)
            payload = {"ticket": {"comment": {"body": comment, "public": public}}}
            resp = httpx.put(f"{self._base}/tickets/{ticket_id}", headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            t = resp.json().get("ticket", {})
            return json.dumps({"id": t["id"], "status": t.get("status"), "updated_at": t.get("updated_at")})
        except Exception as e:
            return _handle_error("zendesk_add_comment", e)

    def list_macros(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_list_macros", inp)
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("per_page", 25)}
            if inp.get("active") is not None:
                params["active"] = str(inp["active"]).lower()
            resp = httpx.get(f"{self._base}/macros", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            macros = [{"id": m["id"], "title": m.get("title"), "active": m.get("active")} for m in data.get("macros", [])]
            return json.dumps({"macros": macros, "count": len(macros)})
        except Exception as e:
            return _handle_error("zendesk_list_macros", e)

    def apply_macro(self, inp: dict) -> str:
        permission_error, ticket_id, macro_id = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_apply_macro", inp, "ticket_id", "macro_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/tickets/{ticket_id}/macros/{macro_id}/apply", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            ticket_changes = resp.json().get("result", {}).get("ticket", {})
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            update_resp = httpx.put(f"{self._base}/tickets/{ticket_id}", headers=headers, json={"ticket": ticket_changes}, timeout=15)
            update_resp.raise_for_status()
            t = update_resp.json().get("ticket", {})
            return json.dumps({"id": t.get("id"), "status": t.get("status"), "updated_at": t.get("updated_at")})
        except Exception as e:
            return _handle_error("zendesk_apply_macro", e)

    def merge_tickets(self, inp: dict) -> str:
        permission_error, ticket_id, source_ticket_ids = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_merge_tickets", inp, "ticket_id", "source_ticket_ids")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"ids": source_ticket_ids}
            if inp.get("target_comment"):
                body["target_comment"] = inp["target_comment"]
            resp = httpx.post(f"{self._base}/tickets/{ticket_id}/merge", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            job = resp.json().get("job_status", {})
            return json.dumps({"job_id": job.get("id"), "status": job.get("status"), "message": job.get("message")})
        except Exception as e:
            return _handle_error("zendesk_merge_tickets", e)

    def add_tags(self, inp: dict) -> str:
        permission_error, ticket_id, tags = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_add_tags", inp, "ticket_id", "tags")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.put(f"{self._base}/tickets/{ticket_id}/tags", headers=headers, json={"tags": tags}, timeout=15)
            resp.raise_for_status()
            return json.dumps({"ticket_id": ticket_id, "tags": resp.json().get("tags", tags)})
        except Exception as e:
            return _handle_error("zendesk_add_tags", e)

    def list_ticket_comments(self, inp: dict) -> str:
        permission_error, ticket_id = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_list_ticket_comments", inp, "ticket_id")
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("per_page", 25)}
            resp = httpx.get(f"{self._base}/tickets/{ticket_id}/comments", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            comments = [
                {
                    "id": c["id"],
                    "author_id": c.get("author_id"),
                    "body": c.get("body"),
                    "public": c.get("public"),
                    "created_at": c.get("created_at"),
                }
                for c in resp.json().get("comments", [])
            ]
            return json.dumps({"comments": comments, "count": len(comments)})
        except Exception as e:
            return _handle_error("zendesk_list_ticket_comments", e)

    def list_satisfaction_ratings(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_list_satisfaction_ratings", inp)
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("per_page", 25)}
            if inp.get("score"):
                params["score"] = inp["score"]
            resp = httpx.get(f"{self._base}/satisfaction_ratings", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            ratings = [
                {
                    "id": r["id"],
                    "score": r.get("score"),
                    "ticket_id": r.get("ticket_id"),
                    "comment": r.get("comment"),
                    "created_at": r.get("created_at"),
                }
                for r in data.get("satisfaction_ratings", [])
            ]
            return json.dumps({"satisfaction_ratings": ratings, "count": len(ratings)})
        except Exception as e:
            return _handle_error("zendesk_list_satisfaction_ratings", e)

    def list_organizations(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zendesk_list_organizations", inp)
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("limit", 25)}
            resp = httpx.get(f"{self._base}/organizations", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            orgs = [
                {
                    "id": o["id"],
                    "name": o.get("name"),
                    "notes": o.get("notes"),
                    "domain_names": o.get("domain_names"),
                }
                for o in data.get("organizations", [])
            ]
            return json.dumps(orgs)
        except Exception as e:
            return _handle_error("zendesk_list_organizations", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "zendesk_list_tickets",
                    "description": "List support tickets in Zendesk.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "per_page": {"type": "integer", "description": "Max tickets to return (default 20)."},
                            "status": {"type": "string", "description": "Filter by status: new, open, pending, solved, closed."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zendesk_get_ticket",
                    "description": "Get details of a specific Zendesk ticket.",
                    "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string", "description": "The ticket ID."}}, "required": ["ticket_id"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zendesk_search_tickets",
                    "description": "Search Zendesk tickets by keyword.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query (e.g. 'login error status:open')."},
                            "per_page": {"type": "integer", "description": "Max results (default 10)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zendesk_create_ticket",
                    "description": "Create a new support ticket in Zendesk.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string", "description": "Ticket subject."},
                            "body": {"type": "string", "description": "Ticket description/body."},
                            "priority": {"type": "string", "description": "Priority: low, normal, high, urgent."},
                            "requester_email": {"type": "string", "description": "Email of the requester."},
                        },
                        "required": ["subject", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zendesk_update_ticket",
                    "description": "Update the status, priority, or add a comment to a Zendesk ticket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string", "description": "The ticket ID to update."},
                            "status": {"type": "string", "description": "New status: open, pending, solved, closed."},
                            "priority": {"type": "string", "description": "New priority: low, normal, high, urgent."},
                            "comment": {"type": "string", "description": "Comment to add to the ticket."},
                        },
                        "required": ["ticket_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zendesk_delete_ticket",
                    "description": "Permanently delete a Zendesk ticket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string", "description": "The ticket ID to delete."},
                        },
                        "required": ["ticket_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zendesk_list_users",
                    "description": "List users in Zendesk, optionally filtered by role.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string", "description": "Filter by role: end-user, agent, or admin."},
                            "limit": {"type": "integer", "description": "Max users to return (default 25)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zendesk_get_user",
                    "description": "Get details of a specific Zendesk user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "The user ID."},
                        },
                        "required": ["user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zendesk_add_comment",
                    "description": "Add a public or private comment to an existing Zendesk ticket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string", "description": "The ticket ID to comment on."},
                            "comment": {"type": "string", "description": "Comment text to add."},
                            "public": {"type": "boolean", "description": "Whether the comment is public (visible to requester). Default true."},
                        },
                        "required": ["ticket_id", "comment"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zendesk_list_organizations",
                    "description": "List organizations in Zendesk.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max organizations to return (default 25)."},
                        },
                        "required": [],
                    },
                },
            },
        ]
        callables = {
            "zendesk_list_tickets": self.list_tickets,
            "zendesk_get_ticket": self.get_ticket,
            "zendesk_search_tickets": self.search_tickets,
            "zendesk_create_ticket": self.create_ticket,
            "zendesk_update_ticket": self.update_ticket,
            "zendesk_delete_ticket": self.delete_ticket,
            "zendesk_list_users": self.list_users,
            "zendesk_get_user": self.get_user,
            "zendesk_add_comment": self.add_comment,
            "zendesk_list_organizations": self.list_organizations,
        }
        return tools, callables

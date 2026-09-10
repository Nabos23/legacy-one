import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.intercom.io"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Intercom account lacks permission "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their Intercom connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class IntercomConnector(BaseConnector):

    PROVIDER_ID = "intercom"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id=agent_id)
        self._token = access_token

    @property
    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Accept": "application/json", "Intercom-Version": "2.10"}

    @_auth_headers.setter
    def _auth_headers(self, value: dict) -> None:
        pass

    def list_conversations(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "intercom_list_conversations", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"per_page": inp.get("limit", 20), "order": "desc", "sort": "updated_at"}
            if inp.get("state"):
                params["state"] = inp["state"]
            resp = httpx.get(f"{_BASE}/conversations", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            conversations = [
                {
                    "id": c["id"],
                    "state": c.get("state"),
                    "read": c.get("read"),
                    "subject": c.get("source", {}).get("subject", ""),
                    "assignee": (c.get("assignee") or {}).get("name"),
                    "contact_name": (c.get("source", {}).get("author") or {}).get("name"),
                    "created_at": c.get("created_at"),
                    "updated_at": c.get("updated_at"),
                }
                for c in data.get("conversations", [])
            ]
            return json.dumps({"conversations": conversations, "total": data.get("total_count"), "count": len(conversations)})
        except Exception as e:
            return _handle_error("intercom_list_conversations", e)

    def get_conversation(self, inp: dict) -> str:
        permission_error, conversation_id = self._check(self.agent_id, self.PROVIDER_ID, "intercom_get_conversation", inp, "conversation_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/conversations/{conversation_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            c = resp.json()
            parts = c.get("conversation_parts", {}).get("conversation_parts", [])
            messages = [
                {"author": p.get("author", {}).get("name"), "body": p.get("body", ""), "created_at": p.get("created_at")}
                for p in parts
                if p.get("body")
            ]
            return json.dumps({
                "id": c["id"],
                "state": c.get("state"),
                "subject": c.get("source", {}).get("subject"),
                "contact": (c.get("source", {}).get("author") or {}).get("name"),
                "assignee": (c.get("assignee") or {}).get("name"),
                "messages": messages[-10:],
            })
        except Exception as e:
            return _handle_error("intercom_get_conversation", e)

    def reply_to_conversation(self, inp: dict) -> str:
        permission_error, conversation_id, body = self._check(self.agent_id, self.PROVIDER_ID, "intercom_reply_to_conversation", inp, "conversation_id", "body")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            payload = {"message_type": "comment", "type": "admin", "body": body}
            if inp.get("admin_id"):
                payload["admin_id"] = inp["admin_id"]
            resp = httpx.post(f"{_BASE}/conversations/{conversation_id}/reply", headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            return json.dumps({"conversation_id": conversation_id, "status": "reply_sent"})
        except Exception as e:
            return _handle_error("intercom_reply_to_conversation", e)

    def search_contacts(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "intercom_search_contacts", inp, "query")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "query": {
                    "operator": "OR",
                    "value": [
                        {"field": "email", "operator": "~", "value": query},
                        {"field": "name", "operator": "~", "value": query},
                    ],
                },
                "pagination": {"per_page": inp.get("limit", 10)},
            }
            resp = httpx.post(f"{_BASE}/contacts/search", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            contacts = [
                {
                    "id": c["id"],
                    "name": c.get("name"),
                    "email": c.get("email"),
                    "role": c.get("role"),
                    "created_at": c.get("created_at"),
                }
                for c in data.get("data", [])
            ]
            return json.dumps({"contacts": contacts, "total": data.get("total_count")})
        except Exception as e:
            return _handle_error("intercom_search_contacts", e)

    def get_contact(self, inp: dict) -> str:
        permission_error, contact_id = self._check(self.agent_id, self.PROVIDER_ID, "intercom_get_contact", inp, "contact_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/contacts/{contact_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            c = resp.json()
            return json.dumps({
                "id": c["id"],
                "name": c.get("name"),
                "email": c.get("email"),
                "phone": c.get("phone"),
                "role": c.get("role"),
                "created_at": c.get("created_at"),
                "last_seen_at": c.get("last_seen_at"),
                "custom_attributes": c.get("custom_attributes", {}),
            })
        except Exception as e:
            return _handle_error("intercom_get_contact", e)

    def create_note(self, inp: dict) -> str:
        permission_error, contact_id, body = self._check(self.agent_id, self.PROVIDER_ID, "intercom_create_note", inp, "contact_id", "body")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            payload = {"body": body, "contact_id": contact_id, "admin_id": inp.get("admin_id", "")}
            resp = httpx.post(f"{_BASE}/notes", headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "body": data.get("body"), "status": "note_created"})
        except Exception as e:
            return _handle_error("intercom_create_note", e)

    def create_contact(self, inp: dict) -> str:
        permission_error, email = self._check(self.agent_id, self.PROVIDER_ID, "intercom_create_contact", inp, "email")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            payload: dict = {"email": email, "role": inp.get("role", "user")}
            if inp.get("name"):
                payload["name"] = inp["name"]
            if inp.get("phone"):
                payload["phone"] = inp["phone"]
            resp = httpx.post(f"{_BASE}/contacts", headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            c = resp.json()
            return json.dumps({"id": c.get("id"), "email": c.get("email"), "name": c.get("name"), "role": c.get("role")})
        except Exception as e:
            return _handle_error("intercom_create_contact", e)

    def close_conversation(self, inp: dict) -> str:
        permission_error, conversation_id, admin_id = self._check(self.agent_id, self.PROVIDER_ID, "intercom_close_conversation", inp, "conversation_id", "admin_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            payload = {"message_type": "close", "type": "admin", "admin_id": admin_id}
            resp = httpx.put(f"{_BASE}/conversations/{conversation_id}/parts", headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            return json.dumps({"conversation_id": conversation_id, "status": "closed"})
        except Exception as e:
            return _handle_error("intercom_close_conversation", e)

    def assign_conversation(self, inp: dict) -> str:
        permission_error, conversation_id, admin_id, assignee_id = self._check(self.agent_id, self.PROVIDER_ID, "intercom_assign_conversation", inp, "conversation_id", "admin_id", "assignee_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            payload = {
                "message_type": "assignment",
                "type": "admin",
                "admin_id": admin_id,
                "assignee_id": assignee_id,
            }
            resp = httpx.put(f"{_BASE}/conversations/{conversation_id}/parts", headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            return json.dumps({"conversation_id": conversation_id, "assignee_id": assignee_id, "status": "assigned"})
        except Exception as e:
            return _handle_error("intercom_assign_conversation", e)

    def list_admins(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "intercom_list_admins", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/admins", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            admins = [
                {
                    "id": a.get("id"),
                    "name": a.get("name"),
                    "email": a.get("email"),
                    "job_title": a.get("job_title"),
                }
                for a in data.get("admins", [])
            ]
            return json.dumps(admins)
        except Exception as e:
            return _handle_error("intercom_list_admins", e)

    def update_contact(self, inp: dict) -> str:
        permission_error, contact_id = self._check(self.agent_id, self.PROVIDER_ID, "intercom_update_contact", inp, "contact_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            payload: dict = {}
            if inp.get("name"):
                payload["name"] = inp["name"]
            if inp.get("email"):
                payload["email"] = inp["email"]
            if inp.get("phone"):
                payload["phone"] = inp["phone"]
            if not payload:
                return "Error: at least one of 'name', 'email', or 'phone' must be provided."
            resp = httpx.put(f"{_BASE}/contacts/{contact_id}", headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            c = resp.json()
            return json.dumps({"id": c.get("id"), "name": c.get("name"), "email": c.get("email"), "phone": c.get("phone")})
        except Exception as e:
            return _handle_error("intercom_update_contact", e)

    def list_companies(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "intercom_list_companies", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"per_page": inp.get("limit", 20)}
            resp = httpx.get(f"{_BASE}/companies", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            companies = [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "company_id": c.get("company_id"),
                    "user_count": c.get("user_count"),
                    "created_at": c.get("created_at"),
                }
                for c in data.get("data", [])
            ]
            return json.dumps({"companies": companies, "count": len(companies)})
        except Exception as e:
            return _handle_error("intercom_list_companies", e)

    def list_tags(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "intercom_list_tags", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/tags", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            tags = [{"id": t.get("id"), "name": t.get("name")} for t in data.get("data", [])]
            return json.dumps({"tags": tags, "count": len(tags)})
        except Exception as e:
            return _handle_error("intercom_list_tags", e)

    def tag_contact(self, inp: dict) -> str:
        permission_error, contact_id, tag_id = self._check(self.agent_id, self.PROVIDER_ID, "intercom_tag_contact", inp, "contact_id", "tag_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(f"{_BASE}/contacts/{contact_id}/tags", headers=headers, json={"id": tag_id}, timeout=15)
            resp.raise_for_status()
            t = resp.json()
            return json.dumps({"contact_id": contact_id, "tag_id": t.get("id"), "tag_name": t.get("name"), "status": "tagged"})
        except Exception as e:
            return _handle_error("intercom_tag_contact", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "intercom_list_conversations",
                    "description": "List Intercom conversations (support chats/tickets).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "state": {"type": "string", "description": "Filter by state: open, closed, snoozed."},
                            "limit": {"type": "integer", "description": "Max conversations to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "intercom_get_conversation",
                    "description": "Get full details and message history of an Intercom conversation.",
                    "parameters": {
                        "type": "object",
                        "properties": {"conversation_id": {"type": "string", "description": "Intercom conversation ID."}},
                        "required": ["conversation_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "intercom_reply_to_conversation",
                    "description": "Send a reply to an Intercom conversation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "conversation_id": {"type": "string", "description": "Conversation ID to reply to."},
                            "body": {"type": "string", "description": "Reply message body."},
                            "admin_id": {"type": "string", "description": "Optional admin ID to reply as."},
                        },
                        "required": ["conversation_id", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "intercom_search_contacts",
                    "description": "Search Intercom contacts by name or email.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Name or email search query."},
                            "limit": {"type": "integer", "description": "Max results (default 10)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "intercom_get_contact",
                    "description": "Get details of a specific Intercom contact.",
                    "parameters": {
                        "type": "object",
                        "properties": {"contact_id": {"type": "string", "description": "Intercom contact ID."}},
                        "required": ["contact_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "intercom_create_note",
                    "description": "Create an internal note on an Intercom contact.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "contact_id": {"type": "string", "description": "Contact ID to add the note to."},
                            "body": {"type": "string", "description": "Note content."},
                            "admin_id": {"type": "string", "description": "Optional admin ID creating the note."},
                        },
                        "required": ["contact_id", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "intercom_create_contact",
                    "description": "Create a new contact (user or lead) in Intercom.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string", "description": "Contact email address."},
                            "name": {"type": "string", "description": "Contact full name (optional)."},
                            "phone": {"type": "string", "description": "Contact phone number (optional)."},
                            "role": {"type": "string", "description": "Contact role: user or lead (default user)."},
                        },
                        "required": ["email"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "intercom_close_conversation",
                    "description": "Close an open Intercom conversation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "conversation_id": {"type": "string", "description": "The conversation ID to close."},
                            "admin_id": {"type": "string", "description": "The admin ID performing the close action."},
                        },
                        "required": ["conversation_id", "admin_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "intercom_assign_conversation",
                    "description": "Assign an Intercom conversation to a specific admin or team.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "conversation_id": {"type": "string", "description": "The conversation ID to assign."},
                            "admin_id": {"type": "string", "description": "The admin ID performing the assignment."},
                            "assignee_id": {"type": "string", "description": "The admin or team ID to assign the conversation to."},
                        },
                        "required": ["conversation_id", "admin_id", "assignee_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "intercom_list_admins",
                    "description": "List all admins in the Intercom workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "intercom_update_contact",
                    "description": "Update an existing Intercom contact's name, email, or phone.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "contact_id": {"type": "string", "description": "The contact ID to update."},
                            "name": {"type": "string", "description": "New name for the contact (optional)."},
                            "email": {"type": "string", "description": "New email for the contact (optional)."},
                            "phone": {"type": "string", "description": "New phone number for the contact (optional)."},
                        },
                        "required": ["contact_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "intercom_list_companies",
                    "description": "List companies in the Intercom workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "description": "Max companies to return (default 20)."}},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "intercom_list_tags",
                    "description": "List all tags defined in the Intercom workspace.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "intercom_tag_contact",
                    "description": "Attach an existing tag to an Intercom contact.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "contact_id": {"type": "string", "description": "Contact ID to tag."},
                            "tag_id": {"type": "string", "description": "Tag ID to attach (use intercom_list_tags to find IDs)."},
                        },
                        "required": ["contact_id", "tag_id"],
                    },
                },
            },
        ]
        callables = {
            "intercom_list_conversations": self.list_conversations,
            "intercom_get_conversation": self.get_conversation,
            "intercom_reply_to_conversation": self.reply_to_conversation,
            "intercom_search_contacts": self.search_contacts,
            "intercom_get_contact": self.get_contact,
            "intercom_create_note": self.create_note,
            "intercom_create_contact": self.create_contact,
            "intercom_close_conversation": self.close_conversation,
            "intercom_assign_conversation": self.assign_conversation,
            "intercom_list_admins": self.list_admins,
            "intercom_update_contact": self.update_contact,
            "intercom_list_companies": self.list_companies,
            "intercom_list_tags": self.list_tags,
            "intercom_tag_contact": self.tag_contact,
        }
        return tools, callables

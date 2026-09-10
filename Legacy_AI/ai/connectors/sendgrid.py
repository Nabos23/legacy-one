import json
import httpx
from ai.connectors.base import BaseConnector

_BASE = "https://api.sendgrid.com/v3"


def _handle_error(tool_name, e):
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class SendgridConnector(BaseConnector):
    """SendGrid connector for marketing contacts, campaigns, templates, stats, and suppression."""

    PROVIDER_ID = "sendgrid"

    def sendgrid_list_contacts(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_list_contacts", inp)
        if permission_error: return permission_error
        try:
            with httpx.Client() as client:
                r = client.get(f"{_BASE}/marketing/contacts", headers=self._auth_headers)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_list_contacts", e)

    def sendgrid_list_marketing_lists(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_list_marketing_lists", inp)
        if permission_error: return permission_error
        try:
            params = {}
            if inp.get("page_size"):
                params["page_size"] = inp["page_size"]
            with httpx.Client() as client:
                r = client.get(f"{_BASE}/marketing/lists", headers=self._auth_headers, params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_list_marketing_lists", e)

    def sendgrid_list_templates(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_list_templates", inp)
        if permission_error: return permission_error
        try:
            params = {"generations": inp.get("generations", "dynamic")}
            with httpx.Client() as client:
                r = client.get(f"{_BASE}/templates", headers=self._auth_headers, params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_list_templates", e)

    def sendgrid_get_stats(self, inp: dict) -> str:
        permission_error, start_date = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_get_stats", inp, "start_date")
        if permission_error: return permission_error
        try:
            params = {"start_date": start_date}
            if inp.get("end_date"):
                params["end_date"] = inp["end_date"]
            if inp.get("aggregated_by"):
                params["aggregated_by"] = inp["aggregated_by"]
            with httpx.Client() as client:
                r = client.get(f"{_BASE}/stats", headers=self._auth_headers, params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_get_stats", e)

    def sendgrid_list_bounces(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_list_bounces", inp)
        if permission_error: return permission_error
        try:
            params = {}
            if inp.get("start_time"):
                params["start_time"] = inp["start_time"]
            if inp.get("end_time"):
                params["end_time"] = inp["end_time"]
            if inp.get("limit"):
                params["limit"] = inp["limit"]
            with httpx.Client() as client:
                r = client.get(f"{_BASE}/suppression/bounces", headers=self._auth_headers, params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_list_bounces", e)

    def sendgrid_list_campaigns(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_list_campaigns", inp)
        if permission_error: return permission_error
        try:
            params = {}
            if inp.get("page_size"):
                params["page_size"] = inp["page_size"]
            with httpx.Client() as client:
                r = client.get(f"{_BASE}/marketing/campaigns", headers=self._auth_headers, params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_list_campaigns", e)

    def sendgrid_get_messages(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_get_messages", inp)
        if permission_error: return permission_error
        try:
            params = {}
            if inp.get("limit"):
                params["limit"] = inp["limit"]
            if inp.get("query"):
                params["query"] = inp["query"]
            with httpx.Client() as client:
                r = client.get(f"{_BASE}/messages", headers=self._auth_headers, params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_get_messages", e)

    def sendgrid_send_email(self, inp: dict) -> str:
        permission_error, raw_to, from_email, subject = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_send_email", inp, "to", "from_email", "subject")
        if permission_error: return permission_error
        try:
            if isinstance(raw_to, str):
                to_list = [{"email": raw_to}]
            elif isinstance(raw_to, dict):
                to_list = [raw_to]
            else:
                to_list = [
                    {"email": r} if isinstance(r, str) else r
                    for r in raw_to
                ]

            from_obj = {"email": from_email}
            if inp.get("from_name"):
                from_obj["name"] = inp["from_name"]

            body: dict = {
                "personalizations": [{"to": to_list}],
                "from": from_obj,
                "subject": subject,
            }

            template_id = inp.get("template_id")
            if template_id:
                body["template_id"] = template_id
                if inp.get("template_data"):
                    body["personalizations"][0]["dynamic_template_data"] = inp["template_data"]
            else:
                content_type = inp.get("content_type", "text/plain")
                body["content"] = [{"type": content_type, "value": inp.get("content", "")}]

            headers = {**self._auth_headers, "Content-Type": "application/json"}
            with httpx.Client() as client:
                r = client.post(f"{_BASE}/mail/send", headers=headers, json=body)
                r.raise_for_status()
                return json.dumps({"status": "accepted", "http_status": r.status_code})
        except Exception as e:
            return _handle_error("sendgrid_send_email", e)

    def sendgrid_add_contact(self, inp: dict) -> str:
        permission_error, email = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_add_contact", inp, "email")
        if permission_error: return permission_error
        try:
            contact: dict = {"email": email}
            if inp.get("first_name"):
                contact["first_name"] = inp["first_name"]
            if inp.get("last_name"):
                contact["last_name"] = inp["last_name"]

            body: dict = {"contacts": [contact]}
            if inp.get("list_ids"):
                body["list_ids"] = inp["list_ids"]

            headers = {**self._auth_headers, "Content-Type": "application/json"}
            with httpx.Client() as client:
                r = client.put(f"{_BASE}/marketing/contacts", headers=headers, json=body)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_add_contact", e)

    def sendgrid_delete_contacts(self, inp: dict) -> str:
        permission_error, emails = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_delete_contacts", inp, "emails")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            with httpx.Client() as client:
                search_r = client.post(
                    f"{_BASE}/marketing/contacts/search/emails",
                    headers=headers,
                    json={"emails": emails},
                )
                search_r.raise_for_status()
                result = search_r.json()

                contact_ids = [
                    v["contact"]["id"]
                    for v in result.get("result", {}).values()
                    if v.get("contact", {}).get("id")
                ]

                if not contact_ids:
                    return json.dumps({"status": "no matching contacts found"})

                delete_r = client.delete(
                    f"{_BASE}/marketing/contacts",
                    headers=self._auth_headers,
                    params={"ids": ",".join(contact_ids)},
                )
                delete_r.raise_for_status()
                return json.dumps(delete_r.json())
        except Exception as e:
            return _handle_error("sendgrid_delete_contacts", e)

    def sendgrid_create_list(self, inp: dict) -> str:
        permission_error, name = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_create_list", inp, "name")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            with httpx.Client() as client:
                r = client.post(
                    f"{_BASE}/marketing/lists",
                    headers=headers,
                    json={"name": name},
                )
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_create_list", e)

    def sendgrid_list_suppressions(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_list_suppressions", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            with httpx.Client() as client:
                r = client.get(
                    f"{_BASE}/suppression/unsubscribes",
                    headers=self._auth_headers,
                    params=params,
                )
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_list_suppressions", e)

    def sendgrid_add_suppression(self, inp: dict) -> str:
        permission_error, recipient_emails = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_add_suppression", inp, "recipient_emails")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            with httpx.Client() as client:
                r = client.post(
                    f"{_BASE}/asm/suppressions/global",
                    headers=headers,
                    json={"recipient_emails": recipient_emails},
                )
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_add_suppression", e)

    def sendgrid_validate_email(self, inp: dict) -> str:
        permission_error, email = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_validate_email", inp, "email")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"email": email}
            if inp.get("source"):
                body["source"] = inp["source"]
            with httpx.Client() as client:
                r = client.post(f"{_BASE}/validations/email", headers=headers, json=body)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_validate_email", e)

    def sendgrid_search_contacts_by_email(self, inp: dict) -> str:
        permission_error, emails = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_search_contacts_by_email", inp, "emails")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            with httpx.Client() as client:
                r = client.post(
                    f"{_BASE}/marketing/contacts/search/emails",
                    headers=headers,
                    json={"emails": emails},
                )
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_search_contacts_by_email", e)

    def sendgrid_create_single_send(self, inp: dict) -> str:
        permission_error, name, subject, html_content = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_create_single_send", inp, "name", "subject", "html_content")
        if permission_error: return permission_error
        body: dict = {
            "name": name,
            "email_config": {
                "subject": subject,
                "html_content": html_content,
            },
        }
        if inp.get("list_ids"):
            body["send_to"] = {"list_ids": inp["list_ids"]}
        if inp.get("suppression_group_id"):
            body["email_config"]["suppression_group_id"] = inp["suppression_group_id"]
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            with httpx.Client() as client:
                r = client.post(f"{_BASE}/marketing/singlesends", headers=headers, json=body)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_create_single_send", e)

    def sendgrid_schedule_single_send(self, inp: dict) -> str:
        permission_error, single_send_id = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_schedule_single_send", inp, "single_send_id")
        if permission_error: return permission_error
        send_at = inp.get("send_at", "now")
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            with httpx.Client() as client:
                r = client.put(
                    f"{_BASE}/marketing/singlesends/{single_send_id}/schedule",
                    headers=headers,
                    json={"send_at": send_at},
                )
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_schedule_single_send", e)

    def sendgrid_get_single_send_stats(self, inp: dict) -> str:
        permission_error, single_send_id = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_get_single_send_stats", inp, "single_send_id")
        if permission_error: return permission_error
        try:
            with httpx.Client() as client:
                r = client.get(
                    f"{_BASE}/marketing/stats/singlesends/{single_send_id}",
                    headers=self._auth_headers,
                )
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_get_single_send_stats", e)

    def sendgrid_list_verified_senders(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "sendgrid_list_verified_senders", inp)
        if permission_error: return permission_error
        try:
            with httpx.Client() as client:
                r = client.get(f"{_BASE}/verified_senders", headers=self._auth_headers)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("sendgrid_list_verified_senders", e)

    def as_tools(self):
        tool_defs = [
            {
                "type": "function",
                "function": {
                    "name": "sendgrid_list_contacts",
                    "description": "List all marketing contacts in SendGrid.",
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
                    "name": "sendgrid_list_marketing_lists",
                    "description": "List all marketing contact lists in SendGrid.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_size": {
                                "type": "integer",
                                "description": "Number of results per page.",
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sendgrid_list_templates",
                    "description": "List email templates in SendGrid.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "generations": {
                                "type": "string",
                                "description": "Template generation type: 'legacy', 'dynamic', or 'legacy,dynamic'. Defaults to 'dynamic'.",
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sendgrid_get_stats",
                    "description": "Retrieve global email send statistics for a date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {
                                "type": "string",
                                "description": "Start date in YYYY-MM-DD format.",
                            },
                            "end_date": {
                                "type": "string",
                                "description": "End date in YYYY-MM-DD format.",
                            },
                            "aggregated_by": {
                                "type": "string",
                                "description": "Aggregate stats by 'day', 'week', or 'month'.",
                            },
                        },
                        "required": ["start_date"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sendgrid_list_bounces",
                    "description": "List bounced email addresses from SendGrid suppression list.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_time": {
                                "type": "integer",
                                "description": "Unix timestamp to filter bounces from.",
                            },
                            "end_time": {
                                "type": "integer",
                                "description": "Unix timestamp to filter bounces until.",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return.",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sendgrid_list_campaigns",
                    "description": "List all marketing campaigns in SendGrid.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_size": {
                                "type": "integer",
                                "description": "Number of results per page.",
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sendgrid_get_messages",
                    "description": "Retrieve email activity messages from SendGrid (requires paid plan).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of messages to return.",
                            },
                            "query": {
                                "type": "string",
                                "description": "SGQL query string to filter messages (e.g. 'to_email=example@example.com').",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sendgrid_send_email",
                    "description": "Send a transactional email via SendGrid. Supports plain text, HTML, and dynamic templates.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {
                                "description": "Recipient(s). A single email string, a single {email, name} object, or a list of email strings / {email, name} objects.",
                            },
                            "from_email": {
                                "type": "string",
                                "description": "Verified sender email address.",
                            },
                            "from_name": {
                                "type": "string",
                                "description": "Optional display name for the sender.",
                            },
                            "subject": {
                                "type": "string",
                                "description": "Email subject line.",
                            },
                            "content": {
                                "type": "string",
                                "description": "Email body text. Not required when template_id is set.",
                            },
                            "content_type": {
                                "type": "string",
                                "description": "MIME type of content: 'text/plain' (default) or 'text/html'.",
                            },
                            "template_id": {
                                "type": "string",
                                "description": "SendGrid dynamic template ID. When set, content is ignored.",
                            },
                            "template_data": {
                                "type": "object",
                                "description": "Key-value pairs substituted into the dynamic template.",
                            },
                        },
                        "required": ["to", "from_email", "subject"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sendgrid_add_contact",
                    "description": "Add or upsert a contact in SendGrid Marketing Contacts.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "email": {
                                "type": "string",
                                "description": "Contact email address.",
                            },
                            "first_name": {
                                "type": "string",
                                "description": "Contact first name.",
                            },
                            "last_name": {
                                "type": "string",
                                "description": "Contact last name.",
                            },
                            "list_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of marketing list IDs to add the contact to.",
                            },
                        },
                        "required": ["email"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sendgrid_delete_contacts",
                    "description": "Delete one or more marketing contacts from SendGrid by email address.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "emails": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of email addresses to delete.",
                            }
                        },
                        "required": ["emails"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sendgrid_create_list",
                    "description": "Create a new marketing contact list in SendGrid.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the new contact list.",
                            }
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sendgrid_list_suppressions",
                    "description": "List globally unsubscribed email addresses from SendGrid.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return. Defaults to 20.",
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sendgrid_add_suppression",
                    "description": "Add one or more email addresses to the global SendGrid unsubscribe suppression list.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "recipient_emails": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of email addresses to suppress.",
                            }
                        },
                        "required": ["recipient_emails"],
                    },
                },
            },
        ]

        callables = {
            "sendgrid_list_contacts": self.sendgrid_list_contacts,
            "sendgrid_list_marketing_lists": self.sendgrid_list_marketing_lists,
            "sendgrid_list_templates": self.sendgrid_list_templates,
            "sendgrid_get_stats": self.sendgrid_get_stats,
            "sendgrid_list_bounces": self.sendgrid_list_bounces,
            "sendgrid_list_campaigns": self.sendgrid_list_campaigns,
            "sendgrid_get_messages": self.sendgrid_get_messages,
            "sendgrid_send_email": self.sendgrid_send_email,
            "sendgrid_add_contact": self.sendgrid_add_contact,
            "sendgrid_delete_contacts": self.sendgrid_delete_contacts,
            "sendgrid_create_list": self.sendgrid_create_list,
            "sendgrid_list_suppressions": self.sendgrid_list_suppressions,
            "sendgrid_add_suppression": self.sendgrid_add_suppression,
        }

        return tool_defs, callables

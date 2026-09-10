import hashlib
import json
import httpx
from ai.connectors.base import BaseConnector


def _handle_error(tool_name, e):
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class MailchimpConnector(BaseConnector):
    """Mailchimp connector for managing lists, campaigns, reports, automations, and templates."""

    PROVIDER_ID = "mailchimp"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id=agent_id)
        parts = access_token.split(":")
        self._token = parts[0]
        self._dc = parts[1] if len(parts) > 1 else "us1"

    @property
    def _auth_headers(self):
        return {"Accept": "application/json"}

    @property
    def _base(self):
        return f"https://{self._dc}.api.mailchimp.com/3.0"

    def _auth(self):
        return ("anystring", self._token)

    def mailchimp_get_account_info(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_get_account_info", inp)
        if permission_error: return permission_error
        try:
            with httpx.Client() as client:
                r = client.get(f"{self._base}/", auth=self._auth(), headers=self._auth_headers)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("mailchimp_get_account_info", e)

    def mailchimp_list_audiences(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_list_audiences", inp)
        if permission_error: return permission_error
        params = {}
        if inp.get("count"):
            params["count"] = inp["count"]
        if inp.get("offset"):
            params["offset"] = inp["offset"]
        try:
            with httpx.Client() as client:
                r = client.get(f"{self._base}/lists", auth=self._auth(), headers=self._auth_headers, params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("mailchimp_list_audiences", e)

    def mailchimp_get_audience_members(self, inp: dict) -> str:
        permission_error, list_id = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_get_audience_members", inp, "list_id")
        if permission_error: return permission_error
        params = {}
        if inp.get("count"):
            params["count"] = inp["count"]
        if inp.get("offset"):
            params["offset"] = inp["offset"]
        if inp.get("status"):
            params["status"] = inp["status"]
        try:
            with httpx.Client() as client:
                r = client.get(f"{self._base}/lists/{list_id}/members", auth=self._auth(), headers=self._auth_headers, params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("mailchimp_get_audience_members", e)

    def mailchimp_list_campaigns(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_list_campaigns", inp)
        if permission_error: return permission_error
        params = {}
        if inp.get("count"):
            params["count"] = inp["count"]
        if inp.get("offset"):
            params["offset"] = inp["offset"]
        if inp.get("status"):
            params["status"] = inp["status"]
        if inp.get("type"):
            params["type"] = inp["type"]
        try:
            with httpx.Client() as client:
                r = client.get(f"{self._base}/campaigns", auth=self._auth(), headers=self._auth_headers, params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("mailchimp_list_campaigns", e)

    def mailchimp_get_campaign_reports(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_get_campaign_reports", inp)
        if permission_error: return permission_error
        params = {}
        if inp.get("count"):
            params["count"] = inp["count"]
        if inp.get("offset"):
            params["offset"] = inp["offset"]
        try:
            with httpx.Client() as client:
                r = client.get(f"{self._base}/reports", auth=self._auth(), headers=self._auth_headers, params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("mailchimp_get_campaign_reports", e)

    def mailchimp_list_automations(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_list_automations", inp)
        if permission_error: return permission_error
        params = {}
        if inp.get("count"):
            params["count"] = inp["count"]
        if inp.get("offset"):
            params["offset"] = inp["offset"]
        try:
            with httpx.Client() as client:
                r = client.get(f"{self._base}/automations", auth=self._auth(), headers=self._auth_headers, params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("mailchimp_list_automations", e)

    def mailchimp_list_templates(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_list_templates", inp)
        if permission_error: return permission_error
        params = {}
        if inp.get("count"):
            params["count"] = inp["count"]
        if inp.get("offset"):
            params["offset"] = inp["offset"]
        if inp.get("type"):
            params["type"] = inp["type"]
        try:
            with httpx.Client() as client:
                r = client.get(f"{self._base}/templates", auth=self._auth(), headers=self._auth_headers, params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("mailchimp_list_templates", e)

    def mailchimp_add_subscriber(self, inp: dict) -> str:
        permission_error, list_id, email = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_add_subscriber", inp, "list_id", "email")
        if permission_error: return permission_error
        status = inp.get("status", "subscribed")
        body: dict = {"email_address": email, "status": status}
        merge_fields = {}
        if inp.get("first_name"):
            merge_fields["FNAME"] = inp["first_name"]
        if inp.get("last_name"):
            merge_fields["LNAME"] = inp["last_name"]
        if merge_fields:
            body["merge_fields"] = merge_fields
        try:
            with httpx.Client() as client:
                r = client.post(
                    f"{self._base}/lists/{list_id}/members",
                    auth=self._auth(),
                    headers={**self._auth_headers, "Content-Type": "application/json"},
                    json=body,
                )
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("mailchimp_add_subscriber", e)

    def mailchimp_update_subscriber(self, inp: dict) -> str:
        permission_error, list_id, email = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_update_subscriber", inp, "list_id", "email")
        if permission_error: return permission_error
        subscriber_hash = hashlib.md5(email.lower().encode()).hexdigest()
        body: dict = {}
        if inp.get("status"):
            body["status"] = inp["status"]
        merge_fields = {}
        if inp.get("first_name"):
            merge_fields["FNAME"] = inp["first_name"]
        if inp.get("last_name"):
            merge_fields["LNAME"] = inp["last_name"]
        if merge_fields:
            body["merge_fields"] = merge_fields
        try:
            with httpx.Client() as client:
                r = client.patch(
                    f"{self._base}/lists/{list_id}/members/{subscriber_hash}",
                    auth=self._auth(),
                    headers={**self._auth_headers, "Content-Type": "application/json"},
                    json=body,
                )
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("mailchimp_update_subscriber", e)

    def mailchimp_remove_subscriber(self, inp: dict) -> str:
        permission_error, list_id, email = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_remove_subscriber", inp, "list_id", "email")
        if permission_error: return permission_error
        subscriber_hash = hashlib.md5(email.lower().encode()).hexdigest()
        try:
            with httpx.Client() as client:
                r = client.patch(
                    f"{self._base}/lists/{list_id}/members/{subscriber_hash}",
                    auth=self._auth(),
                    headers={**self._auth_headers, "Content-Type": "application/json"},
                    json={"status": "unsubscribed"},
                )
                r.raise_for_status()
                return json.dumps({"status": "unsubscribed", "email": email})
        except Exception as e:
            return _handle_error("mailchimp_remove_subscriber", e)

    def mailchimp_create_campaign(self, inp: dict) -> str:
        permission_error, list_id, subject, from_name, reply_to = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_create_campaign", inp, "list_id", "subject", "from_name", "reply_to")
        if permission_error: return permission_error
        campaign_type = inp.get("type", "regular")
        body = {
            "type": campaign_type,
            "recipients": {"list_id": list_id},
            "settings": {
                "subject_line": subject,
                "from_name": from_name,
                "reply_to": reply_to,
            },
        }
        try:
            with httpx.Client() as client:
                r = client.post(
                    f"{self._base}/campaigns",
                    auth=self._auth(),
                    headers={**self._auth_headers, "Content-Type": "application/json"},
                    json=body,
                )
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("mailchimp_create_campaign", e)

    def mailchimp_send_campaign(self, inp: dict) -> str:
        permission_error, campaign_id = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_send_campaign", inp, "campaign_id")
        if permission_error: return permission_error
        try:
            with httpx.Client() as client:
                r = client.post(
                    f"{self._base}/campaigns/{campaign_id}/actions/send",
                    auth=self._auth(),
                    headers=self._auth_headers,
                )
                r.raise_for_status()
                return json.dumps({"status": "sent"})
        except Exception as e:
            return _handle_error("mailchimp_send_campaign", e)

    def mailchimp_create_audience(self, inp: dict) -> str:
        permission_error, name, company, address1, city, state, zip_code, country, from_name, from_email = self._check(
            self.agent_id, self.PROVIDER_ID, "mailchimp_create_audience", inp, "name", "company", "address1", "city", "state", "zip", "country", "from_name", "from_email"
        )
        if permission_error: return permission_error
        body = {
            "name": name,
            "contact": {
                "company": company,
                "address1": address1,
                "city": city,
                "state": state,
                "zip": zip_code,
                "country": country,
            },
            "permission_reminder": inp.get("permission_reminder", "You are receiving this email because you signed up for updates."),
            "campaign_defaults": {
                "from_name": from_name,
                "from_email": from_email,
                "subject": inp.get("default_subject", "Update"),
                "language": inp.get("language", "en"),
            },
            "email_type_option": inp.get("email_type_option", False),
        }
        try:
            with httpx.Client() as client:
                r = client.post(
                    f"{self._base}/lists",
                    auth=self._auth(),
                    headers={**self._auth_headers, "Content-Type": "application/json"},
                    json=body,
                )
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("mailchimp_create_audience", e)

    def mailchimp_create_segment(self, inp: dict) -> str:
        permission_error, list_id, name = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_create_segment", inp, "list_id", "name")
        if permission_error: return permission_error
        body: dict = {"name": name}
        static_emails = inp.get("static_emails")
        conditions = inp.get("conditions")
        if static_emails:
            body["static_segment"] = static_emails
        elif conditions:
            body["options"] = {"match": inp.get("match", "all"), "conditions": conditions}
        try:
            with httpx.Client() as client:
                r = client.post(
                    f"{self._base}/lists/{list_id}/segments",
                    auth=self._auth(),
                    headers={**self._auth_headers, "Content-Type": "application/json"},
                    json=body,
                )
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("mailchimp_create_segment", e)

    def mailchimp_tag_member(self, inp: dict) -> str:
        permission_error, list_id, email, tags = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_tag_member", inp, "list_id", "email", "tags")
        if permission_error: return permission_error
        status = inp.get("status", "active")
        subscriber_hash = hashlib.md5(email.lower().encode()).hexdigest()
        body = {"tags": [{"name": t, "status": status} for t in tags]}
        try:
            with httpx.Client() as client:
                r = client.post(
                    f"{self._base}/lists/{list_id}/members/{subscriber_hash}/tags",
                    auth=self._auth(),
                    headers={**self._auth_headers, "Content-Type": "application/json"},
                    json=body,
                )
                r.raise_for_status()
                return json.dumps({"status": "tags_updated", "email": email, "tags": tags})
        except Exception as e:
            return _handle_error("mailchimp_tag_member", e)

    def mailchimp_search_members(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_search_members", inp, "query")
        if permission_error: return permission_error
        params = {"query": query}
        if inp.get("list_id"):
            params["list_id"] = inp["list_id"]
        try:
            with httpx.Client() as client:
                r = client.get(f"{self._base}/search-members", auth=self._auth(), headers=self._auth_headers, params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("mailchimp_search_members", e)

    def mailchimp_get_campaign_content(self, inp: dict) -> str:
        permission_error, campaign_id = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_get_campaign_content", inp, "campaign_id")
        if permission_error: return permission_error
        try:
            with httpx.Client() as client:
                r = client.get(f"{self._base}/campaigns/{campaign_id}/content", auth=self._auth(), headers=self._auth_headers)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("mailchimp_get_campaign_content", e)

    def mailchimp_get_list_growth_history(self, inp: dict) -> str:
        permission_error, list_id = self._check(self.agent_id, self.PROVIDER_ID, "mailchimp_get_list_growth_history", inp, "list_id")
        if permission_error: return permission_error
        params = {}
        if inp.get("count"):
            params["count"] = inp["count"]
        if inp.get("offset"):
            params["offset"] = inp["offset"]
        try:
            with httpx.Client() as client:
                r = client.get(f"{self._base}/lists/{list_id}/growth-history", auth=self._auth(), headers=self._auth_headers, params=params)
                r.raise_for_status()
                return json.dumps(r.json())
        except Exception as e:
            return _handle_error("mailchimp_get_list_growth_history", e)

    def as_tools(self):
        tool_defs = [
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_get_account_info",
                    "description": "Retrieve Mailchimp account details including account name, email, and subscription info.",
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
                    "name": "mailchimp_list_audiences",
                    "description": "List all Mailchimp audiences (mailing lists) in the account.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "count": {"type": "integer", "description": "Number of records to return (default 10, max 1000)."},
                            "offset": {"type": "integer", "description": "Number of records to skip for pagination."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_get_audience_members",
                    "description": "Get members of a specific Mailchimp audience (list).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "list_id": {"type": "string", "description": "The unique ID of the Mailchimp audience/list."},
                            "count": {"type": "integer", "description": "Number of members to return."},
                            "offset": {"type": "integer", "description": "Number of members to skip for pagination."},
                            "status": {"type": "string", "description": "Filter by member status: subscribed, unsubscribed, cleaned, pending, transactional."},
                        },
                        "required": ["list_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_list_campaigns",
                    "description": "List all Mailchimp campaigns with optional filtering by status or type.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "count": {"type": "integer", "description": "Number of campaigns to return."},
                            "offset": {"type": "integer", "description": "Number of campaigns to skip for pagination."},
                            "status": {"type": "string", "description": "Filter by campaign status: save, paused, schedule, sending, sent."},
                            "type": {"type": "string", "description": "Filter by campaign type: regular, plaintext, absplit, rss, variate."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_get_campaign_reports",
                    "description": "Retrieve campaign reports including open rates, click rates, and other engagement metrics.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "count": {"type": "integer", "description": "Number of reports to return."},
                            "offset": {"type": "integer", "description": "Number of reports to skip for pagination."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_list_automations",
                    "description": "List all Mailchimp automation workflows in the account.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "count": {"type": "integer", "description": "Number of automations to return."},
                            "offset": {"type": "integer", "description": "Number of automations to skip for pagination."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_list_templates",
                    "description": "List all available Mailchimp email templates.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "count": {"type": "integer", "description": "Number of templates to return."},
                            "offset": {"type": "integer", "description": "Number of templates to skip for pagination."},
                            "type": {"type": "string", "description": "Filter by template type: user, base, gallery."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_add_subscriber",
                    "description": "Add a new subscriber to a Mailchimp audience (list).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "list_id": {"type": "string", "description": "The unique ID of the Mailchimp audience/list."},
                            "email": {"type": "string", "description": "Email address of the subscriber."},
                            "status": {"type": "string", "description": "Subscription status: subscribed or pending (default: subscribed)."},
                            "first_name": {"type": "string", "description": "Subscriber's first name (optional)."},
                            "last_name": {"type": "string", "description": "Subscriber's last name (optional)."},
                        },
                        "required": ["list_id", "email"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_update_subscriber",
                    "description": "Update an existing subscriber in a Mailchimp audience (list).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "list_id": {"type": "string", "description": "The unique ID of the Mailchimp audience/list."},
                            "email": {"type": "string", "description": "Email address of the subscriber to update."},
                            "status": {"type": "string", "description": "New subscription status: subscribed, unsubscribed, cleaned, pending."},
                            "first_name": {"type": "string", "description": "Updated first name (optional)."},
                            "last_name": {"type": "string", "description": "Updated last name (optional)."},
                        },
                        "required": ["list_id", "email"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_remove_subscriber",
                    "description": "Unsubscribe a member from a Mailchimp audience (list) by setting their status to unsubscribed.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "list_id": {"type": "string", "description": "The unique ID of the Mailchimp audience/list."},
                            "email": {"type": "string", "description": "Email address of the subscriber to remove."},
                        },
                        "required": ["list_id", "email"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_create_campaign",
                    "description": "Create a new Mailchimp email campaign.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "list_id": {"type": "string", "description": "The unique ID of the Mailchimp audience/list to send to."},
                            "subject": {"type": "string", "description": "Subject line of the email campaign."},
                            "from_name": {"type": "string", "description": "Name displayed as the sender."},
                            "reply_to": {"type": "string", "description": "Reply-to email address."},
                            "type": {"type": "string", "description": "Campaign type: regular or plaintext (default: regular)."},
                        },
                        "required": ["list_id", "subject", "from_name", "reply_to"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_send_campaign",
                    "description": "Send a Mailchimp campaign that has been created and is ready to send.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "campaign_id": {"type": "string", "description": "The unique ID of the campaign to send."},
                        },
                        "required": ["campaign_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_create_audience",
                    "description": "Create a new Mailchimp audience (mailing list) with contact and campaign defaults.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Name of the audience."},
                            "company": {"type": "string", "description": "Company name (required by Mailchimp for CAN-SPAM compliance)."},
                            "address1": {"type": "string", "description": "Street address."},
                            "city": {"type": "string", "description": "City."},
                            "state": {"type": "string", "description": "State/province."},
                            "zip": {"type": "string", "description": "ZIP/postal code."},
                            "country": {"type": "string", "description": "Country code, e.g. 'US'."},
                            "from_name": {"type": "string", "description": "Default 'from' name for campaigns sent to this audience."},
                            "from_email": {"type": "string", "description": "Default 'from' email for campaigns sent to this audience."},
                            "default_subject": {"type": "string", "description": "Default campaign subject line (optional)."},
                            "permission_reminder": {"type": "string", "description": "Reminder of how contacts opted in (optional)."},
                            "language": {"type": "string", "description": "Default campaign language code (optional, default 'en')."},
                            "email_type_option": {"type": "boolean", "description": "Whether subscribers can choose plain-text vs HTML (optional)."},
                        },
                        "required": ["name", "company", "address1", "city", "state", "zip", "country", "from_name", "from_email"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_create_segment",
                    "description": "Create an audience segment in Mailchimp for targeted sending, either as a static list of emails or a saved segment defined by conditions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "list_id": {"type": "string", "description": "The unique ID of the Mailchimp audience/list."},
                            "name": {"type": "string", "description": "Name of the segment."},
                            "static_emails": {"type": "array", "items": {"type": "string"}, "description": "Email addresses to include as a static segment (optional)."},
                            "conditions": {"type": "array", "items": {"type": "object"}, "description": "Mailchimp segment condition objects for a saved/dynamic segment (optional)."},
                            "match": {"type": "string", "description": "How conditions are combined: 'all' or 'any' (default 'all')."},
                        },
                        "required": ["list_id", "name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_tag_member",
                    "description": "Add or remove tags on a Mailchimp audience member, used for segmentation and automation triggers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "list_id": {"type": "string", "description": "The unique ID of the Mailchimp audience/list."},
                            "email": {"type": "string", "description": "Email address of the member to tag."},
                            "tags": {"type": "array", "items": {"type": "string"}, "description": "Tag names to apply."},
                            "status": {"type": "string", "description": "'active' to add tags or 'inactive' to remove them (default 'active')."},
                        },
                        "required": ["list_id", "email", "tags"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_search_members",
                    "description": "Search for audience members across one or all Mailchimp lists by email or name.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search text (email or name fragment)."},
                            "list_id": {"type": "string", "description": "Restrict search to a specific audience/list (optional)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_get_campaign_content",
                    "description": "Retrieve the HTML/plain-text content of a Mailchimp campaign.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "campaign_id": {"type": "string", "description": "The unique ID of the campaign."},
                        },
                        "required": ["campaign_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mailchimp_get_list_growth_history",
                    "description": "Get monthly subscriber growth history (new subscribes vs unsubscribes) for a Mailchimp audience.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "list_id": {"type": "string", "description": "The unique ID of the Mailchimp audience/list."},
                            "count": {"type": "integer", "description": "Number of records to return (optional)."},
                            "offset": {"type": "integer", "description": "Number of records to skip for pagination (optional)."},
                        },
                        "required": ["list_id"],
                    },
                },
            },
        ]

        callables = {
            "mailchimp_get_account_info": self.mailchimp_get_account_info,
            "mailchimp_list_audiences": self.mailchimp_list_audiences,
            "mailchimp_get_audience_members": self.mailchimp_get_audience_members,
            "mailchimp_list_campaigns": self.mailchimp_list_campaigns,
            "mailchimp_get_campaign_reports": self.mailchimp_get_campaign_reports,
            "mailchimp_list_automations": self.mailchimp_list_automations,
            "mailchimp_list_templates": self.mailchimp_list_templates,
            "mailchimp_add_subscriber": self.mailchimp_add_subscriber,
            "mailchimp_update_subscriber": self.mailchimp_update_subscriber,
            "mailchimp_remove_subscriber": self.mailchimp_remove_subscriber,
            "mailchimp_create_campaign": self.mailchimp_create_campaign,
            "mailchimp_send_campaign": self.mailchimp_send_campaign,
            "mailchimp_create_audience": self.mailchimp_create_audience,
            "mailchimp_create_segment": self.mailchimp_create_segment,
            "mailchimp_tag_member": self.mailchimp_tag_member,
            "mailchimp_search_members": self.mailchimp_search_members,
            "mailchimp_get_campaign_content": self.mailchimp_get_campaign_content,
            "mailchimp_get_list_growth_history": self.mailchimp_get_list_growth_history,
        }

        return tool_defs, callables

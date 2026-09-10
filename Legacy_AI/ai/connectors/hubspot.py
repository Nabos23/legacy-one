import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.hubapi.com"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected HubSpot account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their HubSpot connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class HubSpotConnector(BaseConnector):

    PROVIDER_ID = "hubspot"

    def list_contacts(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_list_contacts", inp)
        if permission_error: return permission_error
        try:
            params = {
                "limit": inp.get("limit", 20),
                "properties": "firstname,lastname,email,phone,company,jobtitle,createdate,lastmodifieddate",
            }
            if inp.get("after"):
                params["after"] = inp["after"]
            resp = httpx.get(f"{_BASE}/crm/v3/objects/contacts", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            contacts = [{"id": c["id"], **c.get("properties", {})} for c in data.get("results", [])]
            return json.dumps({"contacts": contacts, "next": data.get("paging", {}).get("next", {}).get("after")})
        except Exception as e:
            return _handle_error("hubspot_list_contacts", e)

    def search_contacts(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_search_contacts", inp, "query")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "query": query,
                "limit": inp.get("limit", 10),
                "properties": ["firstname", "lastname", "email", "phone", "company"],
            }
            resp = httpx.post(f"{_BASE}/crm/v3/objects/contacts/search", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps([{"id": c["id"], **c.get("properties", {})} for c in data.get("results", [])])
        except Exception as e:
            return _handle_error("hubspot_search_contacts", e)

    def get_contact(self, inp: dict) -> str:
        permission_error, contact_id = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_get_contact", inp, "contact_id")
        if permission_error: return permission_error
        try:
            params = {"properties": "firstname,lastname,email,phone,company,jobtitle,lifecyclestage,createdate"}
            resp = httpx.get(f"{_BASE}/crm/v3/objects/contacts/{contact_id}", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], **data.get("properties", {})})
        except Exception as e:
            return _handle_error("hubspot_get_contact", e)

    def create_contact(self, inp: dict) -> str:
        permission_error, email = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_create_contact", inp, "email")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            properties = {"email": email}
            for field in ("firstname", "lastname", "phone", "company", "jobtitle"):
                if inp.get(field):
                    properties[field] = inp[field]
            resp = httpx.post(f"{_BASE}/crm/v3/objects/contacts", headers=headers, json={"properties": properties}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], **data.get("properties", {})})
        except Exception as e:
            return _handle_error("hubspot_create_contact", e)

    def update_contact(self, inp: dict) -> str:
        permission_error, contact_id = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_update_contact", inp, "contact_id")
        if permission_error: return permission_error
        properties = {}
        for field in ("email", "firstname", "lastname", "phone", "company"):
            if inp.get(field) is not None:
                properties[field] = inp[field]
        if not properties:
            return "Error: at least one property (email, firstname, lastname, phone, company) is required."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.patch(f"{_BASE}/crm/v3/objects/contacts/{contact_id}", headers=headers, json={"properties": properties}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], **data.get("properties", {})})
        except Exception as e:
            return _handle_error("hubspot_update_contact", e)

    def delete_contact(self, inp: dict) -> str:
        permission_error, contact_id = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_delete_contact", inp, "contact_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/crm/v3/objects/contacts/{contact_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "deleted", "contact_id": contact_id})
        except Exception as e:
            return _handle_error("hubspot_delete_contact", e)

    def list_deals(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_list_deals", inp)
        if permission_error: return permission_error
        try:
            params = {
                "limit": inp.get("limit", 20),
                "properties": "dealname,amount,dealstage,closedate,pipeline,createdate",
            }
            resp = httpx.get(f"{_BASE}/crm/v3/objects/deals", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            deals = [{"id": d["id"], **d.get("properties", {})} for d in data.get("results", [])]
            return json.dumps({"deals": deals, "next": data.get("paging", {}).get("next", {}).get("after")})
        except Exception as e:
            return _handle_error("hubspot_list_deals", e)

    def create_deal(self, inp: dict) -> str:
        permission_error, name = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_create_deal", inp, "dealname")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            properties = {"dealname": name}
            for field in ("amount", "dealstage", "closedate", "pipeline"):
                if inp.get(field):
                    properties[field] = str(inp[field])
            resp = httpx.post(f"{_BASE}/crm/v3/objects/deals", headers=headers, json={"properties": properties}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], **data.get("properties", {})})
        except Exception as e:
            return _handle_error("hubspot_create_deal", e)

    def get_deal(self, inp: dict) -> str:
        permission_error, deal_id = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_get_deal", inp, "deal_id")
        if permission_error: return permission_error
        try:
            params = {"properties": "dealname,amount,dealstage,closedate,pipeline"}
            resp = httpx.get(f"{_BASE}/crm/v3/objects/deals/{deal_id}", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], **data.get("properties", {})})
        except Exception as e:
            return _handle_error("hubspot_get_deal", e)

    def update_deal(self, inp: dict) -> str:
        permission_error, deal_id = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_update_deal", inp, "deal_id")
        if permission_error: return permission_error
        properties = {}
        for field in ("dealname", "amount", "dealstage", "closedate"):
            if inp.get(field) is not None:
                properties[field] = str(inp[field])
        if not properties:
            return "Error: at least one property (dealname, amount, dealstage, closedate) is required."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.patch(f"{_BASE}/crm/v3/objects/deals/{deal_id}", headers=headers, json={"properties": properties}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], **data.get("properties", {})})
        except Exception as e:
            return _handle_error("hubspot_update_deal", e)

    def list_companies(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_list_companies", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20), "properties": "name,domain,industry,city,country,createdate"}
            resp = httpx.get(f"{_BASE}/crm/v3/objects/companies", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps([{"id": c["id"], **c.get("properties", {})} for c in data.get("results", [])])
        except Exception as e:
            return _handle_error("hubspot_list_companies", e)

    def create_company(self, inp: dict) -> str:
        permission_error, name = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_create_company", inp, "name")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            properties = {"name": name}
            for field in ("domain", "phone", "city", "country"):
                if inp.get(field):
                    properties[field] = inp[field]
            resp = httpx.post(f"{_BASE}/crm/v3/objects/companies", headers=headers, json={"properties": properties}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], **data.get("properties", {})})
        except Exception as e:
            return _handle_error("hubspot_create_company", e)

    def get_company(self, inp: dict) -> str:
        permission_error, company_id = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_get_company", inp, "company_id")
        if permission_error: return permission_error
        try:
            params = {"properties": "name,domain,phone,city,country"}
            resp = httpx.get(f"{_BASE}/crm/v3/objects/companies/{company_id}", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], **data.get("properties", {})})
        except Exception as e:
            return _handle_error("hubspot_get_company", e)

    def list_tickets(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_list_tickets", inp)
        if permission_error: return permission_error
        try:
            params = {
                "limit": inp.get("limit", 20),
                "properties": "subject,content,hs_ticket_priority,hs_pipeline_stage",
            }
            resp = httpx.get(f"{_BASE}/crm/v3/objects/tickets", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            tickets = [{"id": t["id"], **t.get("properties", {})} for t in data.get("results", [])]
            return json.dumps({"tickets": tickets, "next": data.get("paging", {}).get("next", {}).get("after")})
        except Exception as e:
            return _handle_error("hubspot_list_tickets", e)

    def create_ticket(self, inp: dict) -> str:
        permission_error, subject = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_create_ticket", inp, "subject")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            properties = {"subject": subject}
            for field in ("content", "hs_ticket_priority", "hs_pipeline_stage"):
                if inp.get(field):
                    properties[field] = inp[field]
            resp = httpx.post(f"{_BASE}/crm/v3/objects/tickets", headers=headers, json={"properties": properties}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], **data.get("properties", {})})
        except Exception as e:
            return _handle_error("hubspot_create_ticket", e)

    def create_note(self, inp: dict) -> str:
        permission_error, body_text = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_create_note", inp, "body")
        if permission_error: return permission_error
        contact_id = inp.get("contact_id", "")
        deal_id = inp.get("deal_id", "")
        company_id = inp.get("company_id", "")
        if not (contact_id or deal_id or company_id):
            return "Error: at least one of 'contact_id', 'deal_id', or 'company_id' is required to associate the note."
        try:
            import time
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            properties = {"hs_note_body": body_text, "hs_timestamp": str(int(time.time() * 1000))}
            resp = httpx.post(f"{_BASE}/crm/v3/objects/notes", headers=headers, json={"properties": properties}, timeout=15)
            resp.raise_for_status()
            note_id = resp.json()["id"]
            for to_type, to_id in (("contacts", contact_id), ("deals", deal_id), ("companies", company_id)):
                if to_id:
                    assoc_resp = httpx.put(
                        f"{_BASE}/crm/v4/objects/notes/{note_id}/associations/default/{to_type}/{to_id}",
                        headers=headers,
                        timeout=15,
                    )
                    assoc_resp.raise_for_status()
            return json.dumps({"id": note_id, "status": "note_created"})
        except Exception as e:
            return _handle_error("hubspot_create_note", e)

    def create_task(self, inp: dict) -> str:
        permission_error, subject = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_create_task", inp, "subject")
        if permission_error: return permission_error
        try:
            import time
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            properties = {
                "hs_task_subject": subject,
                "hs_task_status": inp.get("status", "NOT_STARTED"),
                "hs_timestamp": str(inp.get("timestamp") or int(time.time() * 1000)),
            }
            if inp.get("body"):
                properties["hs_task_body"] = inp["body"]
            if inp.get("priority"):
                properties["hs_task_priority"] = inp["priority"]
            resp = httpx.post(f"{_BASE}/crm/v3/objects/tasks", headers=headers, json={"properties": properties}, timeout=15)
            resp.raise_for_status()
            task_id = resp.json()["id"]
            contact_id = inp.get("contact_id", "")
            deal_id = inp.get("deal_id", "")
            for to_type, to_id in (("contacts", contact_id), ("deals", deal_id)):
                if to_id:
                    assoc_resp = httpx.put(
                        f"{_BASE}/crm/v4/objects/tasks/{task_id}/associations/default/{to_type}/{to_id}",
                        headers=headers,
                        timeout=15,
                    )
                    assoc_resp.raise_for_status()
            return json.dumps({"id": task_id, "subject": subject, "status": "task_created"})
        except Exception as e:
            return _handle_error("hubspot_create_task", e)

    def list_owners(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_list_owners", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 100)}
            if inp.get("email"):
                params["email"] = inp["email"]
            resp = httpx.get(f"{_BASE}/crm/v3/owners", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            owners = [
                {"id": o["id"], "email": o.get("email"), "firstName": o.get("firstName"), "lastName": o.get("lastName")}
                for o in data.get("results", [])
            ]
            return json.dumps({"owners": owners, "count": len(owners)})
        except Exception as e:
            return _handle_error("hubspot_list_owners", e)

    def list_pipelines(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_list_pipelines", inp)
        if permission_error: return permission_error
        object_type = inp.get("object_type", "deals")
        try:
            resp = httpx.get(f"{_BASE}/crm/v3/pipelines/{object_type}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            pipelines = [
                {
                    "id": p["id"],
                    "label": p.get("label"),
                    "stages": [{"id": s["id"], "label": s.get("label"), "displayOrder": s.get("displayOrder")} for s in p.get("stages", [])],
                }
                for p in data.get("results", [])
            ]
            return json.dumps({"pipelines": pipelines})
        except Exception as e:
            return _handle_error("hubspot_list_pipelines", e)

    def create_association(self, inp: dict) -> str:
        permission_error, from_object_type, from_object_id, to_object_type, to_object_id = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_create_association", inp, "from_object_type", "from_object_id", "to_object_type", "to_object_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.put(
                f"{_BASE}/crm/v4/objects/{from_object_type}/{from_object_id}/associations/default/{to_object_type}/{to_object_id}",
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"status": "associated", "from": from_object_id, "to": to_object_id})
        except Exception as e:
            return _handle_error("hubspot_create_association", e)

    def merge_contacts(self, inp: dict) -> str:
        permission_error, primary_contact_id, contact_id_to_merge = self._check(self.agent_id, self.PROVIDER_ID, "hubspot_merge_contacts", inp, "primary_contact_id", "contact_id_to_merge")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"primaryObjectId": primary_contact_id, "objectIdToMerge": contact_id_to_merge}
            resp = httpx.post(f"{_BASE}/crm/v3/objects/contacts/merge", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "status": "merged", **data.get("properties", {})})
        except Exception as e:
            return _handle_error("hubspot_merge_contacts", e)
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"primaryObjectId": primary_contact_id, "objectIdToMerge": contact_id_to_merge}
            resp = httpx.post(f"{_BASE}/crm/v3/objects/contacts/merge", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "status": "merged", **data.get("properties", {})})
        except Exception as e:
            return _handle_error("hubspot_merge_contacts", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "hubspot_list_contacts",
                    "description": "List contacts in HubSpot CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max contacts to return (default 20)."},
                            "after": {"type": "string", "description": "Pagination cursor for next page."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "hubspot_search_contacts",
                    "description": "Search HubSpot contacts by name, email, or company.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query string."},
                            "limit": {"type": "integer", "description": "Max results (default 10)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "hubspot_get_contact",
                    "description": "Get details for a specific HubSpot contact.",
                    "parameters": {"type": "object", "properties": {"contact_id": {"type": "string", "description": "HubSpot contact ID."}}, "required": ["contact_id"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "hubspot_create_contact",
                    "description": "Create a new contact in HubSpot.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string", "description": "Contact email address (required)."},
                            "firstname": {"type": "string", "description": "First name."},
                            "lastname": {"type": "string", "description": "Last name."},
                            "phone": {"type": "string", "description": "Phone number."},
                            "company": {"type": "string", "description": "Company name."},
                            "jobtitle": {"type": "string", "description": "Job title."},
                        },
                        "required": ["email"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "hubspot_update_contact",
                    "description": "Update an existing HubSpot contact's properties.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "contact_id": {"type": "string", "description": "HubSpot contact ID to update."},
                            "email": {"type": "string", "description": "New email address."},
                            "firstname": {"type": "string", "description": "New first name."},
                            "lastname": {"type": "string", "description": "New last name."},
                            "phone": {"type": "string", "description": "New phone number."},
                            "company": {"type": "string", "description": "New company name."},
                        },
                        "required": ["contact_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "hubspot_delete_contact",
                    "description": "Delete (archive) a HubSpot contact by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {"contact_id": {"type": "string", "description": "HubSpot contact ID to delete."}},
                        "required": ["contact_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "hubspot_list_deals",
                    "description": "List deals in HubSpot CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "description": "Max deals to return (default 20)."}},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "hubspot_create_deal",
                    "description": "Create a new deal in HubSpot.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dealname": {"type": "string", "description": "Deal name (required)."},
                            "amount": {"type": "number", "description": "Deal value."},
                            "dealstage": {"type": "string", "description": "Deal stage (e.g. appointmentscheduled)."},
                            "closedate": {"type": "string", "description": "Expected close date (YYYY-MM-DD)."},
                            "pipeline": {"type": "string", "description": "Pipeline ID (default: default)."},
                        },
                        "required": ["dealname"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "hubspot_get_deal",
                    "description": "Get details for a specific HubSpot deal.",
                    "parameters": {
                        "type": "object",
                        "properties": {"deal_id": {"type": "string", "description": "HubSpot deal ID."}},
                        "required": ["deal_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "hubspot_update_deal",
                    "description": "Update an existing HubSpot deal's properties.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "deal_id": {"type": "string", "description": "HubSpot deal ID to update."},
                            "dealname": {"type": "string", "description": "New deal name."},
                            "amount": {"type": "number", "description": "New deal value."},
                            "dealstage": {"type": "string", "description": "New deal stage."},
                            "closedate": {"type": "string", "description": "New close date (YYYY-MM-DD)."},
                        },
                        "required": ["deal_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "hubspot_list_companies",
                    "description": "List companies in HubSpot CRM.",
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
                    "name": "hubspot_create_company",
                    "description": "Create a new company in HubSpot CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Company name (required)."},
                            "domain": {"type": "string", "description": "Company website domain (e.g. acme.com)."},
                            "phone": {"type": "string", "description": "Company phone number."},
                            "city": {"type": "string", "description": "City."},
                            "country": {"type": "string", "description": "Country."},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "hubspot_get_company",
                    "description": "Get details for a specific HubSpot company.",
                    "parameters": {
                        "type": "object",
                        "properties": {"company_id": {"type": "string", "description": "HubSpot company ID."}},
                        "required": ["company_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "hubspot_list_tickets",
                    "description": "List support tickets in HubSpot.",
                    "parameters": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "description": "Max tickets to return (default 20)."}},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "hubspot_create_ticket",
                    "description": "Create a new support ticket in HubSpot.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string", "description": "Ticket subject (required)."},
                            "content": {"type": "string", "description": "Ticket description/body."},
                            "hs_ticket_priority": {"type": "string", "description": "Priority: LOW, MEDIUM, or HIGH."},
                            "hs_pipeline_stage": {"type": "string", "description": "Pipeline stage ID."},
                        },
                        "required": ["subject"],
                    },
                },
            },
        ]
        callables = {
            "hubspot_list_contacts": self.list_contacts,
            "hubspot_search_contacts": self.search_contacts,
            "hubspot_get_contact": self.get_contact,
            "hubspot_create_contact": self.create_contact,
            "hubspot_update_contact": self.update_contact,
            "hubspot_delete_contact": self.delete_contact,
            "hubspot_list_deals": self.list_deals,
            "hubspot_create_deal": self.create_deal,
            "hubspot_get_deal": self.get_deal,
            "hubspot_update_deal": self.update_deal,
            "hubspot_list_companies": self.list_companies,
            "hubspot_create_company": self.create_company,
            "hubspot_get_company": self.get_company,
            "hubspot_list_tickets": self.list_tickets,
            "hubspot_create_ticket": self.create_ticket,
        }
        return tools, callables

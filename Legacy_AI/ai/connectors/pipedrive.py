import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.pipedrive.com/v1"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Pipedrive account lacks permission "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their Pipedrive connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class PipedriveConnector(BaseConnector):

    PROVIDER_ID = "pipedrive"

    def list_deals(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_list_deals", inp)
        if permission_error: return permission_error
        try:
            params = {
                "limit": inp.get("limit", 25),
                "status": inp.get("status", "open"),
                "sort": inp.get("sort", "update_time DESC"),
            }
            if inp.get("stage_id"):
                params["stage_id"] = inp["stage_id"]
            resp = httpx.get(f"{_BASE}/deals", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            deals = [
                {
                    "id": d["id"],
                    "title": d["title"],
                    "status": d["status"],
                    "value": d.get("value"),
                    "currency": d.get("currency"),
                    "stage": d.get("stage_id"),
                    "owner": (d.get("owner_name") or ""),
                    "person": (d.get("person_name") or ""),
                    "org": (d.get("org_name") or ""),
                    "close_time": d.get("close_time"),
                    "update_time": d.get("update_time"),
                }
                for d in (data.get("data") or [])
            ]
            return json.dumps({"deals": deals, "count": len(deals)})
        except Exception as e:
            return _handle_error("pipedrive_list_deals", e)

    def get_deal(self, inp: dict) -> str:
        permission_error, deal_id = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_get_deal", inp, "deal_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/deals/{deal_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            d = resp.json().get("data", {})
            return json.dumps({
                "id": d["id"],
                "title": d["title"],
                "status": d["status"],
                "value": d.get("value"),
                "currency": d.get("currency"),
                "stage_id": d.get("stage_id"),
                "person": (d.get("person_name") or ""),
                "org": (d.get("org_name") or ""),
                "owner": (d.get("owner_name") or ""),
                "expected_close_date": d.get("expected_close_date"),
                "notes_count": d.get("notes_count"),
                "activities_count": d.get("activities_count"),
            })
        except Exception as e:
            return _handle_error("pipedrive_get_deal", e)

    def create_deal(self, inp: dict) -> str:
        permission_error, title = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_create_deal", inp, "title")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"title": title}
            if inp.get("value"):
                body["value"] = inp["value"]
            if inp.get("currency"):
                body["currency"] = inp["currency"]
            if inp.get("person_id"):
                body["person_id"] = inp["person_id"]
            if inp.get("org_id"):
                body["org_id"] = inp["org_id"]
            if inp.get("stage_id"):
                body["stage_id"] = inp["stage_id"]
            if inp.get("expected_close_date"):
                body["expected_close_date"] = inp["expected_close_date"]
            resp = httpx.post(f"{_BASE}/deals", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            d = resp.json().get("data", {})
            return json.dumps({"id": d["id"], "title": d["title"], "status": d["status"], "status_created": "created"})
        except Exception as e:
            return _handle_error("pipedrive_create_deal", e)

    def update_deal(self, inp: dict) -> str:
        permission_error, deal_id = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_update_deal", inp, "id")
        if permission_error: return permission_error
        body: dict = {}
        for field in ("title", "value", "currency", "status", "stage_id"):
            if inp.get(field) is not None:
                body[field] = inp[field]
        if not body:
            return "Error: at least one property (title, value, currency, status, stage_id) is required."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.put(f"{_BASE}/deals/{deal_id}", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            d = resp.json().get("data", {})
            return json.dumps({"id": d["id"], "title": d["title"], "status": d["status"]})
        except Exception as e:
            return _handle_error("pipedrive_update_deal", e)

    def list_persons(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_list_persons", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 25)}
            if inp.get("search"):
                resp = httpx.get(f"{_BASE}/persons/search", headers=self._auth_headers, params={"term": inp["search"], "limit": params["limit"]}, timeout=15)
            else:
                resp = httpx.get(f"{_BASE}/persons", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("data") or []
            if inp.get("search") and isinstance(raw, dict):
                raw = raw.get("items", [])
                persons = [{"id": p["item"]["id"], "name": p["item"]["name"], "email": p["item"].get("primary_email"), "phone": p["item"].get("phones", [None])[0]} for p in raw]
            else:
                persons = [
                    {"id": p["id"], "name": p["name"], "email": p.get("primary_email") or (p.get("email") or [{}])[0].get("value"), "phone": (p.get("phone") or [{}])[0].get("value"), "org": p.get("org_name")}
                    for p in (raw or [])
                ]
            return json.dumps({"persons": persons, "count": len(persons)})
        except Exception as e:
            return _handle_error("pipedrive_list_persons", e)

    def create_person(self, inp: dict) -> str:
        permission_error, name = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_create_person", inp, "name")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"name": name}
            if inp.get("email"):
                email = inp["email"]
                body["email"] = email if isinstance(email, list) else [{"value": email, "primary": True}]
            if inp.get("phone"):
                phone = inp["phone"]
                body["phone"] = phone if isinstance(phone, list) else [{"value": phone, "primary": True}]
            if inp.get("org_id"):
                body["org_id"] = inp["org_id"]
            resp = httpx.post(f"{_BASE}/persons", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            d = resp.json().get("data", {})
            return json.dumps({"id": d["id"], "name": d["name"], "status": "created"})
        except Exception as e:
            return _handle_error("pipedrive_create_person", e)

    def update_person(self, inp: dict) -> str:
        permission_error, person_id = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_update_person", inp, "id")
        if permission_error: return permission_error
        body: dict = {}
        if inp.get("name"):
            body["name"] = inp["name"]
        if inp.get("email"):
            email = inp["email"]
            body["email"] = email if isinstance(email, list) else [{"value": email, "primary": True}]
        if inp.get("phone"):
            phone = inp["phone"]
            body["phone"] = phone if isinstance(phone, list) else [{"value": phone, "primary": True}]
        if inp.get("org_id") is not None:
            body["org_id"] = inp["org_id"]
        if not body:
            return "Error: at least one property (name, email, phone, org_id) is required."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.put(f"{_BASE}/persons/{person_id}", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            d = resp.json().get("data", {})
            return json.dumps({"id": d["id"], "name": d["name"]})
        except Exception as e:
            return _handle_error("pipedrive_update_person", e)

    def list_organizations(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_list_organizations", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 25)}
            if inp.get("search"):
                resp = httpx.get(f"{_BASE}/organizations/search", headers=self._auth_headers, params={"term": inp["search"], "limit": params["limit"]}, timeout=15)
            else:
                resp = httpx.get(f"{_BASE}/organizations", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("data") or []
            if inp.get("search") and isinstance(raw, dict):
                raw = raw.get("items", [])
                orgs = [{"id": o["item"]["id"], "name": o["item"]["name"]} for o in raw]
            else:
                orgs = [{"id": o["id"], "name": o["name"], "people_count": o.get("people_count"), "open_deals": o.get("open_deals_count")} for o in (raw or [])]
            return json.dumps({"organizations": orgs, "count": len(orgs)})
        except Exception as e:
            return _handle_error("pipedrive_list_organizations", e)

    def create_organization(self, inp: dict) -> str:
        permission_error, name = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_create_organization", inp, "name")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"name": name}
            if inp.get("address"):
                body["address"] = inp["address"]
            resp = httpx.post(f"{_BASE}/organizations", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            d = resp.json().get("data", {})
            return json.dumps({"id": d["id"], "name": d["name"], "status": "created"})
        except Exception as e:
            return _handle_error("pipedrive_create_organization", e)

    def add_activity(self, inp: dict) -> str:
        permission_error, subject = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_add_activity", inp, "subject")
        if permission_error: return permission_error
        activity_type = inp.get("type", "task")
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"subject": subject, "type": activity_type, "done": 0}
            if inp.get("deal_id"):
                body["deal_id"] = inp["deal_id"]
            if inp.get("person_id"):
                body["person_id"] = inp["person_id"]
            if inp.get("due_date"):
                body["due_date"] = inp["due_date"]
            if inp.get("due_time"):
                body["due_time"] = inp["due_time"]
            if inp.get("note"):
                body["note"] = inp["note"]
            resp = httpx.post(f"{_BASE}/activities", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            a = resp.json().get("data", {})
            return json.dumps({"id": a["id"], "subject": a["subject"], "type": a["type"], "status": "created"})
        except Exception as e:
            return _handle_error("pipedrive_add_activity", e)

    def list_activities(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_list_activities", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"limit": inp.get("limit", 20)}
            if inp.get("type"):
                params["type"] = inp["type"]
            if inp.get("done") is not None:
                params["done"] = inp["done"]
            resp = httpx.get(f"{_BASE}/activities", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            activities = [
                {
                    "id": a["id"],
                    "subject": a.get("subject"),
                    "type": a.get("type"),
                    "done": a.get("done"),
                    "due_date": a.get("due_date"),
                    "due_time": a.get("due_time"),
                    "deal_id": a.get("deal_id"),
                    "person_id": a.get("person_id"),
                    "note": a.get("note"),
                }
                for a in (data.get("data") or [])
            ]
            return json.dumps({"activities": activities, "count": len(activities)})
        except Exception as e:
            return _handle_error("pipedrive_list_activities", e)

    def list_pipelines(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_list_pipelines", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/pipelines", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            pipelines = [{"id": p["id"], "name": p["name"]} for p in (data.get("data") or [])]
            return json.dumps({"pipelines": pipelines, "count": len(pipelines)})
        except Exception as e:
            return _handle_error("pipedrive_list_pipelines", e)

    def list_stages(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_list_stages", inp)
        if permission_error: return permission_error
        try:
            params: dict = {}
            if inp.get("pipeline_id"):
                params["pipeline_id"] = inp["pipeline_id"]
            resp = httpx.get(f"{_BASE}/stages", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            stages = [
                {"id": s["id"], "name": s["name"], "pipeline_id": s.get("pipeline_id"), "order_nr": s.get("order_nr")}
                for s in (data.get("data") or [])
            ]
            return json.dumps({"stages": stages, "count": len(stages)})
        except Exception as e:
            return _handle_error("pipedrive_list_stages", e)

    def delete_deal(self, inp: dict) -> str:
        permission_error, deal_id = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_delete_deal", inp, "deal_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/deals/{deal_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"deleted": True, "id": deal_id})
        except Exception as e:
            return _handle_error("pipedrive_delete_deal", e)

    def delete_person(self, inp: dict) -> str:
        permission_error, person_id = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_delete_person", inp, "person_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/persons/{person_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"deleted": True, "id": person_id})
        except Exception as e:
            return _handle_error("pipedrive_delete_person", e)

    def list_notes(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_list_notes", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"limit": inp.get("limit", 20)}
            if inp.get("deal_id"):
                params["deal_id"] = inp["deal_id"]
            if inp.get("person_id"):
                params["person_id"] = inp["person_id"]
            if inp.get("org_id"):
                params["org_id"] = inp["org_id"]
            resp = httpx.get(f"{_BASE}/notes", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            notes = [
                {"id": n["id"], "content": n.get("content"), "deal_id": n.get("deal_id"), "person_id": n.get("person_id"), "add_time": n.get("add_time")}
                for n in (data.get("data") or [])
            ]
            return json.dumps({"notes": notes, "count": len(notes)})
        except Exception as e:
            return _handle_error("pipedrive_list_notes", e)

    def add_note(self, inp: dict) -> str:
        permission_error, content = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_add_note", inp, "content")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"content": content}
            if inp.get("deal_id"):
                body["deal_id"] = inp["deal_id"]
            if inp.get("person_id"):
                body["person_id"] = inp["person_id"]
            if inp.get("org_id"):
                body["org_id"] = inp["org_id"]
            resp = httpx.post(f"{_BASE}/notes", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            n = resp.json().get("data", {})
            return json.dumps({"id": n["id"], "content": n.get("content"), "status": "created"})
        except Exception as e:
            return _handle_error("pipedrive_add_note", e)

    def list_products(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "pipedrive_list_products", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 25)}
            resp = httpx.get(f"{_BASE}/products", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            products = [
                {"id": p["id"], "name": p["name"], "code": p.get("code"), "prices": p.get("prices")}
                for p in (data.get("data") or [])
            ]
            return json.dumps({"products": products, "count": len(products)})
        except Exception as e:
            return _handle_error("pipedrive_list_products", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_list_deals",
                    "description": "List deals in Pipedrive CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by status: open, won, lost, all_not_deleted (default open)."},
                            "stage_id": {"type": "integer", "description": "Filter by pipeline stage ID."},
                            "limit": {"type": "integer", "description": "Max deals (default 25)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_get_deal",
                    "description": "Get full details of a specific Pipedrive deal.",
                    "parameters": {
                        "type": "object",
                        "properties": {"deal_id": {"type": "integer", "description": "Pipedrive deal ID."}},
                        "required": ["deal_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_create_deal",
                    "description": "Create a new deal in Pipedrive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Deal title."},
                            "value": {"type": "number", "description": "Deal value/amount."},
                            "currency": {"type": "string", "description": "Currency code (e.g. USD, EUR)."},
                            "person_id": {"type": "integer", "description": "Associated contact person ID."},
                            "org_id": {"type": "integer", "description": "Associated organization ID."},
                            "stage_id": {"type": "integer", "description": "Pipeline stage ID."},
                            "expected_close_date": {"type": "string", "description": "Expected close date (YYYY-MM-DD)."},
                        },
                        "required": ["title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_update_deal",
                    "description": "Update an existing deal in Pipedrive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "description": "Pipedrive deal ID to update."},
                            "title": {"type": "string", "description": "New deal title."},
                            "value": {"type": "number", "description": "New deal value."},
                            "currency": {"type": "string", "description": "New currency code."},
                            "status": {"type": "string", "description": "Deal status: open, won, or lost."},
                            "stage_id": {"type": "integer", "description": "New pipeline stage ID."},
                        },
                        "required": ["id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_list_persons",
                    "description": "List or search contacts/persons in Pipedrive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "search": {"type": "string", "description": "Search term to filter persons."},
                            "limit": {"type": "integer", "description": "Max persons (default 25)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_create_person",
                    "description": "Create a new contact person in Pipedrive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Person's full name (required)."},
                            "email": {"type": "string", "description": "Email address (string or list of email objects)."},
                            "phone": {"type": "string", "description": "Phone number (string or list of phone objects)."},
                            "org_id": {"type": "integer", "description": "Associated organization ID."},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_update_person",
                    "description": "Update an existing contact person in Pipedrive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "description": "Pipedrive person ID to update."},
                            "name": {"type": "string", "description": "New name."},
                            "email": {"type": "string", "description": "New email address."},
                            "phone": {"type": "string", "description": "New phone number."},
                            "org_id": {"type": "integer", "description": "New associated organization ID."},
                        },
                        "required": ["id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_list_organizations",
                    "description": "List or search organizations in Pipedrive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "search": {"type": "string", "description": "Search term to filter organizations."},
                            "limit": {"type": "integer", "description": "Max organizations (default 25)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_create_organization",
                    "description": "Create a new organization in Pipedrive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Organization name (required)."},
                            "address": {"type": "string", "description": "Organization address."},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_add_activity",
                    "description": "Add an activity (task, call, email, meeting) to a Pipedrive deal or contact.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string", "description": "Activity subject/title."},
                            "type": {"type": "string", "description": "Activity type: task, call, email, meeting, deadline, lunch (default task)."},
                            "deal_id": {"type": "integer", "description": "Deal ID to associate with."},
                            "person_id": {"type": "integer", "description": "Person ID to associate with."},
                            "due_date": {"type": "string", "description": "Due date (YYYY-MM-DD)."},
                            "due_time": {"type": "string", "description": "Due time (HH:MM)."},
                            "note": {"type": "string", "description": "Activity note/description."},
                        },
                        "required": ["subject"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_list_activities",
                    "description": "List activities in Pipedrive, optionally filtered by type or completion status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "description": "Filter by activity type (e.g. call, meeting, task)."},
                            "limit": {"type": "integer", "description": "Max activities to return (default 20)."},
                            "done": {"type": "integer", "description": "Filter by completion: 0 for open, 1 for done."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_list_pipelines",
                    "description": "List all pipelines in Pipedrive.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_list_stages",
                    "description": "List pipeline stages in Pipedrive, optionally filtered by pipeline.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pipeline_id": {"type": "integer", "description": "Filter stages by pipeline ID."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_delete_deal",
                    "description": "Delete a deal from Pipedrive by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {"deal_id": {"type": "integer", "description": "Pipedrive deal ID to delete."}},
                        "required": ["deal_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_delete_person",
                    "description": "Delete a contact person from Pipedrive by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {"person_id": {"type": "integer", "description": "Pipedrive person ID to delete."}},
                        "required": ["person_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_list_notes",
                    "description": "List notes in Pipedrive, optionally filtered by deal, person, or organization.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "deal_id": {"type": "integer", "description": "Filter notes by deal ID."},
                            "person_id": {"type": "integer", "description": "Filter notes by person ID."},
                            "org_id": {"type": "integer", "description": "Filter notes by organization ID."},
                            "limit": {"type": "integer", "description": "Max notes to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_add_note",
                    "description": "Add a note to a Pipedrive deal, person, or organization.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "Note content (HTML-formatted text supported)."},
                            "deal_id": {"type": "integer", "description": "Deal ID to attach the note to."},
                            "person_id": {"type": "integer", "description": "Person ID to attach the note to."},
                            "org_id": {"type": "integer", "description": "Organization ID to attach the note to."},
                        },
                        "required": ["content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "pipedrive_list_products",
                    "description": "List products defined in the Pipedrive product catalog.",
                    "parameters": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "description": "Max products to return (default 25)."}},
                        "required": [],
                    },
                },
            },
        ]
        callables = {
            "pipedrive_list_deals": self.list_deals,
            "pipedrive_get_deal": self.get_deal,
            "pipedrive_create_deal": self.create_deal,
            "pipedrive_update_deal": self.update_deal,
            "pipedrive_list_persons": self.list_persons,
            "pipedrive_create_person": self.create_person,
            "pipedrive_update_person": self.update_person,
            "pipedrive_list_organizations": self.list_organizations,
            "pipedrive_create_organization": self.create_organization,
            "pipedrive_add_activity": self.add_activity,
            "pipedrive_list_activities": self.list_activities,
            "pipedrive_list_pipelines": self.list_pipelines,
            "pipedrive_list_stages": self.list_stages,
            "pipedrive_delete_deal": self.delete_deal,
            "pipedrive_delete_person": self.delete_person,
            "pipedrive_list_notes": self.list_notes,
            "pipedrive_add_note": self.add_note,
            "pipedrive_list_products": self.list_products,
        }
        return tools, callables

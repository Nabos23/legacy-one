import json
import httpx
from ai.connectors.base import BaseConnector

_BASE = "https://www.zohoapis.com/crm/v6"


def _handle_error(tool_name, e):
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class ZohoCrmConnector(BaseConnector):
    """Zoho CRM connector for contacts, leads, accounts, deals, tasks, users, and modules."""

    PROVIDER_ID = "zoho_crm"

    def list_contacts(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_list_contacts", inp)
        if permission_error: return permission_error
        try:
            params = {
                "page": inp.get("page", 1),
                "per_page": min(inp.get("per_page", 20), 200),
                "fields": "First_Name,Last_Name,Email,Phone,Account_Name,Title,Created_Time,Modified_Time",
            }
            resp = httpx.get(f"{_BASE}/contacts", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"contacts": data.get("data", []), "info": data.get("info", {})})
        except Exception as e:
            return _handle_error("zoho_crm_list_contacts", e)

    def list_leads(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_list_leads", inp)
        if permission_error: return permission_error
        try:
            params = {
                "page": inp.get("page", 1),
                "per_page": min(inp.get("per_page", 20), 200),
                "fields": "First_Name,Last_Name,Email,Phone,Company,Lead_Source,Lead_Status,Created_Time",
            }
            resp = httpx.get(f"{_BASE}/leads", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"leads": data.get("data", []), "info": data.get("info", {})})
        except Exception as e:
            return _handle_error("zoho_crm_list_leads", e)

    def list_accounts(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_list_accounts", inp)
        if permission_error: return permission_error
        try:
            params = {
                "page": inp.get("page", 1),
                "per_page": min(inp.get("per_page", 20), 200),
                "fields": "Account_Name,Website,Phone,Industry,Annual_Revenue,Billing_City,Billing_Country,Created_Time",
            }
            resp = httpx.get(f"{_BASE}/accounts", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"accounts": data.get("data", []), "info": data.get("info", {})})
        except Exception as e:
            return _handle_error("zoho_crm_list_accounts", e)

    def list_deals(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_list_deals", inp)
        if permission_error: return permission_error
        try:
            params = {
                "page": inp.get("page", 1),
                "per_page": min(inp.get("per_page", 20), 200),
                "fields": "Deal_Name,Amount,Stage,Closing_Date,Account_Name,Probability,Created_Time",
            }
            resp = httpx.get(f"{_BASE}/deals", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"deals": data.get("data", []), "info": data.get("info", {})})
        except Exception as e:
            return _handle_error("zoho_crm_list_deals", e)

    def list_tasks(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_list_tasks", inp)
        if permission_error: return permission_error
        try:
            params = {
                "page": inp.get("page", 1),
                "per_page": min(inp.get("per_page", 20), 200),
                "fields": "Subject,Status,Due_Date,Priority,Who_Id,What_Id,Description,Created_Time",
            }
            resp = httpx.get(f"{_BASE}/tasks", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"tasks": data.get("data", []), "info": data.get("info", {})})
        except Exception as e:
            return _handle_error("zoho_crm_list_tasks", e)

    def list_users(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_list_users", inp)
        if permission_error: return permission_error
        try:
            params = {"type": inp.get("type", "AllUsers")}
            resp = httpx.get(f"{_BASE}/users", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"users": data.get("users", [])})
        except Exception as e:
            return _handle_error("zoho_crm_list_users", e)

    def list_modules(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_list_modules", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/settings/modules", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            modules = [
                {"api_name": m.get("api_name"), "module_name": m.get("module_name"), "singular_label": m.get("singular_label"), "visible": m.get("visible")}
                for m in data.get("modules", [])
            ]
            return json.dumps({"modules": modules})
        except Exception as e:
            return _handle_error("zoho_crm_list_modules", e)

    def search_records(self, inp: dict) -> str:
        permission_error, module, criteria = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_search_records", inp, "module", "criteria")
        if permission_error: return permission_error
        try:
            params = {
                "criteria": criteria,
                "page": inp.get("page", 1),
                "per_page": min(inp.get("per_page", 20), 200),
            }
            resp = httpx.get(f"{_BASE}/{module}/search", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"records": data.get("data", []), "info": data.get("info", {})})
        except Exception as e:
            return _handle_error("zoho_crm_search_records", e)

    def get_record(self, inp: dict) -> str:
        permission_error, module, record_id = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_get_record", inp, "module", "id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/{module}/{record_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            records = data.get("data", [])
            return json.dumps({"record": records[0] if records else None})
        except Exception as e:
            return _handle_error("zoho_crm_get_record", e)

    def create_contact(self, inp: dict) -> str:
        permission_error, last_name = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_create_contact", inp, "Last_Name")
        if permission_error: return permission_error
        try:
            record: dict = {"Last_Name": last_name}
            for field in ("First_Name", "Email", "Phone", "Account_Name"):
                if inp.get(field):
                    record[field] = inp[field]
            resp = httpx.post(
                f"{_BASE}/Contacts",
                headers=self._auth_headers,
                json={"data": [record]},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"result": data.get("data", [])})
        except Exception as e:
            return _handle_error("zoho_crm_create_contact", e)

    def update_contact(self, inp: dict) -> str:
        permission_error, record_id = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_update_contact", inp, "id")
        if permission_error: return permission_error
        try:
            record: dict = {"id": record_id}
            for field in ("First_Name", "Last_Name", "Email", "Phone"):
                if inp.get(field) is not None:
                    record[field] = inp[field]
            resp = httpx.put(
                f"{_BASE}/Contacts",
                headers=self._auth_headers,
                json={"data": [record]},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"result": data.get("data", [])})
        except Exception as e:
            return _handle_error("zoho_crm_update_contact", e)

    def create_lead(self, inp: dict) -> str:
        permission_error, last_name, company = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_create_lead", inp, "Last_Name", "Company")
        if permission_error: return permission_error
        try:
            record: dict = {"Last_Name": last_name, "Company": company}
            for field in ("First_Name", "Email", "Phone", "Lead_Source"):
                if inp.get(field):
                    record[field] = inp[field]
            resp = httpx.post(
                f"{_BASE}/Leads",
                headers=self._auth_headers,
                json={"data": [record]},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"result": data.get("data", [])})
        except Exception as e:
            return _handle_error("zoho_crm_create_lead", e)

    def update_lead(self, inp: dict) -> str:
        permission_error, record_id = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_update_lead", inp, "id")
        if permission_error: return permission_error
        try:
            record: dict = {"id": record_id}
            for field in ("First_Name", "Last_Name", "Email", "Phone", "Company", "Lead_Source", "Lead_Status"):
                if inp.get(field) is not None:
                    record[field] = inp[field]
            resp = httpx.put(
                f"{_BASE}/Leads",
                headers=self._auth_headers,
                json={"data": [record]},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"result": data.get("data", [])})
        except Exception as e:
            return _handle_error("zoho_crm_update_lead", e)

    def create_deal(self, inp: dict) -> str:
        permission_error, deal_name, stage = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_create_deal", inp, "Deal_Name", "Stage")
        if permission_error: return permission_error
        try:
            record: dict = {"Deal_Name": deal_name, "Stage": stage}
            for field in ("Account_Name", "Amount", "Closing_Date"):
                if inp.get(field) is not None:
                    record[field] = inp[field]
            resp = httpx.post(
                f"{_BASE}/Deals",
                headers=self._auth_headers,
                json={"data": [record]},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"result": data.get("data", [])})
        except Exception as e:
            return _handle_error("zoho_crm_create_deal", e)

    def update_deal(self, inp: dict) -> str:
        permission_error, record_id = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_update_deal", inp, "id")
        if permission_error: return permission_error
        try:
            record: dict = {"id": record_id}
            for field in ("Deal_Name", "Stage", "Amount", "Closing_Date", "Account_Name", "Probability"):
                if inp.get(field) is not None:
                    record[field] = inp[field]
            resp = httpx.put(
                f"{_BASE}/Deals",
                headers=self._auth_headers,
                json={"data": [record]},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"result": data.get("data", [])})
        except Exception as e:
            return _handle_error("zoho_crm_update_deal", e)

    def delete_record(self, inp: dict) -> str:
        permission_error, module, record_id = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_delete_record", inp, "module", "id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(
                f"{_BASE}/{module}",
                headers=self._auth_headers,
                params={"ids": record_id},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"result": data.get("data", [])})
        except Exception as e:
            return _handle_error("zoho_crm_delete_record", e)

    def create_task(self, inp: dict) -> str:
        permission_error, subject = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_create_task", inp, "Subject")
        if permission_error: return permission_error
        try:
            record: dict = {"Subject": subject}
            for field in ("Status", "Due_Date", "Description", "Priority"):
                if inp.get(field) is not None:
                    record[field] = inp[field]
            resp = httpx.post(
                f"{_BASE}/Tasks",
                headers=self._auth_headers,
                json={"data": [record]},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"result": data.get("data", [])})
        except Exception as e:
            return _handle_error("zoho_crm_create_task", e)

    def coql_query(self, inp: dict) -> str:
        permission_error, select_query = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_coql_query", inp, "select_query")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/coql",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"select_query": select_query},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"records": data.get("data", []), "info": data.get("info", {})})
        except Exception as e:
            return _handle_error("zoho_crm_coql_query", e)

    def get_organization(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_get_organization", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/org", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            org = (data.get("org") or [{}])[0]
            return json.dumps({
                "company_name": org.get("company_name"),
                "domain_name": org.get("domain_name"),
                "currency": org.get("currency"),
                "time_zone": org.get("time_zone"),
                "country": org.get("country"),
                "website": org.get("website"),
            })
        except Exception as e:
            return _handle_error("zoho_crm_get_organization", e)

    def create_account(self, inp: dict) -> str:
        permission_error, account_name = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_create_account", inp, "Account_Name")
        if permission_error: return permission_error
        try:
            record: dict = {"Account_Name": account_name}
            for field in ("Website", "Phone", "Industry", "Annual_Revenue", "Billing_City", "Billing_Country"):
                if inp.get(field) is not None:
                    record[field] = inp[field]
            resp = httpx.post(f"{_BASE}/Accounts", headers=self._auth_headers, json={"data": [record]}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"result": data.get("data", [])})
        except Exception as e:
            return _handle_error("zoho_crm_create_account", e)

    def update_account(self, inp: dict) -> str:
        permission_error, record_id = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_update_account", inp, "id")
        if permission_error: return permission_error
        try:
            record: dict = {"id": record_id}
            for field in ("Account_Name", "Website", "Phone", "Industry", "Annual_Revenue", "Billing_City", "Billing_Country"):
                if inp.get(field) is not None:
                    record[field] = inp[field]
            resp = httpx.put(f"{_BASE}/Accounts", headers=self._auth_headers, json={"data": [record]}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"result": data.get("data", [])})
        except Exception as e:
            return _handle_error("zoho_crm_update_account", e)

    def list_notes(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_list_notes", inp)
        if permission_error: return permission_error
        try:
            module = inp.get("module")
            record_id = inp.get("record_id")
            params = {"page": inp.get("page", 1), "per_page": min(inp.get("per_page", 20), 200)}
            if module and record_id:
                url = f"{_BASE}/{module}/{record_id}/Notes"
            else:
                url = f"{_BASE}/Notes"
            resp = httpx.get(url, headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"notes": data.get("data", []), "info": data.get("info", {})})
        except Exception as e:
            return _handle_error("zoho_crm_list_notes", e)

    def add_note(self, inp: dict) -> str:
        permission_error, module, record_id, content = self._check(self.agent_id, self.PROVIDER_ID, "zoho_crm_add_note", inp, "module", "record_id", "content")
        if permission_error: return permission_error
        try:
            body = {
                "data": [{
                    "Parent_Id": record_id,
                    "se_module": module,
                    "Note_Content": content,
                    "Note_Title": inp.get("title", ""),
                }]
            }
            resp = httpx.post(
                f"{_BASE}/{module}/{record_id}/Notes",
                headers=self._auth_headers,
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"result": data.get("data", [])})
        except Exception as e:
            return _handle_error("zoho_crm_add_note", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_list_contacts",
                    "description": "List contacts from Zoho CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                            "per_page": {"type": "integer", "description": "Records per page, max 200 (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_list_leads",
                    "description": "List leads from Zoho CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                            "per_page": {"type": "integer", "description": "Records per page, max 200 (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_list_accounts",
                    "description": "List accounts (companies) from Zoho CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                            "per_page": {"type": "integer", "description": "Records per page, max 200 (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_list_deals",
                    "description": "List deals/opportunities from Zoho CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                            "per_page": {"type": "integer", "description": "Records per page, max 200 (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_list_tasks",
                    "description": "List tasks from Zoho CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                            "per_page": {"type": "integer", "description": "Records per page, max 200 (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_list_users",
                    "description": "List users in the Zoho CRM organization.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "description": "User filter type: AllUsers, ActiveUsers, DeactiveUsers, ConfirmedUsers, AdminUsers (default AllUsers).",
                            }
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_list_modules",
                    "description": "List all available CRM modules in the Zoho CRM account.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_search_records",
                    "description": "Search records in any Zoho CRM module using criteria.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "module": {"type": "string", "description": "Module API name to search (e.g. Contacts, Leads, Deals)."},
                            "criteria": {"type": "string", "description": "Search criteria in Zoho format, e.g. '(Email:equals:test@example.com)' or '(Last_Name:contains:Smith)'."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                            "per_page": {"type": "integer", "description": "Records per page, max 200 (default 20)."},
                        },
                        "required": ["module", "criteria"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_get_record",
                    "description": "Retrieve a single record by ID from any Zoho CRM module.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "module": {"type": "string", "description": "Module name (e.g. Contacts, Leads, Accounts, Deals)."},
                            "id": {"type": "string", "description": "Record ID to retrieve."},
                        },
                        "required": ["module", "id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_create_contact",
                    "description": "Create a new contact in Zoho CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "Last_Name": {"type": "string", "description": "Contact's last name (required)."},
                            "First_Name": {"type": "string", "description": "Contact's first name."},
                            "Email": {"type": "string", "description": "Contact's email address."},
                            "Phone": {"type": "string", "description": "Contact's phone number."},
                            "Account_Name": {"type": "string", "description": "Name of the associated account/company."},
                        },
                        "required": ["Last_Name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_update_contact",
                    "description": "Update an existing contact in Zoho CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Record ID of the contact to update."},
                            "First_Name": {"type": "string", "description": "Updated first name."},
                            "Last_Name": {"type": "string", "description": "Updated last name."},
                            "Email": {"type": "string", "description": "Updated email address."},
                            "Phone": {"type": "string", "description": "Updated phone number."},
                        },
                        "required": ["id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_create_lead",
                    "description": "Create a new lead in Zoho CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "Last_Name": {"type": "string", "description": "Lead's last name (required)."},
                            "Company": {"type": "string", "description": "Lead's company name (required)."},
                            "First_Name": {"type": "string", "description": "Lead's first name."},
                            "Email": {"type": "string", "description": "Lead's email address."},
                            "Phone": {"type": "string", "description": "Lead's phone number."},
                            "Lead_Source": {"type": "string", "description": "Source of the lead (e.g. Web, Cold Call, Advertisement)."},
                        },
                        "required": ["Last_Name", "Company"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_update_lead",
                    "description": "Update an existing lead in Zoho CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Record ID of the lead to update."},
                            "First_Name": {"type": "string", "description": "Updated first name."},
                            "Last_Name": {"type": "string", "description": "Updated last name."},
                            "Email": {"type": "string", "description": "Updated email address."},
                            "Phone": {"type": "string", "description": "Updated phone number."},
                            "Company": {"type": "string", "description": "Updated company name."},
                            "Lead_Source": {"type": "string", "description": "Updated lead source."},
                            "Lead_Status": {"type": "string", "description": "Updated lead status."},
                        },
                        "required": ["id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_create_deal",
                    "description": "Create a new deal/opportunity in Zoho CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "Deal_Name": {"type": "string", "description": "Name of the deal (required)."},
                            "Stage": {"type": "string", "description": "Deal stage (required), e.g. Qualification, Needs Analysis, Closed Won."},
                            "Account_Name": {"type": "string", "description": "Name of the associated account."},
                            "Amount": {"type": "number", "description": "Deal amount/value."},
                            "Closing_Date": {"type": "string", "description": "Expected closing date in YYYY-MM-DD format."},
                        },
                        "required": ["Deal_Name", "Stage"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_update_deal",
                    "description": "Update an existing deal/opportunity in Zoho CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Record ID of the deal to update."},
                            "Deal_Name": {"type": "string", "description": "Updated deal name."},
                            "Stage": {"type": "string", "description": "Updated deal stage."},
                            "Amount": {"type": "number", "description": "Updated deal amount."},
                            "Closing_Date": {"type": "string", "description": "Updated closing date in YYYY-MM-DD format."},
                            "Account_Name": {"type": "string", "description": "Updated associated account name."},
                            "Probability": {"type": "number", "description": "Updated probability percentage (0-100)."},
                        },
                        "required": ["id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_delete_record",
                    "description": "Delete a record from any Zoho CRM module by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "module": {"type": "string", "description": "Module name (e.g. Contacts, Leads, Accounts, Deals)."},
                            "id": {"type": "string", "description": "Record ID to delete."},
                        },
                        "required": ["module", "id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_create_task",
                    "description": "Create a new task in Zoho CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "Subject": {"type": "string", "description": "Task subject/title (required)."},
                            "Status": {"type": "string", "description": "Task status (e.g. Not Started, In Progress, Completed, Deferred, Waiting for input)."},
                            "Due_Date": {"type": "string", "description": "Due date in YYYY-MM-DD format."},
                            "Description": {"type": "string", "description": "Task description or notes."},
                            "Priority": {"type": "string", "description": "Task priority (e.g. High, Medium, Low)."},
                        },
                        "required": ["Subject"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_coql_query",
                    "description": "Run a COQL (SQL-like) query against Zoho CRM for advanced filtering, joins, or aggregations beyond basic list/search.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "select_query": {"type": "string", "description": "COQL SELECT statement, e.g. 'SELECT id, Last_Name, Email FROM Contacts WHERE Email is not null LIMIT 20'."},
                        },
                        "required": ["select_query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_get_organization",
                    "description": "Get details about the connected Zoho CRM organization (company name, domain, currency, timezone, country).",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_create_account",
                    "description": "Create a new account (company) in Zoho CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "Account_Name": {"type": "string", "description": "Account/company name (required)."},
                            "Website": {"type": "string", "description": "Company website."},
                            "Phone": {"type": "string", "description": "Company phone number."},
                            "Industry": {"type": "string", "description": "Industry."},
                            "Annual_Revenue": {"type": "number", "description": "Annual revenue."},
                            "Billing_City": {"type": "string", "description": "Billing city."},
                            "Billing_Country": {"type": "string", "description": "Billing country."},
                        },
                        "required": ["Account_Name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_update_account",
                    "description": "Update an existing account (company) in Zoho CRM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Record ID of the account to update."},
                            "Account_Name": {"type": "string", "description": "Updated account name."},
                            "Website": {"type": "string", "description": "Updated website."},
                            "Phone": {"type": "string", "description": "Updated phone number."},
                            "Industry": {"type": "string", "description": "Updated industry."},
                            "Annual_Revenue": {"type": "number", "description": "Updated annual revenue."},
                            "Billing_City": {"type": "string", "description": "Updated billing city."},
                            "Billing_Country": {"type": "string", "description": "Updated billing country."},
                        },
                        "required": ["id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_list_notes",
                    "description": "List notes in Zoho CRM, optionally scoped to a specific record.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "module": {"type": "string", "description": "Module API name (e.g. Contacts, Leads, Deals) to scope notes to a record. Omit to list all notes."},
                            "record_id": {"type": "string", "description": "Record ID within the module to scope notes to. Required if 'module' is set."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                            "per_page": {"type": "integer", "description": "Records per page, max 200 (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoho_crm_add_note",
                    "description": "Add a note to a specific Zoho CRM record.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "module": {"type": "string", "description": "Module API name (e.g. Contacts, Leads, Deals, Accounts)."},
                            "record_id": {"type": "string", "description": "Record ID to attach the note to."},
                            "content": {"type": "string", "description": "Note content/body text."},
                            "title": {"type": "string", "description": "Optional note title."},
                        },
                        "required": ["module", "record_id", "content"],
                    },
                },
            },
        ]
        callables = {
            "zoho_crm_list_contacts": self.list_contacts,
            "zoho_crm_list_leads": self.list_leads,
            "zoho_crm_list_accounts": self.list_accounts,
            "zoho_crm_list_deals": self.list_deals,
            "zoho_crm_list_tasks": self.list_tasks,
            "zoho_crm_list_users": self.list_users,
            "zoho_crm_list_modules": self.list_modules,
            "zoho_crm_search_records": self.search_records,
            "zoho_crm_get_record": self.get_record,
            "zoho_crm_create_contact": self.create_contact,
            "zoho_crm_update_contact": self.update_contact,
            "zoho_crm_create_lead": self.create_lead,
            "zoho_crm_update_lead": self.update_lead,
            "zoho_crm_create_deal": self.create_deal,
            "zoho_crm_update_deal": self.update_deal,
            "zoho_crm_delete_record": self.delete_record,
            "zoho_crm_create_task": self.create_task,
            "zoho_crm_coql_query": self.coql_query,
            "zoho_crm_get_organization": self.get_organization,
            "zoho_crm_create_account": self.create_account,
            "zoho_crm_update_account": self.update_account,
            "zoho_crm_list_notes": self.list_notes,
            "zoho_crm_add_note": self.add_note,
        }
        return tools, callables

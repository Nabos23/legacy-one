import json
import httpx

from ai.connectors.base import BaseConnector

_API_VERSION = "v59.0"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Salesforce account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Salesforce connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class SalesforceConnector(BaseConnector):

    PROVIDER_ID = "salesforce"

    def _get_instance_url(self) -> str:
        try:
            resp = httpx.get("https://login.salesforce.com/services/oauth2/userinfo", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return resp.json().get("profile", "").split("/id/")[0] or "https://login.salesforce.com"
        except Exception:
            return "https://login.salesforce.com"

    def _query(self, soql: str, instance_url: str) -> dict:
        resp = httpx.get(
            f"{instance_url}/services/data/{_API_VERSION}/query",
            headers=self._auth_headers,
            params={"q": soql},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def get_user_info(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "salesforce_get_user_info", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get("https://login.salesforce.com/services/oauth2/userinfo", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"name": data.get("name"), "email": data.get("email"), "organization_id": data.get("organization_id")})
        except Exception as e:
            return _handle_error("salesforce_get_user_info", e)

    def list_leads(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "salesforce_list_leads", inp)
        if permission_error: return permission_error
        try:
            limit = inp.get("limit", 20)
            soql = f"SELECT Id, FirstName, LastName, Email, Company, Status, CreatedDate FROM Lead ORDER BY CreatedDate DESC LIMIT {limit}"
            instance_url = self._get_instance_url()
            data = self._query(soql, instance_url)
            return json.dumps([{k: v for k, v in r.items() if k != "attributes"} for r in data.get("records", [])])
        except Exception as e:
            return _handle_error("salesforce_list_leads", e)

    def list_opportunities(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "salesforce_list_opportunities", inp)
        if permission_error: return permission_error
        try:
            limit = inp.get("limit", 20)
            soql = f"SELECT Id, Name, Amount, StageName, CloseDate, AccountId FROM Opportunity ORDER BY CloseDate ASC LIMIT {limit}"
            instance_url = self._get_instance_url()
            data = self._query(soql, instance_url)
            return json.dumps([{k: v for k, v in r.items() if k != "attributes"} for r in data.get("records", [])])
        except Exception as e:
            return _handle_error("salesforce_list_opportunities", e)

    def list_accounts(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "salesforce_list_accounts", inp)
        if permission_error: return permission_error
        try:
            limit = inp.get("limit", 20)
            soql = f"SELECT Id, Name, Industry, Type, Phone, Website FROM Account ORDER BY Name ASC LIMIT {limit}"
            instance_url = self._get_instance_url()
            data = self._query(soql, instance_url)
            return json.dumps([{k: v for k, v in r.items() if k != "attributes"} for r in data.get("records", [])])
        except Exception as e:
            return _handle_error("salesforce_list_accounts", e)

    def list_contacts(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "salesforce_list_contacts", inp)
        if permission_error: return permission_error
        try:
            limit = inp.get("limit", 20)
            soql = f"SELECT Id, FirstName, LastName, Email, Phone, AccountId FROM Contact ORDER BY LastName ASC LIMIT {limit}"
            instance_url = self._get_instance_url()
            data = self._query(soql, instance_url)
            return json.dumps([{k: v for k, v in r.items() if k != "attributes"} for r in data.get("records", [])])
        except Exception as e:
            return _handle_error("salesforce_list_contacts", e)

    def run_soql(self, inp: dict) -> str:
        permission_error, soql = self._check(self.agent_id, self.PROVIDER_ID, "salesforce_run_soql", inp, "soql")
        if permission_error: return permission_error
        try:
            instance_url = self._get_instance_url()
            data = self._query(soql, instance_url)
            records = [{k: v for k, v in r.items() if k != "attributes"} for r in data.get("records", [])]
            return json.dumps({"totalSize": data.get("totalSize"), "records": records})
        except Exception as e:
            return _handle_error("salesforce_run_soql", e)

    def create_record(self, inp: dict) -> str:
        permission_error, object_type, fields = self._check(self.agent_id, self.PROVIDER_ID, "salesforce_create_record", inp, "object_type", "fields")
        if permission_error: return permission_error
        try:
            instance_url = self._get_instance_url()
            resp = httpx.post(
                f"{instance_url}/services/data/{_API_VERSION}/sobjects/{object_type}/",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=fields,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "success": data.get("success", True)})
        except Exception as e:
            return _handle_error("salesforce_create_record", e)

    def update_record(self, inp: dict) -> str:
        permission_error, object_type, record_id, fields = self._check(self.agent_id, self.PROVIDER_ID, "salesforce_update_record", inp, "object_type", "record_id", "fields")
        if permission_error: return permission_error
        try:
            instance_url = self._get_instance_url()
            resp = httpx.patch(
                f"{instance_url}/services/data/{_API_VERSION}/sobjects/{object_type}/{record_id}",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=fields,
                timeout=15,
            )
            resp.raise_for_status()
            # Salesforce returns 204 No Content on success
            return json.dumps({"updated": True, "id": record_id})
        except Exception as e:
            return _handle_error("salesforce_update_record", e)

    def delete_record(self, inp: dict) -> str:
        permission_error, object_type, record_id = self._check(self.agent_id, self.PROVIDER_ID, "salesforce_delete_record", inp, "object_type", "record_id")
        if permission_error: return permission_error
        try:
            instance_url = self._get_instance_url()
            resp = httpx.delete(
                f"{instance_url}/services/data/{_API_VERSION}/sobjects/{object_type}/{record_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"deleted": True, "id": record_id})
        except Exception as e:
            return _handle_error("salesforce_delete_record", e)

    def get_record(self, inp: dict) -> str:
        permission_error, object_type, record_id = self._check(self.agent_id, self.PROVIDER_ID, "salesforce_get_record", inp, "object_type", "record_id")
        if permission_error: return permission_error
        try:
            instance_url = self._get_instance_url()
            url = f"{instance_url}/services/data/{_API_VERSION}/sobjects/{object_type}/{record_id}"
            params = {}
            fields = inp.get("fields")
            if fields:
                params["fields"] = ",".join(fields)
            resp = httpx.get(url, headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            # Strip the attributes metadata key Salesforce always includes
            return json.dumps({k: v for k, v in data.items() if k != "attributes"})
        except Exception as e:
            return _handle_error("salesforce_get_record", e)

    def describe_object(self, inp: dict) -> str:
        permission_error, object_type = self._check(self.agent_id, self.PROVIDER_ID, "salesforce_describe_object", inp, "object_type")
        if permission_error: return permission_error
        try:
            instance_url = self._get_instance_url()
            resp = httpx.get(
                f"{instance_url}/services/data/{_API_VERSION}/sobjects/{object_type}/describe/",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            fields = [
                {"name": f["name"], "label": f["label"], "type": f["type"]}
                for f in data.get("fields", [])
            ]
            return json.dumps({
                "name": data.get("name"),
                "label": data.get("label"),
                "fields": fields,
                "createable": data.get("createable"),
                "updateable": data.get("updateable"),
                "deletable": data.get("deletable"),
            })
        except Exception as e:
            return _handle_error("salesforce_describe_object", e)

    def search(self, inp: dict) -> str:
        permission_error, term = self._check(self.agent_id, self.PROVIDER_ID, "salesforce_search", inp, "term")
        if permission_error: return permission_error
        try:
            returning = inp.get("returning", "Lead(Id, Name), Contact(Id, Name), Account(Id, Name), Opportunity(Id, Name)")
            sosl = f"FIND {{{term}}} RETURNING {returning}"
            instance_url = self._get_instance_url()
            resp = httpx.get(
                f"{instance_url}/services/data/{_API_VERSION}/search",
                headers=self._auth_headers,
                params={"q": sosl},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            results = [{k: v for k, v in r.items() if k != "attributes"} for r in data.get("searchRecords", [])]
            return json.dumps({"results": results, "count": len(results)})
        except Exception as e:
            return _handle_error("salesforce_search", e)

    def get_limits(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "salesforce_get_limits", inp)
        if permission_error: return permission_error
        try:
            instance_url = self._get_instance_url()
            resp = httpx.get(f"{instance_url}/services/data/{_API_VERSION}/limits", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            limits = {
                k: {"Max": v.get("Max"), "Remaining": v.get("Remaining")}
                for k, v in data.items()
                if isinstance(v, dict) and "Max" in v
            }
            return json.dumps(limits)
        except Exception as e:
            return _handle_error("salesforce_get_limits", e)

    def list_tasks(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "salesforce_list_tasks", inp)
        if permission_error: return permission_error
        try:
            limit = inp.get("limit", 20)
            soql = f"SELECT Id, Subject, Status, Priority, ActivityDate, WhoId, WhatId FROM Task ORDER BY ActivityDate DESC LIMIT {limit}"
            instance_url = self._get_instance_url()
            data = self._query(soql, instance_url)
            return json.dumps([{k: v for k, v in r.items() if k != "attributes"} for r in data.get("records", [])])
        except Exception as e:
            return _handle_error("salesforce_list_tasks", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "salesforce_get_user_info",
                    "description": "Get info about the connected Salesforce user and organization.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "salesforce_list_leads",
                    "description": "List leads from Salesforce.",
                    "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "description": "Max leads to return (default 20)."}}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "salesforce_list_opportunities",
                    "description": "List opportunities/deals from Salesforce.",
                    "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "description": "Max opportunities (default 20)."}}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "salesforce_list_accounts",
                    "description": "List accounts from Salesforce.",
                    "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "description": "Max accounts (default 20)."}}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "salesforce_list_contacts",
                    "description": "List contacts from Salesforce.",
                    "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "description": "Max contacts (default 20)."}}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "salesforce_run_soql",
                    "description": "Run a custom SOQL query against Salesforce.",
                    "parameters": {
                        "type": "object",
                        "properties": {"soql": {"type": "string", "description": "SOQL query string (e.g. SELECT Id, Name FROM Account LIMIT 10)."}},
                        "required": ["soql"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "salesforce_create_record",
                    "description": "Create a new record in Salesforce (e.g. Lead, Contact, Account, Opportunity).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "object_type": {"type": "string", "description": "Salesforce object type, e.g. 'Lead', 'Contact', 'Account', 'Opportunity'."},
                            "fields": {
                                "type": "object",
                                "description": "Dict of field names to values for the new record (e.g. {\"FirstName\": \"Jane\", \"LastName\": \"Doe\", \"Company\": \"Acme\"}).",
                                "additionalProperties": True,
                            },
                        },
                        "required": ["object_type", "fields"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "salesforce_update_record",
                    "description": "Update an existing Salesforce record by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "object_type": {"type": "string", "description": "Salesforce object type, e.g. 'Lead', 'Contact', 'Account', 'Opportunity'."},
                            "record_id": {"type": "string", "description": "Salesforce record ID (18-character string)."},
                            "fields": {
                                "type": "object",
                                "description": "Dict of field names to new values to update (only include fields to change).",
                                "additionalProperties": True,
                            },
                        },
                        "required": ["object_type", "record_id", "fields"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "salesforce_delete_record",
                    "description": "Delete a Salesforce record by object type and ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "object_type": {"type": "string", "description": "Salesforce object type, e.g. 'Lead', 'Contact', 'Account'."},
                            "record_id": {"type": "string", "description": "Salesforce record ID to delete."},
                        },
                        "required": ["object_type", "record_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "salesforce_get_record",
                    "description": "Fetch a single Salesforce record by object type and ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "object_type": {"type": "string", "description": "Salesforce object type, e.g. 'Lead', 'Contact', 'Account', 'Opportunity'."},
                            "record_id": {"type": "string", "description": "Salesforce record ID."},
                            "fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of specific field names to return. If omitted, all fields are returned.",
                            },
                        },
                        "required": ["object_type", "record_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "salesforce_describe_object",
                    "description": "Describe a Salesforce object: returns its fields, types, and whether it is createable/updateable/deletable.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "object_type": {"type": "string", "description": "Salesforce object type to describe, e.g. 'Lead', 'Contact', 'Account', 'Opportunity'."},
                        },
                        "required": ["object_type"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "salesforce_search",
                    "description": "Run a SOSL text search across multiple Salesforce object types at once (e.g. find a name/email across Leads, Contacts, Accounts, Opportunities).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "term": {"type": "string", "description": "Text to search for."},
                            "returning": {"type": "string", "description": "SOSL RETURNING clause specifying objects/fields, e.g. 'Lead(Id, Name), Contact(Id, Name)'. Defaults to common objects."},
                        },
                        "required": ["term"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "salesforce_get_limits",
                    "description": "Get the connected Salesforce org's current API usage limits (max and remaining for each limit type).",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "salesforce_list_tasks",
                    "description": "List tasks (to-dos, calls, etc.) from Salesforce.",
                    "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "description": "Max tasks to return (default 20)."}}, "required": []},
                },
            },
        ]
        callables = {
            "salesforce_get_user_info": self.get_user_info,
            "salesforce_list_leads": self.list_leads,
            "salesforce_list_opportunities": self.list_opportunities,
            "salesforce_list_accounts": self.list_accounts,
            "salesforce_list_contacts": self.list_contacts,
            "salesforce_run_soql": self.run_soql,
            "salesforce_create_record": self.create_record,
            "salesforce_update_record": self.update_record,
            "salesforce_delete_record": self.delete_record,
            "salesforce_get_record": self.get_record,
            "salesforce_describe_object": self.describe_object,
            "salesforce_search": self.search,
            "salesforce_get_limits": self.get_limits,
            "salesforce_list_tasks": self.list_tasks,
        }
        return tools, callables

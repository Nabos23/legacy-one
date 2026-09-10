import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.airtable.com/v0"
_META_BASE = "https://api.airtable.com/v0/meta"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Airtable account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Airtable connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class AirtableConnector(BaseConnector):

    PROVIDER_ID = "airtable"

    def list_bases(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "airtable_list_bases", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_META_BASE}/bases", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            bases = [{"id": b["id"], "name": b["name"], "permissionLevel": b.get("permissionLevel")} for b in data.get("bases", [])]
            return json.dumps(bases)
        except Exception as e:
            return _handle_error("airtable_list_bases", e)

    def list_tables(self, inp: dict) -> str:
        permission_error, base_id = self._check(self.agent_id, self.PROVIDER_ID, "airtable_list_tables", inp, "base_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_META_BASE}/bases/{base_id}/tables", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            tables = [{"id": t["id"], "name": t["name"], "fields": [f["name"] for f in t.get("fields", [])]} for t in data.get("tables", [])]
            return json.dumps(tables)
        except Exception as e:
            return _handle_error("airtable_list_tables", e)

    def list_records(self, inp: dict) -> str:
        permission_error, base_id, table_name = self._check(self.agent_id, self.PROVIDER_ID, "airtable_list_records", inp, "base_id", "table_name")
        if permission_error: return permission_error
        try:
            params = {"maxRecords": inp.get("max_records", 20)}
            if inp.get("filter_formula"):
                params["filterByFormula"] = inp["filter_formula"]
            if inp.get("sort_field"):
                params["sort[0][field]"] = inp["sort_field"]
                params["sort[0][direction]"] = inp.get("sort_direction", "asc")
            resp = httpx.get(f"{_BASE}/{base_id}/{table_name}", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            records = [{"id": r["id"], **r.get("fields", {})} for r in data.get("records", [])]
            return json.dumps({"records": records, "offset": data.get("offset")})
        except Exception as e:
            return _handle_error("airtable_list_records", e)

    def get_record(self, inp: dict) -> str:
        permission_error, base_id, table_name, record_id = self._check(self.agent_id, self.PROVIDER_ID, "airtable_get_record", inp, "base_id", "table_name", "record_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/{base_id}/{table_name}/{record_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], **data.get("fields", {})})
        except Exception as e:
            return _handle_error("airtable_get_record", e)

    def create_record(self, inp: dict) -> str:
        permission_error, base_id, table_name, fields = self._check(self.agent_id, self.PROVIDER_ID, "airtable_create_record", inp, "base_id", "table_name", "fields")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(f"{_BASE}/{base_id}/{table_name}", headers=headers, json={"fields": fields}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], **data.get("fields", {})})
        except Exception as e:
            return _handle_error("airtable_create_record", e)

    def update_record(self, inp: dict) -> str:
        permission_error, base_id, table_name, record_id, fields = self._check(self.agent_id, self.PROVIDER_ID, "airtable_update_record", inp, "base_id", "table_name", "record_id", "fields")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.patch(f"{_BASE}/{base_id}/{table_name}/{record_id}", headers=headers, json={"fields": fields}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], **data.get("fields", {})})
        except Exception as e:
            return _handle_error("airtable_update_record", e)

    def delete_record(self, inp: dict) -> str:
        permission_error, base_id, table_name, record_id = self._check(self.agent_id, self.PROVIDER_ID, "airtable_delete_record", inp, "base_id", "table_name", "record_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/{base_id}/{table_name}/{record_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"deleted": True, "id": record_id})
        except Exception as e:
            return _handle_error("airtable_delete_record", e)

    def create_records(self, inp: dict) -> str:
        permission_error, base_id, table_name, records = self._check(self.agent_id, self.PROVIDER_ID, "airtable_create_records", inp, "base_id", "table_name", "records")
        if permission_error: return permission_error
        if len(records) > 10:
            return "Error: a maximum of 10 records can be created per request. Split into multiple calls."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            payload = {"records": [{"fields": r} for r in records]}
            resp = httpx.post(f"{_BASE}/{base_id}/{table_name}", headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            created = [{"id": r["id"], **r.get("fields", {})} for r in data.get("records", [])]
            return json.dumps({"records": created, "count": len(created)})
        except Exception as e:
            return _handle_error("airtable_create_records", e)

    def update_records(self, inp: dict) -> str:
        permission_error, base_id, table_name, records = self._check(self.agent_id, self.PROVIDER_ID, "airtable_update_records", inp, "base_id", "table_name", "records")
        if permission_error: return permission_error
        if len(records) > 10:
            return "Error: a maximum of 10 records can be updated per request. Split into multiple calls."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            payload = {"records": records}
            resp = httpx.patch(f"{_BASE}/{base_id}/{table_name}", headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            updated = [{"id": r["id"], **r.get("fields", {})} for r in data.get("records", [])]
            return json.dumps({"records": updated, "count": len(updated)})
        except Exception as e:
            return _handle_error("airtable_update_records", e)

    def delete_records(self, inp: dict) -> str:
        permission_error, base_id, table_name, record_ids = self._check(self.agent_id, self.PROVIDER_ID, "airtable_delete_records", inp, "base_id", "table_name", "record_ids")
        if permission_error: return permission_error
        if len(record_ids) > 10:
            return "Error: a maximum of 10 records can be deleted per request. Split into multiple calls."
        try:
            params = [("records[]", rid) for rid in record_ids]
            resp = httpx.delete(f"{_BASE}/{base_id}/{table_name}", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"deleted": [r["id"] for r in data.get("records", []) if r.get("deleted")]})
        except Exception as e:
            return _handle_error("airtable_delete_records", e)

    def create_table(self, inp: dict) -> str:
        permission_error, base_id, name, fields = self._check(self.agent_id, self.PROVIDER_ID, "airtable_create_table", inp, "base_id", "name", "fields")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            payload: dict = {"name": name, "fields": fields}
            if inp.get("description"):
                payload["description"] = inp["description"]
            resp = httpx.post(f"{_META_BASE}/bases/{base_id}/tables", headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "name": data.get("name"), "fields": [f["name"] for f in data.get("fields", [])]})
        except Exception as e:
            return _handle_error("airtable_create_table", e)

    def create_field(self, inp: dict) -> str:
        permission_error, base_id, table_id, name, field_type = self._check(self.agent_id, self.PROVIDER_ID, "airtable_create_field", inp, "base_id", "table_id", "name", "type")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            payload: dict = {"name": name, "type": field_type}
            if inp.get("options"):
                payload["options"] = inp["options"]
            if inp.get("description"):
                payload["description"] = inp["description"]
            resp = httpx.post(f"{_META_BASE}/bases/{base_id}/tables/{table_id}/fields", headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "name": data.get("name"), "type": data.get("type")})
        except Exception as e:
            return _handle_error("airtable_create_field", e)

    def list_webhooks(self, inp: dict) -> str:
        permission_error, base_id = self._check(self.agent_id, self.PROVIDER_ID, "airtable_list_webhooks", inp, "base_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/bases/{base_id}/webhooks", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            webhooks = [
                {"id": w["id"], "notificationUrl": w.get("notificationUrl"), "isHookEnabled": w.get("isHookEnabled")}
                for w in data.get("webhooks", [])
            ]
            return json.dumps({"webhooks": webhooks, "count": len(webhooks)})
        except Exception as e:
            return _handle_error("airtable_list_webhooks", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "airtable_list_bases",
                    "description": "List all Airtable bases the user has access to.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "airtable_list_tables",
                    "description": "List all tables in an Airtable base.",
                    "parameters": {"type": "object", "properties": {"base_id": {"type": "string", "description": "The Airtable base ID."}}, "required": ["base_id"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "airtable_list_records",
                    "description": "List records from an Airtable table.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_id": {"type": "string", "description": "The Airtable base ID."},
                            "table_name": {"type": "string", "description": "The table name."},
                            "max_records": {"type": "integer", "description": "Max records to return (default 20)."},
                            "filter_formula": {"type": "string", "description": "Airtable formula to filter records."},
                            "sort_field": {"type": "string", "description": "Field name to sort by."},
                            "sort_direction": {"type": "string", "description": "'asc' or 'desc' (default asc)."},
                        },
                        "required": ["base_id", "table_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "airtable_get_record",
                    "description": "Get a specific record from an Airtable table.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_id": {"type": "string", "description": "The Airtable base ID."},
                            "table_name": {"type": "string", "description": "The table name."},
                            "record_id": {"type": "string", "description": "The record ID."},
                        },
                        "required": ["base_id", "table_name", "record_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "airtable_create_record",
                    "description": "Create a new record in an Airtable table.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_id": {"type": "string", "description": "The Airtable base ID."},
                            "table_name": {"type": "string", "description": "The table name."},
                            "fields": {"type": "object", "description": "Key-value pairs of field names and values."},
                        },
                        "required": ["base_id", "table_name", "fields"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "airtable_update_record",
                    "description": "Update fields on an existing Airtable record.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_id": {"type": "string", "description": "The Airtable base ID."},
                            "table_name": {"type": "string", "description": "The table name."},
                            "record_id": {"type": "string", "description": "The record ID to update."},
                            "fields": {"type": "object", "description": "Fields to update."},
                        },
                        "required": ["base_id", "table_name", "record_id", "fields"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "airtable_delete_record",
                    "description": "Delete a record from an Airtable table.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_id": {"type": "string", "description": "The Airtable base ID."},
                            "table_name": {"type": "string", "description": "The table name."},
                            "record_id": {"type": "string", "description": "The record ID to delete."},
                        },
                        "required": ["base_id", "table_name", "record_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "airtable_create_records",
                    "description": "Batch-create up to 10 records in an Airtable table in a single request.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_id": {"type": "string", "description": "The Airtable base ID."},
                            "table_name": {"type": "string", "description": "The table name."},
                            "records": {"type": "array", "items": {"type": "object"}, "description": "Array of field dicts, one per record to create (max 10)."},
                        },
                        "required": ["base_id", "table_name", "records"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "airtable_update_records",
                    "description": "Batch-update up to 10 existing records in an Airtable table in a single request.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_id": {"type": "string", "description": "The Airtable base ID."},
                            "table_name": {"type": "string", "description": "The table name."},
                            "records": {
                                "type": "array",
                                "items": {"type": "object", "properties": {"id": {"type": "string"}, "fields": {"type": "object"}}},
                                "description": "Array of {id, fields} objects, one per record to update (max 10).",
                            },
                        },
                        "required": ["base_id", "table_name", "records"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "airtable_delete_records",
                    "description": "Batch-delete up to 10 records from an Airtable table in a single request.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_id": {"type": "string", "description": "The Airtable base ID."},
                            "table_name": {"type": "string", "description": "The table name."},
                            "record_ids": {"type": "array", "items": {"type": "string"}, "description": "Record IDs to delete (max 10)."},
                        },
                        "required": ["base_id", "table_name", "record_ids"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "airtable_create_table",
                    "description": "Create a new table in an Airtable base.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_id": {"type": "string", "description": "The Airtable base ID."},
                            "name": {"type": "string", "description": "Name of the new table."},
                            "description": {"type": "string", "description": "Optional table description."},
                            "fields": {
                                "type": "array",
                                "items": {"type": "object", "properties": {"name": {"type": "string"}, "type": {"type": "string"}}},
                                "description": "Array of {name, type} field definitions (Airtable field types e.g. singleLineText, number, checkbox).",
                            },
                        },
                        "required": ["base_id", "name", "fields"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "airtable_create_field",
                    "description": "Add a new field (column) to an existing Airtable table.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_id": {"type": "string", "description": "The Airtable base ID."},
                            "table_id": {"type": "string", "description": "The table ID (use airtable_list_tables to find it)."},
                            "name": {"type": "string", "description": "Field name."},
                            "type": {"type": "string", "description": "Airtable field type, e.g. singleLineText, number, checkbox, singleSelect."},
                            "options": {"type": "object", "description": "Type-specific field options (e.g. choices for singleSelect)."},
                            "description": {"type": "string", "description": "Optional field description."},
                        },
                        "required": ["base_id", "table_id", "name", "type"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "airtable_list_webhooks",
                    "description": "List webhooks configured on an Airtable base.",
                    "parameters": {
                        "type": "object",
                        "properties": {"base_id": {"type": "string", "description": "The Airtable base ID."}},
                        "required": ["base_id"],
                    },
                },
            },
        ]
        callables = {
            "airtable_list_bases": self.list_bases,
            "airtable_list_tables": self.list_tables,
            "airtable_list_records": self.list_records,
            "airtable_get_record": self.get_record,
            "airtable_create_record": self.create_record,
            "airtable_update_record": self.update_record,
            "airtable_delete_record": self.delete_record,
            "airtable_create_records": self.create_records,
            "airtable_update_records": self.update_records,
            "airtable_delete_records": self.delete_records,
            "airtable_create_table": self.create_table,
            "airtable_create_field": self.create_field,
            "airtable_list_webhooks": self.list_webhooks,
        }
        return tools, callables

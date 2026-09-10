import io
import json

import httpx
import openpyxl

from ai.connectors.base import BaseConnector

_DRIVE_BASE = "https://graph.microsoft.com/v1.0/me/drive"
_SEARCH_BASE = "https://graph.microsoft.com/v1.0/me/drive/root/search"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Microsoft Excel account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Excel connector with the required OAuth scopes."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class ExcelConnector(BaseConnector):
    """
    Microsoft Excel connector, backed by the Microsoft Graph Excel REST API operating
    on workbooks (.xlsx) stored in the connected account's OneDrive/SharePoint drive.
    """

    PROVIDER_ID = "excel"

    def _workbook_base(self, item_id: str) -> str:
        return f"{_DRIVE_BASE}/items/{item_id}/workbook"

    def _worksheet_ref(self, worksheet: str) -> str:
        return worksheet

    # ── Workbooks ─────────────────────────────────────────────────────────────

    def create_workbook(self, inp: dict) -> str:
        permission_error, name = self._check(self.agent_id, self.PROVIDER_ID, "excel_create_workbook", inp, "name")
        if permission_error: return permission_error
        if not name.lower().endswith(".xlsx"):
            name += ".xlsx"
        try:
            folder = inp.get("folder", "root")
            parent = "root" if folder == "root" else f"items/{folder}"
            wb = openpyxl.Workbook()
            buf = io.BytesIO()
            wb.save(buf)
            resp = httpx.put(
                f"{_DRIVE_BASE}/{parent}:/{name}:/content",
                headers={**self._auth_headers, "Content-Type": "application/octet-stream"},
                content=buf.getvalue(),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"item_id": data.get("id"), "name": data.get("name"), "web_url": data.get("webUrl")})
        except Exception as e:
            return _handle_error("excel_create_workbook", e)

    def list_workbooks(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "excel_list_workbooks", inp)
        if permission_error: return permission_error
        query = inp.get("query", "")
        try:
            if query:
                resp = httpx.get(
                    f"{_SEARCH_BASE}(q='{query}')",
                    headers=self._auth_headers,
                    params={"$select": "id,name,size,lastModifiedDateTime,webUrl", "$top": inp.get("limit", 25)},
                    timeout=15,
                )
            else:
                resp = httpx.get(
                    f"{_DRIVE_BASE}/root/children",
                    headers=self._auth_headers,
                    params={"$select": "id,name,size,lastModifiedDateTime,webUrl", "$top": inp.get("limit", 25)},
                    timeout=15,
                )
            resp.raise_for_status()
            items = [
                {"item_id": i["id"], "name": i["name"], "web_url": i.get("webUrl"), "modified": i.get("lastModifiedDateTime")}
                for i in resp.json().get("value", [])
                if i.get("name", "").lower().endswith(".xlsx")
            ]
            return json.dumps({"workbooks": items})
        except Exception as e:
            return _handle_error("excel_list_workbooks", e)

    def delete_workbook(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "excel_delete_workbook", inp, "item_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_DRIVE_BASE}/items/{item_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"deleted": True, "item_id": item_id})
        except Exception as e:
            return _handle_error("excel_delete_workbook", e)

    # ── Worksheets ────────────────────────────────────────────────────────────

    def list_worksheets(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "excel_list_worksheets", inp, "item_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._workbook_base(item_id)}/worksheets", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            sheets = [{"id": s.get("id"), "name": s.get("name"), "position": s.get("position")} for s in resp.json().get("value", [])]
            return json.dumps({"item_id": item_id, "worksheets": sheets})
        except Exception as e:
            return _handle_error("excel_list_worksheets", e)

    def add_worksheet(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "excel_add_worksheet", inp, "item_id")
        if permission_error: return permission_error
        name = inp.get("name", "")
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"name": name} if name else {}
            resp = httpx.post(f"{self._workbook_base(item_id)}/worksheets", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"item_id": item_id, "id": data.get("id"), "name": data.get("name")})
        except Exception as e:
            return _handle_error("excel_add_worksheet", e)

    def rename_worksheet(self, inp: dict) -> str:
        permission_error, item_id, worksheet, new_name = self._check(self.agent_id, self.PROVIDER_ID, "excel_rename_worksheet", inp, "item_id", "worksheet", "new_name")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.patch(
                f"{self._workbook_base(item_id)}/worksheets/{self._worksheet_ref(worksheet)}",
                headers=headers,
                json={"name": new_name},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"item_id": item_id, "renamed_to": new_name})
        except Exception as e:
            return _handle_error("excel_rename_worksheet", e)

    def delete_worksheet(self, inp: dict) -> str:
        permission_error, item_id, worksheet = self._check(self.agent_id, self.PROVIDER_ID, "excel_delete_worksheet", inp, "item_id", "worksheet")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(
                f"{self._workbook_base(item_id)}/worksheets/{self._worksheet_ref(worksheet)}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"item_id": item_id, "deleted_worksheet": worksheet})
        except Exception as e:
            return _handle_error("excel_delete_worksheet", e)

    # ── Ranges ────────────────────────────────────────────────────────────────

    def get_range(self, inp: dict) -> str:
        permission_error, item_id, worksheet, address = self._check(self.agent_id, self.PROVIDER_ID, "excel_get_range", inp, "item_id", "worksheet", "address")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{self._workbook_base(item_id)}/worksheets/{self._worksheet_ref(worksheet)}/range(address='{address}')",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"address": data.get("address"), "values": data.get("values"), "text": data.get("text")})
        except Exception as e:
            return _handle_error("excel_get_range", e)

    def update_range(self, inp: dict) -> str:
        permission_error, item_id, worksheet, address, values = self._check(self.agent_id, self.PROVIDER_ID, "excel_update_range", inp, "item_id", "worksheet", "address", "values")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.patch(
                f"{self._workbook_base(item_id)}/worksheets/{self._worksheet_ref(worksheet)}/range(address='{address}')",
                headers=headers,
                json={"values": values},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"address": data.get("address"), "status": "updated"})
        except Exception as e:
            return _handle_error("excel_update_range", e)

    def clear_range(self, inp: dict) -> str:
        permission_error, item_id, worksheet, address = self._check(self.agent_id, self.PROVIDER_ID, "excel_clear_range", inp, "item_id", "worksheet", "address")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{self._workbook_base(item_id)}/worksheets/{self._worksheet_ref(worksheet)}/range(address='{address}')/clear",
                headers=headers,
                json={"applyTo": inp.get("apply_to", "All")},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"address": address, "status": "cleared"})
        except Exception as e:
            return _handle_error("excel_clear_range", e)

    def get_used_range(self, inp: dict) -> str:
        permission_error, item_id, worksheet = self._check(self.agent_id, self.PROVIDER_ID, "excel_get_used_range", inp, "item_id", "worksheet")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{self._workbook_base(item_id)}/worksheets/{self._worksheet_ref(worksheet)}/usedRange",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"address": data.get("address"), "values": data.get("values"), "row_count": data.get("rowCount"), "column_count": data.get("columnCount")})
        except Exception as e:
            return _handle_error("excel_get_used_range", e)

    def append_row(self, inp: dict) -> str:
        permission_error, item_id, worksheet, values = self._check(self.agent_id, self.PROVIDER_ID, "excel_append_row", inp, "item_id", "worksheet", "values")
        if permission_error: return permission_error
        try:
            used_resp = httpx.get(
                f"{self._workbook_base(item_id)}/worksheets/{self._worksheet_ref(worksheet)}/usedRange",
                headers=self._auth_headers,
                timeout=15,
            )
            used_resp.raise_for_status()
            used = used_resp.json()
            row_count = used.get("rowCount", 0)
            col_count = max(used.get("columnCount", 0), len(values))
            next_row = row_count + 1
            start_col = "A"
            end_col_index = col_count - 1
            end_col = chr(ord("A") + end_col_index) if end_col_index < 26 else "Z"
            address = f"{start_col}{next_row}:{end_col}{next_row}"
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.patch(
                f"{self._workbook_base(item_id)}/worksheets/{self._worksheet_ref(worksheet)}/range(address='{address}')",
                headers=headers,
                json={"values": [values]},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"item_id": item_id, "appended_at": address, "status": "appended"})
        except Exception as e:
            return _handle_error("excel_append_row", e)

    # ── Tables ────────────────────────────────────────────────────────────────

    def create_table(self, inp: dict) -> str:
        permission_error, item_id, worksheet, address = self._check(self.agent_id, self.PROVIDER_ID, "excel_create_table", inp, "item_id", "worksheet", "address")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"address": address, "hasHeaders": inp.get("has_headers", True)}
            resp = httpx.post(
                f"{self._workbook_base(item_id)}/worksheets/{self._worksheet_ref(worksheet)}/tables/add",
                headers=headers,
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "name": data.get("name"), "status": "created"})
        except Exception as e:
            return _handle_error("excel_create_table", e)

    def list_tables(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "excel_list_tables", inp, "item_id")
        if permission_error: return permission_error
        try:
            worksheet = inp.get("worksheet", "")
            base = self._workbook_base(item_id)
            url = f"{base}/worksheets/{self._worksheet_ref(worksheet)}/tables" if worksheet else f"{base}/tables"
            resp = httpx.get(url, headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            tables = [{"id": t.get("id"), "name": t.get("name")} for t in resp.json().get("value", [])]
            return json.dumps({"item_id": item_id, "tables": tables})
        except Exception as e:
            return _handle_error("excel_list_tables", e)

    def add_table_row(self, inp: dict) -> str:
        permission_error, item_id, table, values = self._check(self.agent_id, self.PROVIDER_ID, "excel_add_table_row", inp, "item_id", "table", "values")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{self._workbook_base(item_id)}/tables/{table}/rows/add",
                headers=headers,
                json={"values": [values]},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"item_id": item_id, "table": table, "status": "row_added"})
        except Exception as e:
            return _handle_error("excel_add_table_row", e)

    # ── Formatting & charts ───────────────────────────────────────────────────

    def format_range(self, inp: dict) -> str:
        permission_error, item_id, worksheet, address = self._check(self.agent_id, self.PROVIDER_ID, "excel_format_range", inp, "item_id", "worksheet", "address")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            font_body: dict = {}
            if inp.get("bold") is not None:
                font_body["bold"] = inp["bold"]
            if inp.get("font_color"):
                font_body["color"] = inp["font_color"]
            if font_body:
                resp = httpx.patch(
                    f"{self._workbook_base(item_id)}/worksheets/{self._worksheet_ref(worksheet)}/range(address='{address}')/format/font",
                    headers=headers,
                    json=font_body,
                    timeout=15,
                )
                resp.raise_for_status()
            if inp.get("fill_color"):
                resp2 = httpx.patch(
                    f"{self._workbook_base(item_id)}/worksheets/{self._worksheet_ref(worksheet)}/range(address='{address}')/format/fill",
                    headers=headers,
                    json={"color": inp["fill_color"]},
                    timeout=15,
                )
                resp2.raise_for_status()
            return json.dumps({"address": address, "status": "formatted"})
        except Exception as e:
            return _handle_error("excel_format_range", e)

    def create_chart(self, inp: dict) -> str:
        permission_error, item_id, worksheet, source_data = self._check(self.agent_id, self.PROVIDER_ID, "excel_create_chart", inp, "item_id", "worksheet", "source_data")
        if permission_error: return permission_error
        chart_type = inp.get("chart_type", "ColumnClustered")
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"type": chart_type, "sourceData": source_data, "seriesBy": inp.get("series_by", "Auto")}
            resp = httpx.post(
                f"{self._workbook_base(item_id)}/worksheets/{self._worksheet_ref(worksheet)}/charts/add",
                headers=headers,
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "name": data.get("name"), "status": "created"})
        except Exception as e:
            return _handle_error("excel_create_chart", e)

    # ── Tool manifest ─────────────────────────────────────────────────────────

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "excel_create_workbook",
                    "description": "Create a new blank Excel workbook (.xlsx) in Microsoft OneDrive/SharePoint.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Workbook file name (e.g. 'Budget')."},
                            "folder": {"type": "string", "description": "Parent folder ID (default 'root')."},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_list_workbooks",
                    "description": "List or search Excel workbooks (.xlsx files) in the connected Microsoft account.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Optional search text; omit to list from the root folder."},
                            "limit": {"type": "integer", "description": "Max results (default 25)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_delete_workbook",
                    "description": "Permanently delete an Excel workbook.",
                    "parameters": {
                        "type": "object",
                        "properties": {"item_id": {"type": "string", "description": "The workbook's OneDrive item ID."}},
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_list_worksheets",
                    "description": "List worksheets (tabs) in an Excel workbook.",
                    "parameters": {
                        "type": "object",
                        "properties": {"item_id": {"type": "string", "description": "The workbook's OneDrive item ID."}},
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_add_worksheet",
                    "description": "Add a new worksheet (tab) to an Excel workbook.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The workbook's OneDrive item ID."},
                            "name": {"type": "string", "description": "Name for the new worksheet (optional)."},
                        },
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_rename_worksheet",
                    "description": "Rename a worksheet in an Excel workbook.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The workbook's OneDrive item ID."},
                            "worksheet": {"type": "string", "description": "Current worksheet name or ID."},
                            "new_name": {"type": "string", "description": "New worksheet name."},
                        },
                        "required": ["item_id", "worksheet", "new_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_delete_worksheet",
                    "description": "Delete a worksheet from an Excel workbook.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The workbook's OneDrive item ID."},
                            "worksheet": {"type": "string", "description": "Worksheet name or ID to delete."},
                        },
                        "required": ["item_id", "worksheet"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_get_range",
                    "description": "Read cell values from a range in an Excel worksheet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The workbook's OneDrive item ID."},
                            "worksheet": {"type": "string", "description": "Worksheet name or ID."},
                            "address": {"type": "string", "description": "Range address (e.g. 'A1:C10')."},
                        },
                        "required": ["item_id", "worksheet", "address"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_update_range",
                    "description": "Write cell values into a range in an Excel worksheet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The workbook's OneDrive item ID."},
                            "worksheet": {"type": "string", "description": "Worksheet name or ID."},
                            "address": {"type": "string", "description": "Range address (e.g. 'A1:B2')."},
                            "values": {"type": "array", "items": {"type": "array"}, "description": "2D array of row values matching the range's shape."},
                        },
                        "required": ["item_id", "worksheet", "address", "values"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_clear_range",
                    "description": "Clear the contents and/or formatting of a range in an Excel worksheet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The workbook's OneDrive item ID."},
                            "worksheet": {"type": "string", "description": "Worksheet name or ID."},
                            "address": {"type": "string", "description": "Range address (e.g. 'A1:C10')."},
                            "apply_to": {"type": "string", "description": "'All', 'Formats', or 'Contents' (default 'All')."},
                        },
                        "required": ["item_id", "worksheet", "address"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_get_used_range",
                    "description": "Get all data in the used (non-empty) range of an Excel worksheet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The workbook's OneDrive item ID."},
                            "worksheet": {"type": "string", "description": "Worksheet name or ID."},
                        },
                        "required": ["item_id", "worksheet"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_append_row",
                    "description": "Append a new row of values after the last used row in an Excel worksheet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The workbook's OneDrive item ID."},
                            "worksheet": {"type": "string", "description": "Worksheet name or ID."},
                            "values": {"type": "array", "items": {}, "description": "Row values, one per column."},
                        },
                        "required": ["item_id", "worksheet", "values"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_create_table",
                    "description": "Convert a range into a formatted Excel table.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The workbook's OneDrive item ID."},
                            "worksheet": {"type": "string", "description": "Worksheet name or ID."},
                            "address": {"type": "string", "description": "Range address to convert (e.g. 'A1:D10')."},
                            "has_headers": {"type": "boolean", "description": "Whether the first row is a header row (default true)."},
                        },
                        "required": ["item_id", "worksheet", "address"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_list_tables",
                    "description": "List Excel tables in a workbook or worksheet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The workbook's OneDrive item ID."},
                            "worksheet": {"type": "string", "description": "Optional worksheet name/ID to filter tables."},
                        },
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_add_table_row",
                    "description": "Add a row of values to the end of an existing Excel table.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The workbook's OneDrive item ID."},
                            "table": {"type": "string", "description": "Table name or ID (from excel_list_tables)."},
                            "values": {"type": "array", "items": {}, "description": "Row values, one per table column."},
                        },
                        "required": ["item_id", "table", "values"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_format_range",
                    "description": "Apply bold, font color, and/or fill color formatting to a range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The workbook's OneDrive item ID."},
                            "worksheet": {"type": "string", "description": "Worksheet name or ID."},
                            "address": {"type": "string", "description": "Range address (e.g. 'A1:D1')."},
                            "bold": {"type": "boolean", "description": "Set bold text."},
                            "font_color": {"type": "string", "description": "Font color as hex (e.g. '#FF0000')."},
                            "fill_color": {"type": "string", "description": "Cell background color as hex (e.g. '#FFFF00')."},
                        },
                        "required": ["item_id", "worksheet", "address"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "excel_create_chart",
                    "description": "Create a chart in an Excel worksheet from a source data range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The workbook's OneDrive item ID."},
                            "worksheet": {"type": "string", "description": "Worksheet name or ID."},
                            "chart_type": {"type": "string", "description": "Chart type, e.g. 'ColumnClustered', 'Line', 'Pie', 'BarClustered' (default 'ColumnClustered')."},
                            "source_data": {"type": "string", "description": "Range address for chart data (e.g. 'A1:B10')."},
                            "series_by": {"type": "string", "description": "'Auto', 'Rows', or 'Columns' (default 'Auto')."},
                        },
                        "required": ["item_id", "worksheet", "source_data"],
                    },
                },
            },
        ]
        callables = {
            "excel_create_workbook": self.create_workbook,
            "excel_list_workbooks": self.list_workbooks,
            "excel_delete_workbook": self.delete_workbook,
            "excel_list_worksheets": self.list_worksheets,
            "excel_add_worksheet": self.add_worksheet,
            "excel_rename_worksheet": self.rename_worksheet,
            "excel_delete_worksheet": self.delete_worksheet,
            "excel_get_range": self.get_range,
            "excel_update_range": self.update_range,
            "excel_clear_range": self.clear_range,
            "excel_get_used_range": self.get_used_range,
            "excel_append_row": self.append_row,
            "excel_create_table": self.create_table,
            "excel_list_tables": self.list_tables,
            "excel_add_table_row": self.add_table_row,
            "excel_format_range": self.format_range,
            "excel_create_chart": self.create_chart,
        }
        return tools, callables

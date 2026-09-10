import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://sheets.googleapis.com/v4/spreadsheets"
_DRIVE_BASE = "https://www.googleapis.com/drive/v3"

def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Google Sheets account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Google Sheets connector with the required OAuth scopes."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class GoogleSheetsConnector(BaseConnector):

    PROVIDER_ID = "google-sheets"

    # ── Spreadsheets ──────────────────────────────────────────────────────────

    def list_spreadsheets(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "google_sheets_list_spreadsheets", inp)
        if permission_error: return permission_error
        try:
            params = {
                "q": "mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
                "pageSize": inp.get("page_size", 20),
                "fields": "files(id,name,modifiedTime,webViewLink)",
            }
            resp = httpx.get(f"{_DRIVE_BASE}/files", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json().get("files", []))
        except Exception as e:
            return _handle_error("google_sheets_list_spreadsheets", e)

    def get_spreadsheet_info(self, inp: dict) -> str:
        permission_error, spreadsheet_id = self._check(self.agent_id, self.PROVIDER_ID, "google_sheets_get_spreadsheet_info", inp, "spreadsheet_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/{spreadsheet_id}",
                headers=self._auth_headers,
                params={"fields": "spreadsheetId,properties,sheets(properties)"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data["spreadsheetId"],
                "title": data.get("properties", {}).get("title", ""),
                "sheets": [s["properties"]["title"] for s in data.get("sheets", [])],
            })
        except Exception as e:
            return _handle_error("google_sheets_get_spreadsheet_info", e)

    # ── Read ──────────────────────────────────────────────────────────────────

    def read_sheet(self, inp: dict) -> str:
        permission_error, spreadsheet_id = self._check(self.agent_id, self.PROVIDER_ID, "google_sheets_read_sheet", inp, "spreadsheet_id")
        if permission_error: return permission_error
        range_ = inp.get("range", "Sheet1")
        try:
            resp = httpx.get(
                f"{_BASE}/{spreadsheet_id}/values/{range_}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"range": data.get("range"), "values": data.get("values", [])})
        except Exception as e:
            return _handle_error("google_sheets_read_sheet", e)

    # ── Write ─────────────────────────────────────────────────────────────────

    def write_sheet(self, inp: dict) -> str:
        permission_error, spreadsheet_id, values = self._check(self.agent_id, self.PROVIDER_ID, "google_sheets_write_sheet", inp, "spreadsheet_id", "values")
        if permission_error: return permission_error
        range_ = inp.get("range", "Sheet1!A1")
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"values": values}
            resp = httpx.put(
                f"{_BASE}/{spreadsheet_id}/values/{range_}",
                headers=headers,
                json=body,
                params={"valueInputOption": inp.get("value_input_option", "USER_ENTERED")},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"updatedRange": data.get("updatedRange"), "updatedRows": data.get("updatedRows"), "updatedCells": data.get("updatedCells")})
        except Exception as e:
            return _handle_error("google_sheets_write_sheet", e)

    def append_rows(self, inp: dict) -> str:
        permission_error, spreadsheet_id, values = self._check(self.agent_id, self.PROVIDER_ID, "google_sheets_append_rows", inp, "spreadsheet_id", "values")
        if permission_error: return permission_error
        range_ = inp.get("range", "Sheet1")
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"values": values}
            resp = httpx.post(
                f"{_BASE}/{spreadsheet_id}/values/{range_}:append",
                headers=headers,
                json=body,
                params={"valueInputOption": inp.get("value_input_option", "USER_ENTERED")},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"updatedRange": data.get("updates", {}).get("updatedRange"), "updatedRows": data.get("updates", {}).get("updatedRows")})
        except Exception as e:
            return _handle_error("google_sheets_append_rows", e)

    def clear_range(self, inp: dict) -> str:
        permission_error, spreadsheet_id, range_ = self._check(self.agent_id, self.PROVIDER_ID, "google_sheets_clear_range", inp, "spreadsheet_id", "range")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{_BASE}/{spreadsheet_id}/values/{range_}:clear",
                headers=headers,
                json={},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"status": "cleared", "clearedRange": range_})
        except Exception as e:
            return _handle_error("google_sheets_clear_range", e)

    def create_spreadsheet(self, inp: dict) -> str:
        permission_error, title = self._check(self.agent_id, self.PROVIDER_ID, "google_sheets_create_spreadsheet", inp, "title")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"properties": {"title": title}}
            if inp.get("sheets"):
                body["sheets"] = [{"properties": {"title": s}} for s in inp["sheets"]]
            resp = httpx.post(_BASE, headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data["spreadsheetId"],
                "title": data.get("properties", {}).get("title"),
                "url": data.get("spreadsheetUrl"),
            })
        except Exception as e:
            return _handle_error("google_sheets_create_spreadsheet", e)

    # ── Structural / batch operations ────────────────────────────────────────

    def batch_get_ranges(self, inp: dict) -> str:
        permission_error, spreadsheet_id, ranges = self._check(self.agent_id, self.PROVIDER_ID, "google_sheets_batch_get_ranges", inp, "spreadsheet_id", "ranges")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/{spreadsheet_id}/values:batchGet",
                headers=self._auth_headers,
                params={"ranges": ranges},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            value_ranges = [{"range": vr.get("range"), "values": vr.get("values", [])} for vr in data.get("valueRanges", [])]
            return json.dumps({"valueRanges": value_ranges})
        except Exception as e:
            return _handle_error("google_sheets_batch_get_ranges", e)

    def add_sheet(self, inp: dict) -> str:
        permission_error, spreadsheet_id, title = self._check(self.agent_id, self.PROVIDER_ID, "google_sheets_add_sheet", inp, "spreadsheet_id", "title")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
            resp = httpx.post(f"{_BASE}/{spreadsheet_id}:batchUpdate", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            props = data.get("replies", [{}])[0].get("addSheet", {}).get("properties", {})
            return json.dumps({"sheetId": props.get("sheetId"), "title": props.get("title"), "status": "created"})
        except Exception as e:
            return _handle_error("google_sheets_add_sheet", e)

    def delete_sheet(self, inp: dict) -> str:
        permission_error, spreadsheet_id, sheet_id = self._check(self.agent_id, self.PROVIDER_ID, "google_sheets_delete_sheet", inp, "spreadsheet_id", "sheet_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"requests": [{"deleteSheet": {"sheetId": sheet_id}}]}
            resp = httpx.post(f"{_BASE}/{spreadsheet_id}:batchUpdate", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "deleted", "sheetId": sheet_id})
        except Exception as e:
            return _handle_error("google_sheets_delete_sheet", e)

    def find_replace(self, inp: dict) -> str:
        permission_error, spreadsheet_id, find = self._check(self.agent_id, self.PROVIDER_ID, "google_sheets_find_replace", inp, "spreadsheet_id", "find")
        if permission_error: return permission_error
        replacement = inp.get("replacement", "")
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            find_replace_req: dict = {
                "find": find,
                "replacement": replacement,
                "matchCase": inp.get("match_case", False),
                "matchEntireCell": inp.get("match_entire_cell", False),
                "allSheets": inp.get("sheet_id") is None,
            }
            if inp.get("sheet_id") is not None:
                find_replace_req["sheetId"] = inp["sheet_id"]
            body = {"requests": [{"findReplace": find_replace_req}]}
            resp = httpx.post(f"{_BASE}/{spreadsheet_id}:batchUpdate", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            result = data.get("replies", [{}])[0].get("findReplace", {})
            return json.dumps({"valuesChanged": result.get("valuesChanged", 0), "occurrencesChanged": result.get("occurrencesChanged", 0)})
        except Exception as e:
            return _handle_error("google_sheets_find_replace", e)

    def format_cells(self, inp: dict) -> str:
        permission_error, spreadsheet_id, sheet_id = self._check(self.agent_id, self.PROVIDER_ID, "google_sheets_format_cells", inp, "spreadsheet_id", "sheet_id")
        if permission_error: return permission_error
        try:
            cell_format: dict = {}
            if inp.get("bold") is not None:
                cell_format.setdefault("textFormat", {})["bold"] = inp["bold"]
            if inp.get("background_color"):
                cell_format["backgroundColor"] = inp["background_color"]
            if not cell_format:
                return "Error: at least one of 'bold' or 'background_color' (e.g. {'red':1,'green':0,'blue':0}) is required."
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "requests": [
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": inp.get("start_row", 0),
                                "endRowIndex": inp.get("end_row", 1),
                                "startColumnIndex": inp.get("start_col", 0),
                                "endColumnIndex": inp.get("end_col", 1),
                            },
                            "cell": {"userEnteredFormat": cell_format},
                            "fields": ",".join(f"userEnteredFormat.{k}" for k in cell_format.keys()),
                        }
                    }
                ]
            }
            resp = httpx.post(f"{_BASE}/{spreadsheet_id}:batchUpdate", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "formatted", "sheetId": sheet_id})
        except Exception as e:
            return _handle_error("google_sheets_format_cells", e)

    def sort_range(self, inp: dict) -> str:
        permission_error, spreadsheet_id, sheet_id, sort_column_index = self._check(self.agent_id, self.PROVIDER_ID, "google_sheets_sort_range", inp, "spreadsheet_id", "sheet_id", "sort_column_index")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "requests": [
                    {
                        "sortRange": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": inp.get("start_row", 0),
                                "endRowIndex": inp.get("end_row"),
                                "startColumnIndex": inp.get("start_col", 0),
                                "endColumnIndex": inp.get("end_col"),
                            },
                            "sortSpecs": [{"dimensionIndex": sort_column_index, "sortOrder": inp.get("sort_order", "ASCENDING")}],
                        }
                    }
                ]
            }
            resp = httpx.post(f"{_BASE}/{spreadsheet_id}:batchUpdate", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "sorted", "sheetId": sheet_id})
        except Exception as e:
            return _handle_error("google_sheets_sort_range", e)

    # ── Tool manifest ─────────────────────────────────────────────────────────

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "google_sheets_list_spreadsheets",
                    "description": "List all Google Sheets spreadsheets in the user's Drive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_size": {"type": "integer", "description": "Max spreadsheets to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_sheets_get_spreadsheet_info",
                    "description": "Get title and sheet names for a spreadsheet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {"type": "string", "description": "The spreadsheet ID."},
                        },
                        "required": ["spreadsheet_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_sheets_read_sheet",
                    "description": "Read cell values from a Google Sheet range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {"type": "string", "description": "The spreadsheet ID."},
                            "range": {"type": "string", "description": "A1 notation range (e.g. 'Sheet1!A1:D10' or 'Sheet1')."},
                        },
                        "required": ["spreadsheet_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_sheets_write_sheet",
                    "description": "Write values to a specific range in a Google Sheet (overwrites existing values).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {"type": "string", "description": "The spreadsheet ID."},
                            "range": {"type": "string", "description": "A1 notation range to write to (e.g. 'Sheet1!A1')."},
                            "values": {"type": "array", "items": {"type": "array"}, "description": "2D array of values to write (rows of columns)."},
                        },
                        "required": ["spreadsheet_id", "range", "values"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_sheets_append_rows",
                    "description": "Append new rows to the end of a Google Sheet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {"type": "string", "description": "The spreadsheet ID."},
                            "range": {"type": "string", "description": "Sheet name or range to append to (e.g. 'Sheet1')."},
                            "values": {"type": "array", "items": {"type": "array"}, "description": "2D array of rows to append."},
                        },
                        "required": ["spreadsheet_id", "values"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_sheets_clear_range",
                    "description": "Clear all values from a range in a Google Sheet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "spreadsheet_id": {"type": "string", "description": "The spreadsheet ID."},
                            "range": {"type": "string", "description": "A1 notation range to clear (e.g. 'Sheet1!A1:D10')."},
                        },
                        "required": ["spreadsheet_id", "range"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_sheets_create_spreadsheet",
                    "description": "Create a new Google Sheets spreadsheet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Title of the new spreadsheet."},
                            "sheets": {"type": "array", "items": {"type": "string"}, "description": "Optional list of sheet tab names to create."},
                        },
                        "required": ["title"],
                    },
                },
            },
        ]
        callables = {
            "google_sheets_list_spreadsheets": self.list_spreadsheets,
            "google_sheets_get_spreadsheet_info": self.get_spreadsheet_info,
            "google_sheets_read_sheet": self.read_sheet,
            "google_sheets_write_sheet": self.write_sheet,
            "google_sheets_append_rows": self.append_rows,
            "google_sheets_clear_range": self.clear_range,
            "google_sheets_create_spreadsheet": self.create_spreadsheet,
        }
        return tools, callables

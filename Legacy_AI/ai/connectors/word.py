import io
import json

import httpx
from docx import Document

from ai.connectors.base import BaseConnector

_DRIVE_BASE = "https://graph.microsoft.com/v1.0/me/drive"
_SEARCH_BASE = "https://graph.microsoft.com/v1.0/me/drive/root/search"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Microsoft Word account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Word connector with the required OAuth scopes."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class WordConnector(BaseConnector):
    """
    Microsoft Word connector. Microsoft Graph has no native rich-content API for .docx,
    so edits are done by downloading the file, editing it locally with python-docx,
    and re-uploading the result to the same OneDrive/SharePoint item.
    """

    PROVIDER_ID = "word"

    def _download_docx(self, item_id: str) -> Document:
        meta_resp = httpx.get(
            f"{_DRIVE_BASE}/items/{item_id}",
            headers=self._auth_headers,
            params={"select": "@microsoft.graph.downloadUrl"},
            timeout=15,
        )
        meta_resp.raise_for_status()
        download_url = meta_resp.json().get("@microsoft.graph.downloadUrl")
        if not download_url:
            raise ValueError("File does not have a downloadable URL (may be a folder or unsupported item).")
        content_resp = httpx.get(download_url, timeout=30)
        content_resp.raise_for_status()
        return Document(io.BytesIO(content_resp.content))

    def _upload_docx(self, item_id: str, doc: Document) -> dict:
        buf = io.BytesIO()
        doc.save(buf)
        resp = httpx.put(
            f"{_DRIVE_BASE}/items/{item_id}/content",
            headers={**self._auth_headers, "Content-Type": "application/octet-stream"},
            content=buf.getvalue(),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Documents ─────────────────────────────────────────────────────────────

    def create_document(self, inp: dict) -> str:
        permission_error, name = self._check(self.agent_id, self.PROVIDER_ID, "word_create_document", inp, "name")
        if permission_error: return permission_error
        if not name.lower().endswith(".docx"):
            name += ".docx"
        try:
            folder = inp.get("folder", "root")
            parent = "root" if folder == "root" else f"items/{folder}"
            doc = Document()
            if inp.get("title"):
                doc.add_heading(inp["title"], level=1)
            if inp.get("text"):
                doc.add_paragraph(inp["text"])
            buf = io.BytesIO()
            doc.save(buf)
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
            return _handle_error("word_create_document", e)

    def list_documents(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "word_list_documents", inp)
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
                if i.get("name", "").lower().endswith(".docx")
            ]
            return json.dumps({"documents": items})
        except Exception as e:
            return _handle_error("word_list_documents", e)

    def delete_document(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "word_delete_document", inp, "item_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_DRIVE_BASE}/items/{item_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"deleted": True, "item_id": item_id})
        except Exception as e:
            return _handle_error("word_delete_document", e)

    def share_document(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "word_share_document", inp, "item_id")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_DRIVE_BASE}/items/{item_id}/createLink",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"type": inp.get("type", "view"), "scope": inp.get("scope", "anonymous")},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"link": data.get("link", {}).get("webUrl")})
        except Exception as e:
            return _handle_error("word_share_document", e)

    # ── Content read ──────────────────────────────────────────────────────────

    def get_document_text(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "word_get_document_text", inp, "item_id")
        if permission_error: return permission_error
        try:
            doc = self._download_docx(item_id)
            paragraphs = [p.text for p in doc.paragraphs]
            tables = [[[cell.text for cell in row.cells] for row in t.rows] for t in doc.tables]
            return json.dumps({"item_id": item_id, "paragraphs": paragraphs, "tables": tables})
        except Exception as e:
            return _handle_error("word_get_document_text", e)

    # ── Content edit (download → edit → re-upload) ───────────────────────────

    def add_paragraph(self, inp: dict) -> str:
        permission_error, item_id, text = self._check(self.agent_id, self.PROVIDER_ID, "word_add_paragraph", inp, "item_id", "text")
        if permission_error: return permission_error
        try:
            doc = self._download_docx(item_id)
            p = doc.add_paragraph(text)
            if inp.get("style"):
                p.style = inp["style"]
            self._upload_docx(item_id, doc)
            return json.dumps({"item_id": item_id, "status": "paragraph_added"})
        except Exception as e:
            return _handle_error("word_add_paragraph", e)

    def add_heading(self, inp: dict) -> str:
        permission_error, item_id, text = self._check(self.agent_id, self.PROVIDER_ID, "word_add_heading", inp, "item_id", "text")
        if permission_error: return permission_error
        try:
            level = int(inp.get("level", 1))
            doc = self._download_docx(item_id)
            doc.add_heading(text, level=level)
            self._upload_docx(item_id, doc)
            return json.dumps({"item_id": item_id, "status": "heading_added"})
        except Exception as e:
            return _handle_error("word_add_heading", e)

    def add_table(self, inp: dict) -> str:
        permission_error, item_id, rows_data = self._check(self.agent_id, self.PROVIDER_ID, "word_add_table", inp, "item_id", "rows")
        if permission_error: return permission_error
        try:
            doc = self._download_docx(item_id)
            n_rows = len(rows_data)
            n_cols = max(len(r) for r in rows_data)
            table = doc.add_table(rows=n_rows, cols=n_cols)
            if inp.get("style"):
                table.style = inp["style"]
            for r_idx, row_values in enumerate(rows_data):
                for c_idx, value in enumerate(row_values):
                    table.rows[r_idx].cells[c_idx].text = str(value)
            self._upload_docx(item_id, doc)
            return json.dumps({"item_id": item_id, "status": "table_added", "rows": n_rows, "columns": n_cols})
        except Exception as e:
            return _handle_error("word_add_table", e)

    def replace_text(self, inp: dict) -> str:
        permission_error, item_id, find = self._check(self.agent_id, self.PROVIDER_ID, "word_replace_text", inp, "item_id", "find")
        if permission_error: return permission_error
        replace = inp.get("replace", "")
        try:
            doc = self._download_docx(item_id)
            replacements = 0
            for p in doc.paragraphs:
                for run in p.runs:
                    if find in run.text:
                        run.text = run.text.replace(find, replace)
                        replacements += 1
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:
                            for run in p.runs:
                                if find in run.text:
                                    run.text = run.text.replace(find, replace)
                                    replacements += 1
            self._upload_docx(item_id, doc)
            return json.dumps({"item_id": item_id, "status": "replaced", "occurrences": replacements})
        except Exception as e:
            return _handle_error("word_replace_text", e)

    def insert_page_break(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "word_insert_page_break", inp, "item_id")
        if permission_error: return permission_error
        try:
            doc = self._download_docx(item_id)
            doc.add_page_break()
            self._upload_docx(item_id, doc)
            return json.dumps({"item_id": item_id, "status": "page_break_added"})
        except Exception as e:
            return _handle_error("word_insert_page_break", e)

    # ── Tool manifest ─────────────────────────────────────────────────────────

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "word_create_document",
                    "description": "Create a new Word document (.docx) in Microsoft OneDrive/SharePoint, optionally with an initial title and text.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Document file name (e.g. 'Report')."},
                            "folder": {"type": "string", "description": "Parent folder ID (default 'root')."},
                            "title": {"type": "string", "description": "Optional heading to add as the first content."},
                            "text": {"type": "string", "description": "Optional initial body paragraph text."},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "word_list_documents",
                    "description": "List or search Word documents (.docx files) in the connected Microsoft account.",
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
                    "name": "word_delete_document",
                    "description": "Permanently delete a Word document.",
                    "parameters": {
                        "type": "object",
                        "properties": {"item_id": {"type": "string", "description": "The document's OneDrive item ID."}},
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "word_share_document",
                    "description": "Create a sharing link for a Word document.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The document's OneDrive item ID."},
                            "type": {"type": "string", "description": "Link type: 'view' (default) or 'edit'."},
                            "scope": {"type": "string", "description": "Link scope: 'anonymous' (default) or 'organization'."},
                        },
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "word_get_document_text",
                    "description": "Read the full text content (paragraphs and tables) of a Word document.",
                    "parameters": {
                        "type": "object",
                        "properties": {"item_id": {"type": "string", "description": "The document's OneDrive item ID."}},
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "word_add_paragraph",
                    "description": "Append a paragraph of text to the end of a Word document.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The document's OneDrive item ID."},
                            "text": {"type": "string", "description": "Paragraph text to add."},
                            "style": {"type": "string", "description": "Optional paragraph style name (e.g. 'Intense Quote')."},
                        },
                        "required": ["item_id", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "word_add_heading",
                    "description": "Append a heading to the end of a Word document.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The document's OneDrive item ID."},
                            "text": {"type": "string", "description": "Heading text."},
                            "level": {"type": "integer", "description": "Heading level 0-9 (default 1)."},
                        },
                        "required": ["item_id", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "word_add_table",
                    "description": "Append a table to the end of a Word document.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The document's OneDrive item ID."},
                            "rows": {"type": "array", "items": {"type": "array"}, "description": "2D array of cell text, e.g. [['Name','Age'],['Alice','30']]."},
                            "style": {"type": "string", "description": "Optional table style name (e.g. 'Light Grid Accent 1')."},
                        },
                        "required": ["item_id", "rows"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "word_replace_text",
                    "description": "Find and replace text throughout a Word document's paragraphs and tables.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The document's OneDrive item ID."},
                            "find": {"type": "string", "description": "Text to find."},
                            "replace": {"type": "string", "description": "Replacement text."},
                        },
                        "required": ["item_id", "find"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "word_insert_page_break",
                    "description": "Insert a page break at the end of a Word document.",
                    "parameters": {
                        "type": "object",
                        "properties": {"item_id": {"type": "string", "description": "The document's OneDrive item ID."}},
                        "required": ["item_id"],
                    },
                },
            },
        ]
        callables = {
            "word_create_document": self.create_document,
            "word_list_documents": self.list_documents,
            "word_delete_document": self.delete_document,
            "word_share_document": self.share_document,
            "word_get_document_text": self.get_document_text,
            "word_add_paragraph": self.add_paragraph,
            "word_add_heading": self.add_heading,
            "word_add_table": self.add_table,
            "word_replace_text": self.replace_text,
            "word_insert_page_break": self.insert_page_break,
        }
        return tools, callables

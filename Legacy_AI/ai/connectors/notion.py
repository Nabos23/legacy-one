import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Notion account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Notion connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class NotionConnector(BaseConnector):

    PROVIDER_ID = "notion"

    @property
    def _notion_headers(self) -> dict:
        return {**self._auth_headers, "Notion-Version": _NOTION_VERSION, "Content-Type": "application/json"}

    def list_databases(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "notion_list_databases", inp)
        if permission_error: return permission_error
        try:
            body = {"filter": {"value": "database", "property": "object"}, "page_size": inp.get("page_size", 20)}
            resp = httpx.post(f"{_BASE}/search", headers=self._notion_headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            dbs = [
                {
                    "id": d["id"],
                    "title": "".join(t.get("plain_text", "") for t in d.get("title", [])),
                    "url": d.get("url"),
                    "created_time": d.get("created_time"),
                    "last_edited_time": d.get("last_edited_time"),
                }
                for d in data.get("results", [])
            ]
            return json.dumps(dbs)
        except Exception as e:
            return _handle_error("notion_list_databases", e)

    def list_pages(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "notion_list_pages", inp)
        if permission_error: return permission_error
        try:
            body = {"filter": {"value": "page", "property": "object"}, "page_size": inp.get("page_size", 20)}
            if inp.get("query"):
                body["query"] = inp["query"]
            resp = httpx.post(f"{_BASE}/search", headers=self._notion_headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            pages = [
                {
                    "id": p["id"],
                    "title": self._extract_title(p),
                    "url": p.get("url"),
                    "created_time": p.get("created_time"),
                    "last_edited_time": p.get("last_edited_time"),
                }
                for p in data.get("results", [])
            ]
            return json.dumps(pages)
        except Exception as e:
            return _handle_error("notion_list_pages", e)

    def get_page(self, inp: dict) -> str:
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "notion_get_page", inp, "page_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/pages/{page_id}", headers=self._notion_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "title": self._extract_title(data), "url": data.get("url"), "properties": list(data.get("properties", {}).keys())})
        except Exception as e:
            return _handle_error("notion_get_page", e)

    def get_page_content(self, inp: dict) -> str:
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "notion_get_page_content", inp, "page_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/blocks/{page_id}/children", headers=self._notion_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            blocks = []
            for b in data.get("results", [])[:50]:
                btype = b.get("type", "")
                content = b.get(btype, {})
                text = "".join(t.get("plain_text", "") for t in content.get("rich_text", []))
                if text:
                    blocks.append({"type": btype, "text": text})
            return json.dumps(blocks)
        except Exception as e:
            return _handle_error("notion_get_page_content", e)

    def query_database(self, inp: dict) -> str:
        permission_error, database_id = self._check(self.agent_id, self.PROVIDER_ID, "notion_query_database", inp, "database_id")
        if permission_error: return permission_error
        try:
            body: dict = {"page_size": inp.get("page_size", 20)}
            if inp.get("filter"):
                body["filter"] = inp["filter"]
            resp = httpx.post(f"{_BASE}/databases/{database_id}/query", headers=self._notion_headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            rows = [{"id": r["id"], "title": self._extract_title(r), "url": r.get("url")} for r in data.get("results", [])]
            return json.dumps({"rows": rows, "has_more": data.get("has_more", False)})
        except Exception as e:
            return _handle_error("notion_query_database", e)

    def create_page(self, inp: dict) -> str:
        permission_error, parent_id, title = self._check(self.agent_id, self.PROVIDER_ID, "notion_create_page", inp, "parent_id", "title")
        if permission_error: return permission_error
        parent_type = inp.get("parent_type", "page_id")
        try:
            body = {
                "parent": {parent_type: parent_id},
                "properties": {"title": {"title": [{"text": {"content": title}}]}},
            }
            if inp.get("content"):
                body["children"] = [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": inp["content"]}}]}}]
            resp = httpx.post(f"{_BASE}/pages", headers=self._notion_headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "url": data.get("url"), "title": title})
        except Exception as e:
            return _handle_error("notion_create_page", e)

    def update_page(self, inp: dict) -> str:
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "notion_update_page", inp, "page_id")
        if permission_error: return permission_error
        body: dict = {}
        if inp.get("properties") is not None:
            body["properties"] = inp["properties"]
        if inp.get("archived") is not None:
            body["archived"] = inp["archived"]
        if not body:
            return "Error: at least one of 'properties' or 'archived' is required."
        try:
            resp = httpx.patch(f"{_BASE}/pages/{page_id}", headers=self._notion_headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "title": self._extract_title(data), "url": data.get("url"), "archived": data.get("archived", False)})
        except Exception as e:
            return _handle_error("notion_update_page", e)

    def archive_page(self, inp: dict) -> str:
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "notion_archive_page", inp, "page_id")
        if permission_error: return permission_error
        try:
            resp = httpx.patch(f"{_BASE}/pages/{page_id}", headers=self._notion_headers, json={"archived": True}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "archived": data.get("archived", True), "status": "archived"})
        except Exception as e:
            return _handle_error("notion_archive_page", e)

    def append_blocks(self, inp: dict) -> str:
        permission_error, block_id = self._check(self.agent_id, self.PROVIDER_ID, "notion_append_blocks", inp, "block_id")
        if permission_error: return permission_error
        children = inp.get("children")
        text_content = inp.get("text_content")
        if not children and not text_content:
            return "Error: either 'children' (block array) or 'text_content' (plain text) is required."
        if not children and text_content:
            children = [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": text_content}}]},
                }
            ]
        try:
            resp = httpx.patch(f"{_BASE}/blocks/{block_id}/children", headers=self._notion_headers, json={"children": children}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"block_id": block_id, "appended": len(data.get("results", [])), "status": "success"})
        except Exception as e:
            return _handle_error("notion_append_blocks", e)

    def create_database(self, inp: dict) -> str:
        permission_error, parent_page_id = self._check(self.agent_id, self.PROVIDER_ID, "notion_create_database", inp, "parent_page_id")
        if permission_error: return permission_error
        title_prop = inp.get("title_prop", "Name")
        db_title = inp.get("title", "Untitled Database")
        try:
            properties: dict = {
                title_prop: {"title": {}},
            }
            if inp.get("extra_properties"):
                properties.update(inp["extra_properties"])
            body = {
                "parent": {"page_id": parent_page_id},
                "title": [{"type": "text", "text": {"content": db_title}}],
                "properties": properties,
            }
            resp = httpx.post(f"{_BASE}/databases", headers=self._notion_headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "url": data.get("url"), "title": db_title, "status": "created"})
        except Exception as e:
            return _handle_error("notion_create_database", e)

    def search(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "notion_search", inp, "query")
        if permission_error: return permission_error
        try:
            body: dict = {"query": query}
            filter_type = inp.get("filter_type")
            if filter_type in ("page", "database"):
                body["filter"] = {"value": filter_type, "property": "object"}
            resp = httpx.post(f"{_BASE}/search", headers=self._notion_headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            results = [
                {
                    "id": r["id"],
                    "object": r.get("object"),
                    "title": self._extract_title(r) if r.get("object") == "page" else "".join(t.get("plain_text", "") for t in r.get("title", [])),
                    "url": r.get("url"),
                    "last_edited_time": r.get("last_edited_time"),
                }
                for r in data.get("results", [])
            ]
            return json.dumps({"results": results, "count": len(results), "has_more": data.get("has_more", False)})
        except Exception as e:
            return _handle_error("notion_search", e)

    def list_comments(self, inp: dict) -> str:
        permission_error, block_id = self._check(self.agent_id, self.PROVIDER_ID, "notion_list_comments", inp, "block_id")
        if permission_error: return permission_error
        try:
            params = {"block_id": block_id, "page_size": inp.get("page_size", 20)}
            resp = httpx.get(f"{_BASE}/comments", headers=self._notion_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            comments = [
                {
                    "id": c["id"],
                    "text": "".join(t.get("plain_text", "") for t in c.get("rich_text", [])),
                    "created_time": c.get("created_time"),
                    "discussion_id": c.get("discussion_id"),
                    "created_by": c.get("created_by", {}).get("id"),
                }
                for c in data.get("results", [])
            ]
            return json.dumps({"comments": comments, "has_more": data.get("has_more", False)})
        except Exception as e:
            return _handle_error("notion_list_comments", e)

    def create_comment(self, inp: dict) -> str:
        permission_error, text = self._check(self.agent_id, self.PROVIDER_ID, "notion_create_comment", inp, "text")
        if permission_error: return permission_error
        page_id = inp.get("page_id", "")
        discussion_id = inp.get("discussion_id", "")
        if not page_id and not discussion_id:
            return "Error: either 'page_id' (to start a new comment thread) or 'discussion_id' (to reply to an existing thread) is required."
        try:
            body: dict = {"rich_text": [{"type": "text", "text": {"content": text}}]}
            if discussion_id:
                body["discussion_id"] = discussion_id
            else:
                body["parent"] = {"page_id": page_id}
            resp = httpx.post(f"{_BASE}/comments", headers=self._notion_headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "discussion_id": data.get("discussion_id"), "status": "created"})
        except Exception as e:
            return _handle_error("notion_create_comment", e)

    def list_users(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "notion_list_users", inp)
        if permission_error: return permission_error
        try:
            params = {"page_size": inp.get("page_size", 50)}
            resp = httpx.get(f"{_BASE}/users", headers=self._notion_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            users = [
                {
                    "id": u["id"],
                    "name": u.get("name"),
                    "type": u.get("type"),
                    "email": u.get("person", {}).get("email") if u.get("type") == "person" else None,
                }
                for u in data.get("results", [])
            ]
            return json.dumps({"users": users, "has_more": data.get("has_more", False)})
        except Exception as e:
            return _handle_error("notion_list_users", e)

    def get_database(self, inp: dict) -> str:
        permission_error, database_id = self._check(self.agent_id, self.PROVIDER_ID, "notion_get_database", inp, "database_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/databases/{database_id}", headers=self._notion_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            properties = {
                name: prop.get("type")
                for name, prop in data.get("properties", {}).items()
            }
            title = "".join(t.get("plain_text", "") for t in data.get("title", []))
            return json.dumps({"id": data["id"], "title": title, "url": data.get("url"), "properties": properties})
        except Exception as e:
            return _handle_error("notion_get_database", e)

    def delete_block(self, inp: dict) -> str:
        permission_error, block_id = self._check(self.agent_id, self.PROVIDER_ID, "notion_delete_block", inp, "block_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/blocks/{block_id}", headers=self._notion_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id", block_id), "archived": data.get("archived", True), "status": "deleted"})
        except Exception as e:
            return _handle_error("notion_delete_block", e)

    def _extract_title(self, obj: dict) -> str:
        props = obj.get("properties", {})
        for key in ("title", "Name", "Title"):
            if key in props:
                rich = props[key].get("title", [])
                return "".join(t.get("plain_text", "") for t in rich)
        return "(Untitled)"

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "notion_list_databases",
                    "description": "List all Notion databases the integration has access to.",
                    "parameters": {"type": "object", "properties": {"page_size": {"type": "integer", "description": "Max results (default 20)."}}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notion_list_pages",
                    "description": "List or search Notion pages.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Optional search query to filter pages."},
                            "page_size": {"type": "integer", "description": "Max results (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notion_get_page",
                    "description": "Get metadata for a specific Notion page.",
                    "parameters": {"type": "object", "properties": {"page_id": {"type": "string", "description": "The Notion page ID."}}, "required": ["page_id"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notion_get_page_content",
                    "description": "Get the text content (blocks) of a Notion page.",
                    "parameters": {"type": "object", "properties": {"page_id": {"type": "string", "description": "The Notion page ID."}}, "required": ["page_id"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notion_query_database",
                    "description": "Query rows from a Notion database.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "database_id": {"type": "string", "description": "The Notion database ID."},
                            "page_size": {"type": "integer", "description": "Max rows to return (default 20)."},
                        },
                        "required": ["database_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notion_create_page",
                    "description": "Create a new page in Notion under a parent page or database.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "parent_id": {"type": "string", "description": "ID of the parent page or database."},
                            "parent_type": {"type": "string", "description": "'page_id' or 'database_id' (default: page_id)."},
                            "title": {"type": "string", "description": "Title of the new page."},
                            "content": {"type": "string", "description": "Optional text content for the page body."},
                        },
                        "required": ["parent_id", "title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notion_update_page",
                    "description": "Update a Notion page's properties or archived status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "The Notion page ID to update."},
                            "properties": {
                                "type": "object",
                                "description": (
                                    "Properties dict to update. For a simple title update use: "
                                    "{\"title\": {\"title\": [{\"text\": {\"content\": \"New Title\"}}]}}"
                                ),
                            },
                            "archived": {"type": "boolean", "description": "Set to true to archive, false to unarchive."},
                        },
                        "required": ["page_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notion_archive_page",
                    "description": "Archive (soft-delete) a Notion page.",
                    "parameters": {
                        "type": "object",
                        "properties": {"page_id": {"type": "string", "description": "The Notion page ID to archive."}},
                        "required": ["page_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notion_append_blocks",
                    "description": "Append content blocks to a Notion page or block.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "block_id": {"type": "string", "description": "The page or block ID to append content to."},
                            "text_content": {"type": "string", "description": "Plain text to append as a paragraph block (simple shorthand)."},
                            "children": {
                                "type": "array",
                                "description": "Array of Notion block objects to append. Overrides text_content if provided.",
                                "items": {"type": "object"},
                            },
                        },
                        "required": ["block_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notion_create_database",
                    "description": "Create a new Notion database inside a parent page.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "parent_page_id": {"type": "string", "description": "ID of the parent page that will contain the database."},
                            "title": {"type": "string", "description": "Title of the new database."},
                            "title_prop": {"type": "string", "description": "Name of the title/primary column (default: Name)."},
                            "extra_properties": {
                                "type": "object",
                                "description": "Additional database property schema entries (Notion property schema format).",
                            },
                        },
                        "required": ["parent_page_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notion_search",
                    "description": "Search across all Notion pages and databases accessible to the integration.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query string (required)."},
                            "filter_type": {"type": "string", "description": "Restrict results to 'page' or 'database'. Omit to search both."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notion_list_comments",
                    "description": "List all unresolved comments on a Notion page or block.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "block_id": {"type": "string", "description": "The page ID or block ID to list comments for."},
                            "page_size": {"type": "integer", "description": "Max comments to return (default 20)."},
                        },
                        "required": ["block_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notion_create_comment",
                    "description": "Create a comment on a Notion page, or reply to an existing comment discussion thread.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "The comment text."},
                            "page_id": {"type": "string", "description": "Page ID to start a new top-level comment thread on."},
                            "discussion_id": {"type": "string", "description": "Existing discussion thread ID to reply to (use instead of page_id)."},
                        },
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notion_list_users",
                    "description": "List all users (members and bots) in the connected Notion workspace.",
                    "parameters": {"type": "object", "properties": {"page_size": {"type": "integer", "description": "Max users to return (default 50)."}}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notion_get_database",
                    "description": "Get a Notion database's schema (property names and types), separate from querying its rows.",
                    "parameters": {
                        "type": "object",
                        "properties": {"database_id": {"type": "string", "description": "The Notion database ID."}},
                        "required": ["database_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "notion_delete_block",
                    "description": "Delete (archive) a Notion block, such as a paragraph, list item, or nested block.",
                    "parameters": {
                        "type": "object",
                        "properties": {"block_id": {"type": "string", "description": "The Notion block ID to delete."}},
                        "required": ["block_id"],
                    },
                },
            },
        ]
        callables = {
            "notion_list_databases": self.list_databases,
            "notion_list_pages": self.list_pages,
            "notion_get_page": self.get_page,
            "notion_get_page_content": self.get_page_content,
            "notion_query_database": self.query_database,
            "notion_create_page": self.create_page,
            "notion_update_page": self.update_page,
            "notion_archive_page": self.archive_page,
            "notion_append_blocks": self.append_blocks,
            "notion_create_database": self.create_database,
            "notion_search": self.search,
            "notion_list_comments": self.list_comments,
            "notion_create_comment": self.create_comment,
            "notion_list_users": self.list_users,
            "notion_get_database": self.get_database,
            "notion_delete_block": self.delete_block,
        }
        return tools, callables

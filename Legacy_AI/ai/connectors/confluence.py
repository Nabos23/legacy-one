import json
import httpx

from ai.connectors.base import BaseConnector


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Confluence account lacks permission "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their Confluence connector."
            )
        if e.response.status_code == 404:
            return f"Not found in {tool_name}: the requested resource does not exist."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class ConfluenceConnector(BaseConnector):
    """
    Confluence Cloud connector using Atlassian OAuth2 3LO.
    access_token format: "TOKEN:SUBDOMAIN" (same pattern as Jira)
    where SUBDOMAIN is the Atlassian site subdomain (e.g. "mycompany").
    If SUBDOMAIN is empty, cloudId is resolved via accessible-resources.
    """

    PROVIDER_ID = "confluence"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id=agent_id)
        parts = access_token.split(":", 1)
        self._token = parts[0]
        self._subdomain = parts[1] if len(parts) > 1 else ""
        if self._subdomain:
            self._base = f"https://{self._subdomain}.atlassian.net/wiki/rest/api"
        else:
            self._base = self._resolve_base_url()

    @property
    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}

    @_auth_headers.setter
    def _auth_headers(self, value: dict) -> None:
        pass

    def _resolve_base_url(self) -> str:
        try:
            resp = httpx.get(
                "https://api.atlassian.com/oauth/token/accessible-resources",
                headers=self._auth_headers,
                timeout=10,
            )
            resp.raise_for_status()
            resources = resp.json()
            if not resources:
                return "https://api.atlassian.com/ex/confluence/none/wiki/rest/api"
            cloud_id = resources[0]["id"]
            return f"https://api.atlassian.com/ex/confluence/{cloud_id}/wiki/rest/api"
        except Exception:
            return "https://api.atlassian.com/ex/confluence/none/wiki/rest/api"

    def list_spaces(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "confluence_list_spaces", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"limit": inp.get("limit", 20), "type": inp.get("type", "global")}
            resp = httpx.get(f"{self._base}/space", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            spaces = [
                {
                    "key": s["key"],
                    "name": s["name"],
                    "type": s.get("type"),
                    "status": s.get("status"),
                }
                for s in data.get("results", [])
            ]
            return json.dumps({"spaces": spaces, "count": len(spaces)})
        except Exception as e:
            return _handle_error("confluence_list_spaces", e)

    def search_content(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "confluence_search_content", inp, "query")
        if permission_error: return permission_error
        try:
            cql = f'text ~ "{query}"'
            if inp.get("space_key"):
                cql += f' AND space.key = "{inp["space_key"]}"'
            if inp.get("type"):
                cql += f' AND type = "{inp["type"]}"'
            else:
                cql += " AND type in (\"page\", \"blogpost\")"
            params = {"cql": cql, "limit": inp.get("limit", 10), "expand": "space,version"}
            resp = httpx.get(f"{self._base}/content/search", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            results = [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "type": r["type"],
                    "space": r.get("space", {}).get("name"),
                    "url": r.get("_links", {}).get("webui"),
                    "last_modified": r.get("version", {}).get("when"),
                }
                for r in data.get("results", [])
            ]
            return json.dumps({"results": results, "count": len(results)})
        except Exception as e:
            return _handle_error("confluence_search_content", e)

    def get_page(self, inp: dict) -> str:
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "confluence_get_page", inp, "page_id")
        if permission_error: return permission_error
        try:
            params = {"expand": "body.storage,version,space,ancestors"}
            resp = httpx.get(f"{self._base}/content/{page_id}", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            p = resp.json()
            body_text = p.get("body", {}).get("storage", {}).get("value", "")
            import re
            clean_text = re.sub(r"<[^>]+>", " ", body_text)[:2000]
            return json.dumps({
                "id": p["id"],
                "title": p["title"],
                "type": p.get("type"),
                "space": p.get("space", {}).get("name"),
                "version": p.get("version", {}).get("number"),
                "last_modified": p.get("version", {}).get("when"),
                "body_text": clean_text,
                "url": p.get("_links", {}).get("webui"),
            })
        except Exception as e:
            return _handle_error("confluence_get_page", e)

    def list_pages_in_space(self, inp: dict) -> str:
        permission_error, space_key = self._check(self.agent_id, self.PROVIDER_ID, "confluence_list_pages_in_space", inp, "space_key")
        if permission_error: return permission_error
        try:
            params = {
                "spaceKey": space_key,
                "type": "page",
                "limit": inp.get("limit", 25),
                "expand": "version",
                "orderby": "modified desc",
            }
            resp = httpx.get(f"{self._base}/content", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            pages = [
                {
                    "id": p["id"],
                    "title": p["title"],
                    "last_modified": p.get("version", {}).get("when"),
                    "version": p.get("version", {}).get("number"),
                }
                for p in data.get("results", [])
            ]
            return json.dumps({"pages": pages, "count": len(pages), "space_key": space_key})
        except Exception as e:
            return _handle_error("confluence_list_pages_in_space", e)

    def create_page(self, inp: dict) -> str:
        permission_error, space_key, title = self._check(self.agent_id, self.PROVIDER_ID, "confluence_create_page", inp, "space_key", "title")
        if permission_error: return permission_error
        body = inp.get("body", "")
        try:
            payload: dict = {
                "type": "page",
                "title": title,
                "space": {"key": space_key},
                "body": {
                    "storage": {
                        "value": body or f"<p>{title}</p>",
                        "representation": "storage",
                    }
                },
            }
            if inp.get("parent_id"):
                payload["ancestors"] = [{"id": inp["parent_id"]}]
            resp = httpx.post(
                f"{self._base}/content",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            p = resp.json()
            return json.dumps({
                "id": p["id"],
                "title": p["title"],
                "url": p.get("_links", {}).get("webui"),
                "status": "created",
            })
        except Exception as e:
            return _handle_error("confluence_create_page", e)

    def add_comment(self, inp: dict) -> str:
        permission_error, page_id, body = self._check(self.agent_id, self.PROVIDER_ID, "confluence_add_comment", inp, "page_id", "body")
        if permission_error: return permission_error
        try:
            payload = {
                "type": "comment",
                "container": {"id": page_id, "type": "page"},
                "body": {
                    "storage": {
                        "value": f"<p>{body}</p>",
                        "representation": "storage",
                    }
                },
            }
            resp = httpx.post(
                f"{self._base}/content",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            c = resp.json()
            return json.dumps({"id": c["id"], "status": "comment_added"})
        except Exception as e:
            return _handle_error("confluence_add_comment", e)

    def update_page(self, inp: dict) -> str:
        permission_error, page_id, title, content = self._check(self.agent_id, self.PROVIDER_ID, "confluence_update_page", inp, "page_id", "title", "content")
        if permission_error: return permission_error
        try:
            get_resp = httpx.get(
                f"{self._base}/content/{page_id}",
                headers=self._auth_headers,
                params={"expand": "version"},
                timeout=15,
            )
            get_resp.raise_for_status()
            current = get_resp.json()
            current_version = current.get("version", {}).get("number", 1)

            payload = {
                "version": {"number": current_version + 1},
                "title": title,
                "type": "page",
                "body": {
                    "storage": {
                        "value": content,
                        "representation": "storage",
                    }
                },
            }
            put_resp = httpx.put(
                f"{self._base}/content/{page_id}",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            put_resp.raise_for_status()
            p = put_resp.json()
            return json.dumps({
                "id": p["id"],
                "title": p["title"],
                "version_number": p.get("version", {}).get("number"),
                "webui_url": p.get("_links", {}).get("webui"),
            })
        except Exception as e:
            return _handle_error("confluence_update_page", e)

    def delete_page(self, inp: dict) -> str:
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "confluence_delete_page", inp, "page_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(
                f"{self._base}/content/{page_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"deleted": True, "id": page_id})
        except Exception as e:
            return _handle_error("confluence_delete_page", e)

    def get_page_children(self, inp: dict) -> str:
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "confluence_get_page_children", inp, "page_id")
        if permission_error: return permission_error
        try:
            limit = inp.get("limit", 25)
            resp = httpx.get(
                f"{self._base}/content/{page_id}/child/page",
                headers=self._auth_headers,
                params={"limit": limit},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            children = [
                {
                    "id": p["id"],
                    "title": p["title"],
                    "webui": p.get("_links", {}).get("webui"),
                }
                for p in data.get("results", [])
            ]
            return json.dumps(children)
        except Exception as e:
            return _handle_error("confluence_get_page_children", e)

    def attach_file(self, inp: dict) -> str:
        permission_error, page_id, filename, content = self._check(self.agent_id, self.PROVIDER_ID, "confluence_attach_file", inp, "page_id", "filename", "content")
        if permission_error: return permission_error
        content_type = inp.get("content_type", "text/plain")
        try:
            upload_headers = {
                **self._auth_headers,
                "X-Atlassian-Token": "no-check",
            }
            files = {"file": (filename, content.encode("utf-8"), content_type)}
            resp = httpx.post(
                f"{self._base}/content/{page_id}/child/attachment",
                headers=upload_headers,
                files=files,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                return json.dumps({"error": "Attachment uploaded but no result returned."})
            att = results[0]
            return json.dumps({
                "id": att.get("id"),
                "filename": att.get("title"),
                "mediaType": att.get("metadata", {}).get("mediaType"),
                "fileSize": att.get("extensions", {}).get("fileSize"),
            })
        except Exception as e:
            return _handle_error("confluence_attach_file", e)

    def list_labels(self, inp: dict) -> str:
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "confluence_list_labels", inp, "page_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/content/{page_id}/label", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            labels = [{"name": l["name"], "prefix": l.get("prefix")} for l in data.get("results", [])]
            return json.dumps({"labels": labels, "count": len(labels)})
        except Exception as e:
            return _handle_error("confluence_list_labels", e)

    def add_label(self, inp: dict) -> str:
        permission_error, page_id, label = self._check(self.agent_id, self.PROVIDER_ID, "confluence_add_label", inp, "page_id", "label")
        if permission_error: return permission_error
        try:
            payload = [{"prefix": "global", "name": label}]
            resp = httpx.post(
                f"{self._base}/content/{page_id}/label",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            labels = [l["name"] for l in data.get("results", [])]
            return json.dumps({"page_id": page_id, "labels": labels, "status": "added"})
        except Exception as e:
            return _handle_error("confluence_add_label", e)

    def remove_label(self, inp: dict) -> str:
        permission_error, page_id, label = self._check(self.agent_id, self.PROVIDER_ID, "confluence_remove_label", inp, "page_id", "label")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{self._base}/content/{page_id}/label/{label}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"page_id": page_id, "label": label, "status": "removed"})
        except Exception as e:
            return _handle_error("confluence_remove_label", e)

    def list_attachments(self, inp: dict) -> str:
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "confluence_list_attachments", inp, "page_id")
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 25), "expand": "version"}
            resp = httpx.get(f"{self._base}/content/{page_id}/child/attachment", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            attachments = [
                {
                    "id": a["id"],
                    "title": a["title"],
                    "mediaType": a.get("metadata", {}).get("mediaType"),
                    "fileSize": a.get("extensions", {}).get("fileSize"),
                    "download_url": a.get("_links", {}).get("download"),
                }
                for a in data.get("results", [])
            ]
            return json.dumps({"attachments": attachments, "count": len(attachments)})
        except Exception as e:
            return _handle_error("confluence_list_attachments", e)

    def get_space(self, inp: dict) -> str:
        permission_error, space_key = self._check(self.agent_id, self.PROVIDER_ID, "confluence_get_space", inp, "space_key")
        if permission_error: return permission_error
        try:
            params = {"expand": "description.plain,homepage"}
            resp = httpx.get(f"{self._base}/space/{space_key}", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            s = resp.json()
            return json.dumps({
                "key": s["key"],
                "name": s["name"],
                "type": s.get("type"),
                "description": s.get("description", {}).get("plain", {}).get("value"),
                "homepage_id": s.get("homepage", {}).get("id"),
            })
        except Exception as e:
            return _handle_error("confluence_get_space", e)
        try:
            params = {"expand": "description.plain,homepage"}
            resp = httpx.get(f"{self._base}/space/{space_key}", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            s = resp.json()
            return json.dumps({
                "key": s["key"],
                "name": s["name"],
                "type": s.get("type"),
                "description": s.get("description", {}).get("plain", {}).get("value"),
                "homepage_id": s.get("homepage", {}).get("id"),
            })
        except Exception as e:
            return _handle_error("confluence_get_space", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "confluence_list_spaces",
                    "description": "List all Confluence spaces the user has access to.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "description": "Space type: global (default) or personal."},
                            "limit": {"type": "integer", "description": "Max spaces to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confluence_search_content",
                    "description": "Search Confluence pages and blog posts by text query.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Text to search for."},
                            "space_key": {"type": "string", "description": "Limit search to a specific space key."},
                            "type": {"type": "string", "description": "Content type: page or blogpost."},
                            "limit": {"type": "integer", "description": "Max results (default 10)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confluence_get_page",
                    "description": "Get the full content of a specific Confluence page.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Confluence page ID."},
                        },
                        "required": ["page_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confluence_list_pages_in_space",
                    "description": "List pages in a Confluence space ordered by most recently modified.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "space_key": {"type": "string", "description": "Confluence space key."},
                            "limit": {"type": "integer", "description": "Max pages to return (default 25)."},
                        },
                        "required": ["space_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confluence_create_page",
                    "description": "Create a new page in a Confluence space.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "space_key": {"type": "string", "description": "Confluence space key."},
                            "title": {"type": "string", "description": "Page title."},
                            "body": {"type": "string", "description": "Page body in Confluence storage format (HTML-like) or plain text."},
                            "parent_id": {"type": "string", "description": "Optional parent page ID to nest this page under."},
                        },
                        "required": ["space_key", "title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confluence_add_comment",
                    "description": "Add a comment to a Confluence page.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Confluence page ID."},
                            "body": {"type": "string", "description": "Comment text."},
                        },
                        "required": ["page_id", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confluence_update_page",
                    "description": "Update an existing Confluence page's title and content. Automatically fetches the current version number before writing.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Confluence page ID to update."},
                            "title": {"type": "string", "description": "New title for the page."},
                            "content": {"type": "string", "description": "New page content in Confluence storage format (HTML-like markup)."},
                        },
                        "required": ["page_id", "title", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confluence_delete_page",
                    "description": "Delete a Confluence page by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Confluence page ID to delete."},
                        },
                        "required": ["page_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confluence_get_page_children",
                    "description": "List child pages of a given Confluence page.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Confluence page ID whose children to list."},
                            "limit": {"type": "integer", "description": "Max child pages to return (default 25)."},
                        },
                        "required": ["page_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confluence_attach_file",
                    "description": "Attach a text file to a Confluence page.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Confluence page ID to attach the file to."},
                            "filename": {"type": "string", "description": "Name of the file to attach (e.g. 'report.txt')."},
                            "content": {"type": "string", "description": "String content of the file to attach."},
                            "content_type": {"type": "string", "description": "MIME type of the file (default 'text/plain')."},
                        },
                        "required": ["page_id", "filename", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confluence_list_labels",
                    "description": "List labels attached to a Confluence page.",
                    "parameters": {
                        "type": "object",
                        "properties": {"page_id": {"type": "string", "description": "Confluence page ID."}},
                        "required": ["page_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confluence_add_label",
                    "description": "Add a label to a Confluence page.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Confluence page ID."},
                            "label": {"type": "string", "description": "Label name to add."},
                        },
                        "required": ["page_id", "label"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confluence_remove_label",
                    "description": "Remove a label from a Confluence page.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Confluence page ID."},
                            "label": {"type": "string", "description": "Label name to remove."},
                        },
                        "required": ["page_id", "label"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confluence_list_attachments",
                    "description": "List file attachments on a Confluence page.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Confluence page ID."},
                            "limit": {"type": "integer", "description": "Max attachments to return (default 25)."},
                        },
                        "required": ["page_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "confluence_get_space",
                    "description": "Get details of a Confluence space including description and homepage.",
                    "parameters": {
                        "type": "object",
                        "properties": {"space_key": {"type": "string", "description": "Confluence space key."}},
                        "required": ["space_key"],
                    },
                },
            },
        ]
        callables = {
            "confluence_list_spaces": self.list_spaces,
            "confluence_search_content": self.search_content,
            "confluence_get_page": self.get_page,
            "confluence_list_pages_in_space": self.list_pages_in_space,
            "confluence_create_page": self.create_page,
            "confluence_add_comment": self.add_comment,
            "confluence_update_page": self.update_page,
            "confluence_delete_page": self.delete_page,
            "confluence_get_page_children": self.get_page_children,
            "confluence_attach_file": self.attach_file,
            "confluence_list_labels": self.list_labels,
            "confluence_add_label": self.add_label,
            "confluence_remove_label": self.remove_label,
            "confluence_list_attachments": self.list_attachments,
            "confluence_get_space": self.get_space,
        }
        return tools, callables

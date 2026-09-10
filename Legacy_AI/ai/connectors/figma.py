import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.figma.com/v1"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Figma account lacks permission "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their Figma connector."
            )
        if e.response.status_code == 404:
            return f"Not found in {tool_name}: the requested resource does not exist."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class FigmaConnector(BaseConnector):

    PROVIDER_ID = "figma"

    def get_me(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "figma_get_me", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/me", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            u = resp.json()
            return json.dumps({
                "id": u.get("id"),
                "email": u.get("email"),
                "handle": u.get("handle"),
                "img_url": u.get("img_url"),
            })
        except Exception as e:
            return _handle_error("figma_get_me", e)

    def list_projects(self, inp: dict) -> str:
        permission_error, team_id = self._check(self.agent_id, self.PROVIDER_ID, "figma_list_projects", inp, "team_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/teams/{team_id}/projects", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            projects = [
                {"id": p["id"], "name": p["name"]}
                for p in resp.json().get("projects", [])
            ]
            return json.dumps({"projects": projects, "count": len(projects)})
        except Exception as e:
            return _handle_error("figma_list_projects", e)

    def list_files(self, inp: dict) -> str:
        permission_error, project_id = self._check(self.agent_id, self.PROVIDER_ID, "figma_list_files", inp, "project_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/projects/{project_id}/files", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            files = [
                {
                    "key": f["key"],
                    "name": f["name"],
                    "last_modified": f.get("last_modified"),
                    "thumbnail_url": f.get("thumbnail_url"),
                }
                for f in resp.json().get("files", [])
            ]
            return json.dumps({"files": files, "count": len(files)})
        except Exception as e:
            return _handle_error("figma_list_files", e)

    def get_file(self, inp: dict) -> str:
        permission_error, file_key = self._check(self.agent_id, self.PROVIDER_ID, "figma_get_file", inp, "file_key")
        if permission_error: return permission_error
        try:
            params = {"depth": inp.get("depth", 2)}
            resp = httpx.get(f"{_BASE}/files/{file_key}", headers=self._auth_headers, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            doc = data.get("document", {})
            pages = [
                {"id": child.get("id"), "name": child.get("name"), "type": child.get("type")}
                for child in doc.get("children", [])
            ]
            return json.dumps({
                "name": data.get("name"),
                "last_modified": data.get("lastModified"),
                "version": data.get("version"),
                "pages": pages,
            })
        except Exception as e:
            return _handle_error("figma_get_file", e)

    def get_comments(self, inp: dict) -> str:
        permission_error, file_key = self._check(self.agent_id, self.PROVIDER_ID, "figma_get_comments", inp, "file_key")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/files/{file_key}/comments", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            comments = [
                {
                    "id": c.get("id"),
                    "message": c.get("message"),
                    "author": c.get("user", {}).get("handle"),
                    "created_at": c.get("created_at"),
                    "resolved_at": c.get("resolved_at"),
                }
                for c in resp.json().get("comments", [])
            ]
            return json.dumps({"comments": comments, "count": len(comments)})
        except Exception as e:
            return _handle_error("figma_get_comments", e)

    def post_comment(self, inp: dict) -> str:
        permission_error, file_key, message = self._check(self.agent_id, self.PROVIDER_ID, "figma_post_comment", inp, "file_key", "message")
        if permission_error: return permission_error
        try:
            body = {"message": message}
            resp = httpx.post(
                f"{_BASE}/files/{file_key}/comments",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            c = resp.json()
            return json.dumps({"id": c.get("id"), "message": c.get("message"), "status": "posted"})
        except Exception as e:
            return _handle_error("figma_post_comment", e)

    def get_components(self, inp: dict) -> str:
        permission_error, file_key = self._check(self.agent_id, self.PROVIDER_ID, "figma_get_components", inp, "file_key")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/files/{file_key}/components", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            components = [
                {
                    "key": c.get("key"),
                    "name": c.get("name"),
                    "description": c.get("description"),
                    "containing_frame": c.get("containing_frame", {}).get("name"),
                }
                for c in resp.json().get("meta", {}).get("components", [])
            ]
            return json.dumps({"components": components, "count": len(components)})
        except Exception as e:
            return _handle_error("figma_get_components", e)

    def get_image(self, inp: dict) -> str:
        permission_error, file_key, node_ids = self._check(self.agent_id, self.PROVIDER_ID, "figma_get_image", inp, "file_key", "node_ids")
        if permission_error: return permission_error
        try:
            params = {
                "ids": ",".join(node_ids),
                "format": inp.get("format", "png"),
                "scale": inp.get("scale", 1),
            }
            resp = httpx.get(f"{_BASE}/images/{file_key}", headers=self._auth_headers, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"images": data.get("images", {}), "status": data.get("status")})
        except Exception as e:
            return _handle_error("figma_get_image", e)

    def get_file_nodes(self, inp: dict) -> str:
        permission_error, file_key, node_ids = self._check(self.agent_id, self.PROVIDER_ID, "figma_get_file_nodes", inp, "file_key", "node_ids")
        if permission_error: return permission_error
        try:
            params = {"ids": ",".join(node_ids)}
            resp = httpx.get(f"{_BASE}/files/{file_key}/nodes", headers=self._auth_headers, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            nodes = {
                node_id: {"name": n.get("document", {}).get("name"), "type": n.get("document", {}).get("type")}
                for node_id, n in data.get("nodes", {}).items()
                if n
            }
            return json.dumps({"nodes": nodes})
        except Exception as e:
            return _handle_error("figma_get_file_nodes", e)

    def get_file_styles(self, inp: dict) -> str:
        permission_error, file_key = self._check(self.agent_id, self.PROVIDER_ID, "figma_get_file_styles", inp, "file_key")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/files/{file_key}/styles", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            styles = [
                {"key": s.get("key"), "name": s.get("name"), "style_type": s.get("style_type"), "description": s.get("description")}
                for s in resp.json().get("meta", {}).get("styles", [])
            ]
            return json.dumps({"styles": styles, "count": len(styles)})
        except Exception as e:
            return _handle_error("figma_get_file_styles", e)

    def get_team_components(self, inp: dict) -> str:
        permission_error, team_id = self._check(self.agent_id, self.PROVIDER_ID, "figma_get_team_components", inp, "team_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/teams/{team_id}/components", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            components = [
                {"key": c.get("key"), "name": c.get("name"), "description": c.get("description")}
                for c in resp.json().get("meta", {}).get("components", [])
            ]
            return json.dumps({"components": components, "count": len(components)})
        except Exception as e:
            return _handle_error("figma_get_team_components", e)

    def delete_comment(self, inp: dict) -> str:
        permission_error, file_key, comment_id = self._check(self.agent_id, self.PROVIDER_ID, "figma_delete_comment", inp, "file_key", "comment_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/files/{file_key}/comments/{comment_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"deleted": True, "id": comment_id})
        except Exception as e:
            return _handle_error("figma_delete_comment", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "figma_get_me",
                    "description": "Get the authenticated Figma user's profile.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "figma_list_projects",
                    "description": "List all Figma projects in a team.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "Figma team ID."},
                        },
                        "required": ["team_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "figma_list_files",
                    "description": "List all files in a Figma project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "Figma project ID."},
                        },
                        "required": ["project_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "figma_get_file",
                    "description": "Get details and page structure of a Figma file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_key": {"type": "string", "description": "Figma file key (from the file URL)."},
                            "depth": {"type": "integer", "description": "Depth of the node tree to return (default 2)."},
                        },
                        "required": ["file_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "figma_get_comments",
                    "description": "Get all comments on a Figma file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_key": {"type": "string", "description": "Figma file key."},
                        },
                        "required": ["file_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "figma_post_comment",
                    "description": "Post a comment on a Figma file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_key": {"type": "string", "description": "Figma file key."},
                            "message": {"type": "string", "description": "Comment message text."},
                        },
                        "required": ["file_key", "message"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "figma_get_components",
                    "description": "Get all components defined in a Figma file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_key": {"type": "string", "description": "Figma file key."},
                        },
                        "required": ["file_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "figma_get_image",
                    "description": "Render one or more nodes in a Figma file as images (PNG, JPG, SVG, or PDF) and get temporary download URLs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_key": {"type": "string", "description": "Figma file key."},
                            "node_ids": {"type": "array", "items": {"type": "string"}, "description": "Node IDs to render, e.g. ['1:2', '1:3']."},
                            "format": {"type": "string", "description": "Output format: jpg, png, svg, or pdf (default png)."},
                            "scale": {"type": "number", "description": "Image scaling factor between 0.01 and 4 (default 1)."},
                        },
                        "required": ["file_key", "node_ids"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "figma_get_file_nodes",
                    "description": "Get detailed document data for specific nodes within a Figma file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_key": {"type": "string", "description": "Figma file key."},
                            "node_ids": {"type": "array", "items": {"type": "string"}, "description": "Node IDs to fetch, e.g. ['1:2', '1:3']."},
                        },
                        "required": ["file_key", "node_ids"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "figma_get_file_styles",
                    "description": "Get all shared styles (color, text, effect, grid) defined in a Figma file.",
                    "parameters": {
                        "type": "object",
                        "properties": {"file_key": {"type": "string", "description": "Figma file key."}},
                        "required": ["file_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "figma_get_team_components",
                    "description": "List all published components in a Figma team's library.",
                    "parameters": {
                        "type": "object",
                        "properties": {"team_id": {"type": "string", "description": "Figma team ID."}},
                        "required": ["team_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "figma_delete_comment",
                    "description": "Delete a comment from a Figma file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_key": {"type": "string", "description": "Figma file key."},
                            "comment_id": {"type": "string", "description": "ID of the comment to delete."},
                        },
                        "required": ["file_key", "comment_id"],
                    },
                },
            },
        ]
        callables = {
            "figma_get_me": self.get_me,
            "figma_list_projects": self.list_projects,
            "figma_list_files": self.list_files,
            "figma_get_file": self.get_file,
            "figma_get_comments": self.get_comments,
            "figma_post_comment": self.post_comment,
            "figma_get_components": self.get_components,
            "figma_get_image": self.get_image,
            "figma_get_file_nodes": self.get_file_nodes,
            "figma_get_file_styles": self.get_file_styles,
            "figma_get_team_components": self.get_team_components,
            "figma_delete_comment": self.delete_comment,
        }
        return tools, callables

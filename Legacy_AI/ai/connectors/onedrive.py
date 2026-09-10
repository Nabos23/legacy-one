import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://graph.microsoft.com/v1.0/me/drive"
_SEARCH_BASE = "https://graph.microsoft.com/v1.0/me/drive/root/search"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected OneDrive account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their OneDrive connector with the required OAuth scopes."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


_ITEM_FIELDS = "id,name,size,lastModifiedDateTime,file,folder,parentReference,webUrl,@microsoft.graph.downloadUrl"


class OneDriveConnector(BaseConnector):

    PROVIDER_ID = "onedrive"

    # ── List / Search ─────────────────────────────────────────────────────────

    def list_files(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_list_files", inp)
        if permission_error: return permission_error
        try:
            folder = inp.get("folder", "root")
            path = "root" if folder == "root" else f"items/{folder}"
            params = {"$select": _ITEM_FIELDS, "$top": inp.get("top", 50)}
            if inp.get("order_by"):
                params["$orderby"] = inp["order_by"]
            resp = httpx.get(f"{_BASE}/{path}/children", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("onedrive_list_files", e)

    def search_files(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_search_files", inp, "query")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_SEARCH_BASE}(q='{query}')",
                headers=self._auth_headers,
                params={"$select": _ITEM_FIELDS, "$top": inp.get("top", 25)},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("onedrive_search_files", e)

    def get_file(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_get_file", inp, "item_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/items/{item_id}",
                headers=self._auth_headers,
                params={"$select": _ITEM_FIELDS},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("onedrive_get_file", e)

    # ── Read / Write ──────────────────────────────────────────────────────────

    def download_file(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_download_file", inp, "item_id")
        if permission_error: return permission_error
        try:
            meta_resp = httpx.get(
                f"{_BASE}/items/{item_id}",
                headers=self._auth_headers,
                params={"select": "@microsoft.graph.downloadUrl,name,size"},
                timeout=15,
            )
            meta_resp.raise_for_status()
            download_url = meta_resp.json().get("@microsoft.graph.downloadUrl")
            if not download_url:
                return "Error: file does not have a downloadable URL (may be a folder or special item)."
            content_resp = httpx.get(download_url, timeout=30)
            content_resp.raise_for_status()
            text = content_resp.text[:4000]
            return json.dumps({"item_id": item_id, "content": text, "truncated": len(content_resp.text) > 4000})
        except Exception as e:
            return _handle_error("onedrive_download_file", e)

    def upload_file(self, inp: dict) -> str:
        permission_error, name, content = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_upload_file", inp, "name", "content")
        if permission_error: return permission_error
        try:
            folder = inp.get("folder", "root")
            body = content.encode() if isinstance(content, str) else content
            parent = "root" if folder == "root" else f"items/{folder}"
            resp = httpx.put(
                f"{_BASE}/{parent}:/{name}:/content",
                headers={**self._auth_headers, "Content-Type": "text/plain"},
                content=body,
                timeout=30,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("onedrive_upload_file", e)

    # ── Folders ───────────────────────────────────────────────────────────────

    def create_folder(self, inp: dict) -> str:
        permission_error, name = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_create_folder", inp, "name")
        if permission_error: return permission_error
        parent = inp.get("parent", "root")
        parent_path = "root" if parent == "root" else f"items/{parent}"
        try:
            resp = httpx.post(
                f"{_BASE}/{parent_path}/children",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("onedrive_create_folder", e)

    # ── Manage ────────────────────────────────────────────────────────────────

    def rename_file(self, inp: dict) -> str:
        permission_error, item_id, new_name = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_rename_file", inp, "item_id", "new_name")
        if permission_error: return permission_error
        try:
            resp = httpx.patch(
                f"{_BASE}/items/{item_id}",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"name": new_name},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("onedrive_rename_file", e)

    def move_file(self, inp: dict) -> str:
        permission_error, item_id, new_parent_id = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_move_file", inp, "item_id", "new_parent_id")
        if permission_error: return permission_error
        new_name = inp.get("new_name", "")
        try:
            body: dict = {"parentReference": {"id": new_parent_id}}
            if new_name:
                body["name"] = new_name
            resp = httpx.patch(
                f"{_BASE}/items/{item_id}",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("onedrive_move_file", e)

    def copy_file(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_copy_file", inp, "item_id")
        if permission_error: return permission_error
        new_parent_id = inp.get("new_parent_id", "")
        new_name = inp.get("new_name", "")
        try:
            body: dict = {}
            if new_parent_id:
                body["parentReference"] = {"id": new_parent_id}
            if new_name:
                body["name"] = new_name
            resp = httpx.post(
                f"{_BASE}/items/{item_id}/copy",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"ok": True, "status": resp.status_code, "location": resp.headers.get("Location")})
        except Exception as e:
            return _handle_error("onedrive_copy_file", e)

    def delete_file(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_delete_file", inp, "item_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/items/{item_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"ok": True, "deleted": item_id})
        except Exception as e:
            return _handle_error("onedrive_delete_file", e)

    # ── Discover ──────────────────────────────────────────────────────────────

    def list_recent(self, inp: dict) -> str:
        """List files the user has recently interacted with across OneDrive."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_list_recent", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/recent",
                headers=self._auth_headers,
                params={"$select": _ITEM_FIELDS, "$top": inp.get("top", 25)},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("onedrive_list_recent", e)

    def list_shared_with_me(self, inp: dict) -> str:
        """List items other people have shared with the connected account."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_list_shared_with_me", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/sharedWithMe",
                headers=self._auth_headers,
                params={"$select": _ITEM_FIELDS, "$top": inp.get("top", 25)},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("onedrive_list_shared_with_me", e)

    def track_changes(self, inp: dict) -> str:
        """Track changes (creates/updates/deletes) in a folder since a previous delta link."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_track_changes", inp)
        if permission_error: return permission_error
        folder = inp.get("folder", "root")
        delta_link = inp.get("delta_link", "")
        try:
            if delta_link:
                resp = httpx.get(delta_link, headers=self._auth_headers, timeout=15)
            else:
                path = "root" if folder == "root" else f"items/{folder}"
                resp = httpx.get(
                    f"{_BASE}/{path}/delta",
                    headers=self._auth_headers,
                    params={"$select": _ITEM_FIELDS},
                    timeout=15,
                )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps(
                {
                    "changes": data.get("value", []),
                    "next_link": data.get("@odata.nextLink"),
                    "delta_link": data.get("@odata.deltaLink"),
                }
            )
        except Exception as e:
            return _handle_error("onedrive_track_changes", e)

    # ── Versions ──────────────────────────────────────────────────────────────

    def list_versions(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_list_versions", inp, "item_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/items/{item_id}/versions", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("onedrive_list_versions", e)

    def restore_version(self, inp: dict) -> str:
        permission_error, item_id, version_id = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_restore_version", inp, "item_id", "version_id")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/items/{item_id}/versions/{version_id}/restoreVersion",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"ok": True, "item_id": item_id, "restored_version": version_id})
        except Exception as e:
            return _handle_error("onedrive_restore_version", e)

    # ── Thumbnails ────────────────────────────────────────────────────────────

    def get_thumbnails(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_get_thumbnails", inp, "item_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/items/{item_id}/thumbnails", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("onedrive_get_thumbnails", e)

    # ── Sharing ───────────────────────────────────────────────────────────────

    def get_permissions(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_get_permissions", inp, "item_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/items/{item_id}/permissions", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("onedrive_get_permissions", e)

    def share_file(self, inp: dict) -> str:
        """Create a sharing link for a file."""
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "onedrive_share_file", inp, "item_id")
        if permission_error: return permission_error
        link_type = inp.get("type", "view")
        scope = inp.get("scope", "anonymous")
        try:
            resp = httpx.post(
                f"{_BASE}/items/{item_id}/createLink",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"type": link_type, "scope": scope},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"link": data.get("link", {}).get("webUrl"), "type": link_type, "scope": scope})
        except Exception as e:
            return _handle_error("onedrive_share_file", e)

    # ── Tool manifest ─────────────────────────────────────────────────────────

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "onedrive_list_files",
                    "description": "List files and folders in OneDrive. Specify a folder ID to list its contents.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "folder": {"type": "string", "description": "Folder ID to list (default 'root')."},
                            "top": {"type": "integer", "description": "Max items to return (default 50)."},
                            "order_by": {"type": "string", "description": "Sort field (e.g. 'lastModifiedDateTime desc', 'name')."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_search_files",
                    "description": "Search for files and folders across all of OneDrive by name or content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search text."},
                            "top": {"type": "integer", "description": "Max results (default 25)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_get_file",
                    "description": "Get metadata for a specific file or folder (name, size, last modified, web URL).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The OneDrive item ID."},
                        },
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_download_file",
                    "description": "Download and read the text content of a file from OneDrive (truncated to 4000 chars).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The OneDrive item ID to download."},
                        },
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_upload_file",
                    "description": "Upload a text file to OneDrive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "File name (e.g. 'report.txt')."},
                            "content": {"type": "string", "description": "Text content to upload."},
                            "folder": {"type": "string", "description": "Parent folder ID (default 'root')."},
                        },
                        "required": ["name", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_create_folder",
                    "description": "Create a new folder in OneDrive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Folder name to create."},
                            "parent": {"type": "string", "description": "Parent folder ID (default 'root')."},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_rename_file",
                    "description": "Rename a file or folder in OneDrive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The item ID to rename."},
                            "new_name": {"type": "string", "description": "New name for the item."},
                        },
                        "required": ["item_id", "new_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_move_file",
                    "description": "Move a file or folder to a different location in OneDrive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The item ID to move."},
                            "new_parent_id": {"type": "string", "description": "Destination folder ID."},
                            "new_name": {"type": "string", "description": "Optionally rename while moving."},
                        },
                        "required": ["item_id", "new_parent_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_copy_file",
                    "description": "Create a copy of a file in OneDrive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The item ID to copy."},
                            "new_parent_id": {"type": "string", "description": "Destination folder ID (optional)."},
                            "new_name": {"type": "string", "description": "Name for the copy (optional)."},
                        },
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_delete_file",
                    "description": "Permanently delete a file or folder from OneDrive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The item ID to delete."},
                        },
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_list_recent",
                    "description": "List files across OneDrive that the user has recently viewed or modified.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "top": {"type": "integer", "description": "Max items to return (default 25)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_list_shared_with_me",
                    "description": "List files and folders that other people have shared with the connected OneDrive account.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "top": {"type": "integer", "description": "Max items to return (default 25)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_track_changes",
                    "description": "Track created, updated, and deleted items in a folder since the last sync using delta query. Pass a previous 'delta_link' to resume; omit it to start a fresh sync.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "folder": {"type": "string", "description": "Folder ID to track (default 'root'). Ignored if 'delta_link' is given."},
                            "delta_link": {"type": "string", "description": "The '@odata.deltaLink' or '@odata.nextLink' URL from a previous call, to resume tracking."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_list_versions",
                    "description": "List the version history of a file in OneDrive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The item ID."},
                        },
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_restore_version",
                    "description": "Restore a previous version of a file to be the current version. Existing versions are preserved.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The item ID."},
                            "version_id": {"type": "string", "description": "The version ID to restore (from onedrive_list_versions)."},
                        },
                        "required": ["item_id", "version_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_get_thumbnails",
                    "description": "Get available thumbnail image URLs (small/medium/large) for a file in OneDrive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The item ID."},
                        },
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_get_permissions",
                    "description": "List sharing permissions for a file or folder.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The item ID."},
                        },
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "onedrive_share_file",
                    "description": "Create a sharing link for a file or folder.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The item ID to share."},
                            "type": {"type": "string", "description": "Link type: 'view' (default), 'edit', or 'embed'."},
                            "scope": {"type": "string", "description": "Link scope: 'anonymous' (default, anyone with link) or 'organization'."},
                        },
                        "required": ["item_id"],
                    },
                },
            },
        ]
        callables = {
            "onedrive_list_files": self.list_files,
            "onedrive_search_files": self.search_files,
            "onedrive_get_file": self.get_file,
            "onedrive_download_file": self.download_file,
            "onedrive_upload_file": self.upload_file,
            "onedrive_create_folder": self.create_folder,
            "onedrive_rename_file": self.rename_file,
            "onedrive_move_file": self.move_file,
            "onedrive_copy_file": self.copy_file,
            "onedrive_delete_file": self.delete_file,
            "onedrive_list_recent": self.list_recent,
            "onedrive_list_shared_with_me": self.list_shared_with_me,
            "onedrive_track_changes": self.track_changes,
            "onedrive_list_versions": self.list_versions,
            "onedrive_restore_version": self.restore_version,
            "onedrive_get_thumbnails": self.get_thumbnails,
            "onedrive_get_permissions": self.get_permissions,
            "onedrive_share_file": self.share_file,
        }
        return tools, callables

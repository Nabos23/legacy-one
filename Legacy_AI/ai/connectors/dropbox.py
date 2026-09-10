import base64
import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.dropboxapi.com/2"
_CONTENT_BASE = "https://content.dropboxapi.com/2"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Dropbox account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Dropbox connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class DropboxConnector(BaseConnector):

    PROVIDER_ID = "dropbox"

    def list_files(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_list_files", inp)
        if permission_error: return permission_error
        path = inp.get("path", "")
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "path": path,
                "recursive": inp.get("recursive", False),
                "limit": inp.get("limit", 50),
            }
            resp = httpx.post(f"{_BASE}/files/list_folder", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            entries = [
                {
                    "name": e["name"],
                    "path": e["path_display"],
                    "type": e[".tag"],
                    "size": e.get("size"),
                    "modified": e.get("server_modified"),
                }
                for e in data.get("entries", [])
            ]
            return json.dumps({"entries": entries, "has_more": data.get("has_more", False)})
        except Exception as e:
            return _handle_error("dropbox_list_files", e)

    def get_file_metadata(self, inp: dict) -> str:
        permission_error, path = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_get_file_metadata", inp, "path")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(f"{_BASE}/files/get_metadata", headers=headers, json={"path": path}, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("dropbox_get_file_metadata", e)

    def search_files(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_search_files", inp, "query")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"query": query, "options": {"max_results": inp.get("max_results", 20)}}
            resp = httpx.post(f"{_BASE}/files/search_v2", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            matches = [
                {
                    "name": m["metadata"]["metadata"].get("name"),
                    "path": m["metadata"]["metadata"].get("path_display"),
                    "type": m["metadata"]["metadata"].get(".tag"),
                }
                for m in data.get("matches", [])
            ]
            return json.dumps(matches)
        except Exception as e:
            return _handle_error("dropbox_search_files", e)

    def create_folder(self, inp: dict) -> str:
        permission_error, path = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_create_folder", inp, "path")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(f"{_BASE}/files/create_folder_v2", headers=headers, json={"path": path}, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "created", "path": path})
        except Exception as e:
            return _handle_error("dropbox_create_folder", e)

    def delete_file(self, inp: dict) -> str:
        permission_error, path = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_delete_file", inp, "path")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(f"{_BASE}/files/delete_v2", headers=headers, json={"path": path}, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "deleted", "path": path})
        except Exception as e:
            return _handle_error("dropbox_delete_file", e)

    def get_share_link(self, inp: dict) -> str:
        permission_error, path = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_get_share_link", inp, "path")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{_BASE}/sharing/create_shared_link_with_settings",
                headers=headers,
                json={"path": path},
                timeout=15,
            )
            if resp.status_code == 409:
                data = resp.json()
                return json.dumps({"url": data.get("error", {}).get("shared_link_already_exists", {}).get("metadata", {}).get("url", "Already shared")})
            resp.raise_for_status()
            return json.dumps({"url": resp.json().get("url")})
        except Exception as e:
            return _handle_error("dropbox_get_share_link", e)

    def upload_file(self, inp: dict) -> str:
        permission_error, path, content = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_upload_file", inp, "path", "content")
        if permission_error: return permission_error
        mode = inp.get("mode", "add")
        try:
            api_arg = json.dumps({"path": path, "mode": mode, "autorename": True})
            headers = {
                **self._auth_headers,
                "Content-Type": "application/octet-stream",
                "Dropbox-API-Arg": api_arg,
            }
            resp = httpx.post(
                f"{_CONTENT_BASE}/files/upload",
                headers=headers,
                content=content.encode("utf-8"),
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data.get("id"),
                "name": data.get("name"),
                "path_display": data.get("path_display"),
                "size": data.get("size"),
                "client_modified": data.get("client_modified"),
            })
        except Exception as e:
            return _handle_error("dropbox_upload_file", e)

    def download_file(self, inp: dict) -> str:
        permission_error, path = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_download_file", inp, "path")
        if permission_error: return permission_error
        try:
            api_arg = json.dumps({"path": path})
            headers = {
                **self._auth_headers,
                "Content-Type": "",
                "Dropbox-API-Arg": api_arg,
            }
            resp = httpx.post(
                f"{_CONTENT_BASE}/files/download",
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()
            try:
                return json.dumps({"content": resp.content.decode("utf-8")})
            except UnicodeDecodeError:
                return json.dumps({"content": base64.b64encode(resp.content).decode("ascii"), "encoding": "base64"})
        except Exception as e:
            return _handle_error("dropbox_download_file", e)

    def move_file(self, inp: dict) -> str:
        permission_error, from_path, to_path = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_move_file", inp, "from_path", "to_path")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"from_path": from_path, "to_path": to_path, "autorename": True}
            resp = httpx.post(f"{_BASE}/files/move_v2", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("metadata", {})
            return json.dumps({
                "status": "moved",
                "name": data.get("name"),
                "path_display": data.get("path_display"),
            })
        except Exception as e:
            return _handle_error("dropbox_move_file", e)

    def copy_file(self, inp: dict) -> str:
        permission_error, from_path, to_path = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_copy_file", inp, "from_path", "to_path")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"from_path": from_path, "to_path": to_path, "autorename": True}
            resp = httpx.post(f"{_BASE}/files/copy_v2", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("metadata", {})
            return json.dumps({
                "status": "copied",
                "name": data.get("name"),
                "path_display": data.get("path_display"),
            })
        except Exception as e:
            return _handle_error("dropbox_copy_file", e)

    def create_shared_link(self, inp: dict) -> str:
        permission_error, path = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_create_shared_link", inp, "path")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"path": path, "settings": {"requested_visibility": "public"}}
            resp = httpx.post(
                f"{_BASE}/sharing/create_shared_link_with_settings",
                headers=headers,
                json=body,
                timeout=15,
            )
            if resp.status_code == 409:
                data = resp.json()
                existing_url = (
                    data.get("error", {})
                    .get("shared_link_already_exists", {})
                    .get("metadata", {})
                    .get("url", "Already shared")
                )
                return json.dumps({"url": existing_url})
            resp.raise_for_status()
            return json.dumps({"url": resp.json().get("url")})
        except Exception as e:
            return _handle_error("dropbox_create_shared_link", e)

    def get_account_info(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_get_account_info", inp)
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(f"{_BASE}/users/get_current_account", headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "account_id": data.get("account_id"),
                "display_name": data.get("name", {}).get("display_name"),
                "email": data.get("email"),
                "account_type": data.get("account_type", {}).get(".tag"),
            })
        except Exception as e:
            return _handle_error("dropbox_get_account_info", e)

    def list_files_continue(self, inp: dict) -> str:
        permission_error, cursor = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_list_files_continue", inp, "cursor")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{_BASE}/files/list_folder/continue",
                headers=headers,
                json={"cursor": cursor},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            entries = [
                {
                    "name": e["name"],
                    "path": e["path_display"],
                    "type": e[".tag"],
                    "size": e.get("size"),
                    "modified": e.get("server_modified"),
                }
                for e in data.get("entries", [])
            ]
            return json.dumps({
                "entries": entries,
                "has_more": data.get("has_more", False),
                "cursor": data.get("cursor"),
            })
        except Exception as e:
            return _handle_error("dropbox_list_files_continue", e)

    def get_temporary_link(self, inp: dict) -> str:
        permission_error, path = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_get_temporary_link", inp, "path")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{_BASE}/files/get_temporary_link",
                headers=headers,
                json={"path": path},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "link": data.get("link"),
                "name": data.get("metadata", {}).get("name"),
                "path_display": data.get("metadata", {}).get("path_display"),
            })
        except Exception as e:
            return _handle_error("dropbox_get_temporary_link", e)

    def list_revisions(self, inp: dict) -> str:
        permission_error, path = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_list_revisions", inp, "path")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "path": path,
                "mode": inp.get("mode", "path"),
                "limit": inp.get("limit", 10),
            }
            resp = httpx.post(f"{_BASE}/files/list_revisions", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            entries = [
                {
                    "rev": e.get("rev"),
                    "name": e.get("name"),
                    "size": e.get("size"),
                    "modified": e.get("server_modified"),
                }
                for e in data.get("entries", [])
            ]
            return json.dumps({"is_deleted": data.get("is_deleted", False), "entries": entries})
        except Exception as e:
            return _handle_error("dropbox_list_revisions", e)

    def restore_file(self, inp: dict) -> str:
        permission_error, path, rev = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_restore_file", inp, "path", "rev")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{_BASE}/files/restore",
                headers=headers,
                json={"path": path, "rev": rev},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "status": "restored",
                "name": data.get("name"),
                "path_display": data.get("path_display"),
                "rev": data.get("rev"),
            })
        except Exception as e:
            return _handle_error("dropbox_restore_file", e)

    def delete_batch(self, inp: dict) -> str:
        permission_error, paths = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_delete_batch", inp, "paths")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"entries": [{"path": p} for p in paths]}
            resp = httpx.post(f"{_BASE}/files/delete_batch", headers=headers, json=body, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get(".tag") == "complete":
                results = [
                    {
                        "path": r.get("delete_batch_result", r.get("metadata", {})).get("path_display")
                        if isinstance(r, dict)
                        else None,
                        "status": r.get(".tag"),
                    }
                    for r in data.get("entries", [])
                ]
                return json.dumps({"status": "complete", "results": results})
            return json.dumps({"status": data.get(".tag", "async_job_launched"), "async_job_id": data.get("async_job_id")})
        except Exception as e:
            return _handle_error("dropbox_delete_batch", e)

    def create_file_request(self, inp: dict) -> str:
        permission_error, title, destination = self._check(self.agent_id, self.PROVIDER_ID, "dropbox_create_file_request", inp, "title", "destination")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "title": title,
                "destination": destination,
                "open": inp.get("open", True),
            }
            if inp.get("description"):
                body["description"] = inp["description"]
            resp = httpx.post(f"{_BASE}/file_requests/create", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data.get("id"),
                "url": data.get("url"),
                "title": data.get("title"),
                "destination": data.get("destination"),
                "is_open": data.get("is_open"),
            })
        except Exception as e:
            return _handle_error("dropbox_create_file_request", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "dropbox_list_files",
                    "description": "List files and folders in a Dropbox directory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Folder path (empty string for root)."},
                            "limit": {"type": "integer", "description": "Max items to return (default 50)."},
                            "recursive": {"type": "boolean", "description": "List recursively (default false)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dropbox_get_file_metadata",
                    "description": "Get metadata for a specific file or folder in Dropbox.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Full path to the file or folder."},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dropbox_search_files",
                    "description": "Search for files in Dropbox by name or content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query."},
                            "max_results": {"type": "integer", "description": "Max results (default 20)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dropbox_create_folder",
                    "description": "Create a new folder in Dropbox.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Full path of the folder to create (e.g. /My Folder)."},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dropbox_delete_file",
                    "description": "Delete a file or folder from Dropbox.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Full path of the file or folder to delete."},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dropbox_get_share_link",
                    "description": "Create or get a shareable link for a Dropbox file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Full path to the file."},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dropbox_upload_file",
                    "description": "Upload a file to Dropbox.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Destination path in Dropbox (e.g. /folder/file.txt)."},
                            "content": {"type": "string", "description": "File content as a string."},
                            "mode": {"type": "string", "description": "Write mode: 'add' (default), 'overwrite', or 'update'."},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dropbox_download_file",
                    "description": "Download a file from Dropbox and return its content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Full path to the file in Dropbox."},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dropbox_move_file",
                    "description": "Move a file or folder to a new location in Dropbox.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from_path": {"type": "string", "description": "Current path of the file or folder."},
                            "to_path": {"type": "string", "description": "Destination path."},
                        },
                        "required": ["from_path", "to_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dropbox_copy_file",
                    "description": "Copy a file or folder to a new location in Dropbox.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from_path": {"type": "string", "description": "Path of the file or folder to copy."},
                            "to_path": {"type": "string", "description": "Destination path for the copy."},
                        },
                        "required": ["from_path", "to_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dropbox_create_shared_link",
                    "description": "Create a public shared link for a file or folder in Dropbox.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Full path to the file or folder."},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dropbox_get_account_info",
                    "description": "Get information about the connected Dropbox account (name, email, account type).",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
        ]
        callables = {
            "dropbox_list_files": self.list_files,
            "dropbox_get_file_metadata": self.get_file_metadata,
            "dropbox_search_files": self.search_files,
            "dropbox_create_folder": self.create_folder,
            "dropbox_delete_file": self.delete_file,
            "dropbox_get_share_link": self.get_share_link,
            "dropbox_upload_file": self.upload_file,
            "dropbox_download_file": self.download_file,
            "dropbox_move_file": self.move_file,
            "dropbox_copy_file": self.copy_file,
            "dropbox_create_shared_link": self.create_shared_link,
            "dropbox_get_account_info": self.get_account_info,
        }
        return tools, callables

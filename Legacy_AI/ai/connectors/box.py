import base64
import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.box.com/2.0"
_UPLOAD_BASE = "https://upload.box.com/api/2.0"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Box account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Box connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class BoxConnector(BaseConnector):

    PROVIDER_ID = "box"

    def list_files(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "box_list_files", inp)
        if permission_error: return permission_error
        folder_id = inp.get("folder_id", "0")
        try:
            params = {"limit": inp.get("limit", 50), "fields": "id,name,type,size,modified_at,parent"}
            resp = httpx.get(f"{_BASE}/folders/{folder_id}/items", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            items = [
                {
                    "id": i["id"],
                    "name": i["name"],
                    "type": i["type"],
                    "size": i.get("size"),
                    "modified_at": i.get("modified_at"),
                }
                for i in data.get("entries", [])
            ]
            return json.dumps({"items": items, "total_count": data.get("total_count")})
        except Exception as e:
            return _handle_error("box_list_files", e)

    def get_file_info(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "box_get_file_info", inp, "file_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/files/{file_id}", headers=self._auth_headers, params={"fields": "id,name,size,modified_at,shared_link,parent"}, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("box_get_file_info", e)

    def search_files(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "box_search_files", inp, "query")
        if permission_error: return permission_error
        try:
            params = {"query": query, "limit": inp.get("limit", 20), "fields": "id,name,type,size,modified_at"}
            resp = httpx.get(f"{_BASE}/search", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps([{"id": i["id"], "name": i["name"], "type": i["type"]} for i in data.get("entries", [])])
        except Exception as e:
            return _handle_error("box_search_files", e)

    def create_folder(self, inp: dict) -> str:
        permission_error, name = self._check(self.agent_id, self.PROVIDER_ID, "box_create_folder", inp, "name")
        if permission_error: return permission_error
        parent_id = inp.get("parent_id", "0")
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"name": name, "parent": {"id": parent_id}}
            resp = httpx.post(f"{_BASE}/folders", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "name": data["name"], "status": "created"})
        except Exception as e:
            return _handle_error("box_create_folder", e)

    def delete_file(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "box_delete_file", inp, "file_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/files/{file_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "deleted", "file_id": file_id})
        except Exception as e:
            return _handle_error("box_delete_file", e)

    def get_shared_link(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "box_get_shared_link", inp, "file_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"shared_link": {"access": inp.get("access", "open")}}
            resp = httpx.put(f"{_BASE}/files/{file_id}", headers=headers, json=body, params={"fields": "shared_link"}, timeout=15)
            resp.raise_for_status()
            link = resp.json().get("shared_link", {})
            return json.dumps({"url": link.get("url"), "access": link.get("access")})
        except Exception as e:
            return _handle_error("box_get_shared_link", e)

    def upload_file(self, inp: dict) -> str:
        permission_error, filename, content = self._check(self.agent_id, self.PROVIDER_ID, "box_upload_file", inp, "filename", "content")
        if permission_error: return permission_error
        parent_folder_id = inp.get("parent_folder_id", "0")
        try:
            attributes = json.dumps({"name": filename, "parent": {"id": parent_folder_id}})
            resp = httpx.post(
                f"{_UPLOAD_BASE}/files/content",
                headers=self._auth_headers,
                data={"attributes": attributes},
                files={"file": (filename, content.encode("utf-8"))},
                timeout=60,
            )
            resp.raise_for_status()
            entries = resp.json().get("entries", [])
            if entries:
                f = entries[0]
                return json.dumps({
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "size": f.get("size"),
                    "status": "uploaded",
                })
            return json.dumps({"status": "uploaded", "raw": resp.json()})
        except Exception as e:
            return _handle_error("box_upload_file", e)

    def download_file(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "box_download_file", inp, "file_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/files/{file_id}/content", headers=self._auth_headers, follow_redirects=True, timeout=60)
            resp.raise_for_status()
            try:
                return json.dumps({"content": resp.content.decode("utf-8")})
            except UnicodeDecodeError:
                return json.dumps({"content": base64.b64encode(resp.content).decode("ascii"), "encoding": "base64"})
        except Exception as e:
            return _handle_error("box_download_file", e)

    def move_file(self, inp: dict) -> str:
        permission_error, file_id, folder_id = self._check(self.agent_id, self.PROVIDER_ID, "box_move_file", inp, "file_id", "folder_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"parent": {"id": folder_id}}
            resp = httpx.put(f"{_BASE}/files/{file_id}", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "status": "moved",
                "id": data.get("id"),
                "name": data.get("name"),
                "parent_id": data.get("parent", {}).get("id"),
            })
        except Exception as e:
            return _handle_error("box_move_file", e)

    def copy_file(self, inp: dict) -> str:
        permission_error, file_id, folder_id = self._check(self.agent_id, self.PROVIDER_ID, "box_copy_file", inp, "file_id", "folder_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"parent": {"id": folder_id}}
            new_name = inp.get("new_name")
            if new_name:
                body["name"] = new_name
            resp = httpx.post(f"{_BASE}/files/{file_id}/copy", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "status": "copied",
                "id": data.get("id"),
                "name": data.get("name"),
                "parent_id": data.get("parent", {}).get("id"),
            })
        except Exception as e:
            return _handle_error("box_copy_file", e)

    def delete_folder(self, inp: dict) -> str:
        permission_error, folder_id = self._check(self.agent_id, self.PROVIDER_ID, "box_delete_folder", inp, "folder_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(
                f"{_BASE}/folders/{folder_id}",
                headers=self._auth_headers,
                params={"recursive": "true"},
                timeout=30,
            )
            resp.raise_for_status()
            return json.dumps({"status": "deleted", "folder_id": folder_id})
        except Exception as e:
            return _handle_error("box_delete_folder", e)

    def get_user_info(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "box_get_user_info", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/users/me", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data.get("id"),
                "name": data.get("name"),
                "email": data.get("login"),
                "space_used": data.get("space_used"),
                "space_amount": data.get("space_amount"),
            })
        except Exception as e:
            return _handle_error("box_get_user_info", e)

    def create_shared_link(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "box_create_shared_link", inp, "file_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"shared_link": {"access": "open"}}
            resp = httpx.put(
                f"{_BASE}/files/{file_id}",
                headers=headers,
                json=body,
                params={"fields": "shared_link"},
                timeout=15,
            )
            resp.raise_for_status()
            link = resp.json().get("shared_link", {})
            return json.dumps({"url": link.get("url"), "access": link.get("access")})
        except Exception as e:
            return _handle_error("box_create_shared_link", e)

    def add_collaboration(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "box_add_collaboration", inp, "item_id")
        if permission_error: return permission_error
        item_type = inp.get("item_type", "folder")
        role = inp.get("role", "editor")
        login = inp.get("login", "")
        user_id = inp.get("user_id", "")
        if not login and not user_id:
            return "Error: either 'login' or 'user_id' is required."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            accessible_by: dict = {"type": "user"}
            if user_id:
                accessible_by["id"] = user_id
            else:
                accessible_by["login"] = login
            body = {
                "item": {"id": item_id, "type": item_type},
                "accessible_by": accessible_by,
                "role": role,
            }
            resp = httpx.post(f"{_BASE}/collaborations", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data.get("id"),
                "status": data.get("status"),
                "role": data.get("role"),
            })
        except Exception as e:
            return _handle_error("box_add_collaboration", e)

    def list_file_versions(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "box_list_file_versions", inp, "file_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/files/{file_id}/versions", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            versions = [
                {"id": v.get("id"), "name": v.get("name"), "size": v.get("size"), "modified_at": v.get("modified_at")}
                for v in data.get("entries", [])
            ]
            return json.dumps({"versions": versions, "total_count": data.get("total_count")})
        except Exception as e:
            return _handle_error("box_list_file_versions", e)

    def promote_file_version(self, inp: dict) -> str:
        permission_error, file_id, version_id = self._check(self.agent_id, self.PROVIDER_ID, "box_promote_file_version", inp, "file_id", "version_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"type": "file_version", "id": version_id}
            resp = httpx.post(f"{_BASE}/files/{file_id}/versions/current", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"status": "promoted", "id": data.get("id"), "file_id": file_id})
        except Exception as e:
            return _handle_error("box_promote_file_version", e)

    def add_comment(self, inp: dict) -> str:
        permission_error, file_id, message = self._check(self.agent_id, self.PROVIDER_ID, "box_add_comment", inp, "file_id", "message")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"item": {"id": file_id, "type": "file"}, "message": message}
            resp = httpx.post(f"{_BASE}/comments", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "message": data.get("message"), "status": "created"})
        except Exception as e:
            return _handle_error("box_add_comment", e)

    def list_comments(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "box_list_comments", inp, "file_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/files/{file_id}/comments", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            comments = [
                {"id": c.get("id"), "message": c.get("message"), "created_by": c.get("created_by", {}).get("name")}
                for c in data.get("entries", [])
            ]
            return json.dumps({"comments": comments, "total_count": data.get("total_count")})
        except Exception as e:
            return _handle_error("box_list_comments", e)

    def restore_file(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "box_restore_file", inp, "file_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {}
            parent_id = inp.get("parent_id")
            if parent_id:
                body["parent"] = {"id": parent_id}
            resp = httpx.post(f"{_BASE}/files/{file_id}", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"status": "restored", "id": data.get("id"), "name": data.get("name")})
        except Exception as e:
            return _handle_error("box_restore_file", e)

    def permanently_delete_file(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "box_permanently_delete_file", inp, "file_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/files/{file_id}/trash", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "permanently_deleted", "file_id": file_id})
        except Exception as e:
            return _handle_error("box_permanently_delete_file", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "box_list_files",
                    "description": "List files and folders in a Box folder.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "folder_id": {"type": "string", "description": "Box folder ID (default '0' for root)."},
                            "limit": {"type": "integer", "description": "Max items to return (default 50)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_get_file_info",
                    "description": "Get metadata for a specific Box file.",
                    "parameters": {"type": "object", "properties": {"file_id": {"type": "string", "description": "The Box file ID."}}, "required": ["file_id"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_search_files",
                    "description": "Search for files in Box.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query."},
                            "limit": {"type": "integer", "description": "Max results (default 20)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_create_folder",
                    "description": "Create a new folder in Box.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Folder name."},
                            "parent_id": {"type": "string", "description": "Parent folder ID (default '0' for root)."},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_delete_file",
                    "description": "Delete a file from Box.",
                    "parameters": {"type": "object", "properties": {"file_id": {"type": "string", "description": "The Box file ID to delete."}}, "required": ["file_id"]},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_get_shared_link",
                    "description": "Create or get a shared link for a Box file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The Box file ID."},
                            "access": {"type": "string", "description": "Access level: open, company, collaborators (default open)."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_upload_file",
                    "description": "Upload a file to Box.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string", "description": "Name of the file to create in Box."},
                            "content": {"type": "string", "description": "File content as a string."},
                            "parent_folder_id": {"type": "string", "description": "Parent folder ID (default '0' for root)."},
                        },
                        "required": ["filename", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_download_file",
                    "description": "Download a file from Box and return its content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The Box file ID to download."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_move_file",
                    "description": "Move a file to a different folder in Box.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The Box file ID to move."},
                            "folder_id": {"type": "string", "description": "Destination folder ID."},
                        },
                        "required": ["file_id", "folder_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_copy_file",
                    "description": "Copy a file to a different folder in Box.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The Box file ID to copy."},
                            "folder_id": {"type": "string", "description": "Destination folder ID."},
                            "new_name": {"type": "string", "description": "Optional new name for the copied file."},
                        },
                        "required": ["file_id", "folder_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_delete_folder",
                    "description": "Delete a folder and all its contents from Box.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "folder_id": {"type": "string", "description": "The Box folder ID to delete."},
                        },
                        "required": ["folder_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_get_user_info",
                    "description": "Get information about the connected Box user (id, name, email, storage usage).",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_create_shared_link",
                    "description": "Create a public shared link for a Box file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The Box file ID to share."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_add_collaboration",
                    "description": "Add a collaborator (by email login or user ID) to a Box file or folder with a given role.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "The Box file or folder ID to share."},
                            "item_type": {"type": "string", "description": "Type of item: 'file' or 'folder' (default 'folder')."},
                            "login": {"type": "string", "description": "Email address of the user to invite (use this or user_id)."},
                            "user_id": {"type": "string", "description": "Box user ID to invite (use this or login)."},
                            "role": {"type": "string", "description": "Collaboration role, e.g. editor, viewer, co-owner (default editor)."},
                        },
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_list_file_versions",
                    "description": "List the version history of a Box file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The Box file ID."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_promote_file_version",
                    "description": "Promote an older version of a Box file to become the current version.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The Box file ID."},
                            "version_id": {"type": "string", "description": "The ID of the file version to promote."},
                        },
                        "required": ["file_id", "version_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_add_comment",
                    "description": "Add a comment to a Box file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The Box file ID to comment on."},
                            "message": {"type": "string", "description": "The comment text."},
                        },
                        "required": ["file_id", "message"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_list_comments",
                    "description": "List comments on a Box file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The Box file ID."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_restore_file",
                    "description": "Restore a previously deleted (trashed) Box file, optionally into a different parent folder.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The Box file ID to restore."},
                            "parent_id": {"type": "string", "description": "Optional new parent folder ID, if the original folder no longer exists."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "box_permanently_delete_file",
                    "description": "Permanently remove a file from the Box trash. This action cannot be undone.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The Box file ID (already in trash) to permanently delete."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
        ]
        callables = {
            "box_list_files": self.list_files,
            "box_get_file_info": self.get_file_info,
            "box_search_files": self.search_files,
            "box_create_folder": self.create_folder,
            "box_delete_file": self.delete_file,
            "box_get_shared_link": self.get_shared_link,
            "box_upload_file": self.upload_file,
            "box_download_file": self.download_file,
            "box_move_file": self.move_file,
            "box_copy_file": self.copy_file,
            "box_delete_folder": self.delete_folder,
            "box_get_user_info": self.get_user_info,
            "box_create_shared_link": self.create_shared_link,
            "box_add_collaboration": self.add_collaboration,
            "box_list_file_versions": self.list_file_versions,
            "box_promote_file_version": self.promote_file_version,
            "box_add_comment": self.add_comment,
            "box_list_comments": self.list_comments,
            "box_restore_file": self.restore_file,
            "box_permanently_delete_file": self.permanently_delete_file,
        }
        return tools, callables

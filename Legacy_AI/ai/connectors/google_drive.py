import json
import mimetypes
import os
from pathlib import Path
import httpx

from ai.connectors.base import BaseConnector
from backend.core.uploads import delete_report_file, resolve_local_attachment_path

_BASE = "https://www.googleapis.com/drive/v3"
_UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Google Drive account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Google Drive connector with the required OAuth scopes."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


_FILE_FIELDS = "id,name,mimeType,size,modifiedTime,parents,webViewLink,webContentLink"


class GoogleDriveConnector(BaseConnector):

    PROVIDER_ID = "google-drive"

    # ── List / Search ─────────────────────────────────────────────────────────

    def list_files(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_list_files", inp)
        if permission_error: return permission_error
        try:
            params = {
                "pageSize": inp.get("page_size", 50),
                "fields": f"files({_FILE_FIELDS})",
                "orderBy": inp.get("order_by", "modifiedTime desc"),
            }
            if inp.get("query"):
                params["q"] = inp["query"]
            if inp.get("folder_id"):
                q = f"'{inp['folder_id']}' in parents"
                params["q"] = f"{params['q']} and {q}" if params.get("q") else q
            resp = httpx.get(f"{_BASE}/files", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_drive_list_files", e)

    def get_file(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_get_file", inp, "file_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/files/{file_id}",
                headers=self._auth_headers,
                params={"fields": _FILE_FIELDS},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_drive_get_file", e)

    # ── Read / Write ──────────────────────────────────────────────────────────

    def download_file(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_download_file", inp, "file_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/files/{file_id}",
                headers=self._auth_headers,
                params={"alt": "media"},
                timeout=30,
            )
            resp.raise_for_status()
            text = resp.text[:4000]
            return json.dumps({"file_id": file_id, "content": text, "truncated": len(resp.text) > 4000})
        except Exception as e:
            return _handle_error("google_drive_download_file", e)

    def export_file(self, inp: dict) -> str:
        """Export a Google Workspace file (Docs/Sheets/Slides) to a plain format."""
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_export_file", inp, "file_id")
        if permission_error: return permission_error
        mime_type = inp.get("mime_type", "text/plain")
        try:
            resp = httpx.get(
                f"{_BASE}/files/{file_id}/export",
                headers=self._auth_headers,
                params={"mimeType": mime_type},
                timeout=30,
            )
            resp.raise_for_status()
            text = resp.text[:4000]
            return json.dumps({"file_id": file_id, "content": text, "truncated": len(resp.text) > 4000})
        except Exception as e:
            return _handle_error("google_drive_export_file", e)

    def upload_file(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_upload_file", inp)
        if permission_error: return permission_error
        try:
            name = inp.get("name", "").strip()
            content = inp.get("content", "")
            mime_type = inp.get("mime_type", "").strip()
            folder_id = inp.get("folder_id", "").strip()

            file_key = (
                inp.get("file_path") or inp.get("attachment_path") or inp.get("path") or inp.get("file_name") or ""
            ).strip()

            if not file_key and ("chat/reports/" in name or "reports/" in name or name.endswith((".pdf", ".xlsx", ".png", ".docx", ".csv", ".jpg", ".jpeg"))):
                file_key = name

            report_file_to_delete = None
            body = None

            if file_key:
                safe_name = os.path.basename(file_key)
                filepath = resolve_local_attachment_path(safe_name)
                if not filepath and os.path.isfile(file_key):
                    filepath = file_key

                if filepath:
                    try:
                        with open(filepath, "rb") as f:
                            body = f.read()
                        if not name or "chat/reports/" in name or "reports/" in name:
                            name = safe_name
                        if not mime_type:
                            guessed_type, _ = mimetypes.guess_type(safe_name)
                            mime_type = guessed_type or "application/octet-stream"

                        report_file_to_delete = safe_name
                    except Exception as e:
                        return f"Error reading local file '{file_key}': {str(e)}"
                else:
                    if not content:
                        return f"Error: Local report file '{safe_name}' not found in storage."

            if body is None:
                if not name:
                    name = "untitled"
                body = content.encode() if isinstance(content, str) else content

            if not mime_type:
                mime_type = "text/plain"

            metadata: dict = {"name": name}
            if folder_id:
                metadata["parents"] = [folder_id]

            meta_bytes = json.dumps(metadata).encode()
            boundary = "boundary_oneai"
            parts = (
                f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
                + meta_bytes
                + f"\r\n--{boundary}\r\nContent-Type: {mime_type}\r\n\r\n".encode()
                + body
                + f"\r\n--{boundary}--".encode()
            )

            resp = httpx.post(
                f"{_UPLOAD_BASE}/files?uploadType=multipart",
                headers={**self._auth_headers, "Content-Type": f"multipart/related; boundary={boundary}"},
                content=parts,
                timeout=30,
            )
            resp.raise_for_status()

            if report_file_to_delete:
                delete_report_file(report_file_to_delete)

            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_drive_upload_file", e)

    def list_revisions(self, inp: dict) -> str:
        """List the revision history of a file (previous saved versions)."""
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_list_revisions", inp, "file_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/files/{file_id}/revisions",
                headers=self._auth_headers,
                params={"fields": "revisions(id,modifiedTime,size,keepForever,originalFilename,lastModifyingUser)"},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_drive_list_revisions", e)

    # ── Folder ────────────────────────────────────────────────────────────────

    def create_folder(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_create_folder", inp)
        if permission_error: return permission_error
        name = inp.get("name", "New Folder")
        parent_id = inp.get("parent_id", "")
        try:
            metadata: dict = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
            if parent_id:
                metadata["parents"] = [parent_id]
            resp = httpx.post(
                f"{_BASE}/files",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=metadata,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_drive_create_folder", e)

    # ── Manage ────────────────────────────────────────────────────────────────

    def rename_file(self, inp: dict) -> str:
        permission_error, file_id, new_name = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_rename_file", inp, "file_id", "new_name")
        if permission_error: return permission_error
        try:
            resp = httpx.patch(
                f"{_BASE}/files/{file_id}",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"name": new_name},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_drive_rename_file", e)

    def move_file(self, inp: dict) -> str:
        permission_error, file_id, new_parent_id = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_move_file", inp, "file_id", "new_parent_id")
        if permission_error: return permission_error
        try:
            meta = httpx.get(f"{_BASE}/files/{file_id}", headers=self._auth_headers, params={"fields": "parents"}, timeout=15)
            meta.raise_for_status()
            current_parents = ",".join(meta.json().get("parents", []))
            resp = httpx.patch(
                f"{_BASE}/files/{file_id}",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                params={"addParents": new_parent_id, "removeParents": current_parents, "fields": "id,parents"},
                json={},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_drive_move_file", e)

    def copy_file(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_copy_file", inp, "file_id")
        if permission_error: return permission_error
        new_name = inp.get("new_name", "")
        try:
            body: dict = {}
            if new_name:
                body["name"] = new_name
            if inp.get("parent_id"):
                body["parents"] = [inp["parent_id"]]
            resp = httpx.post(
                f"{_BASE}/files/{file_id}/copy",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_drive_copy_file", e)

    def delete_file(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_delete_file", inp, "file_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/files/{file_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"ok": True, "deleted": file_id})
        except Exception as e:
            return _handle_error("google_drive_delete_file", e)

    def trash_file(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_trash_file", inp, "file_id")
        if permission_error: return permission_error
        try:
            resp = httpx.patch(
                f"{_BASE}/files/{file_id}",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"trashed": True},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"ok": True, "trashed": file_id})
        except Exception as e:
            return _handle_error("google_drive_trash_file", e)

    def empty_trash(self, inp: dict) -> str:
        """Permanently delete all files currently in the trash."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_empty_trash", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/files/trash", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"ok": True, "trash_emptied": True})
        except Exception as e:
            return _handle_error("google_drive_empty_trash", e)

    # ── Sharing / Permissions ─────────────────────────────────────────────────

    def get_permissions(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_get_permissions", inp, "file_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/files/{file_id}/permissions",
                headers=self._auth_headers,
                params={"fields": "permissions(id,type,role,emailAddress,displayName)"},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_drive_get_permissions", e)

    def share_file(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_share_file", inp, "file_id")
        if permission_error: return permission_error
        email = inp.get("email", "")
        role = inp.get("role", "reader")
        try:
            body: dict = {"role": role}
            if email:
                body["type"] = "user"
                body["emailAddress"] = email
            else:
                body["type"] = "anyone"
            resp = httpx.post(
                f"{_BASE}/files/{file_id}/permissions",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_drive_share_file", e)

    def update_permission(self, inp: dict) -> str:
        """Change the role of an existing permission on a file (e.g. reader -> writer)."""
        permission_error, file_id, permission_id, role = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_update_permission", inp, "file_id", "permission_id", "role")
        if permission_error: return permission_error
        try:
            resp = httpx.patch(
                f"{_BASE}/files/{file_id}/permissions/{permission_id}",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"role": role},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_drive_update_permission", e)

    def delete_permission(self, inp: dict) -> str:
        """Revoke a person's or group's access to a file."""
        permission_error, file_id, permission_id = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_delete_permission", inp, "file_id", "permission_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(
                f"{_BASE}/files/{file_id}/permissions/{permission_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"ok": True, "file_id": file_id, "permission_id": permission_id, "revoked": True})
        except Exception as e:
            return _handle_error("google_drive_delete_permission", e)

    # ── Comments ──────────────────────────────────────────────────────────────

    def list_comments(self, inp: dict) -> str:
        """List comments left on a file, including their replies."""
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_list_comments", inp, "file_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/files/{file_id}/comments",
                headers=self._auth_headers,
                params={
                    "fields": "comments(id,content,author,createdTime,resolved,replies(id,content,author,createdTime))",
                    "includeDeleted": inp.get("include_deleted", False),
                },
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_drive_list_comments", e)

    def create_comment(self, inp: dict) -> str:
        """Add a new comment to a file."""
        permission_error, file_id, content = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_create_comment", inp, "file_id", "content")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/files/{file_id}/comments",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                params={"fields": "id,content,author,createdTime"},
                json={"content": content},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_drive_create_comment", e)

    # ── Changes / Sync ────────────────────────────────────────────────────────

    def list_changes(self, inp: dict) -> str:
        """List recent changes (created/modified/deleted files) for delta sync."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_list_changes", inp)
        if permission_error: return permission_error
        try:
            page_token = inp.get("page_token", "")
            if not page_token:
                start_resp = httpx.get(
                    f"{_BASE}/changes/startPageToken",
                    headers=self._auth_headers,
                    timeout=15,
                )
                start_resp.raise_for_status()
                page_token = start_resp.json().get("startPageToken", "")
            resp = httpx.get(
                f"{_BASE}/changes",
                headers=self._auth_headers,
                params={
                    "pageToken": page_token,
                    "pageSize": inp.get("page_size", 50),
                    "fields": f"newStartPageToken,nextPageToken,changes(fileId,removed,time,file({_FILE_FIELDS}))",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps(
                {
                    "changes": data.get("changes", []),
                    "next_page_token": data.get("nextPageToken", ""),
                    "new_start_page_token": data.get("newStartPageToken", ""),
                }
            )
        except Exception as e:
            return _handle_error("google_drive_list_changes", e)

    # ── Shared Drives ─────────────────────────────────────────────────────────

    def list_shared_drives(self, inp: dict) -> str:
        """List the shared drives (Team Drives) the user has access to."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "google_drive_list_shared_drives", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/drives",
                headers=self._auth_headers,
                params={"pageSize": inp.get("page_size", 50), "fields": "drives(id,name,createdTime)"},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_drive_list_shared_drives", e)

    # ── Tool manifest ─────────────────────────────────────────────────────────

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "google_drive_list_files",
                    "description": (
                        "List files in Google Drive. Supports Drive search query syntax: "
                        "'mimeType=\"application/pdf\"', 'name contains \"report\"', "
                        "'modifiedTime > \"2024-01-01\"', 'trashed = false'. "
                        "Use folder_id to list a specific folder."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Drive search query string."},
                            "folder_id": {"type": "string", "description": "List files inside this folder ID."},
                            "page_size": {"type": "integer", "description": "Max files to return (default 50)."},
                            "order_by": {"type": "string", "description": "Sort order (default 'modifiedTime desc')."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_get_file",
                    "description": "Get metadata for a specific file (name, MIME type, size, last modified, sharing link).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The Google Drive file ID."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_download_file",
                    "description": "Download and read the text content of a file from Google Drive (truncated to 4000 chars).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The Google Drive file ID to download."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_export_file",
                    "description": "Export a Google Workspace file (Docs, Sheets, Slides) to plain text, PDF, or DOCX format.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The Google Drive file ID."},
                            "mime_type": {"type": "string", "description": "Export format: 'text/plain' (default), 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_upload_file",
                    "description": "Upload a file or generated report to Google Drive. Supports raw content strings or generated local report files in storage/reports (e.g. 'sandbox:/chat/reports/latest_games_report.pdf' or 'latest_games_report.pdf'). Automatically deletes local report files after successful upload.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "File name (e.g. 'report.pdf')."},
                            "content": {"type": "string", "description": "Text content to upload (optional if file_path is provided)."},
                            "file_path": {"type": "string", "description": "Path or filename of local report generated in storage/reports (e.g. 'sandbox:/chat/reports/latest_games_report.pdf' or 'latest_games_report.pdf')."},
                            "mime_type": {"type": "string", "description": "MIME type (e.g. 'application/pdf', 'text/plain'). Auto-detected if file_path is provided."},
                            "folder_id": {"type": "string", "description": "Parent folder ID (optional, defaults to My Drive root)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_create_folder",
                    "description": "Create a new folder in Google Drive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Folder name."},
                            "parent_id": {"type": "string", "description": "Parent folder ID (optional, defaults to My Drive root)."},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_rename_file",
                    "description": "Rename a file or folder in Google Drive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The file or folder ID."},
                            "new_name": {"type": "string", "description": "New name for the file."},
                        },
                        "required": ["file_id", "new_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_move_file",
                    "description": "Move a file to a different folder in Google Drive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The file ID to move."},
                            "new_parent_id": {"type": "string", "description": "The destination folder ID."},
                        },
                        "required": ["file_id", "new_parent_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_copy_file",
                    "description": "Create a copy of a file in Google Drive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The file ID to copy."},
                            "new_name": {"type": "string", "description": "Name for the copy (optional)."},
                            "parent_id": {"type": "string", "description": "Destination folder ID (optional)."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_trash_file",
                    "description": "Move a file to Google Drive Trash (recoverable).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The file ID to trash."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_delete_file",
                    "description": "Permanently delete a file from Google Drive. This cannot be undone.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The file ID to permanently delete."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_get_permissions",
                    "description": "List who has access to a file (permissions, roles, emails).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The file ID."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_share_file",
                    "description": "Share a file with a specific person or make it public.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The file ID to share."},
                            "email": {"type": "string", "description": "Email address to share with. Leave empty to share with anyone."},
                            "role": {"type": "string", "description": "Permission role: 'reader' (default), 'commenter', or 'writer'."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_list_revisions",
                    "description": "List the revision (version) history of a file, showing previous saved versions with timestamps.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The file ID."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_empty_trash",
                    "description": "Permanently delete all files currently in the Google Drive trash. This cannot be undone.",
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
                    "name": "google_drive_update_permission",
                    "description": "Change the access role of an existing person/group/link on a file (e.g. upgrade a reader to a writer).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The file ID."},
                            "permission_id": {"type": "string", "description": "The permission ID to update (from google_drive_get_permissions)."},
                            "role": {"type": "string", "description": "New role: 'reader', 'commenter', or 'writer'."},
                        },
                        "required": ["file_id", "permission_id", "role"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_delete_permission",
                    "description": "Revoke a person's, group's, or link's access to a file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The file ID."},
                            "permission_id": {"type": "string", "description": "The permission ID to revoke (from google_drive_get_permissions)."},
                        },
                        "required": ["file_id", "permission_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_list_comments",
                    "description": "List comments (and their replies) left on a file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The file ID."},
                            "include_deleted": {"type": "boolean", "description": "Whether to include deleted comments (default false)."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_create_comment",
                    "description": "Add a new top-level comment to a file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The file ID to comment on."},
                            "content": {"type": "string", "description": "The comment text."},
                        },
                        "required": ["file_id", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_list_changes",
                    "description": (
                        "List recent changes (created, modified, or deleted files) for delta sync. "
                        "Pass 'next_page_token' from a previous call as 'page_token' to fetch changes since that point; "
                        "omit it to just obtain a fresh starting token with no historical changes."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_token": {"type": "string", "description": "Token from a previous call's 'next_page_token' or 'new_start_page_token'."},
                            "page_size": {"type": "integer", "description": "Max changes to return (default 50)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_drive_list_shared_drives",
                    "description": "List the shared drives (Team Drives) the connected account has access to.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_size": {"type": "integer", "description": "Max shared drives to return (default 50)."},
                        },
                        "required": [],
                    },
                },
            },
        ]
        callables = {
            "google_drive_list_files": self.list_files,
            "google_drive_get_file": self.get_file,
            "google_drive_download_file": self.download_file,
            "google_drive_export_file": self.export_file,
            "google_drive_upload_file": self.upload_file,
            "google_drive_create_folder": self.create_folder,
            "google_drive_rename_file": self.rename_file,
            "google_drive_move_file": self.move_file,
            "google_drive_copy_file": self.copy_file,
            "google_drive_trash_file": self.trash_file,
            "google_drive_delete_file": self.delete_file,
            "google_drive_get_permissions": self.get_permissions,
            "google_drive_share_file": self.share_file,
            "google_drive_list_revisions": self.list_revisions,
            "google_drive_empty_trash": self.empty_trash,
            "google_drive_update_permission": self.update_permission,
            "google_drive_delete_permission": self.delete_permission,
            "google_drive_list_comments": self.list_comments,
            "google_drive_create_comment": self.create_comment,
            "google_drive_list_changes": self.list_changes,
            "google_drive_list_shared_drives": self.list_shared_drives,
        }
        return tools, callables

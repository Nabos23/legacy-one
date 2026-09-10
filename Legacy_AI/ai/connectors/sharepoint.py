import json
import httpx

from ai.connectors.base import BaseConnector

_GRAPH = "https://graph.microsoft.com/v1.0"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected SharePoint account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their SharePoint connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class SharePointConnector(BaseConnector):

    PROVIDER_ID = "sharepoint"

    def list_sites(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_list_sites", inp)
        if permission_error: return permission_error
        try:
            search = inp.get("search", "")
            if search:
                resp = httpx.get(f"{_GRAPH}/sites", headers=self._auth_headers, params={"search": search}, timeout=15)
            else:
                resp = httpx.get(f"{_GRAPH}/sites/getAllSites", headers=self._auth_headers, params={"$top": inp.get("limit", 20)}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            sites = [
                {"id": s["id"], "name": s.get("name"), "displayName": s.get("displayName"), "webUrl": s.get("webUrl")}
                for s in data.get("value", [])
            ]
            return json.dumps({"sites": sites, "count": len(sites)})
        except Exception as e:
            return _handle_error("sharepoint_list_sites", e)

    def list_files(self, inp: dict) -> str:
        permission_error, site_id = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_list_files", inp, "site_id")
        if permission_error: return permission_error
        drive_id = inp.get("drive_id", "")
        folder_id = inp.get("folder_id", "root")
        try:
            if drive_id:
                url = f"{_GRAPH}/sites/{site_id}/drives/{drive_id}/items/{folder_id}/children"
            else:
                url = f"{_GRAPH}/sites/{site_id}/drive/items/{folder_id}/children"
            params = {"$top": inp.get("limit", 50), "$select": "id,name,file,folder,size,lastModifiedDateTime,webUrl"}
            resp = httpx.get(url, headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            items = [
                {
                    "id": i["id"],
                    "name": i["name"],
                    "type": "folder" if "folder" in i else "file",
                    "size": i.get("size"),
                    "lastModifiedDateTime": i.get("lastModifiedDateTime"),
                    "webUrl": i.get("webUrl"),
                }
                for i in data.get("value", [])
            ]
            return json.dumps({"items": items, "count": len(items)})
        except Exception as e:
            return _handle_error("sharepoint_list_files", e)

    def get_file_info(self, inp: dict) -> str:
        permission_error, site_id, item_id = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_get_file_info", inp, "site_id", "item_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_GRAPH}/sites/{site_id}/drive/items/{item_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            i = resp.json()
            return json.dumps({
                "id": i["id"],
                "name": i.get("name"),
                "size": i.get("size"),
                "webUrl": i.get("webUrl"),
                "lastModifiedDateTime": i.get("lastModifiedDateTime"),
                "createdDateTime": i.get("createdDateTime"),
            })
        except Exception as e:
            return _handle_error("sharepoint_get_file_info", e)

    def search_files(self, inp: dict) -> str:
        permission_error, site_id, query = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_search_files", inp, "site_id", "query")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_GRAPH}/sites/{site_id}/drive/root/search(q='{query}')",
                headers=self._auth_headers,
                params={"$top": inp.get("limit", 20), "$select": "id,name,webUrl,size,lastModifiedDateTime"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            items = [{"id": i["id"], "name": i["name"], "webUrl": i.get("webUrl")} for i in data.get("value", [])]
            return json.dumps(items)
        except Exception as e:
            return _handle_error("sharepoint_search_files", e)

    def list_drives(self, inp: dict) -> str:
        permission_error, site_id = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_list_drives", inp, "site_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_GRAPH}/sites/{site_id}/drives", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            drives = [{"id": d["id"], "name": d.get("name"), "driveType": d.get("driveType")} for d in resp.json().get("value", [])]
            return json.dumps(drives)
        except Exception as e:
            return _handle_error("sharepoint_list_drives", e)

    def upload_file(self, inp: dict) -> str:
        permission_error, site_id, drive_id, file_path, content = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_upload_file", inp, "site_id", "drive_id", "file_path", "content")
        if permission_error: return permission_error
        content_type = inp.get("content_type", "text/plain")
        try:
            url = f"{_GRAPH}/sites/{site_id}/drives/{drive_id}/root:/{file_path}:/content"
            headers = {**self._auth_headers, "Content-Type": content_type}
            resp = httpx.put(url, headers=headers, content=content.encode("utf-8"), timeout=30)
            resp.raise_for_status()
            i = resp.json()
            return json.dumps({
                "id": i.get("id"),
                "name": i.get("name"),
                "size": i.get("size"),
                "webUrl": i.get("webUrl"),
            })
        except Exception as e:
            return _handle_error("sharepoint_upload_file", e)

    def download_file(self, inp: dict) -> str:
        permission_error, site_id, drive_id, file_path = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_download_file", inp, "site_id", "drive_id", "file_path")
        if permission_error: return permission_error
        try:
            url = f"{_GRAPH}/sites/{site_id}/drives/{drive_id}/root:/{file_path}:/content"
            resp = httpx.get(url, headers=self._auth_headers, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            return _handle_error("sharepoint_download_file", e)

    def delete_file(self, inp: dict) -> str:
        permission_error, site_id, drive_id, file_path = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_delete_file", inp, "site_id", "drive_id", "file_path")
        if permission_error: return permission_error
        try:
            url = f"{_GRAPH}/sites/{site_id}/drives/{drive_id}/root:/{file_path}:"
            resp = httpx.delete(url, headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"deleted": True, "path": file_path})
        except Exception as e:
            return _handle_error("sharepoint_delete_file", e)

    def create_folder(self, inp: dict) -> str:
        permission_error, site_id, drive_id, folder_name = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_create_folder", inp, "site_id", "drive_id", "folder_name")
        if permission_error: return permission_error
        parent_path = inp.get("parent_path", "")
        try:
            if parent_path:
                url = f"{_GRAPH}/sites/{site_id}/drives/{drive_id}/root:/{parent_path}:/children"
            else:
                url = f"{_GRAPH}/sites/{site_id}/drives/{drive_id}/root/children"
            body = {
                "name": folder_name,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "rename",
            }
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(url, headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            f = resp.json()
            return json.dumps({
                "id": f.get("id"),
                "name": f.get("name"),
                "webUrl": f.get("webUrl"),
                "createdDateTime": f.get("createdDateTime"),
            })
        except Exception as e:
            return _handle_error("sharepoint_create_folder", e)

    def list_sharepoint_lists(self, inp: dict) -> str:
        permission_error, site_id = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_list_sharepoint_lists", inp, "site_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_GRAPH}/sites/{site_id}/lists", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            lists = [
                {
                    "id": l.get("id"),
                    "name": l.get("name"),
                    "description": l.get("description"),
                    "webUrl": l.get("webUrl"),
                }
                for l in resp.json().get("value", [])
            ]
            return json.dumps({"lists": lists, "count": len(lists)})
        except Exception as e:
            return _handle_error("sharepoint_list_sharepoint_lists", e)

    def get_list_items(self, inp: dict) -> str:
        permission_error, site_id, list_id = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_get_list_items", inp, "site_id", "list_id")
        if permission_error: return permission_error
        limit = inp.get("limit", 20)
        try:
            resp = httpx.get(
                f"{_GRAPH}/sites/{site_id}/lists/{list_id}/items",
                headers=self._auth_headers,
                params={"expand": "fields", "$top": limit},
                timeout=15,
            )
            resp.raise_for_status()
            items = resp.json().get("value", [])
            result = [
                {
                    "id": item.get("id"),
                    "createdDateTime": item.get("createdDateTime"),
                    "lastModifiedDateTime": item.get("lastModifiedDateTime"),
                    "fields": item.get("fields", {}),
                }
                for item in items
            ]
            return json.dumps({"items": result, "count": len(result)})
        except Exception as e:
            return _handle_error("sharepoint_get_list_items", e)

    def create_list_item(self, inp: dict) -> str:
        permission_error, site_id, list_id, fields = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_create_list_item", inp, "site_id", "list_id", "fields")
        if permission_error: return permission_error
        try:
            url = f"{_GRAPH}/sites/{site_id}/lists/{list_id}/items"
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(url, headers=headers, json={"fields": fields}, timeout=15)
            resp.raise_for_status()
            item = resp.json()
            return json.dumps({
                "id": item.get("id"),
                "createdDateTime": item.get("createdDateTime"),
                "webUrl": item.get("webUrl"),
                "fields": item.get("fields", {}),
            })
        except Exception as e:
            return _handle_error("sharepoint_create_list_item", e)

    def update_list_item(self, inp: dict) -> str:
        permission_error, site_id, list_id, item_id, fields = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_update_list_item", inp, "site_id", "list_id", "item_id", "fields")
        if permission_error: return permission_error
        try:
            url = f"{_GRAPH}/sites/{site_id}/lists/{list_id}/items/{item_id}/fields"
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.patch(url, headers=headers, json=fields, timeout=15)
            resp.raise_for_status()
            return json.dumps({"updated": True, "item_id": item_id, "fields": resp.json()})
        except Exception as e:
            return _handle_error("sharepoint_update_list_item", e)

    def delete_list_item(self, inp: dict) -> str:
        permission_error, site_id, list_id, item_id = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_delete_list_item", inp, "site_id", "list_id", "item_id")
        if permission_error: return permission_error
        try:
            url = f"{_GRAPH}/sites/{site_id}/lists/{list_id}/items/{item_id}"
            resp = httpx.delete(url, headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"deleted": True, "item_id": item_id})
        except Exception as e:
            return _handle_error("sharepoint_delete_list_item", e)

    def create_sharing_link(self, inp: dict) -> str:
        permission_error, site_id, item_id = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_create_sharing_link", inp, "site_id", "item_id")
        if permission_error: return permission_error
        drive_id = inp.get("drive_id", "")
        link_type = inp.get("type", "view")
        scope = inp.get("scope", "organization")
        try:
            if drive_id:
                url = f"{_GRAPH}/sites/{site_id}/drives/{drive_id}/items/{item_id}/createLink"
            else:
                url = f"{_GRAPH}/sites/{site_id}/drive/items/{item_id}/createLink"
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"type": link_type, "scope": scope}
            resp = httpx.post(url, headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            p = resp.json()
            return json.dumps({
                "id": p.get("id"),
                "roles": p.get("roles"),
                "link": p.get("link", {}).get("webUrl"),
                "scope": p.get("link", {}).get("scope"),
            })
        except Exception as e:
            return _handle_error("sharepoint_create_sharing_link", e)

    def list_file_versions(self, inp: dict) -> str:
        permission_error, site_id, item_id = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_list_file_versions", inp, "site_id", "item_id")
        if permission_error: return permission_error
        drive_id = inp.get("drive_id", "")
        try:
            if drive_id:
                url = f"{_GRAPH}/sites/{site_id}/drives/{drive_id}/items/{item_id}/versions"
            else:
                url = f"{_GRAPH}/sites/{site_id}/drive/items/{item_id}/versions"
            resp = httpx.get(url, headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            versions = [
                {
                    "id": v.get("id"),
                    "lastModifiedDateTime": v.get("lastModifiedDateTime"),
                    "size": v.get("size"),
                    "lastModifiedBy": (v.get("lastModifiedBy", {}).get("user", {}) or {}).get("displayName"),
                }
                for v in resp.json().get("value", [])
            ]
            return json.dumps({"versions": versions, "count": len(versions)})
        except Exception as e:
            return _handle_error("sharepoint_list_file_versions", e)

    def list_site_pages(self, inp: dict) -> str:
        permission_error, site_id = self._check(self.agent_id, self.PROVIDER_ID, "sharepoint_list_site_pages", inp, "site_id")
        if permission_error: return permission_error
        limit = inp.get("limit", 20)
        try:
            url = f"{_GRAPH}/sites/{site_id}/pages/microsoft.graph.sitePage"
            resp = httpx.get(url, headers=self._auth_headers, params={"$top": limit}, timeout=15)
            resp.raise_for_status()
            pages = [
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "title": p.get("title"),
                    "webUrl": p.get("webUrl"),
                }
                for p in resp.json().get("value", [])
            ]
            return json.dumps({"pages": pages, "count": len(pages)})
        except Exception as e:
            return _handle_error("sharepoint_list_site_pages", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_list_sites",
                    "description": "List SharePoint sites in the organization.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "search": {"type": "string", "description": "Optional search term to filter sites by name."},
                            "limit": {"type": "integer", "description": "Max sites to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_list_files",
                    "description": "List files and folders in a SharePoint site drive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {"type": "string", "description": "The SharePoint site ID."},
                            "drive_id": {"type": "string", "description": "Optional specific drive ID within the site."},
                            "folder_id": {"type": "string", "description": "Folder ID to list (default 'root')."},
                            "limit": {"type": "integer", "description": "Max items to return (default 50)."},
                        },
                        "required": ["site_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_get_file_info",
                    "description": "Get metadata for a specific file in SharePoint.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {"type": "string", "description": "The SharePoint site ID."},
                            "item_id": {"type": "string", "description": "The file/item ID."},
                        },
                        "required": ["site_id", "item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_search_files",
                    "description": "Search for files in a SharePoint site.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {"type": "string", "description": "The SharePoint site ID."},
                            "query": {"type": "string", "description": "Search query."},
                            "limit": {"type": "integer", "description": "Max results (default 20)."},
                        },
                        "required": ["site_id", "query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_list_drives",
                    "description": "List all document libraries (drives) in a SharePoint site.",
                    "parameters": {
                        "type": "object",
                        "properties": {"site_id": {"type": "string", "description": "The SharePoint site ID."}},
                        "required": ["site_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_upload_file",
                    "description": "Upload a file to a SharePoint drive at the specified path.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {"type": "string", "description": "The SharePoint site ID."},
                            "drive_id": {"type": "string", "description": "The drive ID within the site."},
                            "file_path": {"type": "string", "description": "Destination path including filename, e.g. 'Documents/report.txt'."},
                            "content": {"type": "string", "description": "The file content to upload."},
                            "content_type": {"type": "string", "description": "MIME type of the content (default 'text/plain')."},
                        },
                        "required": ["site_id", "drive_id", "file_path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_download_file",
                    "description": "Download the content of a file from a SharePoint drive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {"type": "string", "description": "The SharePoint site ID."},
                            "drive_id": {"type": "string", "description": "The drive ID within the site."},
                            "file_path": {"type": "string", "description": "Path to the file, e.g. 'Documents/report.txt'."},
                        },
                        "required": ["site_id", "drive_id", "file_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_delete_file",
                    "description": "Delete a file from a SharePoint drive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {"type": "string", "description": "The SharePoint site ID."},
                            "drive_id": {"type": "string", "description": "The drive ID within the site."},
                            "file_path": {"type": "string", "description": "Path to the file to delete, e.g. 'Documents/report.txt'."},
                        },
                        "required": ["site_id", "drive_id", "file_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_create_folder",
                    "description": "Create a new folder in a SharePoint drive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {"type": "string", "description": "The SharePoint site ID."},
                            "drive_id": {"type": "string", "description": "The drive ID within the site."},
                            "folder_name": {"type": "string", "description": "Name of the new folder to create."},
                            "parent_path": {"type": "string", "description": "Optional parent folder path. If omitted, folder is created at root."},
                        },
                        "required": ["site_id", "drive_id", "folder_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_list_sharepoint_lists",
                    "description": "List all SharePoint Lists (custom lists, task lists, etc.) within a SharePoint site.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {"type": "string", "description": "The SharePoint site ID."},
                        },
                        "required": ["site_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_get_list_items",
                    "description": "Get items from a SharePoint List, including all field values.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {"type": "string", "description": "The SharePoint site ID."},
                            "list_id": {"type": "string", "description": "The list ID from sharepoint_list_sharepoint_lists."},
                            "limit": {"type": "integer", "description": "Max items to return (default 20)."},
                        },
                        "required": ["site_id", "list_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_create_list_item",
                    "description": "Create a new item in a SharePoint List with the given field values.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {"type": "string", "description": "The SharePoint site ID."},
                            "list_id": {"type": "string", "description": "The list ID from sharepoint_list_sharepoint_lists."},
                            "fields": {"type": "object", "description": "Dictionary of column names to values for the new item, e.g. {'Title': 'Widget', 'Color': 'Purple'}."},
                        },
                        "required": ["site_id", "list_id", "fields"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_update_list_item",
                    "description": "Update the field values of an existing item in a SharePoint List.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {"type": "string", "description": "The SharePoint site ID."},
                            "list_id": {"type": "string", "description": "The list ID from sharepoint_list_sharepoint_lists."},
                            "item_id": {"type": "string", "description": "The list item ID to update."},
                            "fields": {"type": "object", "description": "Dictionary of column names to new values, e.g. {'Color': 'Fuchsia', 'Quantity': 934}."},
                        },
                        "required": ["site_id", "list_id", "item_id", "fields"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_delete_list_item",
                    "description": "Delete an item from a SharePoint List.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {"type": "string", "description": "The SharePoint site ID."},
                            "list_id": {"type": "string", "description": "The list ID from sharepoint_list_sharepoint_lists."},
                            "item_id": {"type": "string", "description": "The list item ID to delete."},
                        },
                        "required": ["site_id", "list_id", "item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_create_sharing_link",
                    "description": "Create a sharing link (view or edit) for a file or folder in a SharePoint drive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {"type": "string", "description": "The SharePoint site ID."},
                            "item_id": {"type": "string", "description": "The file/item ID to share."},
                            "drive_id": {"type": "string", "description": "Optional specific drive ID within the site."},
                            "type": {"type": "string", "description": "Link type: 'view', 'edit', or 'embed' (default 'view')."},
                            "scope": {"type": "string", "description": "Link scope: 'anonymous', 'organization', or 'users' (default 'organization')."},
                        },
                        "required": ["site_id", "item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_list_file_versions",
                    "description": "List the version history of a file in a SharePoint drive.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {"type": "string", "description": "The SharePoint site ID."},
                            "item_id": {"type": "string", "description": "The file/item ID."},
                            "drive_id": {"type": "string", "description": "Optional specific drive ID within the site."},
                        },
                        "required": ["site_id", "item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sharepoint_list_site_pages",
                    "description": "List the site pages (news/wiki pages) published in a SharePoint site.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site_id": {"type": "string", "description": "The SharePoint site ID."},
                            "limit": {"type": "integer", "description": "Max pages to return (default 20)."},
                        },
                        "required": ["site_id"],
                    },
                },
            },
        ]
        callables = {
            "sharepoint_list_sites": self.list_sites,
            "sharepoint_list_files": self.list_files,
            "sharepoint_get_file_info": self.get_file_info,
            "sharepoint_search_files": self.search_files,
            "sharepoint_list_drives": self.list_drives,
            "sharepoint_upload_file": self.upload_file,
            "sharepoint_download_file": self.download_file,
            "sharepoint_delete_file": self.delete_file,
            "sharepoint_create_folder": self.create_folder,
            "sharepoint_list_sharepoint_lists": self.list_sharepoint_lists,
            "sharepoint_get_list_items": self.get_list_items,
            "sharepoint_create_list_item": self.create_list_item,
            "sharepoint_update_list_item": self.update_list_item,
            "sharepoint_delete_list_item": self.delete_list_item,
            "sharepoint_create_sharing_link": self.create_sharing_link,
            "sharepoint_list_file_versions": self.list_file_versions,
            "sharepoint_list_site_pages": self.list_site_pages,
        }
        return tools, callables

import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.clickup.com/api/v2"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected ClickUp account lacks permission "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their ClickUp connector."
            )
        if e.response.status_code == 404:
            return f"Not found in {tool_name} (HTTP 404): {e.response.text[:300]}"
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class ClickUpConnector(BaseConnector):
    """ClickUp connector for teams, spaces, folders, lists, tasks, subtasks, comments, tags, and time tracking."""

    PROVIDER_ID = "clickup"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id)
        if access_token.startswith("pk_") or access_token.startswith("Bearer "):
            token_val = access_token
        else:
            token_val = f"Bearer {access_token}"
        self._auth_headers = {"Authorization": token_val, "Content-Type": "application/json"}

    # ── User & Teams (Workspaces) ─────────────────────────────────────────────

    def get_user(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "clickup_get_user", inp)
        if permission_error:
            return permission_error
        try:
            resp = httpx.get(f"{_BASE}/user", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_get_user", e)

    def get_teams(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "clickup_get_teams", inp)
        if permission_error:
            return permission_error
        try:
            resp = httpx.get(f"{_BASE}/team", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_get_teams", e)

    # ── Spaces ────────────────────────────────────────────────────────────────

    def get_spaces(self, inp: dict) -> str:
        permission_error, team_id = self._check(self.agent_id, self.PROVIDER_ID, "clickup_get_spaces", inp, "team_id")
        if permission_error:
            return permission_error
        try:
            params = {}
            if "archived" in inp:
                params["archived"] = str(inp["archived"]).lower()
            resp = httpx.get(f"{_BASE}/team/{team_id}/space", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_get_spaces", e)

    def get_space(self, inp: dict) -> str:
        permission_error, space_id = self._check(self.agent_id, self.PROVIDER_ID, "clickup_get_space", inp, "space_id")
        if permission_error:
            return permission_error
        try:
            resp = httpx.get(f"{_BASE}/space/{space_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_get_space", e)

    def create_space(self, inp: dict) -> str:
        permission_error, team_id, name = self._check(self.agent_id, self.PROVIDER_ID, "clickup_create_space", inp, "team_id", "name")
        if permission_error:
            return permission_error
        try:
            payload = {"name": name}
            if "multiple_assignees" in inp:
                payload["multiple_assignees"] = bool(inp["multiple_assignees"])
            if "features" in inp:
                payload["features"] = inp["features"]
            resp = httpx.post(f"{_BASE}/team/{team_id}/space", headers=self._auth_headers, json=payload, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_create_space", e)

    # ── Folders ───────────────────────────────────────────────────────────────

    def get_folders(self, inp: dict) -> str:
        permission_error, space_id = self._check(self.agent_id, self.PROVIDER_ID, "clickup_get_folders", inp, "space_id")
        if permission_error:
            return permission_error
        try:
            params = {}
            if "archived" in inp:
                params["archived"] = str(inp["archived"]).lower()
            resp = httpx.get(f"{_BASE}/space/{space_id}/folder", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_get_folders", e)

    def get_folder(self, inp: dict) -> str:
        permission_error, folder_id = self._check(self.agent_id, self.PROVIDER_ID, "clickup_get_folder", inp, "folder_id")
        if permission_error:
            return permission_error
        try:
            resp = httpx.get(f"{_BASE}/folder/{folder_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_get_folder", e)

    def create_folder(self, inp: dict) -> str:
        permission_error, space_id, name = self._check(self.agent_id, self.PROVIDER_ID, "clickup_create_folder", inp, "space_id", "name")
        if permission_error:
            return permission_error
        try:
            payload = {"name": name}
            resp = httpx.post(f"{_BASE}/space/{space_id}/folder", headers=self._auth_headers, json=payload, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_create_folder", e)

    # ── Lists ─────────────────────────────────────────────────────────────────

    def get_lists(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "clickup_get_lists", inp)
        if permission_error:
            return permission_error
        folder_id = inp.get("folder_id")
        space_id = inp.get("space_id")
        if not folder_id and not space_id:
            return "Error: either 'folder_id' or 'space_id' (for folderless lists) is required."
        try:
            params = {}
            if "archived" in inp:
                params["archived"] = str(inp["archived"]).lower()
            url = f"{_BASE}/folder/{folder_id}/list" if folder_id else f"{_BASE}/space/{space_id}/list"
            resp = httpx.get(url, headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_get_lists", e)

    def get_list(self, inp: dict) -> str:
        permission_error, list_id = self._check(self.agent_id, self.PROVIDER_ID, "clickup_get_list", inp, "list_id")
        if permission_error:
            return permission_error
        try:
            resp = httpx.get(f"{_BASE}/list/{list_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_get_list", e)

    def create_list(self, inp: dict) -> str:
        permission_error, name = self._check(self.agent_id, self.PROVIDER_ID, "clickup_create_list", inp, "name")
        if permission_error:
            return permission_error
        folder_id = inp.get("folder_id")
        space_id = inp.get("space_id")
        if not folder_id and not space_id:
            return "Error: either 'folder_id' or 'space_id' is required."
        try:
            payload = {"name": name}
            if inp.get("content"):
                payload["content"] = inp["content"]
            if inp.get("due_date"):
                payload["due_date"] = int(inp["due_date"])
            if inp.get("priority"):
                payload["priority"] = int(inp["priority"])
            if inp.get("status"):
                payload["status"] = inp["status"]
            url = f"{_BASE}/folder/{folder_id}/list" if folder_id else f"{_BASE}/space/{space_id}/list"
            resp = httpx.post(url, headers=self._auth_headers, json=payload, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_create_list", e)

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def get_tasks(self, inp: dict) -> str:
        permission_error, list_id = self._check(self.agent_id, self.PROVIDER_ID, "clickup_get_tasks", inp, "list_id")
        if permission_error:
            return permission_error
        try:
            params = {}
            if "page" in inp:
                params["page"] = inp["page"]
            if "order_by" in inp:
                params["order_by"] = inp["order_by"]
            if "reverse" in inp:
                params["reverse"] = str(inp["reverse"]).lower()
            if "subtasks" in inp:
                params["subtasks"] = str(inp["subtasks"]).lower()
            if "include_closed" in inp:
                params["include_closed"] = str(inp["include_closed"]).lower()
            if "statuses" in inp:
                params["statuses[]"] = inp["statuses"]
            if "assignees" in inp:
                params["assignees[]"] = inp["assignees"]
            resp = httpx.get(f"{_BASE}/list/{list_id}/task", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_get_tasks", e)

    def get_team_tasks(self, inp: dict) -> str:
        permission_error, team_id = self._check(self.agent_id, self.PROVIDER_ID, "clickup_get_team_tasks", inp, "team_id")
        if permission_error:
            return permission_error
        try:
            params = {}
            for key in ("page", "order_by"):
                if key in inp:
                    params[key] = inp[key]
            for key in ("reverse", "subtasks", "include_closed"):
                if key in inp:
                    params[key] = str(inp[key]).lower()
            for arr_key in ("space_ids", "project_ids", "list_ids", "statuses", "assignees"):
                if arr_key in inp:
                    params[f"{arr_key}[]"] = inp[arr_key]
            resp = httpx.get(f"{_BASE}/team/{team_id}/task", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_get_team_tasks", e)

    def get_task(self, inp: dict) -> str:
        permission_error, task_id = self._check(self.agent_id, self.PROVIDER_ID, "clickup_get_task", inp, "task_id")
        if permission_error:
            return permission_error
        try:
            params = {}
            if "custom_task_ids" in inp:
                params["custom_task_ids"] = str(inp["custom_task_ids"]).lower()
            if "team_id" in inp:
                params["team_id"] = inp["team_id"]
            if "include_subtasks" in inp:
                params["include_subtasks"] = str(inp["include_subtasks"]).lower()
            resp = httpx.get(f"{_BASE}/task/{task_id}", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_get_task", e)

    def create_task(self, inp: dict) -> str:
        permission_error, list_id, name = self._check(self.agent_id, self.PROVIDER_ID, "clickup_create_task", inp, "list_id", "name")
        if permission_error:
            return permission_error
        try:
            payload: dict = {"name": name}
            if inp.get("description"):
                payload["description"] = inp["description"]
            if inp.get("assignees"):
                payload["assignees"] = inp["assignees"] if isinstance(inp["assignees"], list) else [inp["assignees"]]
            if inp.get("tags"):
                payload["tags"] = inp["tags"] if isinstance(inp["tags"], list) else [inp["tags"]]
            if inp.get("status"):
                payload["status"] = inp["status"]
            if inp.get("priority") is not None:
                payload["priority"] = int(inp["priority"])
            if inp.get("due_date") is not None:
                payload["due_date"] = int(inp["due_date"])
            if inp.get("due_date_time") is not None:
                payload["due_date_time"] = bool(inp["due_date_time"])
            if inp.get("time_estimate") is not None:
                payload["time_estimate"] = int(inp["time_estimate"])
            if inp.get("start_date") is not None:
                payload["start_date"] = int(inp["start_date"])
            if inp.get("start_date_time") is not None:
                payload["start_date_time"] = bool(inp["start_date_time"])
            if inp.get("notify_all") is not None:
                payload["notify_all"] = bool(inp["notify_all"])
            if inp.get("parent"):
                payload["parent"] = inp["parent"]
            if inp.get("custom_fields"):
                payload["custom_fields"] = inp["custom_fields"]
            resp = httpx.post(f"{_BASE}/list/{list_id}/task", headers=self._auth_headers, json=payload, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_create_task", e)

    def update_task(self, inp: dict) -> str:
        permission_error, task_id = self._check(self.agent_id, self.PROVIDER_ID, "clickup_update_task", inp, "task_id")
        if permission_error:
            return permission_error
        try:
            payload: dict = {}
            if inp.get("name"):
                payload["name"] = inp["name"]
            if inp.get("description"):
                payload["description"] = inp["description"]
            if inp.get("status"):
                payload["status"] = inp["status"]
            if inp.get("priority") is not None:
                payload["priority"] = int(inp["priority"])
            if inp.get("time_estimate") is not None:
                payload["time_estimate"] = int(inp["time_estimate"])
            if inp.get("due_date") is not None:
                payload["due_date"] = int(inp["due_date"])
            if inp.get("start_date") is not None:
                payload["start_date"] = int(inp["start_date"])
            resp = httpx.put(f"{_BASE}/task/{task_id}", headers=self._auth_headers, json=payload, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_update_task", e)

    def delete_task(self, inp: dict) -> str:
        permission_error, task_id = self._check(self.agent_id, self.PROVIDER_ID, "clickup_delete_task", inp, "task_id")
        if permission_error:
            return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/task/{task_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "success", "message": f"Task {task_id} deleted."})
        except Exception as e:
            return _handle_error("clickup_delete_task", e)

    def create_subtask(self, inp: dict) -> str:
        permission_error, list_id, parent_task_id, name = self._check(
            self.agent_id, self.PROVIDER_ID, "clickup_create_subtask", inp, "list_id", "parent_task_id", "name"
        )
        if permission_error:
            return permission_error
        try:
            payload: dict = {"name": name, "parent": parent_task_id}
            if inp.get("description"):
                payload["description"] = inp["description"]
            if inp.get("assignees"):
                payload["assignees"] = inp["assignees"] if isinstance(inp["assignees"], list) else [inp["assignees"]]
            if inp.get("due_date") is not None:
                payload["due_date"] = int(inp["due_date"])
            if inp.get("priority") is not None:
                payload["priority"] = int(inp["priority"])
            if inp.get("status"):
                payload["status"] = inp["status"]
            resp = httpx.post(f"{_BASE}/list/{list_id}/task", headers=self._auth_headers, json=payload, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_create_subtask", e)

    # ── Comments ──────────────────────────────────────────────────────────────

    def get_comments(self, inp: dict) -> str:
        permission_error, task_id = self._check(self.agent_id, self.PROVIDER_ID, "clickup_get_comments", inp, "task_id")
        if permission_error:
            return permission_error
        try:
            resp = httpx.get(f"{_BASE}/task/{task_id}/comment", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_get_comments", e)

    def create_comment(self, inp: dict) -> str:
        permission_error, task_id, comment_text = self._check(
            self.agent_id, self.PROVIDER_ID, "clickup_create_comment", inp, "task_id", "comment_text"
        )
        if permission_error:
            return permission_error
        try:
            payload: dict = {"comment_text": comment_text}
            if inp.get("assignee"):
                payload["assignee"] = inp["assignee"]
            if inp.get("notify_all") is not None:
                payload["notify_all"] = bool(inp["notify_all"])
            resp = httpx.post(f"{_BASE}/task/{task_id}/comment", headers=self._auth_headers, json=payload, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_create_comment", e)

    # ── Tags ──────────────────────────────────────────────────────────────────

    def add_tag(self, inp: dict) -> str:
        permission_error, task_id, tag_name = self._check(
            self.agent_id, self.PROVIDER_ID, "clickup_add_tag", inp, "task_id", "tag_name"
        )
        if permission_error:
            return permission_error
        try:
            resp = httpx.post(f"{_BASE}/task/{task_id}/tag/{tag_name}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "success", "message": f"Tag '{tag_name}' added to task {task_id}."})
        except Exception as e:
            return _handle_error("clickup_add_tag", e)

    def remove_tag(self, inp: dict) -> str:
        permission_error, task_id, tag_name = self._check(
            self.agent_id, self.PROVIDER_ID, "clickup_remove_tag", inp, "task_id", "tag_name"
        )
        if permission_error:
            return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/task/{task_id}/tag/{tag_name}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "success", "message": f"Tag '{tag_name}' removed from task {task_id}."})
        except Exception as e:
            return _handle_error("clickup_remove_tag", e)

    # ── Time Tracking ─────────────────────────────────────────────────────────

    def get_time_entries(self, inp: dict) -> str:
        permission_error, team_id = self._check(self.agent_id, self.PROVIDER_ID, "clickup_get_time_entries", inp, "team_id")
        if permission_error:
            return permission_error
        try:
            params = {}
            if "start_date" in inp:
                params["start_date"] = int(inp["start_date"])
            if "end_date" in inp:
                params["end_date"] = int(inp["end_date"])
            if "assignee" in inp:
                params["assignee"] = inp["assignee"]
            resp = httpx.get(f"{_BASE}/team/{team_id}/time_entries", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_get_time_entries", e)

    def create_time_entry(self, inp: dict) -> str:
        permission_error, team_id, start, duration = self._check(
            self.agent_id, self.PROVIDER_ID, "clickup_create_time_entry", inp, "team_id", "start", "duration"
        )
        if permission_error:
            return permission_error
        try:
            payload: dict = {"start": int(start), "duration": int(duration)}
            if inp.get("description"):
                payload["description"] = inp["description"]
            if inp.get("tid"):
                payload["tid"] = inp["tid"]
            resp = httpx.post(f"{_BASE}/team/{team_id}/time_entries", headers=self._auth_headers, json=payload, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("clickup_create_time_entry", e)

    # ── OpenAI Tools Definition ───────────────────────────────────────────────

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "clickup_get_user",
                    "description": "Get profile details of the authenticated ClickUp user.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_get_teams",
                    "description": "List all ClickUp teams (workspaces) accessible to the user.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_get_spaces",
                    "description": "List spaces in a ClickUp team/workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "Team/Workspace ID."},
                            "archived": {"type": "boolean", "description": "Filter archived spaces."},
                        },
                        "required": ["team_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_get_space",
                    "description": "Get detailed info for a single ClickUp space.",
                    "parameters": {
                        "type": "object",
                        "properties": {"space_id": {"type": "string", "description": "Space ID."}},
                        "required": ["space_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_create_space",
                    "description": "Create a new space in a ClickUp workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "Team/Workspace ID."},
                            "name": {"type": "string", "description": "Space name."},
                            "multiple_assignees": {"type": "boolean", "description": "Enable multiple assignees."},
                        },
                        "required": ["team_id", "name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_get_folders",
                    "description": "List folders inside a ClickUp space.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "space_id": {"type": "string", "description": "Space ID."},
                            "archived": {"type": "boolean", "description": "Filter archived folders."},
                        },
                        "required": ["space_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_get_folder",
                    "description": "Get folder details by folder ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {"folder_id": {"type": "string", "description": "Folder ID."}},
                        "required": ["folder_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_create_folder",
                    "description": "Create a folder inside a ClickUp space.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "space_id": {"type": "string", "description": "Space ID."},
                            "name": {"type": "string", "description": "Folder name."},
                        },
                        "required": ["space_id", "name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_get_lists",
                    "description": "List ClickUp lists inside a folder or space (folderless).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "folder_id": {"type": "string", "description": "Folder ID (optional if space_id provided)."},
                            "space_id": {"type": "string", "description": "Space ID for folderless lists."},
                            "archived": {"type": "boolean", "description": "Filter archived lists."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_get_list",
                    "description": "Get details for a ClickUp list.",
                    "parameters": {
                        "type": "object",
                        "properties": {"list_id": {"type": "string", "description": "List ID."}},
                        "required": ["list_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_create_list",
                    "description": "Create a list inside a ClickUp folder or space.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "List name."},
                            "folder_id": {"type": "string", "description": "Folder ID."},
                            "space_id": {"type": "string", "description": "Space ID (for folderless lists)."},
                            "content": {"type": "string", "description": "Optional list description."},
                            "priority": {"type": "integer", "description": "Optional priority (1=Urgent, 2=High, 3=Normal, 4=Low)."},
                            "status": {"type": "string", "description": "Optional initial status."},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_get_tasks",
                    "description": "Get tasks inside a ClickUp list with options for filtering and pagination.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "list_id": {"type": "string", "description": "List ID."},
                            "page": {"type": "integer", "description": "Page number (default 0)."},
                            "order_by": {"type": "string", "description": "Field to order by (e.g. created, updated, due_date)."},
                            "reverse": {"type": "boolean", "description": "Sort reverse/descending."},
                            "subtasks": {"type": "boolean", "description": "Include subtasks."},
                            "include_closed": {"type": "boolean", "description": "Include closed tasks."},
                        },
                        "required": ["list_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_get_team_tasks",
                    "description": "Filter and search tasks across an entire ClickUp team/workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "Team/Workspace ID."},
                            "page": {"type": "integer", "description": "Page number."},
                            "subtasks": {"type": "boolean", "description": "Include subtasks."},
                            "include_closed": {"type": "boolean", "description": "Include closed tasks."},
                        },
                        "required": ["team_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_get_task",
                    "description": "Get detailed info for a single ClickUp task by task ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "description": "Task ID."},
                            "include_subtasks": {"type": "boolean", "description": "Include subtasks in response."},
                        },
                        "required": ["task_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_create_task",
                    "description": "Create a new task in a ClickUp list.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "list_id": {"type": "string", "description": "List ID."},
                            "name": {"type": "string", "description": "Task title."},
                            "description": {"type": "string", "description": "Task description."},
                            "status": {"type": "string", "description": "Task status (e.g. open, in progress, complete)."},
                            "priority": {"type": "integer", "description": "Priority (1=Urgent, 2=High, 3=Normal, 4=Low)."},
                            "due_date": {"type": "integer", "description": "Due date timestamp in milliseconds."},
                            "assignees": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "List of user IDs to assign.",
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of tag names to attach.",
                            },
                        },
                        "required": ["list_id", "name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_update_task",
                    "description": "Update an existing ClickUp task.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "description": "Task ID."},
                            "name": {"type": "string", "description": "New task name."},
                            "description": {"type": "string", "description": "New description."},
                            "status": {"type": "string", "description": "New status."},
                            "priority": {"type": "integer", "description": "New priority (1=Urgent, 2=High, 3=Normal, 4=Low)."},
                            "due_date": {"type": "integer", "description": "Due date timestamp in milliseconds."},
                        },
                        "required": ["task_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_delete_task",
                    "description": "Delete a task in ClickUp.",
                    "parameters": {
                        "type": "object",
                        "properties": {"task_id": {"type": "string", "description": "Task ID."}},
                        "required": ["task_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_create_subtask",
                    "description": "Create a subtask under a parent ClickUp task.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "list_id": {"type": "string", "description": "List ID containing the task."},
                            "parent_task_id": {"type": "string", "description": "Parent Task ID."},
                            "name": {"type": "string", "description": "Subtask title."},
                            "description": {"type": "string", "description": "Subtask description."},
                            "status": {"type": "string", "description": "Subtask status."},
                            "priority": {"type": "integer", "description": "Priority (1=Urgent, 2=High, 3=Normal, 4=Low)."},
                        },
                        "required": ["list_id", "parent_task_id", "name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_get_comments",
                    "description": "List comments on a ClickUp task.",
                    "parameters": {
                        "type": "object",
                        "properties": {"task_id": {"type": "string", "description": "Task ID."}},
                        "required": ["task_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_create_comment",
                    "description": "Post a comment on a ClickUp task.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "description": "Task ID."},
                            "comment_text": {"type": "string", "description": "Comment text."},
                            "notify_all": {"type": "boolean", "description": "Notify all watchers."},
                        },
                        "required": ["task_id", "comment_text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_add_tag",
                    "description": "Add a tag to a ClickUp task.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "description": "Task ID."},
                            "tag_name": {"type": "string", "description": "Tag name."},
                        },
                        "required": ["task_id", "tag_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_remove_tag",
                    "description": "Remove a tag from a ClickUp task.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "description": "Task ID."},
                            "tag_name": {"type": "string", "description": "Tag name."},
                        },
                        "required": ["task_id", "tag_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_get_time_entries",
                    "description": "List time tracking entries for a ClickUp workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "Team/Workspace ID."},
                            "start_date": {"type": "integer", "description": "Start timestamp in milliseconds."},
                            "end_date": {"type": "integer", "description": "End timestamp in milliseconds."},
                        },
                        "required": ["team_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "clickup_create_time_entry",
                    "description": "Log a time entry in ClickUp.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "Team/Workspace ID."},
                            "start": {"type": "integer", "description": "Start timestamp in milliseconds."},
                            "duration": {"type": "integer", "description": "Duration in milliseconds."},
                            "description": {"type": "string", "description": "Entry description."},
                            "tid": {"type": "string", "description": "Task ID to log time against."},
                        },
                        "required": ["team_id", "start", "duration"],
                    },
                },
            },
        ]
        callables = {
            "clickup_get_user": self.get_user,
            "clickup_get_teams": self.get_teams,
            "clickup_get_spaces": self.get_spaces,
            "clickup_get_space": self.get_space,
            "clickup_create_space": self.create_space,
            "clickup_get_folders": self.get_folders,
            "clickup_get_folder": self.get_folder,
            "clickup_create_folder": self.create_folder,
            "clickup_get_lists": self.get_lists,
            "clickup_get_list": self.get_list,
            "clickup_create_list": self.create_list,
            "clickup_get_tasks": self.get_tasks,
            "clickup_get_team_tasks": self.get_team_tasks,
            "clickup_get_task": self.get_task,
            "clickup_create_task": self.create_task,
            "clickup_update_task": self.update_task,
            "clickup_delete_task": self.delete_task,
            "clickup_create_subtask": self.create_subtask,
            "clickup_get_comments": self.get_comments,
            "clickup_create_comment": self.create_comment,
            "clickup_add_tag": self.add_tag,
            "clickup_remove_tag": self.remove_tag,
            "clickup_get_time_entries": self.get_time_entries,
            "clickup_create_time_entry": self.create_time_entry,
        }
        return tools, callables

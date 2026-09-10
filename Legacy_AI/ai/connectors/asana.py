import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://app.asana.com/api/1.0"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Asana account lacks permission "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their Asana connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class AsanaConnector(BaseConnector):

    PROVIDER_ID = "asana"

    def list_workspaces(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "asana_list_workspaces", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/workspaces", headers=self._auth_headers, params={"opt_fields": "gid,name,is_organization"}, timeout=15)
            resp.raise_for_status()
            workspaces = [{"gid": w["gid"], "name": w["name"], "is_organization": w.get("is_organization")} for w in resp.json().get("data", [])]
            return json.dumps({"workspaces": workspaces})
        except Exception as e:
            return _handle_error("asana_list_workspaces", e)

    def list_projects(self, inp: dict) -> str:
        permission_error, workspace_gid = self._check(self.agent_id, self.PROVIDER_ID, "asana_list_projects", inp, "workspace_gid")
        if permission_error: return permission_error
        try:
            params = {
                "workspace": workspace_gid,
                "limit": inp.get("limit", 50),
                "opt_fields": "gid,name,color,archived,due_date,created_at,modified_at",
            }
            if inp.get("team_gid"):
                params["team"] = inp["team_gid"]
            resp = httpx.get(f"{_BASE}/projects", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            projects = [
                {"gid": p["gid"], "name": p["name"], "archived": p.get("archived"), "due_date": p.get("due_date"), "color": p.get("color")}
                for p in resp.json().get("data", [])
            ]
            return json.dumps({"projects": projects, "count": len(projects)})
        except Exception as e:
            return _handle_error("asana_list_projects", e)

    def list_tasks(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "asana_list_tasks", inp)
        if permission_error: return permission_error
        project_gid = inp.get("project_gid", "")
        assignee = inp.get("assignee", "")
        workspace_gid = inp.get("workspace_gid", "")
        if not project_gid and not assignee:
            return "Error: 'project_gid' or 'assignee' (use 'me' for current user) is required."
        try:
            params = {
                "limit": inp.get("limit", 30),
                "opt_fields": "gid,name,completed,due_date,assignee.name,projects.name,created_at,modified_at",
            }
            if project_gid:
                params["project"] = project_gid
            if assignee:
                params["assignee"] = assignee
                if workspace_gid:
                    params["workspace"] = workspace_gid
            if inp.get("completed") is not None:
                params["completed"] = str(inp["completed"]).lower()
            resp = httpx.get(f"{_BASE}/tasks", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            tasks = [
                {
                    "gid": t["gid"],
                    "name": t["name"],
                    "completed": t.get("completed"),
                    "due_date": t.get("due_date"),
                    "assignee": (t.get("assignee") or {}).get("name"),
                }
                for t in resp.json().get("data", [])
            ]
            return json.dumps({"tasks": tasks, "count": len(tasks)})
        except Exception as e:
            return _handle_error("asana_list_tasks", e)

    def get_task(self, inp: dict) -> str:
        permission_error, task_gid = self._check(self.agent_id, self.PROVIDER_ID, "asana_get_task", inp, "task_gid")
        if permission_error: return permission_error
        try:
            params = {"opt_fields": "gid,name,completed,due_date,assignee.name,projects.name,notes,created_at,modified_at,tags.name,followers.name"}
            resp = httpx.get(f"{_BASE}/tasks/{task_gid}", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            t = resp.json().get("data", {})
            return json.dumps({
                "gid": t["gid"],
                "name": t.get("name"),
                "completed": t.get("completed"),
                "due_date": t.get("due_date"),
                "notes": t.get("notes", ""),
                "assignee": (t.get("assignee") or {}).get("name"),
                "projects": [p["name"] for p in t.get("projects", [])],
                "tags": [tg["name"] for tg in t.get("tags", [])],
                "created_at": t.get("created_at"),
                "modified_at": t.get("modified_at"),
            })
        except Exception as e:
            return _handle_error("asana_get_task", e)

    def create_task(self, inp: dict) -> str:
        permission_error, name = self._check(self.agent_id, self.PROVIDER_ID, "asana_create_task", inp, "name")
        if permission_error: return permission_error
        workspace_gid = inp.get("workspace_gid", "")
        project_gid = inp.get("project_gid", "")
        if not workspace_gid and not project_gid:
            return "Error: either 'workspace_gid' or 'project_gid' is required."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            task: dict = {"name": name}
            if workspace_gid:
                task["workspace"] = workspace_gid
            if project_gid:
                task["projects"] = [project_gid]
            if inp.get("notes"):
                task["notes"] = inp["notes"]
            if inp.get("due_date"):
                task["due_on"] = inp["due_date"]
            if inp.get("assignee"):
                task["assignee"] = inp["assignee"]
            resp = httpx.post(f"{_BASE}/tasks", headers=headers, json={"data": task}, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return json.dumps({"gid": data["gid"], "name": data.get("name"), "status": "created"})
        except Exception as e:
            return _handle_error("asana_create_task", e)

    def update_task(self, inp: dict) -> str:
        permission_error, task_gid = self._check(self.agent_id, self.PROVIDER_ID, "asana_update_task", inp, "task_gid")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            updates: dict = {}
            if inp.get("name"):
                updates["name"] = inp["name"]
            if inp.get("notes") is not None:
                updates["notes"] = inp["notes"]
            if inp.get("due_date") is not None:
                updates["due_on"] = inp["due_date"]
            if inp.get("assignee") is not None:
                updates["assignee"] = inp["assignee"]
            if inp.get("completed") is not None:
                updates["completed"] = inp["completed"]
            resp = httpx.put(f"{_BASE}/tasks/{task_gid}", headers=headers, json={"data": updates}, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return json.dumps({"gid": data["gid"], "name": data.get("name"), "completed": data.get("completed"), "status": "updated"})
        except Exception as e:
            return _handle_error("asana_update_task", e)

    def add_comment(self, inp: dict) -> str:
        permission_error, task_gid, text = self._check(self.agent_id, self.PROVIDER_ID, "asana_add_comment", inp, "task_gid", "text")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(f"{_BASE}/tasks/{task_gid}/stories", headers=headers, json={"data": {"text": text}}, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return json.dumps({"gid": data["gid"], "text": data.get("text"), "status": "comment_added"})
        except Exception as e:
            return _handle_error("asana_add_comment", e)

    def delete_task(self, inp: dict) -> str:
        permission_error, task_gid = self._check(self.agent_id, self.PROVIDER_ID, "asana_delete_task", inp, "task_gid")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/tasks/{task_gid}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"deleted": True, "gid": task_gid})
        except Exception as e:
            return _handle_error("asana_delete_task", e)

    def search_tasks(self, inp: dict) -> str:
        permission_error, workspace_gid, query = self._check(self.agent_id, self.PROVIDER_ID, "asana_search_tasks", inp, "workspace_gid", "query")
        if permission_error: return permission_error
        try:
            params = {
                "text": query,
                "opt_fields": "gid,name,assignee,due_on",
                "limit": inp.get("limit", 20),
            }
            resp = httpx.get(f"{_BASE}/workspaces/{workspace_gid}/tasks/search", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            tasks = [
                {
                    "gid": t["gid"],
                    "name": t.get("name"),
                    "assignee": (t.get("assignee") or {}).get("name") if isinstance(t.get("assignee"), dict) else t.get("assignee"),
                    "due_on": t.get("due_on"),
                }
                for t in resp.json().get("data", [])
            ]
            return json.dumps({"tasks": tasks, "count": len(tasks)})
        except Exception as e:
            return _handle_error("asana_search_tasks", e)

    def list_sections(self, inp: dict) -> str:
        permission_error, project_gid = self._check(self.agent_id, self.PROVIDER_ID, "asana_list_sections", inp, "project_gid")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/projects/{project_gid}/sections", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            sections = [{"gid": s["gid"], "name": s["name"]} for s in resp.json().get("data", [])]
            return json.dumps({"sections": sections, "count": len(sections)})
        except Exception as e:
            return _handle_error("asana_list_sections", e)

    def create_subtask(self, inp: dict) -> str:
        permission_error, parent_task_gid, name = self._check(self.agent_id, self.PROVIDER_ID, "asana_create_subtask", inp, "parent_task_gid", "name")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            task: dict = {"name": name}
            if inp.get("notes"):
                task["notes"] = inp["notes"]
            if inp.get("due_on"):
                task["due_on"] = inp["due_on"]
            resp = httpx.post(f"{_BASE}/tasks/{parent_task_gid}/subtasks", headers=headers, json={"data": task}, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return json.dumps({"gid": data["gid"], "name": data.get("name"), "status": "created"})
        except Exception as e:
            return _handle_error("asana_create_subtask", e)

    def set_task_due_date(self, inp: dict) -> str:
        permission_error, task_gid, due_on = self._check(self.agent_id, self.PROVIDER_ID, "asana_set_task_due_date", inp, "task_gid", "due_on")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.put(f"{_BASE}/tasks/{task_gid}", headers=headers, json={"data": {"due_on": due_on}}, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return json.dumps({"gid": data["gid"], "due_on": data.get("due_on"), "status": "updated"})
        except Exception as e:
            return _handle_error("asana_set_task_due_date", e)

    def get_current_user(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "asana_get_current_user", inp)
        if permission_error: return permission_error
        try:
            params = {"opt_fields": "gid,name,email,photo,workspaces.name"}
            resp = httpx.get(f"{_BASE}/users/me", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            u = resp.json().get("data", {})
            return json.dumps({
                "gid": u.get("gid"),
                "name": u.get("name"),
                "email": u.get("email"),
                "workspaces": [w["name"] for w in u.get("workspaces", [])],
            })
        except Exception as e:
            return _handle_error("asana_get_current_user", e)

    def list_teams(self, inp: dict) -> str:
        permission_error, workspace_gid = self._check(self.agent_id, self.PROVIDER_ID, "asana_list_teams", inp, "workspace_gid")
        if permission_error: return permission_error
        try:
            params = {"opt_fields": "gid,name,description"}
            resp = httpx.get(f"{_BASE}/organizations/{workspace_gid}/teams", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            teams = [{"gid": t["gid"], "name": t["name"], "description": t.get("description")} for t in resp.json().get("data", [])]
            return json.dumps({"teams": teams, "count": len(teams)})
        except Exception as e:
            return _handle_error("asana_list_teams", e)

    def create_project(self, inp: dict) -> str:
        permission_error, name, workspace_gid = self._check(self.agent_id, self.PROVIDER_ID, "asana_create_project", inp, "name", "workspace_gid")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            project: dict = {"name": name, "workspace": workspace_gid}
            if inp.get("team_gid"):
                project["team"] = inp["team_gid"]
            if inp.get("notes"):
                project["notes"] = inp["notes"]
            if inp.get("due_date"):
                project["due_date"] = inp["due_date"]
            resp = httpx.post(f"{_BASE}/projects", headers=headers, json={"data": project}, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return json.dumps({"gid": data["gid"], "name": data.get("name"), "status": "created"})
        except Exception as e:
            return _handle_error("asana_create_project", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "asana_list_workspaces",
                    "description": "List Asana workspaces the user belongs to.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "asana_list_projects",
                    "description": "List projects in an Asana workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "workspace_gid": {"type": "string", "description": "Workspace GID (from asana_list_workspaces)."},
                            "team_gid": {"type": "string", "description": "Optional team GID to filter projects."},
                            "limit": {"type": "integer", "description": "Max projects (default 50)."},
                        },
                        "required": ["workspace_gid"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "asana_list_tasks",
                    "description": "List tasks in an Asana project or assigned to a user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_gid": {"type": "string", "description": "Project GID to list tasks from."},
                            "assignee": {"type": "string", "description": "Assignee (use 'me' for current user, or user GID)."},
                            "workspace_gid": {"type": "string", "description": "Required when filtering by assignee without project."},
                            "completed": {"type": "boolean", "description": "Filter by completion status."},
                            "limit": {"type": "integer", "description": "Max tasks (default 30)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "asana_get_task",
                    "description": "Get full details of a specific Asana task.",
                    "parameters": {
                        "type": "object",
                        "properties": {"task_gid": {"type": "string", "description": "Task GID."}},
                        "required": ["task_gid"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "asana_create_task",
                    "description": "Create a new task in Asana.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Task name."},
                            "workspace_gid": {"type": "string", "description": "Workspace GID (required if no project_gid)."},
                            "project_gid": {"type": "string", "description": "Project GID to add task to."},
                            "notes": {"type": "string", "description": "Task description/notes."},
                            "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format."},
                            "assignee": {"type": "string", "description": "Assignee user GID or 'me'."},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "asana_update_task",
                    "description": "Update an existing Asana task (name, notes, due date, assignee, completion).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_gid": {"type": "string", "description": "Task GID."},
                            "name": {"type": "string", "description": "New task name."},
                            "notes": {"type": "string", "description": "New notes/description."},
                            "due_date": {"type": "string", "description": "New due date in YYYY-MM-DD format."},
                            "assignee": {"type": "string", "description": "New assignee GID or 'me'."},
                            "completed": {"type": "boolean", "description": "Mark task as complete (true) or incomplete (false)."},
                        },
                        "required": ["task_gid"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "asana_add_comment",
                    "description": "Add a comment to an Asana task.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_gid": {"type": "string", "description": "Task GID."},
                            "text": {"type": "string", "description": "Comment text."},
                        },
                        "required": ["task_gid", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "asana_delete_task",
                    "description": "Permanently delete an Asana task.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_gid": {"type": "string", "description": "Task GID to delete."},
                        },
                        "required": ["task_gid"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "asana_search_tasks",
                    "description": "Search for tasks by text within an Asana workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "workspace_gid": {"type": "string", "description": "Workspace GID to search within."},
                            "query": {"type": "string", "description": "Search text to find matching tasks."},
                            "limit": {"type": "integer", "description": "Max results to return (default 20)."},
                        },
                        "required": ["workspace_gid", "query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "asana_list_sections",
                    "description": "List sections in an Asana project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_gid": {"type": "string", "description": "Project GID to list sections for."},
                        },
                        "required": ["project_gid"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "asana_create_subtask",
                    "description": "Create a subtask under an existing Asana task.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "parent_task_gid": {"type": "string", "description": "GID of the parent task."},
                            "name": {"type": "string", "description": "Subtask name."},
                            "notes": {"type": "string", "description": "Optional subtask description/notes."},
                            "due_on": {"type": "string", "description": "Optional due date in YYYY-MM-DD format."},
                        },
                        "required": ["parent_task_gid", "name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "asana_set_task_due_date",
                    "description": "Set or update the due date of an Asana task.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_gid": {"type": "string", "description": "Task GID."},
                            "due_on": {"type": "string", "description": "Due date in YYYY-MM-DD format."},
                        },
                        "required": ["task_gid", "due_on"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "asana_get_current_user",
                    "description": "Get the authenticated Asana user's profile and workspaces.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "asana_list_teams",
                    "description": "List teams within an Asana organization/workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {"workspace_gid": {"type": "string", "description": "Workspace/organization GID."}},
                        "required": ["workspace_gid"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "asana_create_project",
                    "description": "Create a new project in an Asana workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Project name."},
                            "workspace_gid": {"type": "string", "description": "Workspace GID to create the project in."},
                            "team_gid": {"type": "string", "description": "Optional team GID to associate the project with."},
                            "notes": {"type": "string", "description": "Optional project description/notes."},
                            "due_date": {"type": "string", "description": "Optional due date in YYYY-MM-DD format."},
                        },
                        "required": ["name", "workspace_gid"],
                    },
                },
            },
        ]
        callables = {
            "asana_list_workspaces": self.list_workspaces,
            "asana_list_projects": self.list_projects,
            "asana_list_tasks": self.list_tasks,
            "asana_get_task": self.get_task,
            "asana_create_task": self.create_task,
            "asana_update_task": self.update_task,
            "asana_add_comment": self.add_comment,
            "asana_delete_task": self.delete_task,
            "asana_search_tasks": self.search_tasks,
            "asana_list_sections": self.list_sections,
            "asana_create_subtask": self.create_subtask,
            "asana_set_task_due_date": self.set_task_due_date,
            "asana_get_current_user": self.get_current_user,
            "asana_list_teams": self.list_teams,
            "asana_create_project": self.create_project,
        }
        return tools, callables

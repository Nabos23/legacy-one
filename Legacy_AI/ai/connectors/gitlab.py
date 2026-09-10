import json
import httpx
from urllib.parse import quote
from ai.connectors.base import BaseConnector

_BASE = "https://gitlab.com/api/v4"

def _handle_error(tool_name, e):
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class GitlabConnector(BaseConnector):
    """Connector for GitLab — access user info, projects, commits, issues, merge requests, groups, and pipelines."""

    PROVIDER_ID = "gitlab"

    def gitlab_get_current_user(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_get_current_user", inp)
        if permission_error: return permission_error
        try:
            r = httpx.get(f"{_BASE}/user", headers=self._auth_headers, timeout=15)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_get_current_user", e)

    def gitlab_list_projects(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_list_projects", inp)
        if permission_error: return permission_error
        params = {
            "membership": inp.get("membership", True),
            "order_by": inp.get("order_by", "last_activity_at"),
            "per_page": inp.get("per_page", 20),
            "page": inp.get("page", 1),
        }
        if inp.get("search"):
            params["search"] = inp["search"]
        try:
            r = httpx.get(f"{_BASE}/projects", headers=self._auth_headers, params=params, timeout=15)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_list_projects", e)

    def gitlab_list_commits(self, inp: dict) -> str:
        permission_error, project_id = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_list_commits", inp, "project_id")
        if permission_error: return permission_error
        params = {
            "per_page": inp.get("per_page", 20),
            "page": inp.get("page", 1),
        }
        if inp.get("ref_name"):
            params["ref_name"] = inp["ref_name"]
        if inp.get("since"):
            params["since"] = inp["since"]
        if inp.get("until"):
            params["until"] = inp["until"]
        try:
            r = httpx.get(f"{_BASE}/projects/{project_id}/repository/commits", headers=self._auth_headers, params=params, timeout=15)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_list_commits", e)

    def gitlab_list_issues(self, inp: dict) -> str:
        permission_error, project_id = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_list_issues", inp, "project_id")
        if permission_error: return permission_error
        params = {
            "per_page": inp.get("per_page", 20),
            "page": inp.get("page", 1),
        }
        if inp.get("state"):
            params["state"] = inp["state"]
        if inp.get("labels"):
            params["labels"] = inp["labels"]
        if inp.get("assignee_username"):
            params["assignee_username"] = inp["assignee_username"]
        try:
            r = httpx.get(f"{_BASE}/projects/{project_id}/issues", headers=self._auth_headers, params=params, timeout=15)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_list_issues", e)

    def gitlab_list_merge_requests(self, inp: dict) -> str:
        permission_error, project_id = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_list_merge_requests", inp, "project_id")
        if permission_error: return permission_error
        params = {
            "per_page": inp.get("per_page", 20),
            "page": inp.get("page", 1),
        }
        if inp.get("state"):
            params["state"] = inp["state"]
        if inp.get("target_branch"):
            params["target_branch"] = inp["target_branch"]
        if inp.get("author_username"):
            params["author_username"] = inp["author_username"]
        try:
            r = httpx.get(f"{_BASE}/projects/{project_id}/merge_requests", headers=self._auth_headers, params=params, timeout=15)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_list_merge_requests", e)

    def gitlab_list_groups(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_list_groups", inp)
        if permission_error: return permission_error
        params = {
            "per_page": inp.get("per_page", 20),
            "page": inp.get("page", 1),
        }
        if inp.get("search"):
            params["search"] = inp["search"]
        try:
            r = httpx.get(f"{_BASE}/groups", headers=self._auth_headers, params=params, timeout=15)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_list_groups", e)

    def gitlab_list_pipelines(self, inp: dict) -> str:
        permission_error, project_id = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_list_pipelines", inp, "project_id")
        if permission_error: return permission_error
        params = {
            "per_page": inp.get("per_page", 20),
            "page": inp.get("page", 1),
        }
        if inp.get("status"):
            params["status"] = inp["status"]
        if inp.get("ref"):
            params["ref"] = inp["ref"]
        try:
            r = httpx.get(f"{_BASE}/projects/{project_id}/pipelines", headers=self._auth_headers, params=params, timeout=15)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_list_pipelines", e)

    # ── Write / fetch tools ────────────────────────────────────────────────

    def gitlab_get_project(self, inp: dict) -> str:
        permission_error, project_id = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_get_project", inp, "project_id")
        if permission_error: return permission_error
        try:
            r = httpx.get(f"{_BASE}/projects/{project_id}", headers=self._auth_headers, timeout=15)
            r.raise_for_status()
            data = r.json()
            return json.dumps({
                "id": data.get("id"),
                "name": data.get("name"),
                "description": data.get("description"),
                "default_branch": data.get("default_branch"),
                "web_url": data.get("web_url"),
                "visibility": data.get("visibility"),
            })
        except Exception as e:
            return _handle_error("gitlab_get_project", e)

    def gitlab_get_file_contents(self, inp: dict) -> str:
        permission_error, project_id, file_path = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_get_file_contents", inp, "project_id", "file_path")
        if permission_error: return permission_error
        ref = inp.get("ref", "HEAD")
        encoded_path = quote(file_path, safe="")
        try:
            r = httpx.get(
                f"{_BASE}/projects/{project_id}/repository/files/{encoded_path}/raw",
                headers=self._auth_headers,
                params={"ref": ref},
                timeout=30,
            )
            r.raise_for_status()
            return json.dumps({"content": r.text})
        except Exception as e:
            return _handle_error("gitlab_get_file_contents", e)

    def gitlab_create_issue(self, inp: dict) -> str:
        permission_error, project_id, title = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_create_issue", inp, "project_id", "title")
        if permission_error: return permission_error
        payload: dict = {"title": title}
        if inp.get("description") is not None:
            payload["description"] = inp["description"]
        if inp.get("labels") is not None:
            payload["labels"] = inp["labels"]
        if inp.get("assignee_ids") is not None:
            payload["assignee_ids"] = inp["assignee_ids"]
        try:
            r = httpx.post(
                f"{_BASE}/projects/{project_id}/issues",
                headers=self._auth_headers,
                json=payload,
                timeout=15,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_create_issue", e)

    def gitlab_update_issue(self, inp: dict) -> str:
        permission_error, project_id, issue_iid = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_update_issue", inp, "project_id", "issue_iid")
        if permission_error: return permission_error
        payload: dict = {}
        if inp.get("state_event") is not None:
            payload["state_event"] = inp["state_event"]
        if inp.get("title") is not None:
            payload["title"] = inp["title"]
        if inp.get("description") is not None:
            payload["description"] = inp["description"]
        if inp.get("labels") is not None:
            payload["labels"] = inp["labels"]
        if inp.get("assignee_ids") is not None:
            payload["assignee_ids"] = inp["assignee_ids"]
        if not payload:
            return "No fields provided to update."
        try:
            r = httpx.put(
                f"{_BASE}/projects/{project_id}/issues/{issue_iid}",
                headers=self._auth_headers,
                json=payload,
                timeout=15,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_update_issue", e)

    def gitlab_create_merge_request(self, inp: dict) -> str:
        permission_error, project_id, source_branch, target_branch, title = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_create_merge_request", inp, "project_id", "source_branch", "target_branch", "title")
        if permission_error: return permission_error
        payload: dict = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
        }
        if inp.get("description") is not None:
            payload["description"] = inp["description"]
        if inp.get("remove_source_branch") is not None:
            payload["remove_source_branch"] = inp["remove_source_branch"]
        try:
            r = httpx.post(
                f"{_BASE}/projects/{project_id}/merge_requests",
                headers=self._auth_headers,
                json=payload,
                timeout=15,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_create_merge_request", e)

    def gitlab_add_issue_comment(self, inp: dict) -> str:
        permission_error, project_id, issue_iid, body = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_add_issue_comment", inp, "project_id", "issue_iid", "body")
        if permission_error: return permission_error
        try:
            r = httpx.post(
                f"{_BASE}/projects/{project_id}/issues/{issue_iid}/notes",
                headers=self._auth_headers,
                json={"body": body},
                timeout=15,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_add_issue_comment", e)

    def gitlab_trigger_pipeline(self, inp: dict) -> str:
        permission_error, project_id, ref, token = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_trigger_pipeline", inp, "project_id", "ref", "token")
        if permission_error: return permission_error
        try:
            r = httpx.post(
                f"{_BASE}/projects/{project_id}/trigger/pipeline",
                headers=self._auth_headers,
                json={"ref": ref, "token": token},
                timeout=15,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_trigger_pipeline", e)

    def gitlab_list_branches(self, inp: dict) -> str:
        permission_error, project_id = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_list_branches", inp, "project_id")
        if permission_error: return permission_error
        params = {"per_page": inp.get("per_page", 20), "page": inp.get("page", 1)}
        if inp.get("search"):
            params["search"] = inp["search"]
        try:
            r = httpx.get(f"{_BASE}/projects/{project_id}/repository/branches", headers=self._auth_headers, params=params, timeout=15)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_list_branches", e)

    def gitlab_create_branch(self, inp: dict) -> str:
        permission_error, project_id, branch, ref = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_create_branch", inp, "project_id", "branch", "ref")
        if permission_error: return permission_error
        try:
            r = httpx.post(
                f"{_BASE}/projects/{project_id}/repository/branches",
                headers=self._auth_headers,
                params={"branch": branch, "ref": ref},
                timeout=15,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_create_branch", e)

    def gitlab_list_milestones(self, inp: dict) -> str:
        permission_error, project_id = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_list_milestones", inp, "project_id")
        if permission_error: return permission_error
        params = {"per_page": inp.get("per_page", 20), "page": inp.get("page", 1)}
        if inp.get("state"):
            params["state"] = inp["state"]
        try:
            r = httpx.get(f"{_BASE}/projects/{project_id}/milestones", headers=self._auth_headers, params=params, timeout=15)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_list_milestones", e)

    def gitlab_create_milestone(self, inp: dict) -> str:
        permission_error, project_id, title = self._check(self.agent_id, self.PROVIDER_ID, "gitlab_create_milestone", inp, "project_id", "title")
        if permission_error: return permission_error
        payload: dict = {"title": title}
        if inp.get("description") is not None:
            payload["description"] = inp["description"]
        if inp.get("due_date") is not None:
            payload["due_date"] = inp["due_date"]
        try:
            r = httpx.post(
                f"{_BASE}/projects/{project_id}/milestones",
                headers=self._auth_headers,
                json=payload,
                timeout=15,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_create_milestone", e)

    def gitlab_merge_merge_request(self, inp: dict) -> str:
        permission_allowed, permission_action = self.check_permission("gitlab_merge_merge_request")
        if not allowed:
            return f"Permission denied: Agent is not allowed to use GitLab '{action}' actions."
        project_id = inp.get("project_id")
        merge_request_iid = inp.get("merge_request_iid")
        if not project_id:
            return "Missing required parameter: project_id"
        if not merge_request_iid:
            return "Missing required parameter: merge_request_iid"
        payload: dict = {}
        if inp.get("merge_commit_message") is not None:
            payload["merge_commit_message"] = inp["merge_commit_message"]
        if inp.get("should_remove_source_branch") is not None:
            payload["should_remove_source_branch"] = inp["should_remove_source_branch"]
        try:
            r = httpx.put(
                f"{_BASE}/projects/{project_id}/merge_requests/{merge_request_iid}/merge",
                headers=self._auth_headers,
                json=payload,
                timeout=15,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_merge_merge_request", e)

    def gitlab_list_releases(self, inp: dict) -> str:
        permission_allowed, permission_action = self.check_permission("gitlab_list_releases")
        if not permission_allowed:
            return f"Permission denied: Agent is not allowed to use GitLab '{permission_action}' actions."
        project_id = inp.get("project_id")
        if not project_id:
            return "Missing required parameter: project_id"
        params = {"per_page": inp.get("per_page", 20), "page": inp.get("page", 1)}
        try:
            r = httpx.get(f"{_BASE}/projects/{project_id}/releases", headers=self._auth_headers, params=params, timeout=15)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("gitlab_list_releases", e)

    def as_tools(self):
        tool_defs = [
            {
                "type": "function",
                "function": {
                    "name": "gitlab_get_current_user",
                    "description": "Get the profile of the currently authenticated GitLab user.",
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
                    "name": "gitlab_list_projects",
                    "description": "List GitLab projects the authenticated user is a member of.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "membership": {
                                "type": "boolean",
                                "description": "If true, only return projects the user is a member of. Default true.",
                            },
                            "search": {
                                "type": "string",
                                "description": "Filter projects by name search term.",
                            },
                            "order_by": {
                                "type": "string",
                                "description": "Field to order by (e.g. last_activity_at, created_at, name). Default last_activity_at.",
                            },
                            "per_page": {
                                "type": "integer",
                                "description": "Number of results per page (default 20).",
                            },
                            "page": {
                                "type": "integer",
                                "description": "Page number (default 1).",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_list_commits",
                    "description": "List commits for a GitLab project repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "The ID or URL-encoded path of the project.",
                            },
                            "ref_name": {
                                "type": "string",
                                "description": "Branch, tag, or commit SHA to list commits from.",
                            },
                            "since": {
                                "type": "string",
                                "description": "ISO 8601 datetime — only commits after this date.",
                            },
                            "until": {
                                "type": "string",
                                "description": "ISO 8601 datetime — only commits before this date.",
                            },
                            "per_page": {
                                "type": "integer",
                                "description": "Number of results per page (default 20).",
                            },
                            "page": {
                                "type": "integer",
                                "description": "Page number (default 1).",
                            },
                        },
                        "required": ["project_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_list_issues",
                    "description": "List issues for a GitLab project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "The ID or URL-encoded path of the project.",
                            },
                            "state": {
                                "type": "string",
                                "description": "Filter by state: opened, closed, or all.",
                                "enum": ["opened", "closed", "all"],
                            },
                            "labels": {
                                "type": "string",
                                "description": "Comma-separated list of label names to filter by.",
                            },
                            "assignee_username": {
                                "type": "string",
                                "description": "Filter issues by assignee username.",
                            },
                            "per_page": {
                                "type": "integer",
                                "description": "Number of results per page (default 20).",
                            },
                            "page": {
                                "type": "integer",
                                "description": "Page number (default 1).",
                            },
                        },
                        "required": ["project_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_list_merge_requests",
                    "description": "List merge requests for a GitLab project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "The ID or URL-encoded path of the project.",
                            },
                            "state": {
                                "type": "string",
                                "description": "Filter by state: opened, closed, locked, merged, or all.",
                                "enum": ["opened", "closed", "locked", "merged", "all"],
                            },
                            "target_branch": {
                                "type": "string",
                                "description": "Filter MRs by target branch name.",
                            },
                            "author_username": {
                                "type": "string",
                                "description": "Filter MRs by author username.",
                            },
                            "per_page": {
                                "type": "integer",
                                "description": "Number of results per page (default 20).",
                            },
                            "page": {
                                "type": "integer",
                                "description": "Page number (default 1).",
                            },
                        },
                        "required": ["project_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_list_groups",
                    "description": "List GitLab groups accessible to the authenticated user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "search": {
                                "type": "string",
                                "description": "Filter groups by name search term.",
                            },
                            "per_page": {
                                "type": "integer",
                                "description": "Number of results per page (default 20).",
                            },
                            "page": {
                                "type": "integer",
                                "description": "Page number (default 1).",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_list_pipelines",
                    "description": "List CI/CD pipelines for a GitLab project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "The ID or URL-encoded path of the project.",
                            },
                            "status": {
                                "type": "string",
                                "description": "Filter by pipeline status: running, pending, success, failed, canceled, skipped, created, manual.",
                                "enum": ["running", "pending", "success", "failed", "canceled", "skipped", "created", "manual"],
                            },
                            "ref": {
                                "type": "string",
                                "description": "Filter pipelines by branch or tag name.",
                            },
                            "per_page": {
                                "type": "integer",
                                "description": "Number of results per page (default 20).",
                            },
                            "page": {
                                "type": "integer",
                                "description": "Page number (default 1).",
                            },
                        },
                        "required": ["project_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_get_project",
                    "description": "Get metadata for a GitLab project: id, name, description, default branch, web URL, and visibility.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "The numeric ID or URL-encoded namespace/project path (e.g. 'mygroup%2Fmyproject').",
                            },
                        },
                        "required": ["project_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_get_file_contents",
                    "description": "Retrieve the raw contents of a file from a GitLab project repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "The numeric ID or URL-encoded namespace/project path.",
                            },
                            "file_path": {
                                "type": "string",
                                "description": "Path to the file within the repository (e.g. 'src/main.py').",
                            },
                            "ref": {
                                "type": "string",
                                "description": "Branch, tag, or commit SHA to read from. Defaults to HEAD.",
                            },
                        },
                        "required": ["project_id", "file_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_create_issue",
                    "description": "Create a new issue in a GitLab project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "The numeric ID or URL-encoded namespace/project path.",
                            },
                            "title": {
                                "type": "string",
                                "description": "Title of the issue.",
                            },
                            "description": {
                                "type": "string",
                                "description": "Description / body of the issue (optional).",
                            },
                            "labels": {
                                "type": "string",
                                "description": "Comma-separated list of label names to assign (optional).",
                            },
                            "assignee_ids": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "List of user IDs to assign the issue to (optional).",
                            },
                        },
                        "required": ["project_id", "title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_update_issue",
                    "description": "Update an existing issue in a GitLab project. All fields except project_id and issue_iid are optional.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "The numeric ID or URL-encoded namespace/project path.",
                            },
                            "issue_iid": {
                                "type": "integer",
                                "description": "The internal ID (IID) of the issue within the project.",
                            },
                            "state_event": {
                                "type": "string",
                                "description": "Transition the issue state: 'close' or 'reopen'.",
                                "enum": ["close", "reopen"],
                            },
                            "title": {
                                "type": "string",
                                "description": "New title for the issue.",
                            },
                            "description": {
                                "type": "string",
                                "description": "New description for the issue.",
                            },
                            "labels": {
                                "type": "string",
                                "description": "Comma-separated list of label names (replaces existing labels).",
                            },
                            "assignee_ids": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "List of user IDs to assign. Pass an empty list to unassign all.",
                            },
                        },
                        "required": ["project_id", "issue_iid"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_create_merge_request",
                    "description": "Create a new merge request in a GitLab project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "The numeric ID or URL-encoded namespace/project path.",
                            },
                            "source_branch": {
                                "type": "string",
                                "description": "The branch to merge from.",
                            },
                            "target_branch": {
                                "type": "string",
                                "description": "The branch to merge into.",
                            },
                            "title": {
                                "type": "string",
                                "description": "Title of the merge request.",
                            },
                            "description": {
                                "type": "string",
                                "description": "Description / body of the merge request (optional).",
                            },
                            "remove_source_branch": {
                                "type": "boolean",
                                "description": "If true, delete the source branch after the MR is merged (optional).",
                            },
                        },
                        "required": ["project_id", "source_branch", "target_branch", "title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_add_issue_comment",
                    "description": "Add a comment (note) to an existing issue in a GitLab project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "The numeric ID or URL-encoded namespace/project path.",
                            },
                            "issue_iid": {
                                "type": "integer",
                                "description": "The internal ID (IID) of the issue within the project.",
                            },
                            "body": {
                                "type": "string",
                                "description": "The text content of the comment.",
                            },
                        },
                        "required": ["project_id", "issue_iid", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_trigger_pipeline",
                    "description": "Trigger a CI/CD pipeline on a GitLab project using a pipeline trigger token.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "The numeric ID or URL-encoded namespace/project path.",
                            },
                            "ref": {
                                "type": "string",
                                "description": "The branch or tag name to run the pipeline on.",
                            },
                            "token": {
                                "type": "string",
                                "description": "The pipeline trigger token (created under Project > Settings > CI/CD > Pipeline triggers).",
                            },
                        },
                        "required": ["project_id", "ref", "token"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_list_branches",
                    "description": "List branches for a GitLab project repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "The ID or URL-encoded path of the project."},
                            "search": {"type": "string", "description": "Filter branches by name search term."},
                            "per_page": {"type": "integer", "description": "Number of results per page (default 20)."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                        },
                        "required": ["project_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_create_branch",
                    "description": "Create a new branch in a GitLab project from a given ref (branch, tag, or commit SHA).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "The ID or URL-encoded path of the project."},
                            "branch": {"type": "string", "description": "Name of the new branch."},
                            "ref": {"type": "string", "description": "Branch name, tag, or commit SHA to create the branch from."},
                        },
                        "required": ["project_id", "branch", "ref"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_list_milestones",
                    "description": "List milestones for a GitLab project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "The ID or URL-encoded path of the project."},
                            "state": {"type": "string", "description": "Filter by state: active or closed.", "enum": ["active", "closed"]},
                            "per_page": {"type": "integer", "description": "Number of results per page (default 20)."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                        },
                        "required": ["project_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_create_milestone",
                    "description": "Create a new milestone in a GitLab project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "The ID or URL-encoded path of the project."},
                            "title": {"type": "string", "description": "Title of the milestone."},
                            "description": {"type": "string", "description": "Description of the milestone (optional)."},
                            "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format (optional)."},
                        },
                        "required": ["project_id", "title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_merge_merge_request",
                    "description": "Merge (accept) an existing merge request in a GitLab project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "The ID or URL-encoded path of the project."},
                            "merge_request_iid": {"type": "integer", "description": "The internal ID (IID) of the merge request."},
                            "merge_commit_message": {"type": "string", "description": "Custom merge commit message (optional)."},
                            "should_remove_source_branch": {"type": "boolean", "description": "If true, remove the source branch after merge (optional)."},
                        },
                        "required": ["project_id", "merge_request_iid"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gitlab_list_releases",
                    "description": "List releases for a GitLab project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {"type": "string", "description": "The ID or URL-encoded path of the project."},
                            "per_page": {"type": "integer", "description": "Number of results per page (default 20)."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                        },
                        "required": ["project_id"],
                    },
                },
            },
        ]

        callables = {
            "gitlab_get_current_user": self.gitlab_get_current_user,
            "gitlab_list_projects": self.gitlab_list_projects,
            "gitlab_list_commits": self.gitlab_list_commits,
            "gitlab_list_issues": self.gitlab_list_issues,
            "gitlab_list_merge_requests": self.gitlab_list_merge_requests,
            "gitlab_list_groups": self.gitlab_list_groups,
            "gitlab_list_pipelines": self.gitlab_list_pipelines,
            "gitlab_get_project": self.gitlab_get_project,
            "gitlab_get_file_contents": self.gitlab_get_file_contents,
            "gitlab_create_issue": self.gitlab_create_issue,
            "gitlab_update_issue": self.gitlab_update_issue,
            "gitlab_create_merge_request": self.gitlab_create_merge_request,
            "gitlab_add_issue_comment": self.gitlab_add_issue_comment,
            "gitlab_trigger_pipeline": self.gitlab_trigger_pipeline,
            "gitlab_list_branches": self.gitlab_list_branches,
            "gitlab_create_branch": self.gitlab_create_branch,
            "gitlab_list_milestones": self.gitlab_list_milestones,
            "gitlab_create_milestone": self.gitlab_create_milestone,
            "gitlab_merge_merge_request": self.gitlab_merge_merge_request,
            "gitlab_list_releases": self.gitlab_list_releases,
        }

        return tool_defs, callables

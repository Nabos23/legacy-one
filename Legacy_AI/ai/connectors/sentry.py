import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://sentry.io/api/0"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class SentryConnector(BaseConnector):
    """Interact with Sentry organizations, projects, issues, events, and releases."""

    PROVIDER_ID = "sentry"

    def list_organizations(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "sentry_list_organizations", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/organizations/", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            orgs = [
                {
                    "slug": o["slug"],
                    "name": o["name"],
                    "id": o["id"],
                    "status": o.get("status", {}).get("id"),
                    "dateCreated": o.get("dateCreated"),
                }
                for o in resp.json()
            ]
            return json.dumps({"organizations": orgs, "count": len(orgs)})
        except Exception as e:
            return _handle_error("sentry_list_organizations", e)

    def get_organization(self, inp: dict) -> str:
        permission_error, org = self._check(self.agent_id, self.PROVIDER_ID, "sentry_get_organization", inp, "organization_slug")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/organizations/{org}/", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            o = resp.json()
            return json.dumps({
                "slug": o["slug"],
                "name": o["name"],
                "id": o["id"],
                "status": o.get("status", {}).get("id"),
                "dateCreated": o.get("dateCreated"),
                "memberCount": o.get("memberCount"),
                "features": o.get("features", []),
            })
        except Exception as e:
            return _handle_error("sentry_get_organization", e)

    def list_projects(self, inp: dict) -> str:
        permission_error, org = self._check(self.agent_id, self.PROVIDER_ID, "sentry_list_projects", inp, "organization_slug")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/organizations/{org}/projects/", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            projects = [
                {
                    "slug": p["slug"],
                    "name": p["name"],
                    "id": p["id"],
                    "platform": p.get("platform"),
                    "status": p.get("status"),
                    "dateCreated": p.get("dateCreated"),
                }
                for p in resp.json()
            ]
            return json.dumps({"projects": projects, "count": len(projects)})
        except Exception as e:
            return _handle_error("sentry_list_projects", e)

    def list_org_issues(self, inp: dict) -> str:
        permission_error, org = self._check(self.agent_id, self.PROVIDER_ID, "sentry_list_org_issues", inp, "organization_slug")
        if permission_error: return permission_error
        try:
            params: dict = {"limit": inp.get("limit", 25)}
            if inp.get("query"):
                params["query"] = inp["query"]
            if inp.get("project"):
                params["project"] = inp["project"]
            resp = httpx.get(f"{_BASE}/organizations/{org}/issues/", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            issues = [
                {
                    "id": i["id"],
                    "title": i["title"],
                    "culprit": i.get("culprit"),
                    "level": i.get("level"),
                    "status": i.get("status"),
                    "count": i.get("count"),
                    "userCount": i.get("userCount"),
                    "firstSeen": i.get("firstSeen"),
                    "lastSeen": i.get("lastSeen"),
                    "project": i.get("project", {}).get("slug"),
                }
                for i in resp.json()
            ]
            return json.dumps({"issues": issues, "count": len(issues)})
        except Exception as e:
            return _handle_error("sentry_list_org_issues", e)

    def list_project_issues(self, inp: dict) -> str:
        permission_error, org, project = self._check(self.agent_id, self.PROVIDER_ID, "sentry_list_project_issues", inp, "organization_slug", "project_slug")
        if permission_error: return permission_error
        try:
            params: dict = {"limit": inp.get("limit", 25)}
            if inp.get("query"):
                params["query"] = inp["query"]
            if inp.get("status"):
                params["query"] = f"is:{inp['status']} " + params.get("query", "")
            resp = httpx.get(f"{_BASE}/projects/{org}/{project}/issues/", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            issues = [
                {
                    "id": i["id"],
                    "title": i["title"],
                    "culprit": i.get("culprit"),
                    "level": i.get("level"),
                    "status": i.get("status"),
                    "count": i.get("count"),
                    "userCount": i.get("userCount"),
                    "firstSeen": i.get("firstSeen"),
                    "lastSeen": i.get("lastSeen"),
                }
                for i in resp.json()
            ]
            return json.dumps({"issues": issues, "count": len(issues)})
        except Exception as e:
            return _handle_error("sentry_list_project_issues", e)

    def list_project_events(self, inp: dict) -> str:
        permission_error, org, project = self._check(self.agent_id, self.PROVIDER_ID, "sentry_list_project_events", inp, "organization_slug", "project_slug")
        if permission_error: return permission_error
        try:
            params: dict = {"limit": inp.get("limit", 20)}
            resp = httpx.get(f"{_BASE}/projects/{org}/{project}/events/", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            events = [
                {
                    "id": ev["id"],
                    "title": ev.get("title"),
                    "message": ev.get("message"),
                    "platform": ev.get("platform"),
                    "dateCreated": ev.get("dateCreated"),
                    "tags": ev.get("tags", []),
                }
                for ev in resp.json()
            ]
            return json.dumps({"events": events, "count": len(events)})
        except Exception as e:
            return _handle_error("sentry_list_project_events", e)

    def list_releases(self, inp: dict) -> str:
        permission_error, org = self._check(self.agent_id, self.PROVIDER_ID, "sentry_list_releases", inp, "organization_slug")
        if permission_error: return permission_error
        try:
            params: dict = {"limit": inp.get("limit", 20)}
            if inp.get("project"):
                params["project"] = inp["project"]
            resp = httpx.get(f"{_BASE}/organizations/{org}/releases/", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            releases = [
                {
                    "version": r["version"],
                    "dateCreated": r.get("dateCreated"),
                    "dateReleased": r.get("dateReleased"),
                    "newGroups": r.get("newGroups"),
                    "firstEvent": r.get("firstEvent"),
                    "lastEvent": r.get("lastEvent"),
                    "projects": [p["slug"] for p in r.get("projects", [])],
                }
                for r in resp.json()
            ]
            return json.dumps({"releases": releases, "count": len(releases)})
        except Exception as e:
            return _handle_error("sentry_list_releases", e)

    def get_issue(self, inp: dict) -> str:
        permission_error, issue_id = self._check(self.agent_id, self.PROVIDER_ID, "sentry_get_issue", inp, "issue_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/issues/{issue_id}/", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            i = resp.json()
            return json.dumps({
                "id": i.get("id"),
                "title": i.get("title"),
                "culprit": i.get("culprit"),
                "status": i.get("status"),
                "assignedTo": i.get("assignedTo"),
                "permalink": i.get("permalink"),
                "firstSeen": i.get("firstSeen"),
                "lastSeen": i.get("lastSeen"),
                "count": i.get("count"),
            })
        except Exception as e:
            return _handle_error("sentry_get_issue", e)

    def resolve_issue(self, inp: dict) -> str:
        permission_error, issue_id = self._check(self.agent_id, self.PROVIDER_ID, "sentry_resolve_issue", inp, "issue_id")
        if permission_error: return permission_error
        try:
            resp = httpx.put(
                f"{_BASE}/issues/{issue_id}/",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"status": "resolved"},
                timeout=15,
            )
            resp.raise_for_status()
            i = resp.json()
            return json.dumps({
                "id": i.get("id"),
                "status": i.get("status"),
                "title": i.get("title"),
            })
        except Exception as e:
            return _handle_error("sentry_resolve_issue", e)

    def assign_issue(self, inp: dict) -> str:
        permission_error, issue_id, assigned_to = self._check(self.agent_id, self.PROVIDER_ID, "sentry_assign_issue", inp, "issue_id", "assigned_to")
        if permission_error: return permission_error
        try:
            resp = httpx.put(
                f"{_BASE}/issues/{issue_id}/",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"assignedTo": assigned_to},
                timeout=15,
            )
            resp.raise_for_status()
            i = resp.json()
            return json.dumps({
                "id": i.get("id"),
                "status": i.get("status"),
                "title": i.get("title"),
                "assignedTo": i.get("assignedTo"),
            })
        except Exception as e:
            return _handle_error("sentry_assign_issue", e)

    def ignore_issue(self, inp: dict) -> str:
        permission_error, issue_id = self._check(self.agent_id, self.PROVIDER_ID, "sentry_ignore_issue", inp, "issue_id")
        if permission_error: return permission_error
        try:
            resp = httpx.put(
                f"{_BASE}/issues/{issue_id}/",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"status": "ignored"},
                timeout=15,
            )
            resp.raise_for_status()
            i = resp.json()
            return json.dumps({
                "id": i.get("id"),
                "status": i.get("status"),
                "title": i.get("title"),
            })
        except Exception as e:
            return _handle_error("sentry_ignore_issue", e)

    def list_project_tags(self, inp: dict) -> str:
        permission_error, org, project = self._check(self.agent_id, self.PROVIDER_ID, "sentry_list_project_tags", inp, "organization_slug", "project_slug")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/projects/{org}/{project}/tags/",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            tags = [{"key": t.get("key"), "name": t.get("name")} for t in resp.json()]
            return json.dumps({"tags": tags, "count": len(tags)})
        except Exception as e:
            return _handle_error("sentry_list_project_tags", e)

    def get_event_details(self, inp: dict) -> str:
        permission_error, issue_id = self._check(self.agent_id, self.PROVIDER_ID, "sentry_get_event_details", inp, "issue_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/issues/{issue_id}/events/latest/",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            ev = resp.json()
            return json.dumps({
                "id": ev.get("id"),
                "eventID": ev.get("eventID"),
                "title": ev.get("title"),
                "message": ev.get("message"),
                "platform": ev.get("platform"),
                "dateCreated": ev.get("dateCreated"),
                "tags": ev.get("tags", []),
                "contexts": ev.get("contexts", {}),
                "entries": ev.get("entries", []),
                "user": ev.get("user"),
            })
        except Exception as e:
            return _handle_error("sentry_get_event_details", e)

    def list_org_members(self, inp: dict) -> str:
        permission_error, org = self._check(self.agent_id, self.PROVIDER_ID, "sentry_list_org_members", inp, "organization_slug")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/organizations/{org}/members/", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            members = [
                {
                    "id": m.get("id"),
                    "email": m.get("email"),
                    "name": m.get("name"),
                    "role": m.get("orgRole"),
                    "pending": m.get("pending"),
                }
                for m in resp.json()
            ]
            return json.dumps({"members": members, "count": len(members)})
        except Exception as e:
            return _handle_error("sentry_list_org_members", e)

    def add_issue_comment(self, inp: dict) -> str:
        permission_error, issue_id, text = self._check(self.agent_id, self.PROVIDER_ID, "sentry_add_issue_comment", inp, "issue_id", "text")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/issues/{issue_id}/notes/",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"text": text},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"issue_id": issue_id, "comment_id": data.get("id"), "status": "comment_added"})
        except Exception as e:
            return _handle_error("sentry_add_issue_comment", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "sentry_list_organizations",
                    "description": "List all Sentry organizations accessible to the authenticated user.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sentry_get_organization",
                    "description": "Retrieve details about a specific Sentry organization.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "organization_slug": {"type": "string", "description": "The slug of the organization."},
                        },
                        "required": ["organization_slug"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sentry_list_projects",
                    "description": "List all projects in a Sentry organization.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "organization_slug": {"type": "string", "description": "The slug of the organization."},
                        },
                        "required": ["organization_slug"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sentry_list_org_issues",
                    "description": "List all issues across a Sentry organization, optionally filtered by query or project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "organization_slug": {"type": "string", "description": "The slug of the organization."},
                            "query": {"type": "string", "description": "Sentry search query to filter issues (e.g. 'is:unresolved')."},
                            "project": {"type": "string", "description": "Project ID to filter issues to a specific project."},
                            "limit": {"type": "integer", "description": "Max issues to return (default 25)."},
                        },
                        "required": ["organization_slug"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sentry_list_project_issues",
                    "description": "List issues for a specific project in a Sentry organization.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "organization_slug": {"type": "string", "description": "The slug of the organization."},
                            "project_slug": {"type": "string", "description": "The slug of the project."},
                            "query": {"type": "string", "description": "Sentry search query to filter issues."},
                            "status": {"type": "string", "description": "Filter by status: unresolved, resolved, ignored."},
                            "limit": {"type": "integer", "description": "Max issues to return (default 25)."},
                        },
                        "required": ["organization_slug", "project_slug"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sentry_list_project_events",
                    "description": "List error events for a specific project in Sentry.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "organization_slug": {"type": "string", "description": "The slug of the organization."},
                            "project_slug": {"type": "string", "description": "The slug of the project."},
                            "limit": {"type": "integer", "description": "Max events to return (default 20)."},
                        },
                        "required": ["organization_slug", "project_slug"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sentry_list_releases",
                    "description": "List releases for a Sentry organization, optionally filtered by project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "organization_slug": {"type": "string", "description": "The slug of the organization."},
                            "project": {"type": "string", "description": "Project slug to filter releases."},
                            "limit": {"type": "integer", "description": "Max releases to return (default 20)."},
                        },
                        "required": ["organization_slug"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sentry_get_issue",
                    "description": "Get details of a specific Sentry issue by its ID, including title, status, assignee, and occurrence counts.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_id": {"type": "string", "description": "The Sentry issue ID. Required."},
                        },
                        "required": ["issue_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sentry_resolve_issue",
                    "description": "Mark a Sentry issue as resolved.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_id": {"type": "string", "description": "The Sentry issue ID to resolve. Required."},
                        },
                        "required": ["issue_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sentry_assign_issue",
                    "description": "Assign a Sentry issue to a user or team.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_id": {"type": "string", "description": "The Sentry issue ID to assign. Required."},
                            "assigned_to": {"type": "string", "description": "Username or team name to assign the issue to. Required."},
                        },
                        "required": ["issue_id", "assigned_to"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sentry_ignore_issue",
                    "description": "Mark a Sentry issue as ignored.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_id": {"type": "string", "description": "The Sentry issue ID to ignore. Required."},
                        },
                        "required": ["issue_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sentry_list_project_tags",
                    "description": "List all tag keys used in a Sentry project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "organization_slug": {"type": "string", "description": "The Sentry organization slug. Required."},
                            "project_slug": {"type": "string", "description": "The Sentry project slug. Required."},
                        },
                        "required": ["organization_slug", "project_slug"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sentry_get_event_details",
                    "description": "Get the latest event for a Sentry issue, including full stack trace, tags, and context.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_id": {"type": "string", "description": "The Sentry issue ID. Required."},
                        },
                        "required": ["issue_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sentry_list_org_members",
                    "description": "List members of a Sentry organization.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "organization_slug": {"type": "string", "description": "The Sentry organization slug. Required."},
                        },
                        "required": ["organization_slug"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sentry_add_issue_comment",
                    "description": "Add a comment/note to a Sentry issue.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_id": {"type": "string", "description": "The Sentry issue ID. Required."},
                            "text": {"type": "string", "description": "Comment text to add. Required."},
                        },
                        "required": ["issue_id", "text"],
                    },
                },
            },
        ]
        callables = {
            "sentry_list_organizations": self.list_organizations,
            "sentry_get_organization": self.get_organization,
            "sentry_list_projects": self.list_projects,
            "sentry_list_org_issues": self.list_org_issues,
            "sentry_list_project_issues": self.list_project_issues,
            "sentry_list_project_events": self.list_project_events,
            "sentry_list_releases": self.list_releases,
            "sentry_get_issue": self.get_issue,
            "sentry_resolve_issue": self.resolve_issue,
            "sentry_assign_issue": self.assign_issue,
            "sentry_ignore_issue": self.ignore_issue,
            "sentry_list_project_tags": self.list_project_tags,
            "sentry_get_event_details": self.get_event_details,
            "sentry_list_org_members": self.list_org_members,
            "sentry_add_issue_comment": self.add_issue_comment,
        }
        return tools, callables

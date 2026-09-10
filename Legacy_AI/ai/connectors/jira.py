import json
import httpx

from ai.connectors.base import BaseConnector


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Jira account lacks permission "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their Jira connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class JiraConnector(BaseConnector):
    """
    Jira Cloud connector.
    access_token format: "ACCESS_TOKEN" or "ACCESS_TOKEN:SUBDOMAIN"
    If subdomain is omitted, the cloudId is resolved via accessible-resources.
    """

    PROVIDER_ID = "jira"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id=agent_id)
        parts = access_token.split(":", 1)
        self._token = parts[0]
        self._subdomain = parts[1] if len(parts) > 1 else ""
        self._auth_headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        if self._subdomain:
            self._base = f"https://{self._subdomain}.atlassian.net/rest/api/3"
            self._agile_base = f"https://{self._subdomain}.atlassian.net/rest/agile/1.0"
        else:
            self._base, self._agile_base = self._resolve_base_urls()

    def _resolve_base_urls(self) -> tuple[str, str]:
        """Fetch the cloudId from Atlassian accessible-resources and build the correct base URLs."""
        try:
            resp = httpx.get(
                "https://api.atlassian.com/oauth/token/accessible-resources",
                headers=self._auth_headers,
                timeout=10,
            )
            resp.raise_for_status()
            resources = resp.json()
            if not resources:
                return (
                    "https://api.atlassian.com/ex/jira/none/rest/api/3",
                    "https://api.atlassian.com/ex/jira/none/rest/agile/1.0",
                )
            cloud_id = resources[0]["id"]
            return (
                f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3",
                f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/agile/1.0",
            )
        except Exception:
            return (
                "https://api.atlassian.com/ex/jira/none/rest/api/3",
                "https://api.atlassian.com/ex/jira/none/rest/agile/1.0",
            )

    def _resolve_base_url(self) -> str:
        base, _ = self._resolve_base_urls()
        return base

    _DEFAULT_PROJECT_TEMPLATES = {
        "software": "com.pyxis.greenhopper.jira:gh-simplified-kanban-classic",
        "business": "com.atlassian.jira-core-project-templates:jira-core-simplified-process-control",
        "service_desk": "com.atlassian.servicedesk:simplified-it-service-desk",
    }

    def create_project(self, inp: dict) -> str:
        permission_error, key, name = self._check(self.agent_id, self.PROVIDER_ID, "jira_create_project", inp, "key", "name")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            project_type_key = inp.get("project_type_key", "business")
            lead_account_id = inp.get("lead_account_id")
            if not lead_account_id:
                try:
                    me = httpx.get(f"{self._base}/myself", headers=self._auth_headers, timeout=10)
                    me.raise_for_status()
                    lead_account_id = me.json().get("accountId")
                except Exception:
                    lead_account_id = None
            body: dict = {
                "key": key,
                "name": name,
                "projectTypeKey": project_type_key,
                "projectTemplateKey": inp.get(
                    "project_template_key", self._DEFAULT_PROJECT_TEMPLATES.get(project_type_key, self._DEFAULT_PROJECT_TEMPLATES["business"])
                ),
            }
            if lead_account_id:
                body["leadAccountId"] = lead_account_id
            if inp.get("description"):
                body["description"] = inp["description"]
            if inp.get("assignee_type"):
                body["assigneeType"] = inp["assignee_type"]
            if inp.get("url"):
                body["url"] = inp["url"]
            resp = httpx.post(f"{self._base}/project", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "key": data.get("key"), "status": "created"})
        except Exception as e:
            return _handle_error("jira_create_project", e)

    def get_project(self, inp: dict) -> str:
        permission_error, project_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_get_project", inp, "project_key")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/project/{project_key}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            p = resp.json()
            return json.dumps({
                "id": p.get("id"),
                "key": p.get("key"),
                "name": p.get("name"),
                "description": p.get("description"),
                "projectTypeKey": p.get("projectTypeKey"),
                "lead": (p.get("lead") or {}).get("displayName"),
                "url": p.get("self"),
            })
        except Exception as e:
            return _handle_error("jira_get_project", e)

    def update_project(self, inp: dict) -> str:
        permission_error, project_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_update_project", inp, "project_key")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {}
            if inp.get("name"):
                body["name"] = inp["name"]
            if inp.get("description"):
                body["description"] = inp["description"]
            if inp.get("lead_account_id"):
                body["leadAccountId"] = inp["lead_account_id"]
            if inp.get("url"):
                body["url"] = inp["url"]
            resp = httpx.put(f"{self._base}/project/{project_key}", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"key": project_key, "status": "updated"})
        except Exception as e:
            return _handle_error("jira_update_project", e)

    def delete_project(self, inp: dict) -> str:
        permission_error, project_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_delete_project", inp, "project_key")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{self._base}/project/{project_key}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"deleted": True, "key": project_key})
        except Exception as e:
            return _handle_error("jira_delete_project", e)

    def list_project_types(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "jira_list_project_types", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/project/type", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            types = [
                {"key": t.get("key"), "formattedKey": t.get("formattedKey"), "descriptionI18nKey": t.get("descriptionI18nKey")}
                for t in resp.json()
            ]
            return json.dumps({"project_types": types})
        except Exception as e:
            return _handle_error("jira_list_project_types", e)

    def assign_issue(self, inp: dict) -> str:
        permission_error, issue_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_assign_issue", inp, "issue_key")
        if permission_error: return permission_error
        account_id = inp.get("assignee_account_id", "")
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"accountId": account_id or None}
            resp = httpx.put(f"{self._base}/issue/{issue_key}/assignee", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"key": issue_key, "status": "assigned" if account_id else "unassigned"})
        except Exception as e:
            return _handle_error("jira_assign_issue", e)

    def search_users(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "jira_search_users", inp, "query")
        if permission_error: return permission_error
        try:
            params = {"query": query, "maxResults": inp.get("limit", 10)}
            resp = httpx.get(f"{self._base}/user/search", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            users = [
                {"account_id": u.get("accountId"), "display_name": u.get("displayName"), "email": u.get("emailAddress"), "active": u.get("active")}
                for u in resp.json()
            ]
            return json.dumps({"users": users})
        except Exception as e:
            return _handle_error("jira_search_users", e)

    def list_issue_types(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "jira_list_issue_types", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/issuetype", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            issue_types = [
                {"id": t.get("id"), "name": t.get("name"), "description": t.get("description"), "subtask": t.get("subtask")}
                for t in resp.json()
            ]
            return json.dumps({"issue_types": issue_types})
        except Exception as e:
            return _handle_error("jira_list_issue_types", e)

    def list_watchers(self, inp: dict) -> str:
        permission_error, issue_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_list_watchers", inp, "issue_key")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/issue/{issue_key}/watchers", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            watchers = [
                {"account_id": w.get("accountId"), "display_name": w.get("displayName")}
                for w in data.get("watchers", [])
            ]
            return json.dumps({"issue_key": issue_key, "watch_count": data.get("watchCount"), "watchers": watchers})
        except Exception as e:
            return _handle_error("jira_list_watchers", e)

    def add_watcher(self, inp: dict) -> str:
        permission_error, issue_key, account_id = self._check(self.agent_id, self.PROVIDER_ID, "jira_add_watcher", inp, "issue_key", "account_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(f"{self._base}/issue/{issue_key}/watchers", headers=headers, json=account_id, timeout=15)
            resp.raise_for_status()
            return json.dumps({"issue_key": issue_key, "status": "watcher_added"})
        except Exception as e:
            return _handle_error("jira_add_watcher", e)

    def remove_watcher(self, inp: dict) -> str:
        permission_error, issue_key, account_id = self._check(self.agent_id, self.PROVIDER_ID, "jira_remove_watcher", inp, "issue_key", "account_id")
        if permission_error: return permission_error
        try:
            params = {"accountId": account_id}
            resp = httpx.delete(f"{self._base}/issue/{issue_key}/watchers", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps({"issue_key": issue_key, "status": "watcher_removed"})
        except Exception as e:
            return _handle_error("jira_remove_watcher", e)

    def list_components(self, inp: dict) -> str:
        permission_error, project_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_list_components", inp, "project_key")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/project/{project_key}/components", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            components = [
                {"id": c.get("id"), "name": c.get("name"), "description": c.get("description")}
                for c in resp.json()
            ]
            return json.dumps({"project_key": project_key, "components": components})
        except Exception as e:
            return _handle_error("jira_list_components", e)

    def create_component(self, inp: dict) -> str:
        permission_error, project_key, name = self._check(self.agent_id, self.PROVIDER_ID, "jira_create_component", inp, "project_key", "name")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"project": project_key, "name": name}
            if inp.get("description"):
                body["description"] = inp["description"]
            if inp.get("lead_account_id"):
                body["leadAccountId"] = inp["lead_account_id"]
            resp = httpx.post(f"{self._base}/component", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "name": data.get("name"), "status": "created"})
        except Exception as e:
            return _handle_error("jira_create_component", e)

    def list_versions(self, inp: dict) -> str:
        permission_error, project_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_list_versions", inp, "project_key")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/project/{project_key}/versions", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            versions = [
                {"id": v.get("id"), "name": v.get("name"), "released": v.get("released"), "archived": v.get("archived"), "releaseDate": v.get("releaseDate")}
                for v in resp.json()
            ]
            return json.dumps({"project_key": project_key, "versions": versions})
        except Exception as e:
            return _handle_error("jira_list_versions", e)

    def create_version(self, inp: dict) -> str:
        permission_error, project_key, name = self._check(self.agent_id, self.PROVIDER_ID, "jira_create_version", inp, "project_key", "name")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"project": project_key, "name": name}
            if inp.get("description"):
                body["description"] = inp["description"]
            if inp.get("release_date"):
                body["releaseDate"] = inp["release_date"]
            if inp.get("released") is not None:
                body["released"] = inp["released"]
            resp = httpx.post(f"{self._base}/version", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "name": data.get("name"), "status": "created"})
        except Exception as e:
            return _handle_error("jira_create_version", e)

    def add_worklog(self, inp: dict) -> str:
        permission_error, issue_key, time_spent = self._check(self.agent_id, self.PROVIDER_ID, "jira_add_worklog", inp, "issue_key", "time_spent")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"timeSpent": time_spent}
            if inp.get("comment"):
                body["comment"] = {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": inp["comment"]}]}],
                }
            if inp.get("started"):
                body["started"] = inp["started"]
            resp = httpx.post(f"{self._base}/issue/{issue_key}/worklog", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "issue_key": issue_key, "status": "worklog_added"})
        except Exception as e:
            return _handle_error("jira_add_worklog", e)

    def list_worklogs(self, inp: dict) -> str:
        permission_error, issue_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_list_worklogs", inp, "issue_key")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/issue/{issue_key}/worklog", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            worklogs = [
                {
                    "id": w.get("id"),
                    "author": (w.get("author") or {}).get("displayName"),
                    "time_spent": w.get("timeSpent"),
                    "started": w.get("started"),
                }
                for w in data.get("worklogs", [])
            ]
            return json.dumps({"issue_key": issue_key, "worklogs": worklogs, "total": data.get("total")})
        except Exception as e:
            return _handle_error("jira_list_worklogs", e)

    def create_issue_link(self, inp: dict) -> str:
        permission_error, inward_issue, outward_issue, link_type = self._check(self.agent_id, self.PROVIDER_ID, "jira_create_issue_link", inp, "inward_issue_key", "outward_issue_key", "link_type")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "type": {"name": link_type},
                "inwardIssue": {"key": inward_issue},
                "outwardIssue": {"key": outward_issue},
            }
            resp = httpx.post(f"{self._base}/issueLink", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "linked", "inward_issue_key": inward_issue, "outward_issue_key": outward_issue, "link_type": link_type})
        except Exception as e:
            return _handle_error("jira_create_issue_link", e)

    def list_issue_link_types(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "jira_list_issue_link_types", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/issueLinkType", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            link_types = [
                {"id": t.get("id"), "name": t.get("name"), "inward": t.get("inward"), "outward": t.get("outward")}
                for t in resp.json().get("issueLinkTypes", [])
            ]
            return json.dumps({"link_types": link_types})
        except Exception as e:
            return _handle_error("jira_list_issue_link_types", e)

    def list_priorities(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "jira_list_priorities", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/priority", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            priorities = [{"id": p.get("id"), "name": p.get("name")} for p in resp.json()]
            return json.dumps({"priorities": priorities})
        except Exception as e:
            return _handle_error("jira_list_priorities", e)

    def list_statuses(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "jira_list_statuses", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/status", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            statuses = [
                {"id": s.get("id"), "name": s.get("name"), "category": (s.get("statusCategory") or {}).get("name")}
                for s in resp.json()
            ]
            return json.dumps({"statuses": statuses})
        except Exception as e:
            return _handle_error("jira_list_statuses", e)

    def list_projects(self, inp: dict) -> str:
        permission_allowed, permission_action = self.check_permission("jira_list_projects")
        if not permission_allowed:
            return f"Permission denied: Agent is not allowed to use Jira '{permission_action}' actions."
        try:
            params = {"maxResults": inp.get("limit", 50), "expand": "lead"}
            resp = httpx.get(f"{self._base}/project/search", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            projects = [
                {"id": p["id"], "key": p["key"], "name": p["name"], "projectTypeKey": p.get("projectTypeKey")}
                for p in data.get("values", [])
            ]
            return json.dumps({"projects": projects, "total": data.get("total")})
        except Exception as e:
            return _handle_error("jira_list_projects", e)

    def list_issues(self, inp: dict) -> str:
        permission_allowed, permission_action = self.check_permission("jira_list_issues")
        if not permission_allowed:
            return f"Permission denied: Agent is not allowed to use Jira '{permission_action}' actions."
        project_key = inp.get("project_key", "")
        jql = inp.get("jql", "")
        if not jql and project_key:
            jql = f"project = {project_key} ORDER BY created DESC"
        elif not jql:
            jql = "ORDER BY created DESC"
        try:
            body = {
                "jql": jql,
                "maxResults": inp.get("limit", 25),
                "fields": ["summary", "status", "assignee", "priority", "issuetype", "created", "updated", "labels"],
            }
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(f"{self._base}/issue/search", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            issues = [
                {
                    "id": i["id"],
                    "key": i["key"],
                    "summary": i["fields"].get("summary"),
                    "status": i["fields"].get("status", {}).get("name"),
                    "assignee": (i["fields"].get("assignee") or {}).get("displayName"),
                    "priority": (i["fields"].get("priority") or {}).get("name"),
                    "type": i["fields"].get("issuetype", {}).get("name"),
                }
                for i in data.get("issues", [])
            ]
            return json.dumps({"issues": issues, "total": data.get("total")})
        except Exception as e:
            return _handle_error("jira_list_issues", e)

    def get_issue(self, inp: dict) -> str:
        permission_error, issue_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_get_issue", inp, "issue_key")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/issue/{issue_key}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            i = resp.json()
            fields = i.get("fields", {})
            return json.dumps({
                "id": i["id"],
                "key": i["key"],
                "summary": fields.get("summary"),
                "description": (fields.get("description") or {}).get("content", [{}])[0].get("content", [{}])[0].get("text", "") if fields.get("description") else "",
                "status": fields.get("status", {}).get("name"),
                "assignee": (fields.get("assignee") or {}).get("displayName"),
                "priority": (fields.get("priority") or {}).get("name"),
                "type": fields.get("issuetype", {}).get("name"),
                "created": fields.get("created"),
                "updated": fields.get("updated"),
                "labels": fields.get("labels", []),
            })
        except Exception as e:
            return _handle_error("jira_get_issue", e)

    def create_issue(self, inp: dict) -> str:
        permission_error, project_key, summary = self._check(self.agent_id, self.PROVIDER_ID, "jira_create_issue", inp, "project_key", "summary")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            fields: dict = {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": inp.get("issue_type", "Task")},
            }
            if inp.get("description"):
                fields["description"] = {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": inp["description"]}]}],
                }
            if inp.get("assignee_account_id"):
                fields["assignee"] = {"accountId": inp["assignee_account_id"]}
            if inp.get("priority"):
                fields["priority"] = {"name": inp["priority"]}
            if inp.get("labels"):
                fields["labels"] = inp["labels"]
            resp = httpx.post(f"{self._base}/issue", headers=headers, json={"fields": fields}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "key": data["key"], "status": "created"})
        except Exception as e:
            return _handle_error("jira_create_issue", e)

    def update_issue(self, inp: dict) -> str:
        permission_error, issue_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_update_issue", inp, "issue_key")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            fields: dict = {}
            if inp.get("summary"):
                fields["summary"] = inp["summary"]
            if inp.get("priority"):
                fields["priority"] = {"name": inp["priority"]}
            if inp.get("assignee_account_id"):
                fields["assignee"] = {"accountId": inp["assignee_account_id"]}
            if inp.get("labels"):
                fields["labels"] = inp["labels"]
            resp = httpx.put(f"{self._base}/issue/{issue_key}", headers=headers, json={"fields": fields}, timeout=15)
            resp.raise_for_status()
            return json.dumps({"key": issue_key, "status": "updated"})
        except Exception as e:
            return _handle_error("jira_update_issue", e)

    def add_comment(self, inp: dict) -> str:
        permission_error, issue_key, comment = self._check(self.agent_id, self.PROVIDER_ID, "jira_add_comment", inp, "issue_key", "comment")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "body": {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}],
                }
            }
            resp = httpx.post(f"{self._base}/issue/{issue_key}/comment", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "issue_key": issue_key, "status": "comment_added"})
        except Exception as e:
            return _handle_error("jira_add_comment", e)

    def transition_issue(self, inp: dict) -> str:
        permission_error, issue_key, status_name = self._check(self.agent_id, self.PROVIDER_ID, "jira_transition_issue", inp, "issue_key", "status")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/issue/{issue_key}/transitions", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            transitions = resp.json().get("transitions", [])
            match = next((t for t in transitions if status_name.lower() in t["name"].lower()), None)
            if not match:
                available = [t["name"] for t in transitions]
                return json.dumps({"error": f"Transition '{status_name}' not found.", "available": available})
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp2 = httpx.post(f"{self._base}/issue/{issue_key}/transitions", headers=headers, json={"transition": {"id": match["id"]}}, timeout=15)
            resp2.raise_for_status()
            return json.dumps({"key": issue_key, "transitioned_to": match["name"], "status": "success"})
        except Exception as e:
            return _handle_error("jira_transition_issue", e)

    def delete_issue(self, inp: dict) -> str:
        permission_error, issue_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_delete_issue", inp, "issue_key")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{self._base}/issue/{issue_key}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"deleted": True, "key": issue_key})
        except Exception as e:
            return _handle_error("jira_delete_issue", e)

    def get_comments(self, inp: dict) -> str:
        permission_error, issue_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_get_comments", inp, "issue_key")
        if permission_error: return permission_error
        try:
            params = {"maxResults": inp.get("limit", 20)}
            resp = httpx.get(f"{self._base}/issue/{issue_key}/comment", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            comments = []
            for c in data.get("comments", []):
                # Extract plain text from Atlassian Document Format body
                body_text = ""
                body = c.get("body", {})
                if isinstance(body, dict):
                    for block in body.get("content", []):
                        for inline in block.get("content", []):
                            if inline.get("type") == "text":
                                body_text += inline.get("text", "")
                        body_text += "\n"
                    body_text = body_text.strip()
                elif isinstance(body, str):
                    body_text = body
                comments.append({
                    "id": c.get("id"),
                    "author_display_name": (c.get("author") or {}).get("displayName"),
                    "body_text": body_text,
                    "created": c.get("created"),
                })
            return json.dumps({"comments": comments, "total": data.get("total"), "issue_key": issue_key})
        except Exception as e:
            return _handle_error("jira_get_comments", e)

    def list_sprints(self, inp: dict) -> str:
        permission_error, board_id = self._check(self.agent_id, self.PROVIDER_ID, "jira_list_sprints", inp, "board_id")
        if permission_error: return permission_error
        try:
            params = {
                "state": inp.get("state", "active"),
                "maxResults": inp.get("limit", 20),
            }
            resp = httpx.get(f"{self._agile_base}/board/{board_id}/sprint", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            sprints = [
                {
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "state": s.get("state"),
                    "startDate": s.get("startDate"),
                    "endDate": s.get("endDate"),
                    "goal": s.get("goal"),
                }
                for s in data.get("values", [])
            ]
            return json.dumps({"sprints": sprints, "total": data.get("total")})
        except Exception as e:
            return _handle_error("jira_list_sprints", e)

    def list_boards(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "jira_list_boards", inp)
        if permission_error: return permission_error
        try:
            params = {"maxResults": inp.get("limit", 20)}
            if inp.get("project_key"):
                params["projectKeyOrId"] = inp["project_key"]
            resp = httpx.get(f"{self._agile_base}/board", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            boards = [
                {"id": b.get("id"), "name": b.get("name"), "type": b.get("type")}
                for b in data.get("values", [])
            ]
            return json.dumps({"boards": boards, "total": data.get("total")})
        except Exception as e:
            return _handle_error("jira_list_boards", e)

    def attach_description_update(self, inp: dict) -> str:
        permission_error, issue_key, description = self._check(self.agent_id, self.PROVIDER_ID, "jira_attach_description_update", inp, "issue_key", "description")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "fields": {
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
                    }
                }
            }
            resp = httpx.put(f"{self._base}/issue/{issue_key}", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"key": issue_key, "status": "description_updated"})
        except Exception as e:
            return _handle_error("jira_attach_description_update", e)

    def get_current_user(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "jira_get_current_user", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/myself", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            u = resp.json()
            return json.dumps({
                "account_id": u.get("accountId"),
                "display_name": u.get("displayName"),
                "email": u.get("emailAddress"),
                "active": u.get("active"),
                "timezone": u.get("timeZone"),
            })
        except Exception as e:
            return _handle_error("jira_get_current_user", e)

    def get_transitions(self, inp: dict) -> str:
        permission_error, issue_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_get_transitions", inp, "issue_key")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/issue/{issue_key}/transitions", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            transitions = [
                {"id": t.get("id"), "name": t.get("name"), "to_status": (t.get("to") or {}).get("name")}
                for t in resp.json().get("transitions", [])
            ]
            return json.dumps({"issue_key": issue_key, "transitions": transitions})
        except Exception as e:
            return _handle_error("jira_get_transitions", e)

    def update_issue_labels(self, inp: dict) -> str:
        permission_error, issue_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_update_issue_labels", inp, "issue_key")
        if permission_error: return permission_error
        add_labels = inp.get("add_labels") or []
        remove_labels = inp.get("remove_labels") or []
        if not add_labels and not remove_labels:
            return "Error: at least one of 'add_labels'/'remove_labels' is required."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            update_ops = [{"add": label} for label in add_labels] + [{"remove": label} for label in remove_labels]
            body = {"update": {"labels": update_ops}}
            resp = httpx.put(f"{self._base}/issue/{issue_key}", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"key": issue_key, "added": add_labels, "removed": remove_labels, "status": "updated"})
        except Exception as e:
            return _handle_error("jira_update_issue_labels", e)

    def get_issue_changelog(self, inp: dict) -> str:
        permission_error, issue_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_get_issue_changelog", inp, "issue_key")
        if permission_error: return permission_error
        try:
            params = {"expand": "changelog"}
            resp = httpx.get(f"{self._base}/issue/{issue_key}", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            histories = []
            for h in data.get("changelog", {}).get("histories", []):
                for item in h.get("items", []):
                    histories.append({
                        "author": (h.get("author") or {}).get("displayName"),
                        "created": h.get("created"),
                        "field": item.get("field"),
                        "from": item.get("fromString"),
                        "to": item.get("toString"),
                    })
            return json.dumps({"issue_key": issue_key, "changelog": histories})
        except Exception as e:
            return _handle_error("jira_get_issue_changelog", e)

    def get_epic_issues(self, inp: dict) -> str:
        permission_error, epic_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_get_epic_issues", inp, "epic_key")
        if permission_error: return permission_error
        try:
            params = {"maxResults": inp.get("limit", 50)}
            resp = httpx.get(f"{self._agile_base}/epic/{epic_key}/issue", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            issues = [
                {
                    "key": i["key"],
                    "summary": i.get("fields", {}).get("summary"),
                    "status": (i.get("fields", {}).get("status") or {}).get("name"),
                }
                for i in data.get("issues", [])
            ]
            return json.dumps({"epic_key": epic_key, "issues": issues, "total": data.get("total")})
        except Exception as e:
            return _handle_error("jira_get_epic_issues", e)

    def link_to_epic(self, inp: dict) -> str:
        permission_error, epic_key = self._check(self.agent_id, self.PROVIDER_ID, "jira_link_to_epic", inp, "epic_key")
        if permission_error: return permission_error
        issue_keys = inp.get("issue_keys") or []
        if not issue_keys:
            return "Error: 'issue_keys' (list) is required."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(f"{self._agile_base}/epic/{epic_key}/issue", headers=headers, json={"issues": issue_keys}, timeout=15)
            resp.raise_for_status()
            return json.dumps({"epic_key": epic_key, "issue_keys": issue_keys, "status": "linked"})
        except Exception as e:
            return _handle_error("jira_link_to_epic", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "jira_list_projects",
                    "description": "List Jira projects in the workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "description": "Max projects to return (default 50)."}},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_create_project",
                    "description": "Create a new Jira project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "Project key, 2-10 uppercase letters (e.g. 'PROJ')."},
                            "name": {"type": "string", "description": "Project name."},
                            "project_type_key": {"type": "string", "description": "Project type: 'software', 'business', or 'service_desk' (default 'business')."},
                            "project_template_key": {"type": "string", "description": "Optional Atlassian project template key. Defaults to a sensible template for the given project_type_key."},
                            "lead_account_id": {"type": "string", "description": "Atlassian account ID of the project lead. Defaults to the connected account if omitted."},
                            "description": {"type": "string", "description": "Project description."},
                            "assignee_type": {"type": "string", "description": "Default assignee type: 'PROJECT_LEAD' or 'UNASSIGNED'."},
                            "url": {"type": "string", "description": "Project URL."},
                        },
                        "required": ["key", "name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_get_project",
                    "description": "Get details of a Jira project by key or id.",
                    "parameters": {
                        "type": "object",
                        "properties": {"project_key": {"type": "string", "description": "Project key or id."}},
                        "required": ["project_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_update_project",
                    "description": "Update a Jira project's name, description, lead, or URL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_key": {"type": "string", "description": "Project key or id."},
                            "name": {"type": "string", "description": "New project name."},
                            "description": {"type": "string", "description": "New project description."},
                            "lead_account_id": {"type": "string", "description": "New project lead's account ID."},
                            "url": {"type": "string", "description": "New project URL."},
                        },
                        "required": ["project_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_delete_project",
                    "description": "Permanently delete a Jira project.",
                    "parameters": {
                        "type": "object",
                        "properties": {"project_key": {"type": "string", "description": "Project key or id to delete."}},
                        "required": ["project_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_list_project_types",
                    "description": "List available Jira project types (software, business, service_desk) for this instance.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_list_issue_types",
                    "description": "List issue types available in the Jira instance (e.g. Task, Bug, Story, Epic).",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_assign_issue",
                    "description": "Assign or unassign a Jira issue to a user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_key": {"type": "string", "description": "Issue key (e.g. 'PROJ-123')."},
                            "assignee_account_id": {"type": "string", "description": "Atlassian account ID to assign. Omit to unassign."},
                        },
                        "required": ["issue_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_search_users",
                    "description": "Search Jira users by name or email to find their account ID (e.g. for assigning issues or projects).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Name or email fragment to search for."},
                            "limit": {"type": "integer", "description": "Max users to return (default 10)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_list_watchers",
                    "description": "List watchers of a Jira issue.",
                    "parameters": {
                        "type": "object",
                        "properties": {"issue_key": {"type": "string", "description": "Issue key (e.g. 'PROJ-123')."}},
                        "required": ["issue_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_add_watcher",
                    "description": "Add a watcher to a Jira issue.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_key": {"type": "string", "description": "Issue key (e.g. 'PROJ-123')."},
                            "account_id": {"type": "string", "description": "Atlassian account ID of the user to add as watcher."},
                        },
                        "required": ["issue_key", "account_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_remove_watcher",
                    "description": "Remove a watcher from a Jira issue.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_key": {"type": "string", "description": "Issue key (e.g. 'PROJ-123')."},
                            "account_id": {"type": "string", "description": "Atlassian account ID of the watcher to remove."},
                        },
                        "required": ["issue_key", "account_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_list_components",
                    "description": "List components defined in a Jira project.",
                    "parameters": {
                        "type": "object",
                        "properties": {"project_key": {"type": "string", "description": "Project key (e.g. 'PROJ')."}},
                        "required": ["project_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_create_component",
                    "description": "Create a new component in a Jira project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_key": {"type": "string", "description": "Project key (e.g. 'PROJ')."},
                            "name": {"type": "string", "description": "Component name."},
                            "description": {"type": "string", "description": "Component description."},
                            "lead_account_id": {"type": "string", "description": "Account ID of the component lead."},
                        },
                        "required": ["project_key", "name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_list_versions",
                    "description": "List fix versions/releases defined in a Jira project.",
                    "parameters": {
                        "type": "object",
                        "properties": {"project_key": {"type": "string", "description": "Project key (e.g. 'PROJ')."}},
                        "required": ["project_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_create_version",
                    "description": "Create a new fix version/release in a Jira project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_key": {"type": "string", "description": "Project key (e.g. 'PROJ')."},
                            "name": {"type": "string", "description": "Version name (e.g. 'v1.2.0')."},
                            "description": {"type": "string", "description": "Version description."},
                            "release_date": {"type": "string", "description": "Release date (YYYY-MM-DD)."},
                            "released": {"type": "boolean", "description": "Whether the version is already released."},
                        },
                        "required": ["project_key", "name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_add_worklog",
                    "description": "Log work time against a Jira issue.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_key": {"type": "string", "description": "Issue key (e.g. 'PROJ-123')."},
                            "time_spent": {"type": "string", "description": "Time spent, Jira duration format (e.g. '2h 30m', '1d')."},
                            "comment": {"type": "string", "description": "Optional worklog comment."},
                            "started": {"type": "string", "description": "Optional ISO-8601 start timestamp for the work."},
                        },
                        "required": ["issue_key", "time_spent"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_list_worklogs",
                    "description": "List worklogs recorded on a Jira issue.",
                    "parameters": {
                        "type": "object",
                        "properties": {"issue_key": {"type": "string", "description": "Issue key (e.g. 'PROJ-123')."}},
                        "required": ["issue_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_create_issue_link",
                    "description": "Link two Jira issues together (e.g. 'blocks', 'relates to').",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inward_issue_key": {"type": "string", "description": "Key of the inward issue (e.g. issue that 'is blocked by')."},
                            "outward_issue_key": {"type": "string", "description": "Key of the outward issue (e.g. issue that 'blocks')."},
                            "link_type": {"type": "string", "description": "Link type name (e.g. 'Blocks', 'Relates', 'Duplicate'). Use jira_list_issue_link_types to see options."},
                        },
                        "required": ["inward_issue_key", "outward_issue_key", "link_type"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_list_issue_link_types",
                    "description": "List available Jira issue link types (e.g. Blocks, Relates, Duplicate).",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_list_priorities",
                    "description": "List available Jira issue priorities.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_list_statuses",
                    "description": "List available Jira issue statuses.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_list_issues",
                    "description": "List Jira issues, optionally filtered by project or JQL query.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_key": {"type": "string", "description": "Jira project key (e.g. 'PROJ')."},
                            "jql": {"type": "string", "description": "JQL query string (overrides project_key if provided)."},
                            "limit": {"type": "integer", "description": "Max issues to return (default 25)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_get_issue",
                    "description": "Get full details of a specific Jira issue.",
                    "parameters": {
                        "type": "object",
                        "properties": {"issue_key": {"type": "string", "description": "Issue key (e.g. 'PROJ-123')."}},
                        "required": ["issue_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_create_issue",
                    "description": "Create a new Jira issue (task, bug, story, etc.).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_key": {"type": "string", "description": "Project key (e.g. 'PROJ')."},
                            "summary": {"type": "string", "description": "Issue title/summary."},
                            "description": {"type": "string", "description": "Issue description."},
                            "issue_type": {"type": "string", "description": "Type: Task, Bug, Story, Epic (default Task)."},
                            "priority": {"type": "string", "description": "Priority: Highest, High, Medium, Low, Lowest."},
                            "assignee_account_id": {"type": "string", "description": "Assignee's Atlassian account ID."},
                            "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to apply."},
                        },
                        "required": ["project_key", "summary"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_update_issue",
                    "description": "Update fields of an existing Jira issue.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_key": {"type": "string", "description": "Issue key (e.g. 'PROJ-123')."},
                            "summary": {"type": "string", "description": "New summary."},
                            "priority": {"type": "string", "description": "New priority."},
                            "assignee_account_id": {"type": "string", "description": "New assignee account ID."},
                            "labels": {"type": "array", "items": {"type": "string"}, "description": "New labels."},
                        },
                        "required": ["issue_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_add_comment",
                    "description": "Add a comment to a Jira issue.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_key": {"type": "string", "description": "Issue key (e.g. 'PROJ-123')."},
                            "comment": {"type": "string", "description": "Comment text to add."},
                        },
                        "required": ["issue_key", "comment"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_transition_issue",
                    "description": "Move a Jira issue to a different status (e.g. 'In Progress', 'Done').",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_key": {"type": "string", "description": "Issue key (e.g. 'PROJ-123')."},
                            "status": {"type": "string", "description": "Target status name (e.g. 'In Progress', 'Done', 'To Do')."},
                        },
                        "required": ["issue_key", "status"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_delete_issue",
                    "description": "Permanently delete a Jira issue.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_key": {"type": "string", "description": "Issue key to delete (e.g. 'PROJ-123')."},
                        },
                        "required": ["issue_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_get_comments",
                    "description": "Get comments on a Jira issue.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_key": {"type": "string", "description": "Issue key (e.g. 'PROJ-123')."},
                            "limit": {"type": "integer", "description": "Max comments to return (default 20)."},
                        },
                        "required": ["issue_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_list_boards",
                    "description": "List Jira Agile boards, optionally filtered by project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max boards to return (default 20)."},
                            "project_key": {"type": "string", "description": "Optional project key to filter boards."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_list_sprints",
                    "description": "List sprints for a Jira board.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "board_id": {"type": "string", "description": "Board ID (from jira_list_boards)."},
                            "state": {"type": "string", "description": "Sprint state: active, future, or closed (default active)."},
                            "limit": {"type": "integer", "description": "Max sprints to return (default 20)."},
                        },
                        "required": ["board_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_attach_description_update",
                    "description": "Update only the description of a Jira issue.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_key": {"type": "string", "description": "Issue key (e.g. 'PROJ-123')."},
                            "description": {"type": "string", "description": "New description text for the issue."},
                        },
                        "required": ["issue_key", "description"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_get_current_user",
                    "description": "Get the profile of the currently authenticated Jira user (their account ID, name, email).",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_get_transitions",
                    "description": "List the workflow transitions currently available for a Jira issue (e.g. what statuses it can move to next).",
                    "parameters": {
                        "type": "object",
                        "properties": {"issue_key": {"type": "string", "description": "Issue key (e.g. 'PROJ-123')."}},
                        "required": ["issue_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_update_issue_labels",
                    "description": "Add and/or remove labels on a Jira issue without replacing the full label set.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_key": {"type": "string", "description": "Issue key (e.g. 'PROJ-123')."},
                            "add_labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to add."},
                            "remove_labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to remove."},
                        },
                        "required": ["issue_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_get_issue_changelog",
                    "description": "Get the change history (field changes over time) of a Jira issue.",
                    "parameters": {
                        "type": "object",
                        "properties": {"issue_key": {"type": "string", "description": "Issue key (e.g. 'PROJ-123')."}},
                        "required": ["issue_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_get_epic_issues",
                    "description": "List all issues (stories, tasks, bugs) that belong to a Jira epic.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "epic_key": {"type": "string", "description": "Epic issue key (e.g. 'PROJ-100')."},
                            "limit": {"type": "integer", "description": "Max issues to return (default 50)."},
                        },
                        "required": ["epic_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_link_to_epic",
                    "description": "Add one or more existing Jira issues to an epic.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "epic_key": {"type": "string", "description": "Epic issue key (e.g. 'PROJ-100')."},
                            "issue_keys": {"type": "array", "items": {"type": "string"}, "description": "Issue keys to add to the epic."},
                        },
                        "required": ["epic_key", "issue_keys"],
                    },
                },
            },
        ]
        callables = {
            "jira_get_current_user": self.get_current_user,
            "jira_get_transitions": self.get_transitions,
            "jira_update_issue_labels": self.update_issue_labels,
            "jira_get_issue_changelog": self.get_issue_changelog,
            "jira_get_epic_issues": self.get_epic_issues,
            "jira_link_to_epic": self.link_to_epic,
            "jira_list_watchers": self.list_watchers,
            "jira_add_watcher": self.add_watcher,
            "jira_remove_watcher": self.remove_watcher,
            "jira_list_components": self.list_components,
            "jira_create_component": self.create_component,
            "jira_list_versions": self.list_versions,
            "jira_create_version": self.create_version,
            "jira_add_worklog": self.add_worklog,
            "jira_list_worklogs": self.list_worklogs,
            "jira_create_issue_link": self.create_issue_link,
            "jira_list_issue_link_types": self.list_issue_link_types,
            "jira_list_priorities": self.list_priorities,
            "jira_list_statuses": self.list_statuses,
            "jira_create_project": self.create_project,
            "jira_get_project": self.get_project,
            "jira_update_project": self.update_project,
            "jira_delete_project": self.delete_project,
            "jira_list_project_types": self.list_project_types,
            "jira_list_issue_types": self.list_issue_types,
            "jira_assign_issue": self.assign_issue,
            "jira_search_users": self.search_users,
            "jira_list_projects": self.list_projects,
            "jira_list_issues": self.list_issues,
            "jira_get_issue": self.get_issue,
            "jira_create_issue": self.create_issue,
            "jira_update_issue": self.update_issue,
            "jira_add_comment": self.add_comment,
            "jira_transition_issue": self.transition_issue,
            "jira_delete_issue": self.delete_issue,
            "jira_get_comments": self.get_comments,
            "jira_list_boards": self.list_boards,
            "jira_list_sprints": self.list_sprints,
            "jira_attach_description_update": self.attach_description_update,
        }
        return tools, callables

import json
import httpx
from ai.connectors.base import BaseConnector

_BASE = "https://api.linear.app/graphql"


def _handle_error(tool_name, e):
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


def _gql(token: str, query: str, variables: dict = None) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    r = httpx.post(_BASE, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


class LinearConnector(BaseConnector):
    """Linear connector for issues, teams, projects, cycles, users, and labels via GraphQL."""

    PROVIDER_ID = "linear"

    def linear_list_issues(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "linear_list_issues", inp)
        if permission_error: return permission_error
        team_id = inp.get("team_id")
        state = inp.get("state")
        assignee_id = inp.get("assignee_id")
        limit = int(inp.get("limit", 25))
        cursor = inp.get("cursor")
        filter_parts = []
        if team_id:
            filter_parts.append(f'team: {{id: {{eq: "{team_id}"}}}}')
        if state:
            filter_parts.append(f'state: {{name: {{eq: "{state}"}}}}')
        if assignee_id:
            filter_parts.append(f'assignee: {{id: {{eq: "{assignee_id}"}}}}')
        filter_str = "{" + ", ".join(filter_parts) + "}" if filter_parts else ""
        after_str = f', after: "{cursor}"' if cursor else ""
        query = f"""
        query {{
          issues(first: {limit}{after_str}{", filter: " + filter_str if filter_str else ""}) {{
            pageInfo {{ hasNextPage endCursor }}
            nodes {{
              id title state {{ name }} priority assignee {{ name }} team {{ name }}
              createdAt updatedAt url
            }}
          }}
        }}
        """
        try:
            data = _gql(self._token, query)
            issues = data.get("data", {}).get("issues", {})
            return json.dumps({"issues": issues.get("nodes", []), "pageInfo": issues.get("pageInfo", {})})
        except Exception as e:
            return _handle_error("linear_list_issues", e)

    def linear_get_issue(self, inp: dict) -> str:
        permission_error, issue_id = self._check(self.agent_id, self.PROVIDER_ID, "linear_get_issue", inp, "issue_id")
        if permission_error: return permission_error
        query = f"""
        query {{
          issue(id: "{issue_id}") {{
            id title description state {{ name }} priority
            assignee {{ id name email }}
            team {{ id name }}
            labels {{ nodes {{ id name color }} }}
            comments {{ nodes {{ id body createdAt user {{ name }} }} }}
            createdAt updatedAt url
          }}
        }}
        """
        try:
            data = _gql(self._token, query)
            issue = data.get("data", {}).get("issue")
            if not issue:
                return f"Issue {issue_id} not found."
            return json.dumps(issue)
        except Exception as e:
            return _handle_error("linear_get_issue", e)

    def linear_list_teams(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "linear_list_teams", inp)
        if permission_error: return permission_error
        query = """
        query {
          teams {
            nodes {
              id name key description
              members { nodes { id name email } }
            }
          }
        }
        """
        try:
            data = _gql(self._token, query)
            teams = data.get("data", {}).get("teams", {}).get("nodes", [])
            return json.dumps({"teams": teams})
        except Exception as e:
            return _handle_error("linear_list_teams", e)

    def linear_list_projects(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "linear_list_projects", inp)
        if permission_error: return permission_error
        team_id = inp.get("team_id")
        limit = int(inp.get("limit", 20))
        filter_str = f', filter: {{teams: {{id: {{eq: "{team_id}"}}}}}}' if team_id else ""
        query = f"""
        query {{
          projects(first: {limit}{filter_str}) {{
            nodes {{
              id name description state progress
              startDate targetDate
              teams {{ nodes {{ id name }} }}
            }}
          }}
        }}
        """
        try:
            data = _gql(self._token, query)
            projects = data.get("data", {}).get("projects", {}).get("nodes", [])
            return json.dumps({"projects": projects})
        except Exception as e:
            return _handle_error("linear_list_projects", e)

    def linear_list_users(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "linear_list_users", inp)
        if permission_error: return permission_error
        query = """
        query {
          users {
            nodes {
              id name email displayName avatarUrl active
            }
          }
        }
        """
        try:
            data = _gql(self._token, query)
            users = data.get("data", {}).get("users", {}).get("nodes", [])
            return json.dumps({"users": users})
        except Exception as e:
            return _handle_error("linear_list_users", e)

    def linear_list_cycles(self, inp: dict) -> str:
        permission_error, team_id = self._check(self.agent_id, self.PROVIDER_ID, "linear_list_cycles", inp, "team_id")
        if permission_error: return permission_error
        query = f"""
        query {{
          cycles(filter: {{team: {{id: {{eq: "{team_id}"}}}}}}) {{
            nodes {{
              id number name startsAt endsAt
              completedAt progress
              team {{ id name }}
            }}
          }}
        }}
        """
        try:
            data = _gql(self._token, query)
            cycles = data.get("data", {}).get("cycles", {}).get("nodes", [])
            return json.dumps({"cycles": cycles})
        except Exception as e:
            return _handle_error("linear_list_cycles", e)

    def linear_list_labels(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "linear_list_labels", inp)
        if permission_error: return permission_error
        team_id = inp.get("team_id")
        filter_str = f', filter: {{team: {{id: {{eq: "{team_id}"}}}}}}' if team_id else ""
        query = f"""
        query {{
          issueLabels(first: 50{filter_str}) {{
            nodes {{
              id name color
              team {{ id name }}
            }}
          }}
        }}
        """
        try:
            data = _gql(self._token, query)
            labels = data.get("data", {}).get("issueLabels", {}).get("nodes", [])
            return json.dumps({"labels": labels})
        except Exception as e:
            return _handle_error("linear_list_labels", e)

    def linear_search_issues(self, inp: dict) -> str:
        permission_error, query_text = self._check(self.agent_id, self.PROVIDER_ID, "linear_search_issues", inp, "query")
        if permission_error: return permission_error
        limit = int(inp.get("limit", 20))
        query = f"""
        query {{
          issueSearch(query: "{query_text}", first: {limit}) {{
            nodes {{
              id title state {{ name }} priority assignee {{ name }}
              team {{ name }} createdAt url
            }}
          }}
        }}
        """
        try:
            data = _gql(self._token, query)
            issues = data.get("data", {}).get("issueSearch", {}).get("nodes", [])
            return json.dumps({"issues": issues})
        except Exception as e:
            return _handle_error("linear_search_issues", e)

    def linear_create_issue(self, inp: dict) -> str:
        permission_error, team_id, title = self._check(self.agent_id, self.PROVIDER_ID, "linear_create_issue", inp, "team_id", "title")
        if permission_error: return permission_error
        issue_input: dict = {"teamId": team_id, "title": title}
        if inp.get("description") is not None:
            issue_input["description"] = inp["description"]
        if inp.get("priority") is not None:
            issue_input["priority"] = int(inp["priority"])
        if inp.get("label_ids") is not None:
            issue_input["labelIds"] = inp["label_ids"]
        if inp.get("assignee_id") is not None:
            issue_input["assigneeId"] = inp["assignee_id"]
        query = """
        mutation CreateIssue($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success
            issue { id identifier title url }
          }
        }
        """
        try:
            data = _gql(self._token, query, {"input": issue_input})
            result = data.get("data", {}).get("issueCreate", {})
            return json.dumps(result)
        except Exception as e:
            return _handle_error("linear_create_issue", e)

    def linear_update_issue(self, inp: dict) -> str:
        permission_error, issue_id = self._check(self.agent_id, self.PROVIDER_ID, "linear_update_issue", inp, "id")
        if permission_error: return permission_error
        issue_input: dict = {}
        if inp.get("title") is not None:
            issue_input["title"] = inp["title"]
        if inp.get("description") is not None:
            issue_input["description"] = inp["description"]
        if inp.get("state_id") is not None:
            issue_input["stateId"] = inp["state_id"]
        if inp.get("priority") is not None:
            issue_input["priority"] = int(inp["priority"])
        if inp.get("assignee_id") is not None:
            issue_input["assigneeId"] = inp["assignee_id"]
        query = """
        mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) {
            success
            issue { id identifier title state { name } }
          }
        }
        """
        try:
            data = _gql(self._token, query, {"id": issue_id, "input": issue_input})
            result = data.get("data", {}).get("issueUpdate", {})
            return json.dumps(result)
        except Exception as e:
            return _handle_error("linear_update_issue", e)

    def linear_add_comment(self, inp: dict) -> str:
        permission_error, issue_id, body = self._check(self.agent_id, self.PROVIDER_ID, "linear_add_comment", inp, "issue_id", "body")
        if permission_error: return permission_error
        query = """
        mutation AddComment($input: CommentCreateInput!) {
          commentCreate(input: $input) {
            success
            comment { id body }
          }
        }
        """
        try:
            data = _gql(self._token, query, {"input": {"issueId": issue_id, "body": body}})
            result = data.get("data", {}).get("commentCreate", {})
            return json.dumps(result)
        except Exception as e:
            return _handle_error("linear_add_comment", e)

    def linear_list_issue_states(self, inp: dict) -> str:
        permission_error, team_id = self._check(self.agent_id, self.PROVIDER_ID, "linear_list_issue_states", inp, "team_id")
        if permission_error: return permission_error
        query = """
        query GetTeamStates($teamId: String!) {
          team(id: $teamId) {
            states {
              nodes { id name type }
            }
          }
        }
        """
        try:
            data = _gql(self._token, query, {"teamId": team_id})
            team = data.get("data", {}).get("team")
            if not team:
                return f"Team {team_id} not found."
            states = team.get("states", {}).get("nodes", [])
            return json.dumps({"states": states})
        except Exception as e:
            return _handle_error("linear_list_issue_states", e)

    def linear_assign_issue(self, inp: dict) -> str:
        permission_error, issue_id, assignee_id = self._check(self.agent_id, self.PROVIDER_ID, "linear_assign_issue", inp, "id", "assignee_id")
        if permission_error: return permission_error
        query = """
        mutation AssignIssue($id: String!, $input: IssueUpdateInput!) {
          issueUpdate(id: $id, input: $input) {
            success
            issue { id assignee { name } }
          }
        }
        """
        try:
            data = _gql(self._token, query, {"id": issue_id, "input": {"assigneeId": assignee_id}})
            result = data.get("data", {}).get("issueUpdate", {})
            return json.dumps(result)
        except Exception as e:
            return _handle_error("linear_assign_issue", e)

    def linear_delete_issue(self, inp: dict) -> str:
        permission_error, issue_id = self._check(self.agent_id, self.PROVIDER_ID, "linear_delete_issue", inp, "id")
        if permission_error: return permission_error
        query = """
        mutation DeleteIssue($id: String!) {
          issueDelete(id: $id) {
            success
          }
        }
        """
        try:
            data = _gql(self._token, query, {"id": issue_id})
            result = data.get("data", {}).get("issueDelete", {})
            return json.dumps(result)
        except Exception as e:
            return _handle_error("linear_delete_issue", e)

    def linear_create_project(self, inp: dict) -> str:
        permission_error, name, team_ids = self._check(self.agent_id, self.PROVIDER_ID, "linear_create_project", inp, "name", "team_ids")
        if permission_error: return permission_error
        project_input: dict = {"name": name, "teamIds": team_ids}
        if inp.get("description") is not None:
            project_input["description"] = inp["description"]
        query = """
        mutation CreateProject($input: ProjectCreateInput!) {
          projectCreate(input: $input) {
            success
            project { id name url }
          }
        }
        """
        try:
            data = _gql(self._token, query, {"input": project_input})
            result = data.get("data", {}).get("projectCreate", {})
            return json.dumps(result)
        except Exception as e:
            return _handle_error("linear_create_project", e)

    def linear_create_label(self, inp: dict) -> str:
        permission_error, name, team_id = self._check(self.agent_id, self.PROVIDER_ID, "linear_create_label", inp, "name", "team_id")
        if permission_error: return permission_error
        label_input: dict = {"name": name, "teamId": team_id}
        if inp.get("color"):
            label_input["color"] = inp["color"]
        query = """
        mutation CreateLabel($input: IssueLabelCreateInput!) {
          issueLabelCreate(input: $input) {
            success
            issueLabel { id name color }
          }
        }
        """
        try:
            data = _gql(self._token, query, {"input": label_input})
            result = data.get("data", {}).get("issueLabelCreate", {})
            return json.dumps(result)
        except Exception as e:
            return _handle_error("linear_create_label", e)

    def as_tools(self):
        tool_defs = [
            {
                "type": "function",
                "function": {
                    "name": "linear_list_issues",
                    "description": "Fetch paginated issues from Linear with optional filters by team, state, or assignee.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "Filter by team ID."},
                            "state": {"type": "string", "description": "Filter by state name (e.g. 'In Progress', 'Done')."},
                            "assignee_id": {"type": "string", "description": "Filter by assignee user ID."},
                            "limit": {"type": "integer", "description": "Number of issues to return (default 25)."},
                            "cursor": {"type": "string", "description": "Pagination cursor (endCursor from previous response)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linear_get_issue",
                    "description": "Fetch a single Linear issue by ID including description, comments, and labels.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_id": {"type": "string", "description": "The Linear issue ID."},
                        },
                        "required": ["issue_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linear_list_teams",
                    "description": "List all teams in the Linear workspace with their members.",
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
                    "name": "linear_list_projects",
                    "description": "List projects in Linear with state, progress, and dates.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "Filter projects by team ID."},
                            "limit": {"type": "integer", "description": "Number of projects to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linear_list_users",
                    "description": "List all members in the Linear workspace.",
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
                    "name": "linear_list_cycles",
                    "description": "List sprints/cycles for a specific team in Linear.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The team ID to list cycles for."},
                        },
                        "required": ["team_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linear_list_labels",
                    "description": "List available issue labels in Linear, optionally filtered by team.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "Filter labels by team ID."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linear_search_issues",
                    "description": "Search Linear issues by keyword query.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query text."},
                            "limit": {"type": "integer", "description": "Number of results to return (default 20)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linear_create_issue",
                    "description": "Create a new issue in Linear for a given team.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The team ID to create the issue in."},
                            "title": {"type": "string", "description": "Issue title."},
                            "description": {"type": "string", "description": "Issue description (markdown supported)."},
                            "priority": {
                                "type": "integer",
                                "description": "Priority: 0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low.",
                            },
                            "label_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of label IDs to attach.",
                            },
                            "assignee_id": {"type": "string", "description": "User ID to assign the issue to."},
                        },
                        "required": ["team_id", "title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linear_update_issue",
                    "description": "Update an existing Linear issue. All fields except id are optional.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "The Linear issue ID to update."},
                            "title": {"type": "string", "description": "New title."},
                            "description": {"type": "string", "description": "New description (markdown supported)."},
                            "state_id": {"type": "string", "description": "Workflow state ID to transition the issue to."},
                            "priority": {
                                "type": "integer",
                                "description": "Priority: 0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low.",
                            },
                            "assignee_id": {"type": "string", "description": "User ID to assign the issue to."},
                        },
                        "required": ["id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linear_add_comment",
                    "description": "Add a comment to a Linear issue.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_id": {"type": "string", "description": "The Linear issue ID to comment on."},
                            "body": {"type": "string", "description": "Comment body (markdown supported)."},
                        },
                        "required": ["issue_id", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linear_list_issue_states",
                    "description": "List workflow states (e.g. Backlog, In Progress, Done) available for a team in Linear.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The team ID to list states for."},
                        },
                        "required": ["team_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linear_assign_issue",
                    "description": "Assign a Linear issue to a specific user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "The Linear issue ID to assign."},
                            "assignee_id": {"type": "string", "description": "The user ID to assign the issue to."},
                        },
                        "required": ["id", "assignee_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linear_delete_issue",
                    "description": "Delete (trash) a Linear issue. It can be restored within 30 days.",
                    "parameters": {
                        "type": "object",
                        "properties": {"id": {"type": "string", "description": "The Linear issue ID to delete."}},
                        "required": ["id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linear_create_project",
                    "description": "Create a new project in Linear for one or more teams.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Project name."},
                            "team_ids": {"type": "array", "items": {"type": "string"}, "description": "IDs of the teams this project belongs to."},
                            "description": {"type": "string", "description": "Optional project description."},
                        },
                        "required": ["name", "team_ids"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linear_create_label",
                    "description": "Create a new issue label for a Linear team.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Label name."},
                            "team_id": {"type": "string", "description": "Team ID the label belongs to."},
                            "color": {"type": "string", "description": "Optional hex color code (e.g. '#FF0000')."},
                        },
                        "required": ["name", "team_id"],
                    },
                },
            },
        ]
        callables = {
            "linear_list_issues": self.linear_list_issues,
            "linear_get_issue": self.linear_get_issue,
            "linear_list_teams": self.linear_list_teams,
            "linear_list_projects": self.linear_list_projects,
            "linear_list_users": self.linear_list_users,
            "linear_list_cycles": self.linear_list_cycles,
            "linear_list_labels": self.linear_list_labels,
            "linear_search_issues": self.linear_search_issues,
            "linear_create_issue": self.linear_create_issue,
            "linear_update_issue": self.linear_update_issue,
            "linear_add_comment": self.linear_add_comment,
            "linear_list_issue_states": self.linear_list_issue_states,
            "linear_assign_issue": self.linear_assign_issue,
            "linear_delete_issue": self.linear_delete_issue,
            "linear_create_project": self.linear_create_project,
            "linear_create_label": self.linear_create_label,
        }
        return tool_defs, callables

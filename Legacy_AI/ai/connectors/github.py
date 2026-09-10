import base64
import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.github.com"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected GitHub account lacks permission "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their GitHub connector."
            )
        if e.response.status_code == 404:
            return f"Not found in {tool_name}: the requested resource does not exist."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class GitHubConnector(BaseConnector):

    PROVIDER_ID = "github"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id=agent_id)
        self._token = access_token

    @property
    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

    @_auth_headers.setter
    def _auth_headers(self, value: dict) -> None:
        pass

    def list_repos(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "github_list_repos", inp)
        if permission_error: return permission_error
        try:
            params = {
                "sort": inp.get("sort", "updated"),
                "per_page": inp.get("limit", 30),
                "visibility": inp.get("visibility", "all"),
            }
            resp = httpx.get(f"{_BASE}/user/repos", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            repos = [
                {
                    "id": r["id"],
                    "full_name": r["full_name"],
                    "description": r.get("description"),
                    "private": r.get("private"),
                    "language": r.get("language"),
                    "stars": r.get("stargazers_count"),
                    "updated_at": r.get("updated_at"),
                    "default_branch": r.get("default_branch"),
                }
                for r in resp.json()
            ]
            return json.dumps({"repos": repos, "count": len(repos)})
        except Exception as e:
            return _handle_error("github_list_repos", e)

    def get_repo(self, inp: dict) -> str:
        permission_error, owner, repo = self._check(self.agent_id, self.PROVIDER_ID, "github_get_repo", inp, "owner", "repo")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/repos/{owner}/{repo}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            r = resp.json()
            return json.dumps({
                "full_name": r["full_name"],
                "description": r.get("description"),
                "private": r.get("private"),
                "language": r.get("language"),
                "stars": r.get("stargazers_count"),
                "forks": r.get("forks_count"),
                "open_issues": r.get("open_issues_count"),
                "default_branch": r.get("default_branch"),
                "created_at": r.get("created_at"),
                "updated_at": r.get("updated_at"),
                "topics": r.get("topics", []),
            })
        except Exception as e:
            return _handle_error("github_get_repo", e)

    def list_issues(self, inp: dict) -> str:
        permission_error, owner, repo = self._check(self.agent_id, self.PROVIDER_ID, "github_list_issues", inp, "owner", "repo")
        if permission_error: return permission_error
        try:
            params = {
                "state": inp.get("state", "open"),
                "per_page": inp.get("limit", 25),
                "sort": inp.get("sort", "updated"),
            }
            if inp.get("labels"):
                params["labels"] = inp["labels"]
            if inp.get("assignee"):
                params["assignee"] = inp["assignee"]
            resp = httpx.get(f"{_BASE}/repos/{owner}/{repo}/issues", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            issues = [
                {
                    "number": i["number"],
                    "title": i["title"],
                    "state": i["state"],
                    "user": i.get("user", {}).get("login"),
                    "assignee": (i.get("assignee") or {}).get("login"),
                    "labels": [l["name"] for l in i.get("labels", [])],
                    "created_at": i.get("created_at"),
                    "updated_at": i.get("updated_at"),
                    "is_pr": "pull_request" in i,
                }
                for i in resp.json()
                if "pull_request" not in i
            ]
            return json.dumps({"issues": issues, "count": len(issues)})
        except Exception as e:
            return _handle_error("github_list_issues", e)

    def create_issue(self, inp: dict) -> str:
        permission_error, owner, repo, title = self._check(self.agent_id, self.PROVIDER_ID, "github_create_issue", inp, "owner", "repo", "title")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"title": title}
            if inp.get("body"):
                body["body"] = inp["body"]
            if inp.get("labels"):
                body["labels"] = inp["labels"]
            if inp.get("assignees"):
                body["assignees"] = inp["assignees"]
            resp = httpx.post(f"{_BASE}/repos/{owner}/{repo}/issues", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"number": data["number"], "title": data["title"], "url": data["html_url"], "status": "created"})
        except Exception as e:
            return _handle_error("github_create_issue", e)

    def list_pull_requests(self, inp: dict) -> str:
        permission_error, owner, repo = self._check(self.agent_id, self.PROVIDER_ID, "github_list_pull_requests", inp, "owner", "repo")
        if permission_error: return permission_error
        try:
            params = {"state": inp.get("state", "open"), "per_page": inp.get("limit", 20), "sort": inp.get("sort", "updated")}
            resp = httpx.get(f"{_BASE}/repos/{owner}/{repo}/pulls", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            prs = [
                {
                    "number": p["number"],
                    "title": p["title"],
                    "state": p["state"],
                    "user": p.get("user", {}).get("login"),
                    "base": p.get("base", {}).get("ref"),
                    "head": p.get("head", {}).get("ref"),
                    "draft": p.get("draft"),
                    "created_at": p.get("created_at"),
                    "updated_at": p.get("updated_at"),
                }
                for p in resp.json()
            ]
            return json.dumps({"pull_requests": prs, "count": len(prs)})
        except Exception as e:
            return _handle_error("github_list_pull_requests", e)

    def get_pull_request(self, inp: dict) -> str:
        permission_error, owner, repo, pr_number = self._check(self.agent_id, self.PROVIDER_ID, "github_get_pull_request", inp, "owner", "repo", "pr_number")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/repos/{owner}/{repo}/pulls/{pr_number}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            p = resp.json()
            return json.dumps({
                "number": p["number"],
                "title": p["title"],
                "state": p["state"],
                "body": p.get("body", ""),
                "user": p.get("user", {}).get("login"),
                "base": p.get("base", {}).get("ref"),
                "head": p.get("head", {}).get("ref"),
                "mergeable": p.get("mergeable"),
                "additions": p.get("additions"),
                "deletions": p.get("deletions"),
                "changed_files": p.get("changed_files"),
                "url": p.get("html_url"),
            })
        except Exception as e:
            return _handle_error("github_get_pull_request", e)

    def search_code(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "github_search_code", inp, "query")
        if permission_error: return permission_error
        try:
            params = {"q": query, "per_page": inp.get("limit", 10)}
            resp = httpx.get(f"{_BASE}/search/code", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            items = [
                {
                    "name": i["name"],
                    "path": i["path"],
                    "repository": i.get("repository", {}).get("full_name"),
                    "url": i.get("html_url"),
                }
                for i in data.get("items", [])
            ]
            return json.dumps({"results": items, "total_count": data.get("total_count")})
        except Exception as e:
            return _handle_error("github_search_code", e)

    def get_user(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "github_get_user", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/user", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            u = resp.json()
            return json.dumps({
                "login": u["login"],
                "name": u.get("name"),
                "email": u.get("email"),
                "public_repos": u.get("public_repos"),
                "followers": u.get("followers"),
                "following": u.get("following"),
            })
        except Exception as e:
            return _handle_error("github_get_user", e)

    def update_issue(self, inp: dict) -> str:
        permission_error, owner, repo, issue_number = self._check(self.agent_id, self.PROVIDER_ID, "github_update_issue", inp, "owner", "repo", "issue_number")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {}
            if inp.get("state") is not None:
                body["state"] = inp["state"]
            if inp.get("title") is not None:
                body["title"] = inp["title"]
            if inp.get("body") is not None:
                body["body"] = inp["body"]
            if inp.get("labels") is not None:
                body["labels"] = inp["labels"]
            if inp.get("assignees") is not None:
                body["assignees"] = inp["assignees"]
            resp = httpx.patch(f"{_BASE}/repos/{owner}/{repo}/issues/{issue_number}", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"number": data["number"], "title": data["title"], "state": data["state"], "url": data["html_url"], "status": "updated"})
        except Exception as e:
            return _handle_error("github_update_issue", e)

    def create_pull_request(self, inp: dict) -> str:
        permission_error, owner, repo, title, head, base = self._check(self.agent_id, self.PROVIDER_ID, "github_create_pull_request", inp, "owner", "repo", "title", "head", "base")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"title": title, "head": head, "base": base}
            if inp.get("body") is not None:
                body["body"] = inp["body"]
            if inp.get("draft") is not None:
                body["draft"] = inp["draft"]
            resp = httpx.post(f"{_BASE}/repos/{owner}/{repo}/pulls", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"number": data["number"], "title": data["title"], "state": data["state"], "draft": data.get("draft"), "url": data["html_url"], "status": "created"})
        except Exception as e:
            return _handle_error("github_create_pull_request", e)

    def merge_pull_request(self, inp: dict) -> str:
        permission_error, owner, repo, pull_number = self._check(self.agent_id, self.PROVIDER_ID, "github_merge_pull_request", inp, "owner", "repo", "pull_number")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"merge_method": inp.get("merge_method", "merge")}
            if inp.get("commit_message") is not None:
                body["commit_message"] = inp["commit_message"]
            resp = httpx.put(f"{_BASE}/repos/{owner}/{repo}/pulls/{pull_number}/merge", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"sha": data.get("sha"), "merged": data.get("merged"), "message": data.get("message"), "status": "merged"})
        except Exception as e:
            return _handle_error("github_merge_pull_request", e)

    def list_commits(self, inp: dict) -> str:
        permission_error, owner, repo = self._check(self.agent_id, self.PROVIDER_ID, "github_list_commits", inp, "owner", "repo")
        if permission_error: return permission_error
        try:
            params: dict = {"per_page": inp.get("limit", 20)}
            if inp.get("sha"):
                params["sha"] = inp["sha"]
            if inp.get("path"):
                params["path"] = inp["path"]
            resp = httpx.get(f"{_BASE}/repos/{owner}/{repo}/commits", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            commits = [
                {
                    "sha": c["sha"],
                    "message": c.get("commit", {}).get("message", "").splitlines()[0],
                    "author": c.get("commit", {}).get("author", {}).get("name"),
                    "date": c.get("commit", {}).get("author", {}).get("date"),
                    "url": c.get("html_url"),
                }
                for c in resp.json()
            ]
            return json.dumps({"commits": commits, "count": len(commits)})
        except Exception as e:
            return _handle_error("github_list_commits", e)

    def get_file_contents(self, inp: dict) -> str:
        permission_error, owner, repo, path = self._check(self.agent_id, self.PROVIDER_ID, "github_get_file_contents", inp, "owner", "repo", "path")
        if permission_error: return permission_error
        try:
            params: dict = {}
            if inp.get("ref"):
                params["ref"] = inp["ref"]
            resp = httpx.get(f"{_BASE}/repos/{owner}/{repo}/contents/{path}", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            content_decoded = ""
            if data.get("encoding") == "base64" and data.get("content"):
                content_decoded = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            return json.dumps({
                "name": data.get("name"),
                "path": data.get("path"),
                "sha": data.get("sha"),
                "size": data.get("size"),
                "type": data.get("type"),
                "content": content_decoded,
                "url": data.get("html_url"),
            })
        except Exception as e:
            return _handle_error("github_get_file_contents", e)

    def create_or_update_file(self, inp: dict) -> str:
        permission_error, owner, repo, path, message, content = self._check(self.agent_id, self.PROVIDER_ID, "github_create_or_update_file", inp, "owner", "repo", "path", "message", "content")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"message": message, "content": content}
            if inp.get("sha") is not None:
                body["sha"] = inp["sha"]
            if inp.get("branch") is not None:
                body["branch"] = inp["branch"]
            resp = httpx.put(f"{_BASE}/repos/{owner}/{repo}/contents/{path}", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            action_status = "updated" if inp.get("sha") else "created"
            return json.dumps({
                "path": data.get("content", {}).get("path"),
                "sha": data.get("content", {}).get("sha"),
                "url": data.get("content", {}).get("html_url"),
                "commit_sha": data.get("commit", {}).get("sha"),
                "status": action_status,
            })
        except Exception as e:
            return _handle_error("github_create_or_update_file", e)

    def list_workflow_runs(self, inp: dict) -> str:
        permission_error, owner, repo = self._check(self.agent_id, self.PROVIDER_ID, "github_list_workflow_runs", inp, "owner", "repo")
        if permission_error: return permission_error
        try:
            params: dict = {"per_page": inp.get("limit", 10)}
            if inp.get("status"):
                params["status"] = inp["status"]
            if inp.get("branch"):
                params["branch"] = inp["branch"]
            resp = httpx.get(f"{_BASE}/repos/{owner}/{repo}/actions/runs", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            runs = [
                {
                    "id": r["id"],
                    "name": r.get("name"),
                    "status": r.get("status"),
                    "conclusion": r.get("conclusion"),
                    "branch": r.get("head_branch"),
                    "event": r.get("event"),
                    "created_at": r.get("created_at"),
                    "updated_at": r.get("updated_at"),
                    "url": r.get("html_url"),
                }
                for r in data.get("workflow_runs", [])
            ]
            return json.dumps({"workflow_runs": runs, "count": len(runs), "total_count": data.get("total_count")})
        except Exception as e:
            return _handle_error("github_list_workflow_runs", e)

    def add_issue_comment(self, inp: dict) -> str:
        permission_error, owner, repo, issue_number, body_text = self._check(self.agent_id, self.PROVIDER_ID, "github_add_issue_comment", inp, "owner", "repo", "issue_number", "body")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(f"{_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments", headers=headers, json={"body": body_text}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "url": data["html_url"], "status": "created"})
        except Exception as e:
            return _handle_error("github_add_issue_comment", e)

    def list_releases(self, inp: dict) -> str:
        permission_error, owner, repo = self._check(self.agent_id, self.PROVIDER_ID, "github_list_releases", inp, "owner", "repo")
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("limit", 10)}
            resp = httpx.get(f"{_BASE}/repos/{owner}/{repo}/releases", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            releases = [
                {
                    "id": r["id"],
                    "tag_name": r.get("tag_name"),
                    "name": r.get("name"),
                    "draft": r.get("draft"),
                    "prerelease": r.get("prerelease"),
                    "created_at": r.get("created_at"),
                    "published_at": r.get("published_at"),
                    "url": r.get("html_url"),
                    "body": r.get("body", ""),
                }
                for r in resp.json()
            ]
            return json.dumps({"releases": releases, "count": len(releases)})
        except Exception as e:
            return _handle_error("github_list_releases", e)

    def list_branches(self, inp: dict) -> str:
        permission_error, owner, repo = self._check(self.agent_id, self.PROVIDER_ID, "github_list_branches", inp, "owner", "repo")
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("limit", 30)}
            resp = httpx.get(f"{_BASE}/repos/{owner}/{repo}/branches", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            branches = [
                {"name": b["name"], "protected": b.get("protected"), "sha": b.get("commit", {}).get("sha")}
                for b in resp.json()
            ]
            return json.dumps({"branches": branches, "count": len(branches)})
        except Exception as e:
            return _handle_error("github_list_branches", e)

    def create_branch(self, inp: dict) -> str:
        permission_error, owner, repo, branch = self._check(self.agent_id, self.PROVIDER_ID, "github_create_branch", inp, "owner", "repo", "branch")
        if permission_error: return permission_error
        from_branch = inp.get("from_branch", "")
        try:
            base_ref = from_branch or ""
            if not base_ref:
                repo_resp = httpx.get(f"{_BASE}/repos/{owner}/{repo}", headers=self._auth_headers, timeout=15)
                repo_resp.raise_for_status()
                base_ref = repo_resp.json().get("default_branch", "main")
            ref_resp = httpx.get(f"{_BASE}/repos/{owner}/{repo}/git/ref/heads/{base_ref}", headers=self._auth_headers, timeout=15)
            ref_resp.raise_for_status()
            base_sha = ref_resp.json().get("object", {}).get("sha")
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"ref": f"refs/heads/{branch}", "sha": base_sha}
            resp = httpx.post(f"{_BASE}/repos/{owner}/{repo}/git/refs", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"ref": data.get("ref"), "sha": data.get("object", {}).get("sha"), "status": "created"})
        except Exception as e:
            return _handle_error("github_create_branch", e)

    def list_pr_files(self, inp: dict) -> str:
        permission_error, owner, repo, pr_number = self._check(self.agent_id, self.PROVIDER_ID, "github_list_pr_files", inp, "owner", "repo", "pr_number")
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("limit", 30)}
            resp = httpx.get(f"{_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            files = [
                {
                    "filename": f["filename"],
                    "status": f.get("status"),
                    "additions": f.get("additions"),
                    "deletions": f.get("deletions"),
                    "changes": f.get("changes"),
                    "patch": (f.get("patch") or "")[:1000],
                }
                for f in resp.json()
            ]
            return json.dumps({"files": files, "count": len(files)})
        except Exception as e:
            return _handle_error("github_list_pr_files", e)

    def create_pr_review(self, inp: dict) -> str:
        permission_error, owner, repo, pr_number = self._check(self.agent_id, self.PROVIDER_ID, "github_create_pr_review", inp, "owner", "repo", "pr_number")
        if permission_error: return permission_error
        event = inp.get("event", "COMMENT")
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"event": event}
            if inp.get("body") is not None:
                body["body"] = inp["body"]
            resp = httpx.post(f"{_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/reviews", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "state": data.get("state"), "status": "submitted"})
        except Exception as e:
            return _handle_error("github_create_pr_review", e)

    def add_labels(self, inp: dict) -> str:
        permission_error, owner, repo, issue_number, labels = self._check(self.agent_id, self.PROVIDER_ID, "github_add_labels", inp, "owner", "repo", "issue_number", "labels")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(f"{_BASE}/repos/{owner}/{repo}/issues/{issue_number}/labels", headers=headers, json={"labels": labels}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"labels": [l["name"] for l in data], "status": "added"})
        except Exception as e:
            return _handle_error("github_add_labels", e)

    def create_release(self, inp: dict) -> str:
        permission_error, owner, repo, tag_name = self._check(self.agent_id, self.PROVIDER_ID, "github_create_release", inp, "owner", "repo", "tag_name")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"tag_name": tag_name}
            if inp.get("target_commitish") is not None:
                body["target_commitish"] = inp["target_commitish"]
            if inp.get("name") is not None:
                body["name"] = inp["name"]
            if inp.get("body") is not None:
                body["body"] = inp["body"]
            if inp.get("draft") is not None:
                body["draft"] = inp["draft"]
            if inp.get("prerelease") is not None:
                body["prerelease"] = inp["prerelease"]
            resp = httpx.post(f"{_BASE}/repos/{owner}/{repo}/releases", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "tag_name": data.get("tag_name"), "url": data.get("html_url"), "status": "created"})
        except Exception as e:
            return _handle_error("github_create_release", e)

    def search_issues(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "github_search_issues", inp, "query")
        if permission_error: return permission_error
        try:
            params = {"q": query, "per_page": inp.get("limit", 20)}
            resp = httpx.get(f"{_BASE}/search/issues", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            items = [
                {
                    "number": i["number"],
                    "title": i["title"],
                    "state": i["state"],
                    "repository_url": i.get("repository_url"),
                    "is_pr": "pull_request" in i,
                    "url": i.get("html_url"),
                }
                for i in data.get("items", [])
            ]
            return json.dumps({"results": items, "total_count": data.get("total_count")})
        except Exception as e:
            return _handle_error("github_search_issues", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "github_list_repos",
                    "description": "List GitHub repositories for the authenticated user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sort": {"type": "string", "description": "Sort by: updated, created, pushed, full_name (default updated)."},
                            "visibility": {"type": "string", "description": "Filter by: all, public, private (default all)."},
                            "limit": {"type": "integer", "description": "Max repos to return (default 30)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_get_repo",
                    "description": "Get details about a specific GitHub repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner (username or org)."},
                            "repo": {"type": "string", "description": "Repository name."},
                        },
                        "required": ["owner", "repo"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_list_issues",
                    "description": "List issues in a GitHub repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "state": {"type": "string", "description": "Filter by state: open, closed, all (default open)."},
                            "labels": {"type": "string", "description": "Comma-separated label names to filter by."},
                            "assignee": {"type": "string", "description": "Filter by assignee username."},
                            "limit": {"type": "integer", "description": "Max issues (default 25)."},
                        },
                        "required": ["owner", "repo"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_create_issue",
                    "description": "Create a new issue in a GitHub repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "title": {"type": "string", "description": "Issue title."},
                            "body": {"type": "string", "description": "Issue body/description."},
                            "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to apply."},
                            "assignees": {"type": "array", "items": {"type": "string"}, "description": "GitHub usernames to assign."},
                        },
                        "required": ["owner", "repo", "title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_list_pull_requests",
                    "description": "List pull requests in a GitHub repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "state": {"type": "string", "description": "Filter by: open, closed, all (default open)."},
                            "limit": {"type": "integer", "description": "Max PRs to return (default 20)."},
                        },
                        "required": ["owner", "repo"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_get_pull_request",
                    "description": "Get details of a specific pull request.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "pr_number": {"type": "integer", "description": "Pull request number."},
                        },
                        "required": ["owner", "repo", "pr_number"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_search_code",
                    "description": "Search for code across GitHub repositories.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query (e.g. 'useState repo:org/repo language:typescript')."},
                            "limit": {"type": "integer", "description": "Max results (default 10)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_get_user",
                    "description": "Get the authenticated GitHub user's profile information.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_update_issue",
                    "description": "Update an existing issue in a GitHub repository (state, title, body, labels, assignees).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "issue_number": {"type": "integer", "description": "Issue number to update."},
                            "state": {"type": "string", "description": "New state: open or closed."},
                            "title": {"type": "string", "description": "New issue title."},
                            "body": {"type": "string", "description": "New issue body/description."},
                            "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to set on the issue (replaces existing labels)."},
                            "assignees": {"type": "array", "items": {"type": "string"}, "description": "GitHub usernames to assign (replaces existing assignees)."},
                        },
                        "required": ["owner", "repo", "issue_number"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_create_pull_request",
                    "description": "Create a new pull request in a GitHub repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "title": {"type": "string", "description": "Pull request title."},
                            "head": {"type": "string", "description": "Source branch name (the branch with changes)."},
                            "base": {"type": "string", "description": "Target branch name (the branch to merge into)."},
                            "body": {"type": "string", "description": "Pull request description."},
                            "draft": {"type": "boolean", "description": "Create as a draft pull request."},
                        },
                        "required": ["owner", "repo", "title", "head", "base"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_merge_pull_request",
                    "description": "Merge a pull request in a GitHub repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "pull_number": {"type": "integer", "description": "Pull request number to merge."},
                            "merge_method": {"type": "string", "description": "Merge strategy: merge, squash, or rebase (default merge)."},
                            "commit_message": {"type": "string", "description": "Custom commit message for the merge."},
                        },
                        "required": ["owner", "repo", "pull_number"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_list_commits",
                    "description": "List commits in a GitHub repository, optionally filtered by branch or file path.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "sha": {"type": "string", "description": "Branch name or commit SHA to start listing from."},
                            "path": {"type": "string", "description": "Only return commits that touch this file path."},
                            "limit": {"type": "integer", "description": "Max commits to return (default 20)."},
                        },
                        "required": ["owner", "repo"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_get_file_contents",
                    "description": "Get the decoded contents of a file in a GitHub repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "path": {"type": "string", "description": "File path within the repository."},
                            "ref": {"type": "string", "description": "Branch name, tag, or commit SHA (defaults to the repo's default branch)."},
                        },
                        "required": ["owner", "repo", "path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_create_or_update_file",
                    "description": "Create or update a single file in a GitHub repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "path": {"type": "string", "description": "File path within the repository."},
                            "message": {"type": "string", "description": "Commit message for this change."},
                            "content": {"type": "string", "description": "Base64-encoded file content."},
                            "sha": {"type": "string", "description": "Blob SHA of the file being replaced (required for updates, omit for creates)."},
                            "branch": {"type": "string", "description": "Branch to commit to (defaults to the repo's default branch)."},
                        },
                        "required": ["owner", "repo", "path", "message", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_list_workflow_runs",
                    "description": "List GitHub Actions workflow runs for a repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "status": {"type": "string", "description": "Filter by status: completed, in_progress, or queued."},
                            "branch": {"type": "string", "description": "Filter runs by branch name."},
                            "limit": {"type": "integer", "description": "Max runs to return (default 10)."},
                        },
                        "required": ["owner", "repo"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_add_issue_comment",
                    "description": "Add a comment to an existing GitHub issue or pull request.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "issue_number": {"type": "integer", "description": "Issue or pull request number to comment on."},
                            "body": {"type": "string", "description": "Comment text (supports Markdown)."},
                        },
                        "required": ["owner", "repo", "issue_number", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_list_releases",
                    "description": "List releases for a GitHub repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "limit": {"type": "integer", "description": "Max releases to return (default 10)."},
                        },
                        "required": ["owner", "repo"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_list_branches",
                    "description": "List branches in a GitHub repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "limit": {"type": "integer", "description": "Max branches to return (default 30)."},
                        },
                        "required": ["owner", "repo"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_create_branch",
                    "description": "Create a new branch in a GitHub repository, optionally from a specific source branch.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "branch": {"type": "string", "description": "Name of the new branch to create."},
                            "from_branch": {"type": "string", "description": "Source branch to branch from (defaults to the repo's default branch)."},
                        },
                        "required": ["owner", "repo", "branch"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_list_pr_files",
                    "description": "List the files changed in a pull request, including diff patches.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "pr_number": {"type": "integer", "description": "Pull request number."},
                            "limit": {"type": "integer", "description": "Max files to return (default 30)."},
                        },
                        "required": ["owner", "repo", "pr_number"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_create_pr_review",
                    "description": "Submit a review on a pull request (approve, request changes, or comment).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "pr_number": {"type": "integer", "description": "Pull request number."},
                            "event": {"type": "string", "description": "Review action: APPROVE, REQUEST_CHANGES, or COMMENT (default COMMENT)."},
                            "body": {"type": "string", "description": "Review summary text."},
                        },
                        "required": ["owner", "repo", "pr_number"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_add_labels",
                    "description": "Add one or more labels to a GitHub issue or pull request.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "issue_number": {"type": "integer", "description": "Issue or pull request number."},
                            "labels": {"type": "array", "items": {"type": "string"}, "description": "Label names to add."},
                        },
                        "required": ["owner", "repo", "issue_number", "labels"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_create_release",
                    "description": "Create a new release/tag in a GitHub repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner."},
                            "repo": {"type": "string", "description": "Repository name."},
                            "tag_name": {"type": "string", "description": "Tag name for the release (e.g. 'v1.2.0')."},
                            "target_commitish": {"type": "string", "description": "Branch or commit SHA to tag (defaults to default branch)."},
                            "name": {"type": "string", "description": "Release title."},
                            "body": {"type": "string", "description": "Release notes/description."},
                            "draft": {"type": "boolean", "description": "Create as a draft release."},
                            "prerelease": {"type": "boolean", "description": "Mark as a prerelease."},
                        },
                        "required": ["owner", "repo", "tag_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_search_issues",
                    "description": "Search for issues and pull requests across GitHub using search qualifiers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query (e.g. 'repo:org/repo is:issue is:open label:bug')."},
                            "limit": {"type": "integer", "description": "Max results (default 20)."},
                        },
                        "required": ["query"],
                    },
                },
            },
        ]
        callables = {
            "github_list_branches": self.list_branches,
            "github_create_branch": self.create_branch,
            "github_list_pr_files": self.list_pr_files,
            "github_create_pr_review": self.create_pr_review,
            "github_add_labels": self.add_labels,
            "github_create_release": self.create_release,
            "github_search_issues": self.search_issues,
            "github_list_repos": self.list_repos,
            "github_get_repo": self.get_repo,
            "github_list_issues": self.list_issues,
            "github_create_issue": self.create_issue,
            "github_list_pull_requests": self.list_pull_requests,
            "github_get_pull_request": self.get_pull_request,
            "github_search_code": self.search_code,
            "github_get_user": self.get_user,
            "github_update_issue": self.update_issue,
            "github_create_pull_request": self.create_pull_request,
            "github_merge_pull_request": self.merge_pull_request,
            "github_list_commits": self.list_commits,
            "github_get_file_contents": self.get_file_contents,
            "github_create_or_update_file": self.create_or_update_file,
            "github_list_workflow_runs": self.list_workflow_runs,
            "github_add_issue_comment": self.add_issue_comment,
            "github_list_releases": self.list_releases,
        }
        return tools, callables

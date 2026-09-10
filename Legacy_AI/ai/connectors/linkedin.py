import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.linkedin.com/v2"


def _handle_error(tool_name, e):
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class LinkedInConnector(BaseConnector):
    """LinkedIn connector for profile, connections, organizations, and posts via the LinkedIn v2 API."""

    PROVIDER_ID = "linkedin"

    def get_profile(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "linkedin_get_profile", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/me", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("linkedin_get_profile", e)

    def get_email(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "linkedin_get_email", inp)
        if permission_error: return permission_error
        try:
            params = {"q": "members", "projection": "(elements*(handle~))"}
            resp = httpx.get(f"{_BASE}/emailAddress", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            elements = data.get("elements", [])
            emails = [el.get("handle~", {}).get("emailAddress") for el in elements if el.get("handle~", {}).get("emailAddress")]
            return json.dumps({"emails": emails})
        except Exception as e:
            return _handle_error("linkedin_get_email", e)

    def get_connections(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "linkedin_get_connections", inp)
        if permission_error: return permission_error
        try:
            params = {
                "q": "viewer",
                "start": inp.get("start", 0),
                "count": inp.get("count", 50),
            }
            resp = httpx.get(f"{_BASE}/connections", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("linkedin_get_connections", e)

    def get_organization(self, inp: dict) -> str:
        permission_error, org_id = self._check(self.agent_id, self.PROVIDER_ID, "linkedin_get_organization", inp, "organization_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/organizations/{org_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("linkedin_get_organization", e)

    def get_person_posts(self, inp: dict) -> str:
        permission_error, person_id = self._check(self.agent_id, self.PROVIDER_ID, "linkedin_get_person_posts", inp, "person_id")
        if permission_error: return permission_error
        try:
            author_urn = f"urn:li:person:{person_id}"
            params = {
                "q": "authors",
                "authors": f"List({author_urn})",
                "count": inp.get("count", 20),
            }
            resp = httpx.get(f"{_BASE}/ugcPosts", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("linkedin_get_person_posts", e)

    def get_organization_shares(self, inp: dict) -> str:
        permission_error, org_id = self._check(self.agent_id, self.PROVIDER_ID, "linkedin_get_organization_shares", inp, "organization_id")
        if permission_error: return permission_error
        try:
            params = {
                "q": "owners",
                "owners": f"urn:li:organization:{org_id}",
                "count": inp.get("count", 20),
            }
            resp = httpx.get(f"{_BASE}/shares", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("linkedin_get_organization_shares", e)

    def get_post_comments(self, inp: dict) -> str:
        permission_error, share_urn = self._check(self.agent_id, self.PROVIDER_ID, "linkedin_get_post_comments", inp, "share_urn")
        if permission_error: return permission_error
        try:
            encoded_urn = share_urn.replace(":", "%3A")
            resp = httpx.get(f"{_BASE}/socialActions/{encoded_urn}/comments", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("linkedin_get_post_comments", e)

    def create_post(self, inp: dict) -> str:
        permission_error, text = self._check(self.agent_id, self.PROVIDER_ID, "linkedin_create_post", inp, "text")
        if permission_error: return permission_error
        author_urn = inp.get("author_urn", "")
        if not author_urn:
            person_id = inp.get("person_id", "")
            org_id = inp.get("organization_id", "")
            if org_id:
                author_urn = f"urn:li:organization:{org_id}"
            elif person_id:
                author_urn = f"urn:li:person:{person_id}"
            else:
                return "Error: one of 'author_urn', 'person_id', or 'organization_id' is required to identify the post author."
        try:
            headers = {
                **self._auth_headers,
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
                "LinkedIn-Version": inp.get("linkedin_version", "202405"),
            }
            body = {
                "author": author_urn,
                "commentary": text,
                "visibility": inp.get("visibility", "PUBLIC"),
                "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
                "lifecycleState": "PUBLISHED",
                "isReshareDisabledByAuthor": False,
            }
            resp = httpx.post("https://api.linkedin.com/rest/posts", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            post_urn = resp.headers.get("x-restli-id", "")
            return json.dumps({"post_urn": post_urn, "status": "published"})
        except Exception as e:
            return _handle_error("linkedin_create_post", e)

    def delete_post(self, inp: dict) -> str:
        permission_error, post_urn = self._check(self.agent_id, self.PROVIDER_ID, "linkedin_delete_post", inp, "post_urn")
        if permission_error: return permission_error
        try:
            encoded_urn = post_urn.replace(":", "%3A")
            headers = {**self._auth_headers, "X-Restli-Protocol-Version": "2.0.0", "LinkedIn-Version": inp.get("linkedin_version", "202405")}
            resp = httpx.delete(f"https://api.linkedin.com/rest/posts/{encoded_urn}", headers=headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"deleted": True, "post_urn": post_urn})
        except Exception as e:
            return _handle_error("linkedin_delete_post", e)

    def list_admin_organizations(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "linkedin_list_admin_organizations", inp)
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "X-Restli-Protocol-Version": "2.0.0"}
            params = {"q": "roleAssignee"}
            if inp.get("role"):
                params["role"] = inp["role"]
            resp = httpx.get("https://api.linkedin.com/rest/organizationAcls", headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            orgs = [
                {"organization": el.get("organization"), "role": el.get("role"), "state": el.get("state")}
                for el in data.get("elements", [])
            ]
            return json.dumps({"organizations": orgs, "count": len(orgs)})
        except Exception as e:
            return _handle_error("linkedin_list_admin_organizations", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "linkedin_get_profile",
                    "description": "Retrieve the authenticated LinkedIn user's own profile (name, headline, location, industry, summary).",
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
                    "name": "linkedin_get_email",
                    "description": "Retrieve the primary email address associated with the authenticated LinkedIn account.",
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
                    "name": "linkedin_get_connections",
                    "description": "List the authenticated user's 1st-degree connections. Requires the r_1st_connections scope to be enabled in the developer portal.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "integer", "description": "Offset for pagination (default 0)."},
                            "count": {"type": "integer", "description": "Number of connections to return (default 50, max 500)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linkedin_get_organization",
                    "description": "Retrieve a LinkedIn company/organization profile by its numeric ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "organization_id": {"type": "string", "description": "LinkedIn organization numeric ID (e.g. '1441')."},
                        },
                        "required": ["organization_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linkedin_get_person_posts",
                    "description": "Retrieve UGC posts authored by a specific LinkedIn member.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "person_id": {"type": "string", "description": "LinkedIn member ID (the numeric part of urn:li:person:{id})."},
                            "count": {"type": "integer", "description": "Number of posts to return (default 20)."},
                        },
                        "required": ["person_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linkedin_get_organization_shares",
                    "description": "Retrieve shares/posts published by a LinkedIn organization. Requires r_organization_social scope.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "organization_id": {"type": "string", "description": "LinkedIn organization numeric ID."},
                            "count": {"type": "integer", "description": "Number of shares to return (default 20)."},
                        },
                        "required": ["organization_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linkedin_get_post_comments",
                    "description": "Retrieve comments on a LinkedIn share/post by its URN.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "share_urn": {"type": "string", "description": "Full URN of the share (e.g. 'urn:li:share:123456789' or 'urn:li:ugcPost:123456789')."},
                        },
                        "required": ["share_urn"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linkedin_create_post",
                    "description": "Publish a new text post to LinkedIn, either on behalf of the authenticated member or an organization page. Requires w_member_social or w_organization_social scope respectively.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "The post text/commentary."},
                            "person_id": {"type": "string", "description": "Numeric LinkedIn member ID to post as (mutually exclusive with organization_id/author_urn)."},
                            "organization_id": {"type": "string", "description": "Numeric LinkedIn organization ID to post as a company page (mutually exclusive with person_id/author_urn)."},
                            "author_urn": {"type": "string", "description": "Full author URN, e.g. 'urn:li:person:{id}' or 'urn:li:organization:{id}'. Overrides person_id/organization_id if set."},
                            "visibility": {"type": "string", "description": "Post visibility: PUBLIC or CONNECTIONS (default PUBLIC)."},
                        },
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linkedin_delete_post",
                    "description": "Delete a LinkedIn post by its URN.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "post_urn": {"type": "string", "description": "Full post URN, e.g. 'urn:li:share:123456789' or 'urn:li:ugcPost:123456789'."},
                        },
                        "required": ["post_urn"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "linkedin_list_admin_organizations",
                    "description": "List LinkedIn organizations (company pages) the authenticated member has administrative access to, along with their role.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string", "description": "Filter by role, e.g. ADMINISTRATOR, CONTENT_ADMIN, DIRECT_SPONSORED_CONTENT_POSTER."},
                        },
                        "required": [],
                    },
                },
            },
        ]
        callables = {
            "linkedin_get_profile": self.get_profile,
            "linkedin_get_email": self.get_email,
            "linkedin_get_connections": self.get_connections,
            "linkedin_get_organization": self.get_organization,
            "linkedin_get_person_posts": self.get_person_posts,
            "linkedin_get_organization_shares": self.get_organization_shares,
            "linkedin_get_post_comments": self.get_post_comments,
            "linkedin_create_post": self.create_post,
            "linkedin_delete_post": self.delete_post,
            "linkedin_list_admin_organizations": self.list_admin_organizations,
        }
        return tools, callables

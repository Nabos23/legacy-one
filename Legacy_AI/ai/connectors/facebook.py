import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://graph.facebook.com/v19.0"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Facebook account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "This usually means a Page Access Token is required but a User Access Token was used — "
                "call facebook_get_pages() to get the page's access_token and pass it as "
                "'page_access_token' on this call. If that still fails, ask the user to reconnect the "
                "Facebook connector."
            )
        if e.response.status_code == 404:
            return f"Not found in {tool_name}: the requested resource does not exist."
        if e.response.status_code == 429:
            return f"Rate limit exceeded in {tool_name}: Facebook API rate limit hit, try again later."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class FacebookConnector(BaseConnector):

    PROVIDER_ID = "facebook"

    def _resolve_token(self, inp: dict) -> str:
        """Prefer an explicit page access token over the connector's user token."""
        return inp.get("page_access_token") or self._token

    def get_me(self, inp: dict) -> str:
        """Get the authenticated user's basic Facebook profile."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "facebook_get_me", inp)
        if permission_error: return permission_error
        try:
            params = {
                "fields": "id,name,email,picture",
                "access_token": self._token,
            }
            resp = httpx.get(f"{_BASE}/me", params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("facebook_get_me", e)

    def get_pages(self, inp: dict) -> str:
        """List Facebook Pages the authenticated user manages, including their page access tokens."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "facebook_get_pages", inp)
        if permission_error: return permission_error
        try:
            params = {
                "fields": "id,name,category,fan_count,access_token,tasks",
                "access_token": self._token,
            }
            resp = httpx.get(f"{_BASE}/me/accounts", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            pages = data.get("data", [])
            return json.dumps({"pages": pages, "total": len(pages)})
        except Exception as e:
            return _handle_error("facebook_get_pages", e)

    def get_page(self, inp: dict) -> str:
        """Get details of a specific Facebook Page by its ID."""
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "facebook_get_page", inp, "page_id")
        if permission_error: return permission_error
        try:
            params = {
                "fields": "id,name,category,description,fan_count,followers_count,website,phone,email,location",
                "access_token": self._resolve_token(inp),
            }
            resp = httpx.get(f"{_BASE}/{page_id}", params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("facebook_get_page", e)

    def get_page_posts(self, inp: dict) -> str:
        """Get posts published on a Facebook Page."""
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "facebook_get_page_posts", inp, "page_id")
        if permission_error: return permission_error
        try:
            params = {
                "fields": "id,message,story,created_time,full_picture,permalink_url,reactions.summary(true),comments.summary(true),shares",
                "limit": min(inp.get("limit", 10), 100),
                "access_token": self._resolve_token(inp),
            }
            if inp.get("after"):
                params["after"] = inp["after"]
            resp = httpx.get(f"{_BASE}/{page_id}/posts", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "posts": data.get("data", []),
                "paging": data.get("paging", {}),
            })
        except Exception as e:
            return _handle_error("facebook_get_page_posts", e)

    def get_page_feed(self, inp: dict) -> str:
        """Get the full feed of a Facebook Page (posts by the page and others)."""
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "facebook_get_page_feed", inp, "page_id")
        if permission_error: return permission_error
        try:
            params = {
                "fields": "id,message,story,created_time,from,permalink_url,reactions.summary(true)",
                "limit": min(inp.get("limit", 10), 100),
                "access_token": self._resolve_token(inp),
            }
            if inp.get("after"):
                params["after"] = inp["after"]
            resp = httpx.get(f"{_BASE}/{page_id}/feed", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "feed": data.get("data", []),
                "paging": data.get("paging", {}),
            })
        except Exception as e:
            return _handle_error("facebook_get_page_feed", e)

    def publish_page_post(self, inp: dict) -> str:
        """Publish a new post to a Facebook Page. Requires a Page Access Token."""
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "facebook_publish_page_post", inp, "page_id")
        if permission_error: return permission_error
        message = inp.get("message", "")
        if not message and not inp.get("link"):
            return "Error: 'message' or 'link' is required."
        try:
            body: dict = {"access_token": self._resolve_token(inp)}
            if message:
                body["message"] = message
            if inp.get("link"):
                body["link"] = inp["link"]
            if inp.get("published") is not None:
                body["published"] = inp["published"]
            resp = httpx.post(
                f"{_BASE}/{page_id}/feed",
                data=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"post_id": data.get("id"), "status": "published"})
        except Exception as e:
            return _handle_error("facebook_publish_page_post", e)

    def delete_post(self, inp: dict) -> str:
        """Delete a Facebook post by its ID. Requires the post's owner page access token."""
        permission_error, post_id = self._check(self.agent_id, self.PROVIDER_ID, "facebook_delete_post", inp, "post_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(
                f"{_BASE}/{post_id}",
                params={"access_token": self._resolve_token(inp)},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"deleted": data.get("success", False), "post_id": post_id})
        except Exception as e:
            return _handle_error("facebook_delete_post", e)

    def get_post_comments(self, inp: dict) -> str:
        """Get comments on a Facebook post or page post."""
        permission_error, post_id = self._check(self.agent_id, self.PROVIDER_ID, "facebook_get_post_comments", inp, "post_id")
        if permission_error: return permission_error
        try:
            params = {
                "fields": "id,message,from,created_time,like_count,can_reply_privately",
                "limit": min(inp.get("limit", 25), 100),
                "access_token": self._resolve_token(inp),
            }
            if inp.get("after"):
                params["after"] = inp["after"]
            resp = httpx.get(f"{_BASE}/{post_id}/comments", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "comments": data.get("data", []),
                "paging": data.get("paging", {}),
            })
        except Exception as e:
            return _handle_error("facebook_get_post_comments", e)

    def reply_to_comment(self, inp: dict) -> str:
        """Reply to a comment on a Facebook post. Requires a Page Access Token."""
        permission_error, comment_id, message = self._check(self.agent_id, self.PROVIDER_ID, "facebook_reply_to_comment", inp, "comment_id", "message")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/{comment_id}/comments",
                data={"message": message, "access_token": self._resolve_token(inp)},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"comment_id": data.get("id"), "status": "replied"})
        except Exception as e:
            return _handle_error("facebook_reply_to_comment", e)

    def delete_comment(self, inp: dict) -> str:
        """Delete a comment on a Facebook post."""
        permission_error, comment_id = self._check(self.agent_id, self.PROVIDER_ID, "facebook_delete_comment", inp, "comment_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(
                f"{_BASE}/{comment_id}",
                params={"access_token": self._resolve_token(inp)},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"deleted": data.get("success", False), "comment_id": comment_id})
        except Exception as e:
            return _handle_error("facebook_delete_comment", e)

    def get_post_reactions(self, inp: dict) -> str:
        """Get reactions (likes, loves, etc.) summary on a Facebook post."""
        permission_error, post_id = self._check(self.agent_id, self.PROVIDER_ID, "facebook_get_post_reactions", inp, "post_id")
        if permission_error: return permission_error
        try:
            params = {
                "fields": "reactions.summary(true).limit(0)",
                "access_token": self._resolve_token(inp),
            }
            resp = httpx.get(f"{_BASE}/{post_id}", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            reactions = data.get("reactions", {})
            return json.dumps({
                "post_id": post_id,
                "total_reactions": reactions.get("summary", {}).get("total_count", 0),
                "reaction_type": reactions.get("summary", {}).get("viewer_reaction"),
            })
        except Exception as e:
            return _handle_error("facebook_get_post_reactions", e)

    def get_page_insights(self, inp: dict) -> str:
        """Get insights/analytics for a Facebook Page (impressions, reach, engagement)."""
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "facebook_get_page_insights", inp, "page_id")
        if permission_error: return permission_error
        metric = inp.get("metric", "page_impressions,page_reach,page_engaged_users,page_fan_count")
        period = inp.get("period", "day")
        try:
            params = {
                "metric": metric,
                "period": period,
                "access_token": self._resolve_token(inp),
            }
            if inp.get("since"):
                params["since"] = inp["since"]
            if inp.get("until"):
                params["until"] = inp["until"]
            resp = httpx.get(f"{_BASE}/{page_id}/insights", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "page_id": page_id,
                "metrics": data.get("data", []),
                "paging": data.get("paging", {}),
            })
        except Exception as e:
            return _handle_error("facebook_get_page_insights", e)

    def get_post_insights(self, inp: dict) -> str:
        """Get insights for a specific Facebook Page post."""
        permission_error, post_id = self._check(self.agent_id, self.PROVIDER_ID, "facebook_get_post_insights", inp, "post_id")
        if permission_error: return permission_error
        metric = inp.get("metric", "post_impressions,post_reach,post_engaged_users,post_clicks")
        try:
            params = {
                "metric": metric,
                "access_token": self._resolve_token(inp),
            }
            resp = httpx.get(f"{_BASE}/{post_id}/insights", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"post_id": post_id, "metrics": data.get("data", [])})
        except Exception as e:
            return _handle_error("facebook_get_post_insights", e)

    def search_pages(self, inp: dict) -> str:
        """Search for public Facebook Pages by name or keyword."""
        permission_error, q = self._check(self.agent_id, self.PROVIDER_ID, "facebook_search_pages", inp, "q")
        if permission_error: return permission_error
        try:
            params = {
                "q": q,
                "type": "page",
                "fields": "id,name,category,fan_count,verification_status",
                "limit": min(inp.get("limit", 10), 25),
                "access_token": self._token,
            }
            resp = httpx.get(f"{_BASE}/search", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"results": data.get("data", []), "paging": data.get("paging", {})})
        except Exception as e:
            return _handle_error("facebook_search_pages", e)

    def get_page_photos(self, inp: dict) -> str:
        """Get photos uploaded to a Facebook Page."""
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "facebook_get_page_photos", inp, "page_id")
        if permission_error: return permission_error
        try:
            params = {
                "fields": "id,name,created_time,images,link",
                "limit": min(inp.get("limit", 10), 50),
                "access_token": self._resolve_token(inp),
            }
            if inp.get("after"):
                params["after"] = inp["after"]
            resp = httpx.get(f"{_BASE}/{page_id}/photos", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"photos": data.get("data", []), "paging": data.get("paging", {})})
        except Exception as e:
            return _handle_error("facebook_get_page_photos", e)
    
    def publish_page_photo(self, inp: dict) -> str:
        """Publish a photo to a Facebook Page, optionally with a caption. Requires a Page Access Token."""
        permission_error, page_id = self._check(self.agent_id, self.PROVIDER_ID, "facebook_publish_page_photo", inp, "page_id")
        if permission_error: return permission_error
        if not inp.get("url"):
            return "Error: 'url' (a publicly reachable image URL) is required."
        try:
            body: dict = {
                "url": inp["url"],
                "access_token": self._resolve_token(inp),
            }
            if inp.get("caption"):
                body["caption"] = inp["caption"]
            if inp.get("published") is not None:
                body["published"] = inp["published"]
            resp = httpx.post(f"{_BASE}/{page_id}/photos", data=body, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "photo_id": data.get("id"),
                "post_id": data.get("post_id"),
                "status": "published" if inp.get("published", True) else "unpublished",
            })
        except Exception as e:
            return _handle_error("facebook_publish_page_photo", e)

    def publish_page_video(self, inp: dict) -> str:
        """Publish a video to a Facebook Page from a hosted URL. Requires a Page Access Token."""
        permission_error, page_id, file_url = self._check(
            self.agent_id, self.PROVIDER_ID, "facebook_publish_page_video", inp, "page_id", "file_url"
        )
        if permission_error: return permission_error
        try:
            body: dict = {
                "file_url": file_url,
                "access_token": self._resolve_token(inp),
            }
            if inp.get("description"):
                body["description"] = inp["description"]
            if inp.get("title"):
                body["title"] = inp["title"]
            resp = httpx.post(f"{_BASE}/{page_id}/videos", data=body, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"video_id": data.get("id"), "status": "published"})
        except Exception as e:
            return _handle_error("facebook_publish_page_video", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        _page_token_param = {
            "page_access_token": {
                "type": "string",
                "description": (
                    "Page Access Token for this specific page, obtained from facebook_get_pages(). "
                    "Required for most page-scoped calls; falls back to the connector's user token "
                    "if omitted, which may cause 401/403 errors."
                ),
            }
        }
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "facebook_get_me",
                    "description": "Get the authenticated Facebook user's basic profile: name, email, and profile picture.",
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
                    "name": "facebook_get_pages",
                    "description": "List all Facebook Pages the authenticated user manages, including page IDs and page access tokens needed for page-level operations. Always call this first to get each page's access_token before using page-scoped tools.",
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
                    "name": "facebook_get_page",
                    "description": "Get detailed information about a specific Facebook Page: name, category, description, fan count, followers, and contact info.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "The numeric Facebook Page ID (e.g. '123456789')."},
                            **_page_token_param,
                        },
                        "required": ["page_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "facebook_get_page_posts",
                    "description": "Get posts published by a Facebook Page, including message text, timestamps, reaction counts, comment counts, and share counts. Requires a page_access_token from facebook_get_pages().",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Numeric Facebook Page ID."},
                            "limit": {"type": "integer", "description": "Number of posts to return (default 10, max 100)."},
                            "after": {"type": "string", "description": "Pagination cursor from a previous response's paging.cursors.after field (optional)."},
                            **_page_token_param,
                        },
                        "required": ["page_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "facebook_get_page_feed",
                    "description": "Get the full activity feed of a Facebook Page, including posts by the page and posts by others on the page's timeline. Requires a page_access_token from facebook_get_pages().",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Numeric Facebook Page ID."},
                            "limit": {"type": "integer", "description": "Number of feed items to return (default 10, max 100)."},
                            "after": {"type": "string", "description": "Pagination cursor (optional)."},
                            **_page_token_param,
                        },
                        "required": ["page_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "facebook_publish_page_post",
                    "description": "Publish a new post to a Facebook Page. Can include text, a link, or both. Requires pages_manage_posts permission and a valid Page Access Token (obtained via facebook_get_pages).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Numeric Facebook Page ID to post to."},
                            "message": {"type": "string", "description": "The text content of the post."},
                            "link": {"type": "string", "description": "URL to attach as a link preview (optional)."},
                            "published": {"type": "boolean", "description": "Whether to publish immediately (default true). Set false to save as draft."},
                            **_page_token_param,
                        },
                        "required": ["page_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "facebook_delete_post",
                    "description": "Delete a Facebook Page post by its ID. Requires the post's owner page access token.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "post_id": {"type": "string", "description": "The full post ID (e.g. '{page_id}_{post_id}' or the full Graph API post ID)."},
                            **_page_token_param,
                        },
                        "required": ["post_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "facebook_get_post_comments",
                    "description": "Get comments on a Facebook post, including commenter name, message text, and timestamp. Requires a page_access_token from facebook_get_pages().",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "post_id": {"type": "string", "description": "The Facebook post ID."},
                            "limit": {"type": "integer", "description": "Number of comments to return (default 25, max 100)."},
                            "after": {"type": "string", "description": "Pagination cursor (optional)."},
                            **_page_token_param,
                        },
                        "required": ["post_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "facebook_reply_to_comment",
                    "description": "Post a reply to an existing comment on a Facebook Page post. Requires a Page Access Token with pages_manage_posts permission.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "comment_id": {"type": "string", "description": "The Facebook comment ID to reply to."},
                            "message": {"type": "string", "description": "The reply text."},
                            **_page_token_param,
                        },
                        "required": ["comment_id", "message"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "facebook_delete_comment",
                    "description": "Delete a comment on a Facebook Page post.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "comment_id": {"type": "string", "description": "The Facebook comment ID to delete."},
                            **_page_token_param,
                        },
                        "required": ["comment_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "facebook_get_post_reactions",
                    "description": "Get a summary of total reactions (likes, loves, hahas, wows, sads, angrys) on a Facebook post. Requires a page_access_token from facebook_get_pages().",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "post_id": {"type": "string", "description": "The Facebook post ID."},
                            **_page_token_param,
                        },
                        "required": ["post_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "facebook_get_page_insights",
                    "description": "Get analytics insights for a Facebook Page including impressions, reach, engaged users, and fan count over a given period. Requires a page_access_token from facebook_get_pages().",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Numeric Facebook Page ID."},
                            "metric": {"type": "string", "description": "Comma-separated metric names (default: 'page_impressions,page_reach,page_engaged_users,page_fan_count')."},
                            "period": {"type": "string", "description": "Aggregation period: 'day', 'week', 'days_28', 'month', 'lifetime' (default: 'day')."},
                            "since": {"type": "string", "description": "Unix timestamp or date string for the start of the range (optional)."},
                            "until": {"type": "string", "description": "Unix timestamp or date string for the end of the range (optional)."},
                            **_page_token_param,
                        },
                        "required": ["page_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "facebook_get_post_insights",
                    "description": "Get performance metrics for a specific Facebook Page post: impressions, reach, engaged users, and click-throughs. Requires a page_access_token from facebook_get_pages().",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "post_id": {"type": "string", "description": "The Facebook post ID."},
                            "metric": {"type": "string", "description": "Comma-separated metric names (default: 'post_impressions,post_reach,post_engaged_users,post_clicks')."},
                            **_page_token_param,
                        },
                        "required": ["post_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "facebook_search_pages",
                    "description": "Search for public Facebook Pages by name or keyword.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "q": {"type": "string", "description": "Search query — name or keyword of the page to find."},
                            "limit": {"type": "integer", "description": "Number of results to return (default 10, max 25)."},
                        },
                        "required": ["q"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "facebook_get_page_photos",
                    "description": "Get photos uploaded to a Facebook Page. Requires a page_access_token from facebook_get_pages().",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Numeric Facebook Page ID."},
                            "limit": {"type": "integer", "description": "Number of photos to return (default 10, max 50)."},
                            "after": {"type": "string", "description": "Pagination cursor (optional)."},
                            **_page_token_param,
                        },
                        "required": ["page_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "facebook_publish_page_photo",
                    "description": "Publish a photo to a Facebook Page from a publicly reachable image URL, with an optional caption. Requires pages_manage_posts permission and a valid Page Access Token (obtained via facebook_get_pages).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Numeric Facebook Page ID to post to."},
                            "url": {"type": "string", "description": "Publicly accessible URL of the image to upload."},
                            "caption": {"type": "string", "description": "Caption text for the photo (optional)."},
                            "published": {"type": "boolean", "description": "Whether to publish immediately (default true). Set false to upload unpublished, e.g. for a later multi-photo post."},
                            **_page_token_param,
                        },
                        "required": ["page_id", "url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "facebook_publish_page_video",
                    "description": "Publish a video to a Facebook Page from a publicly reachable video URL, with an optional title and description. Requires pages_manage_posts permission and a valid Page Access Token (obtained via facebook_get_pages). Intended for reasonably small/short videos; not suited for very large files.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "Numeric Facebook Page ID to post to."},
                            "file_url": {"type": "string", "description": "Publicly accessible URL of the video file to upload."},
                            "title": {"type": "string", "description": "Title for the video (optional)."},
                            "description": {"type": "string", "description": "Description text for the video (optional)."},
                            **_page_token_param,
                        },
                        "required": ["page_id", "file_url"],
                    },
                },
            },
        ]
        callables = {
            "facebook_get_me": self.get_me,
            "facebook_get_pages": self.get_pages,
            "facebook_get_page": self.get_page,
            "facebook_get_page_posts": self.get_page_posts,
            "facebook_get_page_feed": self.get_page_feed,
            "facebook_publish_page_post": self.publish_page_post,
            "facebook_publish_page_photo": self.publish_page_photo,
            "facebook_publish_page_video": self.publish_page_video,
            "facebook_delete_post": self.delete_post,
            "facebook_get_post_comments": self.get_post_comments,
            "facebook_reply_to_comment": self.reply_to_comment,
            "facebook_delete_comment": self.delete_comment,
            "facebook_get_post_reactions": self.get_post_reactions,
            "facebook_get_page_insights": self.get_page_insights,
            "facebook_get_post_insights": self.get_post_insights,
            "facebook_search_pages": self.search_pages,
            "facebook_get_page_photos": self.get_page_photos,
        }
        return tools, callables
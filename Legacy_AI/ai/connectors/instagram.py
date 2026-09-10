import json
import httpx
from ai.connectors.base import BaseConnector


_BASE = "https://graph.facebook.com/v19.0"

def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Instagram account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "This usually means the linked Facebook Page's access token is required — call "
                "facebook_get_pages()/instagram_get_business_accounts() to get it and pass it as "
                "'page_access_token' on this call. If that still fails, ask the user to reconnect the "
                "Instagram connector."
            )
        if e.response.status_code == 404:
            return f"Not found in {tool_name}: the requested resource does not exist."
        if e.response.status_code == 429:
            return f"Rate limit exceeded in {tool_name}: Instagram API rate limit hit, try again later."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


    
class InstagramConnector(BaseConnector):
    """
    Instagram Graph API connector via the Meta Graph API v19.
    Requires a Facebook User Access Token
    """

    PROVIDER_ID = "instagram"

    def _resolve_token(self, inp: dict) -> str:
        """Prefer an explicit page access token over the connector's user token."""
        return inp.get("page_access_token") or self._token

    def get_business_accounts(self, inp: dict) -> str:
        """
        Discover Instagram Business/Creator accounts linked to the authenticated
        Facebook user's pages. Returns account IDs needed for other operations.
        """
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "instagram_get_business_accounts", inp)
        if permission_error: return permission_error
        try:
            params = {
                "fields": "id,name,access_token,instagram_business_account{id,name,username,biography,profile_picture_url,followers_count,media_count}",
                "access_token": self._token,
            }
            resp = httpx.get(f"{_BASE}/me/accounts", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            pages = data.get("data", [])
            accounts = []
            for page in pages:
                ib = page.get("instagram_business_account")
                if ib:
                    accounts.append({
                        "instagram_id": ib.get("id"),
                        "name": ib.get("name"),
                        "username": ib.get("username"),
                        "biography": ib.get("biography"),
                        "profile_picture_url": ib.get("profile_picture_url"),
                        "followers_count": ib.get("followers_count"),
                        "media_count": ib.get("media_count"),
                        "facebook_page_id": page.get("id"),
                        "facebook_page_name": page.get("name"),
                        "page_access_token": page.get("access_token"),
                    })
            return json.dumps({"accounts": accounts, "total": len(accounts)})
        except Exception as e:
            return _handle_error("instagram_get_business_accounts", e)

    def get_account_info(self, inp: dict) -> str:
        """Get detailed profile information for an Instagram Business Account."""
        permission_error, ig_id = self._check(self.agent_id, self.PROVIDER_ID, "instagram_get_account_info", inp, "instagram_id")
        if permission_error: return permission_error
        try:
            params = {
                "fields": "id,name,username,biography,website,profile_picture_url,followers_count,follows_count,media_count",
                "access_token": self._resolve_token(inp),
            }
            resp = httpx.get(f"{_BASE}/{ig_id}", params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("instagram_get_account_info", e)

    def get_media(self, inp: dict) -> str:
        """Get media (posts, reels, stories) published by an Instagram Business Account."""
        permission_error, ig_id = self._check(self.agent_id, self.PROVIDER_ID, "instagram_get_media", inp, "instagram_id")
        if permission_error: return permission_error
        try:
            params = {
                "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count",
                "limit": min(inp.get("limit", 10), 50),
                "access_token": self._resolve_token(inp),
            }
            if inp.get("after"):
                params["after"] = inp["after"]
            resp = httpx.get(f"{_BASE}/{ig_id}/media", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "media": data.get("data", []),
                "paging": data.get("paging", {}),
            })
        except Exception as e:
            return _handle_error("instagram_get_media", e)

    def get_media_item(self, inp: dict) -> str:
        """Get full details of a single Instagram media item by its ID."""
        permission_error, media_id = self._check(self.agent_id, self.PROVIDER_ID, "instagram_get_media_item", inp, "media_id")
        if permission_error: return permission_error
        try:
            params = {
                "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count,ig_id,shortcode",
                "access_token": self._resolve_token(inp),
            }
            resp = httpx.get(f"{_BASE}/{media_id}", params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("instagram_get_media_item", e)

    def get_media_comments(self, inp: dict) -> str:
        """Get comments on an Instagram media item."""
        permission_error, media_id = self._check(self.agent_id, self.PROVIDER_ID, "instagram_get_media_comments", inp, "media_id")
        if permission_error: return permission_error
        try:
            params = {
                "fields": "id,text,username,timestamp,like_count,replies{id,text,username,timestamp}",
                "limit": min(inp.get("limit", 25), 50),
                "access_token": self._resolve_token(inp),
            }
            if inp.get("after"):
                params["after"] = inp["after"]
            resp = httpx.get(f"{_BASE}/{media_id}/comments", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "comments": data.get("data", []),
                "paging": data.get("paging", {}),
            })
        except Exception as e:
            return _handle_error("instagram_get_media_comments", e)

    def reply_to_comment(self, inp: dict) -> str:
        """Reply to a comment on an Instagram media item. Requires instagram_manage_comments scope."""
        permission_error, comment_id, message = self._check(self.agent_id, self.PROVIDER_ID, "instagram_reply_to_comment", inp, "comment_id", "message")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/{comment_id}/replies",
                params={"message": message, "access_token": self._resolve_token(inp)},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"reply_id": data.get("id"), "status": "replied"})
        except Exception as e:
            return _handle_error("instagram_reply_to_comment", e)

    def delete_comment(self, inp: dict) -> str:
        """Delete a comment on an Instagram media item owned by the account."""
        permission_error, comment_id = self._check(self.agent_id, self.PROVIDER_ID, "instagram_delete_comment", inp, "comment_id")
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
            return _handle_error("instagram_delete_comment", e)

    def hide_comment(self, inp: dict) -> str:
        """Hide or unhide a comment on an Instagram media item."""
        permission_error, comment_id = self._check(self.agent_id, self.PROVIDER_ID, "instagram_hide_comment", inp, "comment_id")
        if permission_error: return permission_error
        hidden = inp.get("hide", True)
        try:
            resp = httpx.post(
                f"{_BASE}/{comment_id}",
                params={"hide": str(hidden).lower(), "access_token": self._resolve_token(inp)},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"comment_id": comment_id, "hidden": hidden, "success": data.get("success", False)})
        except Exception as e:
            return _handle_error("instagram_hide_comment", e)

    def publish_photo_post(self, inp: dict) -> str:
        """
        Publish a photo post to an Instagram Business Account.
        This is a two-step process: (1) create a media container, (2) publish it.
        Requires instagram_content_publish scope.
        """
        permission_error, ig_id, image_url = self._check(self.agent_id, self.PROVIDER_ID, "instagram_publish_photo_post", inp, "instagram_id", "image_url")
        if permission_error: return permission_error
        caption = inp.get("caption", "")
        try:
            token = self._resolve_token(inp)
            container_params: dict = {
                "image_url": image_url,
                "access_token": token,
            }
            if caption:
                container_params["caption"] = caption
            if inp.get("location_id"):
                container_params["location_id"] = inp["location_id"]
            resp = httpx.post(f"{_BASE}/{ig_id}/media", params=container_params, timeout=30)
            resp.raise_for_status()
            container_id = resp.json().get("id")
            if not container_id:
                return "Error: Failed to create media container."
            pub_resp = httpx.post(
                f"{_BASE}/{ig_id}/media_publish",
                params={"creation_id": container_id, "access_token": token},
                timeout=30,
            )
            pub_resp.raise_for_status()
            data = pub_resp.json()
            return json.dumps({"media_id": data.get("id"), "status": "published"})
        except Exception as e:
            return _handle_error("instagram_publish_photo_post", e)

    def publish_reel(self, inp: dict) -> str:
        """
        Publish a Reel to an Instagram Business Account.
        Requires instagram_content_publish scope and a publicly accessible video URL.
        """
        permission_error, ig_id, video_url = self._check(self.agent_id, self.PROVIDER_ID, "instagram_publish_reel", inp, "instagram_id", "video_url")
        if permission_error: return permission_error
        caption = inp.get("caption", "")
        try:
            token = self._resolve_token(inp)
            container_params: dict = {
                "media_type": "REELS",
                "video_url": video_url,
                "access_token": token,
            }
            if caption:
                container_params["caption"] = caption
            if inp.get("share_to_feed") is not None:
                container_params["share_to_feed"] = str(inp["share_to_feed"]).lower()
            resp = httpx.post(f"{_BASE}/{ig_id}/media", params=container_params, timeout=30)
            resp.raise_for_status()
            container_id = resp.json().get("id")
            if not container_id:
                return "Error: Failed to create reel container."
            pub_resp = httpx.post(
                f"{_BASE}/{ig_id}/media_publish",
                params={"creation_id": container_id, "access_token": token},
                timeout=30,
            )
            pub_resp.raise_for_status()
            data = pub_resp.json()
            return json.dumps({"media_id": data.get("id"), "status": "published", "type": "reel"})
        except Exception as e:
            return _handle_error("instagram_publish_reel", e)
    
    def publish_carousel_post(self, inp: dict) -> str:
        """ Publish a carousel post (2-10 images and/or videos swiped through in one post)"""
        permission_error, ig_id, media_urls = self._check(
            self.agent_id, self.PROVIDER_ID, "instagram_publish_carousel_post", inp, "instagram_id", "media_urls"
        )
        if permission_error: return permission_error
        if not isinstance(media_urls, list) or not (2 <= len(media_urls) <= 10):
            return "Error: 'media_urls' must be a list of 2 to 10 items."
        caption = inp.get("caption", "")
        try:
            token = self._resolve_token(inp)
            child_ids = []
            for item in media_urls:
                url = item.get("url") if isinstance(item, dict) else item
                media_type = item.get("media_type", "IMAGE") if isinstance(item, dict) else "IMAGE"
                if not url:
                    return "Error: each entry in 'media_urls' must include a 'url'."
                item_params: dict = {
                    "is_carousel_item": "true",
                    "access_token": token,
                }
                if media_type.upper() == "VIDEO":
                    item_params["media_type"] = "VIDEO"
                    item_params["video_url"] = url
                else:
                    item_params["image_url"] = url
                resp = httpx.post(f"{_BASE}/{ig_id}/media", params=item_params, timeout=30)
                resp.raise_for_status()
                child_id = resp.json().get("id")
                if not child_id:
                    return "Error: failed to create a carousel item container."
                child_ids.append(child_id)

            carousel_params: dict = {
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "access_token": token,
            }
            if caption:
                carousel_params["caption"] = caption
            if inp.get("location_id"):
                carousel_params["location_id"] = inp["location_id"]
            resp = httpx.post(f"{_BASE}/{ig_id}/media", params=carousel_params, timeout=30)
            resp.raise_for_status()
            carousel_id = resp.json().get("id")
            if not carousel_id:
                return "Error: failed to create the carousel container."

            pub_resp = httpx.post(
                f"{_BASE}/{ig_id}/media_publish",
                params={"creation_id": carousel_id, "access_token": token},
                timeout=30,
            )
            pub_resp.raise_for_status()
            data = pub_resp.json()
            return json.dumps({"media_id": data.get("id"), "status": "published", "type": "carousel", "item_count": len(child_ids)})
        except Exception as e:
            return _handle_error("instagram_publish_carousel_post", e)

    def get_media_insights(self, inp: dict) -> str:
        """Get insights for a specific Instagram media item: impressions, reach, engagement, saves."""
        permission_error, media_id = self._check(self.agent_id, self.PROVIDER_ID, "instagram_get_media_insights", inp, "media_id")
        if permission_error: return permission_error
        metric = inp.get("metric", "impressions,reach,likes,comments,shares,saved,total_interactions")
        try:
            params = {
                "metric": metric,
                "access_token": self._resolve_token(inp),
            }
            resp = httpx.get(f"{_BASE}/{media_id}/insights", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"media_id": media_id, "metrics": data.get("data", [])})
        except Exception as e:
            return _handle_error("instagram_get_media_insights", e)

    def get_account_insights(self, inp: dict) -> str:
        """Get account-level insights for an Instagram Business Account: impressions, reach, profile views, follower count."""
        permission_error, ig_id = self._check(self.agent_id, self.PROVIDER_ID, "instagram_get_account_insights", inp, "instagram_id")
        if permission_error: return permission_error
        metric = inp.get("metric", "impressions,reach,profile_views,follower_count")
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
            resp = httpx.get(f"{_BASE}/{ig_id}/insights", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "instagram_id": ig_id,
                "metrics": data.get("data", []),
                "paging": data.get("paging", {}),
            })
        except Exception as e:
            return _handle_error("instagram_get_account_insights", e)

    def search_hashtag(self, inp: dict) -> str:
        """Search for an Instagram hashtag and get its ID for use in hashtag feed lookups."""
        permission_error, ig_id, hashtag = self._check(self.agent_id, self.PROVIDER_ID, "instagram_search_hashtag", inp, "instagram_id", "hashtag")
        if permission_error: return permission_error
        hashtag = hashtag.lstrip("#")
        try:
            params = {
                "user_id": ig_id,
                "q": hashtag,
                "access_token": self._resolve_token(inp),
            }
            resp = httpx.get(f"{_BASE}/ig_hashtag_search", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            hashtag_data = data.get("data", [])
            return json.dumps({
                "hashtag": hashtag,
                "id": hashtag_data[0].get("id") if hashtag_data else None,
                "found": bool(hashtag_data),
            })
        except Exception as e:
            return _handle_error("instagram_search_hashtag", e)

    def get_hashtag_top_media(self, inp: dict) -> str:
        """Get top media for an Instagram hashtag. Requires a hashtag_id from instagram_search_hashtag."""
        permission_error, ig_id, hashtag_id = self._check(self.agent_id, self.PROVIDER_ID, "instagram_get_hashtag_top_media", inp, "instagram_id", "hashtag_id")
        if permission_error: return permission_error
        try:
            params = {
                "user_id": ig_id,
                "fields": "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count",
                "access_token": self._resolve_token(inp),
            }
            resp = httpx.get(f"{_BASE}/{hashtag_id}/top_media", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"hashtag_id": hashtag_id, "media": data.get("data", [])})
        except Exception as e:
            return _handle_error("instagram_get_hashtag_top_media", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        _page_token_param = {
            "page_access_token": {
                "type": "string",
                "description": (
                    "Access token for the Facebook Page linked to this Instagram account, obtained from "
                    "instagram_get_business_accounts(). Required for most calls; falls back to the "
                    "connector's user token if omitted, which may cause 401/403 errors."
                ),
            }
        }
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "instagram_get_business_accounts",
                    "description": "Discover Instagram Business or Creator accounts linked to the authenticated user's Facebook Pages. Returns instagram_id and page_access_token values needed for all other Instagram operations.",
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
                    "name": "instagram_get_account_info",
                    "description": "Get detailed profile information for an Instagram Business Account: username, bio, follower count, media count, and website.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "instagram_id": {"type": "string", "description": "The Instagram Business Account ID (obtained from instagram_get_business_accounts)."},
                            **_page_token_param,
                        },
                        "required": ["instagram_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "instagram_get_media",
                    "description": "Get recent media (photos, videos, reels, carousels) published by an Instagram Business Account, including captions, timestamps, like counts, and comment counts. Requires a page_access_token from instagram_get_business_accounts().",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "instagram_id": {"type": "string", "description": "Instagram Business Account ID."},
                            "limit": {"type": "integer", "description": "Number of media items to return (default 10, max 50)."},
                            "after": {"type": "string", "description": "Pagination cursor from a previous response (optional)."},
                            **_page_token_param,
                        },
                        "required": ["instagram_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "instagram_get_media_item",
                    "description": "Get full details of a single Instagram media item by its ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "media_id": {"type": "string", "description": "The Instagram media ID."},
                            **_page_token_param,
                        },
                        "required": ["media_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "instagram_get_media_comments",
                    "description": "Get comments on an Instagram media item, including replies. Requires a page_access_token from instagram_get_business_accounts().",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "media_id": {"type": "string", "description": "The Instagram media ID."},
                            "limit": {"type": "integer", "description": "Number of comments to return (default 25, max 50)."},
                            "after": {"type": "string", "description": "Pagination cursor (optional)."},
                            **_page_token_param,
                        },
                        "required": ["media_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "instagram_reply_to_comment",
                    "description": "Post a reply to a comment on an Instagram media item. Requires instagram_manage_comments scope and a page_access_token.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "comment_id": {"type": "string", "description": "The Instagram comment ID to reply to."},
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
                    "name": "instagram_delete_comment",
                    "description": "Delete a comment on an Instagram media item owned by the authenticated account.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "comment_id": {"type": "string", "description": "The Instagram comment ID to delete."},
                            **_page_token_param,
                        },
                        "required": ["comment_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "instagram_hide_comment",
                    "description": "Hide or unhide a comment on an Instagram media item.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "comment_id": {"type": "string", "description": "The Instagram comment ID to hide or unhide."},
                            "hide": {"type": "boolean", "description": "True to hide the comment, false to unhide it (default true)."},
                            **_page_token_param,
                        },
                        "required": ["comment_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "instagram_publish_photo_post",
                    "description": "Publish a photo post to an Instagram Business Account. The image must be at a publicly accessible URL. Requires instagram_content_publish scope and a page_access_token.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "instagram_id": {"type": "string", "description": "Instagram Business Account ID."},
                            "image_url": {"type": "string", "description": "Publicly accessible URL of the image to post (JPEG or PNG)."},
                            "caption": {"type": "string", "description": "Post caption text (optional, max 2200 chars)."},
                            "location_id": {"type": "string", "description": "Facebook Location page ID to tag a location (optional)."},
                            **_page_token_param,
                        },
                        "required": ["instagram_id", "image_url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "instagram_publish_reel",
                    "description": "Publish a Reel to an Instagram Business Account. The video must be at a publicly accessible URL (MP4). Requires instagram_content_publish scope and a page_access_token.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "instagram_id": {"type": "string", "description": "Instagram Business Account ID."},
                            "video_url": {"type": "string", "description": "Publicly accessible URL of the video file (MP4, H.264, max 15 min)."},
                            "caption": {"type": "string", "description": "Reel caption text (optional)."},
                            "share_to_feed": {"type": "boolean", "description": "Whether to also share the reel to the main feed (default true)."},
                            **_page_token_param,
                        },
                        "required": ["instagram_id", "video_url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "instagram_publish_carousel_post",
                    "description": "Publish a carousel post (2-10 photos and/or videos swiped through in a single post) to an Instagram Business Account. Each item's media must be at a publicly accessible URL. Requires instagram_content_publish scope and a page_access_token.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "instagram_id": {"type": "string", "description": "Instagram Business Account ID."},
                            "media_urls": {
                                "type": "array",
                                "description": "List of 2-10 media items. Each item can be a plain URL string (treated as an image) or an object like {\"url\": \"...\", \"media_type\": \"IMAGE\"|\"VIDEO\"}.",
                                "items": {
                                    "oneOf": [
                                        {"type": "string"},
                                        {
                                            "type": "object",
                                            "properties": {
                                                "url": {"type": "string"},
                                                "media_type": {"type": "string", "enum": ["IMAGE", "VIDEO"]},
                                            },
                                            "required": ["url"],
                                        },
                                    ]
                                },
                            },
                            "caption": {"type": "string", "description": "Post caption text (optional, max 2200 chars)."},
                            "location_id": {"type": "string", "description": "Facebook Location page ID to tag a location (optional)."},
                            **_page_token_param,
                        },
                        "required": ["instagram_id", "media_urls"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "instagram_get_media_insights",
                    "description": "Get performance insights for a specific Instagram media item: impressions, reach, likes, comments, shares, and saves. Requires a page_access_token.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "media_id": {"type": "string", "description": "The Instagram media ID."},
                            "metric": {"type": "string", "description": "Comma-separated metric names (default: 'impressions,reach,likes,comments,shares,saved,total_interactions')."},
                            **_page_token_param,
                        },
                        "required": ["media_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "instagram_get_account_insights",
                    "description": "Get account-level insights for an Instagram Business Account over a time period: impressions, reach, profile views, and follower count. Requires a page_access_token.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "instagram_id": {"type": "string", "description": "Instagram Business Account ID."},
                            "metric": {"type": "string", "description": "Comma-separated metric names (default: 'impressions,reach,profile_views,follower_count')."},
                            "period": {"type": "string", "description": "Aggregation period: 'day', 'week', 'days_28', 'month', 'lifetime' (default: 'day')."},
                            "since": {"type": "string", "description": "Unix timestamp or YYYY-MM-DD date string for the start of the range (optional)."},
                            "until": {"type": "string", "description": "Unix timestamp or YYYY-MM-DD date string for the end of the range (optional)."},
                            **_page_token_param,
                        },
                        "required": ["instagram_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "instagram_search_hashtag",
                    "description": "Search for an Instagram hashtag and get its ID, which can be used to browse top media for that hashtag.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "instagram_id": {"type": "string", "description": "Instagram Business Account ID (needed for scoping the search)."},
                            "hashtag": {"type": "string", "description": "The hashtag to search for, with or without '#' prefix (e.g. 'marketing' or '#marketing')."},
                            **_page_token_param,
                        },
                        "required": ["instagram_id", "hashtag"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "instagram_get_hashtag_top_media",
                    "description": "Get the top-performing recent media for an Instagram hashtag. First use instagram_search_hashtag to get the hashtag_id.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "instagram_id": {"type": "string", "description": "Instagram Business Account ID."},
                            "hashtag_id": {"type": "string", "description": "Hashtag ID from instagram_search_hashtag."},
                            **_page_token_param,
                        },
                        "required": ["instagram_id", "hashtag_id"],
                    },
                },
            },
        ]
        callables = {
            "instagram_get_business_accounts": self.get_business_accounts,
            "instagram_get_account_info": self.get_account_info,
            "instagram_get_media": self.get_media,
            "instagram_get_media_item": self.get_media_item,
            "instagram_get_media_comments": self.get_media_comments,
            "instagram_reply_to_comment": self.reply_to_comment,
            "instagram_delete_comment": self.delete_comment,
            "instagram_hide_comment": self.hide_comment,
            "instagram_publish_photo_post": self.publish_photo_post,
            "instagram_publish_reel": self.publish_reel,
            "instagram_publish_carousel_post": self.publish_carousel_post,
            "instagram_get_media_insights": self.get_media_insights,
            "instagram_get_account_insights": self.get_account_insights,
            "instagram_search_hashtag": self.search_hashtag,
            "instagram_get_hashtag_top_media": self.get_hashtag_top_media,
        }
        return tools, callables
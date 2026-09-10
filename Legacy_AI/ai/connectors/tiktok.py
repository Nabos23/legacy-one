import json
import httpx
from ai.connectors.base import BaseConnector

_BASE = "https://open.tiktokapis.com/v2"

def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected TikTok account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect the TikTok connector."
            )
        if e.response.status_code == 404:
            return f"Not found in {tool_name}: the requested resource does not exist."
        if e.response.status_code == 429:
            return f"Rate limit exceeded in {tool_name}: TikTok API rate limit hit, try again later."
        try:
            err_detail = e.response.json().get("error", {})
            return f"API error in {tool_name} (HTTP {e.response.status_code}): {err_detail}"
        except Exception:
            return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"



def _json_headers(token: str) -> dict:
    """TikTok API v2 requires Content-Type application/json for POST bodies."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }




class TikTokConnector(BaseConnector):
    """
    TikTok Content Posting API (v2) connector.
    Uses the TikTok OAuth 2.0 access token.
    """

    PROVIDER_ID = "tiktok"

    def get_user_info(self, inp: dict) -> str:
        """Get the authenticated TikTok user's basic profile information."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "tiktok_get_user_info", inp)
        if permission_error: return permission_error
        try:
            params = {
                "fields": "open_id,union_id,avatar_url,display_name,bio_description,profile_deep_link,is_verified,follower_count,following_count,likes_count,video_count",
            }
            resp = httpx.get(
                f"{_BASE}/user/info/",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error", {}).get("code", "ok") != "ok":
                return f"TikTok API error: {data['error']}"
            return json.dumps(data.get("data", {}).get("user", {}))
        except Exception as e:
            return _handle_error("tiktok_get_user_info", e)

    def get_user_videos(self, inp: dict) -> str:
        """List videos published by the authenticated TikTok user on their profile."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "tiktok_get_user_videos", inp)
        if permission_error: return permission_error
        try:
            body: dict = {
                "fields": ["id", "title", "video_description", "create_time", "cover_image_url",
                           "share_url", "view_count", "like_count", "comment_count", "share_count",
                           "duration", "height", "width"],
                "max_count": min(inp.get("max_count", 10), 20),
            }
            if inp.get("cursor"):
                body["cursor"] = inp["cursor"]
            resp = httpx.post(
                f"{_BASE}/video/list/",
                headers=_json_headers(self._token),
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error", {}).get("code", "ok") != "ok":
                return f"TikTok API error: {data['error']}"
            result = data.get("data", {})
            return json.dumps({
                "videos": result.get("videos", []),
                "cursor": result.get("cursor"),
                "has_more": result.get("has_more", False),
            })
        except Exception as e:
            return _handle_error("tiktok_get_user_videos", e)

    def query_video(self, inp: dict) -> str:
        """Get details for specific TikTok videos by their IDs."""
        permission_error, video_ids = self._check(self.agent_id, self.PROVIDER_ID, "tiktok_query_video", inp, "video_ids")
        if permission_error: return permission_error
        if isinstance(video_ids, str):
            video_ids = [v.strip() for v in video_ids.split(",") if v.strip()]
        try:
            body = {
                "filters": {"video_ids": video_ids},
                "fields": ["id", "title", "video_description", "create_time", "cover_image_url",
                           "share_url", "view_count", "like_count", "comment_count", "share_count",
                           "duration"],
            }
            resp = httpx.post(
                f"{_BASE}/video/query/",
                headers=_json_headers(self._token),
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error", {}).get("code", "ok") != "ok":
                return f"TikTok API error: {data['error']}"
            return json.dumps(data.get("data", {}).get("videos", []))
        except Exception as e:
            return _handle_error("tiktok_query_video", e)

    def initialize_video_upload(self, inp: dict) -> str:
        """
        Initialize a TikTok video upload session and get an upload URL.
        This is step 1 of the 3-step video publish flow:
        1. initialize_video_upload → get upload_url + publish_id
        2. Upload the video bytes to the upload_url (done externally)
        3. publish_video → finalize and post
        Requires video.upload scope.
        """
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "tiktok_initialize_video_upload", inp)
        if permission_error: return permission_error
        source = inp.get("source", "FILE_UPLOAD")  # FILE_UPLOAD or PULL_FROM_URL
        video_url = inp.get("video_url", "")
        if source == "PULL_FROM_URL" and not video_url:
            return "Error: 'video_url' is required when source is PULL_FROM_URL."
        try:
            body: dict = {"source_info": {"source": source}}
            if source == "FILE_UPLOAD":
                chunk_size = inp.get("chunk_size", 10 * 1024 * 1024)  # default 10 MB
                total_size = inp.get("total_bytes", 0)
                body["source_info"]["video_size"] = total_size
                body["source_info"]["chunk_size"] = chunk_size
                body["source_info"]["total_chunk_count"] = max(1, (total_size + chunk_size - 1) // chunk_size) if total_size else 1
            else:
                body["source_info"]["video_url"] = video_url
            resp = httpx.post(
                f"{_BASE}/post/publish/video/init/",
                headers=_json_headers(self._token),
                json=body,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error", {}).get("code", "ok") != "ok":
                return f"TikTok API error: {data['error']}"
            result = data.get("data", {})
            return json.dumps({
                "publish_id": result.get("publish_id"),
                "upload_url": result.get("upload_url"),
                "instructions": "Upload your video bytes to 'upload_url' using PUT, then call tiktok_publish_video with the publish_id.",
            })

        except Exception as e:

            return _handle_error("tiktok_initialize_video_upload", e)

    def publish_video(self, inp: dict) -> str:
        """
        Finalize and publish a TikTok video after upload is complete.
        Provide the publish_id from tiktok_initialize_video_upload.
        For direct URL publishing (PULL_FROM_URL source), pass video_url directly.
        Requires video.publish scope.
        """
        permission_error, title = self._check(self.agent_id, self.PROVIDER_ID, "tiktok_publish_video", inp, "title")
        if permission_error: return permission_error
        publish_id = inp.get("publish_id", "")
        video_url = inp.get("video_url", "")
        if not publish_id and not video_url:
            return "Error: Either 'publish_id' (from tiktok_initialize_video_upload) or 'video_url' (for direct URL post) is required."
        try:
            # Post info section
            post_info: dict = {
                "title": title,
                "privacy_level": inp.get("privacy_level", "PUBLIC_TO_EVERYONE"),
                "disable_duet": inp.get("disable_duet", False),
                "disable_comment": inp.get("disable_comment", False),
                "disable_stitch": inp.get("disable_stitch", False),
            }
            if inp.get("video_cover_timestamp_ms") is not None:
                post_info["video_cover_timestamp_ms"] = inp["video_cover_timestamp_ms"]
            source_info: dict = {}
            if video_url:
                source_info["source"] = "PULL_FROM_URL"
                source_info["video_url"] = video_url
            else:
                source_info["source"] = "FILE_UPLOAD"
            body: dict = {"post_info": post_info, "source_info": source_info}
            if publish_id:
                body["source_info"]["video_id"] = publish_id
            resp = httpx.post(
                f"{_BASE}/post/publish/video/init/" if video_url else f"{_BASE}/post/publish/",
                headers=_json_headers(self._token),
                json=body,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error", {}).get("code", "ok") != "ok":
                return f"TikTok API error: {data['error']}"
            result = data.get("data", {})
            return json.dumps({
                "publish_id": result.get("publish_id"),
                "status": "submitted",
                "note": "TikTok processes videos asynchronously. Use tiktok_check_publish_status to monitor progress.",
            })
        except Exception as e:
            return _handle_error("tiktok_publish_video", e)

    def check_publish_status(self, inp: dict) -> str:
        """Check the processing status of a TikTok video publish job."""
        permission_error, publish_id = self._check(self.agent_id, self.PROVIDER_ID, "tiktok_check_publish_status", inp, "publish_id")
        if permission_error: return permission_error
        try:
            body = {"publish_id": publish_id}
            resp = httpx.post(
                f"{_BASE}/post/publish/status/fetch/",
                headers=_json_headers(self._token),
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error", {}).get("code", "ok") != "ok":
                return f"TikTok API error: {data['error']}"
            result = data.get("data", {})
            return json.dumps({
                "publish_id": publish_id,
                "status": result.get("status"),
                "publicaly_available_post_id": result.get("publicaly_available_post_id"),
                "fail_reason": result.get("fail_reason"),
                "uploaded_bytes": result.get("uploaded_bytes"),
                "total_bytes": result.get("total_bytes"),
            })
        except Exception as e:
            return _handle_error("tiktok_check_publish_status", e)

    def get_user_followers(self, inp: dict) -> str:
        """Get a list of accounts that follow the authenticated TikTok user. Requires user.info.stats scope."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "tiktok_get_user_followers", inp)
        if permission_error: return permission_error
        try:
            params: dict = {
                "fields": "open_id,union_id,avatar_url,display_name,bio_description,is_verified",
                "max_count": min(inp.get("max_count", 20), 100),
            }
            if inp.get("cursor"):
                params["cursor"] = inp["cursor"]
            resp = httpx.get(
                f"{_BASE}/user/followers/",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error", {}).get("code", "ok") != "ok":
                return f"TikTok API error: {data['error']}"
            result = data.get("data", {})
            return json.dumps({
                "followers": result.get("user_followers", []),
                "cursor": result.get("cursor"),
                "has_more": result.get("has_more", False),
                "total": result.get("total_number"),
            })
        except Exception as e:
            return _handle_error("tiktok_get_user_followers", e)

    def get_user_following(self, inp: dict) -> str:
        """Get a list of accounts the authenticated TikTok user is following. Requires user.info.stats scope."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "tiktok_get_user_following", inp)
        if permission_error: return permission_error
        try:
            params: dict = {
                "fields": "open_id,union_id,avatar_url,display_name,bio_description,is_verified",
                "max_count": min(inp.get("max_count", 20), 100),
            }
            if inp.get("cursor"):
                params["cursor"] = inp["cursor"]
            resp = httpx.get(
                f"{_BASE}/user/following/",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error", {}).get("code", "ok") != "ok":
                return f"TikTok API error: {data['error']}"
            result = data.get("data", {})
            return json.dumps({
                "following": result.get("user_following", []),
                "cursor": result.get("cursor"),
                "has_more": result.get("has_more", False),
                "total": result.get("total_number"),
            })
        except Exception as e:
            return _handle_error("tiktok_get_user_following", e)

    def get_creator_info(self, inp: dict) -> str:
        """
        Get the authenticated creator's content posting eligibility and settings.
        Returns privacy options, comment settings, and duet/stitch availability.
        Requires video.publish scope.
        """
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "tiktok_get_creator_info", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/post/publish/creator_info/query/",
                headers=_json_headers(self._token),
                json={},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error", {}).get("code", "ok") != "ok":
                return f"TikTok API error: {data['error']}"
            return json.dumps(data.get("data", {}))
        except Exception as e:
            return _handle_error("tiktok_get_creator_info", e)


    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "tiktok_get_user_info",
                    "description": "Get the authenticated TikTok user's profile: display name, bio, follower count, following count, likes count, video count, and verification status.",
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
                    "name": "tiktok_get_user_videos",
                    "description": "List videos published on the authenticated TikTok user's profile, including titles, descriptions, view counts, likes, comments, shares, and duration.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "max_count": {"type": "integer", "description": "Number of videos to return (default 10, max 20)."},
                            "cursor": {"type": "integer", "description": "Pagination cursor from a previous response for fetching the next page (optional)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tiktok_query_video",
                    "description": "Get details for one or more specific TikTok videos by their video IDs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "video_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of TikTok video IDs to query (max 20 per request).",
                            },
                        },
                        "required": ["video_ids"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tiktok_initialize_video_upload",
                    "description": (
                        "Initialize a TikTok video upload session. For direct URL publishing (recommended): set source='PULL_FROM_URL' and provide video_url. "
                        "For file uploads: set source='FILE_UPLOAD' with total_bytes and chunk_size, then upload to the returned upload_url. "
                        "Returns a publish_id needed to call tiktok_publish_video. Requires video.upload scope."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string", "description": "'PULL_FROM_URL' (preferred, video downloaded from URL) or 'FILE_UPLOAD' (default: 'FILE_UPLOAD')."},
                            "video_url": {"type": "string", "description": "Publicly accessible video URL — required if source is 'PULL_FROM_URL'."},
                            "total_bytes": {"type": "integer", "description": "Total video file size in bytes — required if source is 'FILE_UPLOAD'."},
                            "chunk_size": {"type": "integer", "description": "Chunk size in bytes for chunked upload (default 10 MB). Only used for FILE_UPLOAD."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tiktok_publish_video",
                    "description": (
                        "Publish a TikTok video. For URL-based publishing: provide video_url and title. "
                        "For file uploads: provide publish_id from tiktok_initialize_video_upload after uploading the file. "
                        "Requires video.publish scope."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Video caption/title (required, max 2200 chars, can include hashtags)."},
                            "video_url": {"type": "string", "description": "Publicly accessible video URL for PULL_FROM_URL publishing (mutually exclusive with publish_id)."},
                            "publish_id": {"type": "string", "description": "Publish ID from tiktok_initialize_video_upload for FILE_UPLOAD publishing (mutually exclusive with video_url)."},
                            "privacy_level": {"type": "string", "description": "Privacy: 'PUBLIC_TO_EVERYONE', 'MUTUAL_FOLLOW_FRIENDS', 'FOLLOWER_OF_CREATOR', 'SELF_ONLY' (default 'PUBLIC_TO_EVERYONE')."},
                            "disable_duet": {"type": "boolean", "description": "Disable duet for this video (default false)."},
                            "disable_comment": {"type": "boolean", "description": "Disable comments on this video (default false)."},
                            "disable_stitch": {"type": "boolean", "description": "Disable stitch for this video (default false)."},
                        },
                        "required": ["title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tiktok_check_publish_status",
                    "description": "Check the processing/upload status of a TikTok video publish job. TikTok processes videos asynchronously after submission.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "publish_id": {"type": "string", "description": "The publish_id returned by tiktok_initialize_video_upload or tiktok_publish_video."},
                        },
                        "required": ["publish_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tiktok_get_user_followers",
                    "description": "Get a list of TikTok accounts that follow the authenticated user. Requires user.info.stats scope.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "max_count": {"type": "integer", "description": "Number of followers to return (default 20, max 100)."},
                            "cursor": {"type": "integer", "description": "Pagination cursor from a previous response (optional)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tiktok_get_user_following",
                    "description": "Get a list of TikTok accounts the authenticated user is following. Requires user.info.stats scope.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "max_count": {"type": "integer", "description": "Number of followed accounts to return (default 20, max 100)."},
                            "cursor": {"type": "integer", "description": "Pagination cursor from a previous response (optional)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tiktok_get_creator_info",
                    "description": "Get the authenticated TikTok creator's eligibility and content settings: available privacy options, whether duet/stitch/comments are allowed, and content disclosure requirements. Requires video.publish scope.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
        ]

        callables = {
            "tiktok_get_user_info": self.get_user_info,
            "tiktok_get_user_videos": self.get_user_videos,
            "tiktok_query_video": self.query_video,
            "tiktok_initialize_video_upload": self.initialize_video_upload,
            "tiktok_publish_video": self.publish_video,
            "tiktok_check_publish_status": self.check_publish_status,
            "tiktok_get_user_followers": self.get_user_followers,
            "tiktok_get_user_following": self.get_user_following,
            "tiktok_get_creator_info": self.get_creator_info,
        }


        return tools, callables

import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.twitter.com/2"

_USER_FIELDS = "id,name,username,description,profile_image_url,public_metrics,verified"
_TWEET_FIELDS = "id,text,created_at,author_id,public_metrics,entities,attachments"
_EXPANSIONS = "author_id"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        if e.response.status_code == 429:
            return f"Rate limit exceeded in {tool_name}: Twitter API rate limit hit, try again later."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class TwitterConnector(BaseConnector):
    """Twitter/X API v2 connector for reading and writing tweets, users, followers, and likes."""

    PROVIDER_ID = "twitter"

    def _get_own_user_id(self) -> str:
        """Fetch the authenticated user's numeric ID."""
        resp = httpx.get(f"{_BASE}/users/me", headers=self._auth_headers, params={"user.fields": "id"}, timeout=15)
        resp.raise_for_status()
        return resp.json()["data"]["id"]

    def get_me(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "twitter_get_me", inp)
        if permission_error: return permission_error
        try:
            params = {"user.fields": _USER_FIELDS}
            resp = httpx.get(f"{_BASE}/users/me", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json().get("data", {}))
        except Exception as e:
            return _handle_error("twitter_get_me", e)

    def get_user_tweets(self, inp: dict) -> str:
        permission_error, user_id = self._check(self.agent_id, self.PROVIDER_ID, "twitter_get_user_tweets", inp, "user_id")
        if permission_error: return permission_error
        try:
            params = {
                "tweet.fields": _TWEET_FIELDS,
                "max_results": min(inp.get("max_results", 10), 100),
            }
            if inp.get("pagination_token"):
                params["pagination_token"] = inp["pagination_token"]
            resp = httpx.get(f"{_BASE}/users/{user_id}/tweets", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"tweets": data.get("data", []), "meta": data.get("meta", {})})
        except Exception as e:
            return _handle_error("twitter_get_user_tweets", e)

    def search_recent_tweets(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "twitter_search_recent_tweets", inp, "query")
        if permission_error: return permission_error
        try:
            params = {
                "query": query,
                "tweet.fields": _TWEET_FIELDS,
                "expansions": _EXPANSIONS,
                "user.fields": "id,name,username",
                "max_results": min(inp.get("max_results", 10), 100),
            }
            if inp.get("next_token"):
                params["next_token"] = inp["next_token"]
            resp = httpx.get(f"{_BASE}/tweets/search/recent", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "tweets": data.get("data", []),
                "includes": data.get("includes", {}),
                "meta": data.get("meta", {}),
            })
        except Exception as e:
            return _handle_error("twitter_search_recent_tweets", e)

    def get_tweet(self, inp: dict) -> str:
        permission_error, tweet_id = self._check(self.agent_id, self.PROVIDER_ID, "twitter_get_tweet", inp, "tweet_id")
        if permission_error: return permission_error
        try:
            params = {
                "tweet.fields": _TWEET_FIELDS,
                "expansions": _EXPANSIONS,
                "user.fields": "id,name,username,profile_image_url",
            }
            resp = httpx.get(f"{_BASE}/tweets/{tweet_id}", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"tweet": data.get("data", {}), "includes": data.get("includes", {})})
        except Exception as e:
            return _handle_error("twitter_get_tweet", e)

    def get_followers(self, inp: dict) -> str:
        permission_error, user_id = self._check(self.agent_id, self.PROVIDER_ID, "twitter_get_followers", inp, "user_id")
        if permission_error: return permission_error
        try:
            params = {
                "user.fields": _USER_FIELDS,
                "max_results": min(inp.get("max_results", 100), 1000),
            }
            if inp.get("pagination_token"):
                params["pagination_token"] = inp["pagination_token"]
            resp = httpx.get(f"{_BASE}/users/{user_id}/followers", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"followers": data.get("data", []), "meta": data.get("meta", {})})
        except Exception as e:
            return _handle_error("twitter_get_followers", e)

    def get_following(self, inp: dict) -> str:
        permission_error, user_id = self._check(self.agent_id, self.PROVIDER_ID, "twitter_get_following", inp, "user_id")
        if permission_error: return permission_error
        try:
            params = {
                "user.fields": _USER_FIELDS,
                "max_results": min(inp.get("max_results", 100), 1000),
            }
            if inp.get("pagination_token"):
                params["pagination_token"] = inp["pagination_token"]
            resp = httpx.get(f"{_BASE}/users/{user_id}/following", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"following": data.get("data", []), "meta": data.get("meta", {})})
        except Exception as e:
            return _handle_error("twitter_get_following", e)

    def get_liked_tweets(self, inp: dict) -> str:
        permission_error, user_id = self._check(self.agent_id, self.PROVIDER_ID, "twitter_get_liked_tweets", inp, "user_id")
        if permission_error: return permission_error
        try:
            params = {
                "tweet.fields": _TWEET_FIELDS,
                "expansions": _EXPANSIONS,
                "user.fields": "id,name,username",
                "max_results": min(inp.get("max_results", 10), 100),
            }
            if inp.get("pagination_token"):
                params["pagination_token"] = inp["pagination_token"]
            resp = httpx.get(f"{_BASE}/users/{user_id}/liked_tweets", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"liked_tweets": data.get("data", []), "meta": data.get("meta", {})})
        except Exception as e:
            return _handle_error("twitter_get_liked_tweets", e)

    def get_bookmarks(self, inp: dict) -> str:
        permission_error, user_id = self._check(self.agent_id, self.PROVIDER_ID, "twitter_get_bookmarks", inp, "user_id")
        if permission_error: return permission_error
        try:
            params = {
                "tweet.fields": _TWEET_FIELDS,
                "expansions": _EXPANSIONS,
                "user.fields": "id,name,username",
                "max_results": min(inp.get("max_results", 10), 100),
            }
            if inp.get("pagination_token"):
                params["pagination_token"] = inp["pagination_token"]
            resp = httpx.get(f"{_BASE}/users/{user_id}/bookmarks", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"bookmarks": data.get("data", []), "meta": data.get("meta", {})})
        except Exception as e:
            return _handle_error("twitter_get_bookmarks", e)

    def create_tweet(self, inp: dict) -> str:
        """Requires OAuth2 user token (not app-only bearer token)."""
        permission_error, text = self._check(self.agent_id, self.PROVIDER_ID, "twitter_create_tweet", inp, "text")
        if permission_error: return permission_error
        try:
            body: dict = {"text": text}
            if inp.get("reply_settings"):
                body["reply_settings"] = inp["reply_settings"]
            if inp.get("in_reply_to_tweet_id"):
                body["reply"] = {"in_reply_to_tweet_id": inp["in_reply_to_tweet_id"]}
            resp = httpx.post(f"{_BASE}/tweets", headers=self._auth_headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return json.dumps({"id": data.get("id"), "text": data.get("text")})
        except Exception as e:
            return _handle_error("twitter_create_tweet", e)

    def delete_tweet(self, inp: dict) -> str:
        """Requires OAuth2 user token (not app-only bearer token)."""
        permission_error, tweet_id = self._check(self.agent_id, self.PROVIDER_ID, "twitter_delete_tweet", inp, "id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/tweets/{tweet_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return json.dumps({"deleted": data.get("deleted", False), "id": tweet_id})
        except Exception as e:
            return _handle_error("twitter_delete_tweet", e)

    def like_tweet(self, inp: dict) -> str:
        """Requires OAuth2 user token (not app-only bearer token)."""
        permission_error, tweet_id = self._check(self.agent_id, self.PROVIDER_ID, "twitter_like_tweet", inp, "tweet_id")
        if permission_error: return permission_error
        try:
            user_id = inp.get("user_id") or self._get_own_user_id()
            resp = httpx.post(
                f"{_BASE}/users/{user_id}/likes",
                headers=self._auth_headers,
                json={"tweet_id": tweet_id},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return json.dumps({"liked": data.get("liked", False), "tweet_id": tweet_id})
        except Exception as e:
            return _handle_error("twitter_like_tweet", e)

    def unlike_tweet(self, inp: dict) -> str:
        """Requires OAuth2 user token (not app-only bearer token)."""
        permission_error, tweet_id = self._check(self.agent_id, self.PROVIDER_ID, "twitter_unlike_tweet", inp, "tweet_id")
        if permission_error: return permission_error
        try:
            user_id = inp.get("user_id") or self._get_own_user_id()
            resp = httpx.delete(
                f"{_BASE}/users/{user_id}/likes/{tweet_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return json.dumps({"liked": data.get("liked", False), "tweet_id": tweet_id})
        except Exception as e:
            return _handle_error("twitter_unlike_tweet", e)

    def retweet(self, inp: dict) -> str:
        """Requires OAuth2 user token (not app-only bearer token)."""
        permission_error, tweet_id = self._check(self.agent_id, self.PROVIDER_ID, "twitter_retweet", inp, "tweet_id")
        if permission_error: return permission_error
        try:
            user_id = inp.get("user_id") or self._get_own_user_id()
            resp = httpx.post(
                f"{_BASE}/users/{user_id}/retweets",
                headers=self._auth_headers,
                json={"tweet_id": tweet_id},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return json.dumps({"retweeted": data.get("retweeted", False), "tweet_id": tweet_id})
        except Exception as e:
            return _handle_error("twitter_retweet", e)

    def follow_user(self, inp: dict) -> str:
        """Requires OAuth2 user token (not app-only bearer token)."""
        permission_error, target_user_id = self._check(self.agent_id, self.PROVIDER_ID, "twitter_follow_user", inp, "target_user_id")
        if permission_error: return permission_error
        try:
            user_id = inp.get("user_id") or self._get_own_user_id()
            resp = httpx.post(
                f"{_BASE}/users/{user_id}/following",
                headers=self._auth_headers,
                json={"target_user_id": target_user_id},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return json.dumps({
                "following": data.get("following", False),
                "pending_follow": data.get("pending_follow", False),
                "target_user_id": target_user_id,
            })
        except Exception as e:
            return _handle_error("twitter_follow_user", e)

    def get_mentions(self, inp: dict) -> str:
        permission_error, user_id = self._check(self.agent_id, self.PROVIDER_ID, "twitter_get_mentions", inp, "user_id")
        if permission_error: return permission_error
        try:
            params = {
                "tweet.fields": _TWEET_FIELDS,
                "max_results": min(inp.get("max_results", 10), 100),
            }
            if inp.get("pagination_token"):
                params["pagination_token"] = inp["pagination_token"]
            resp = httpx.get(f"{_BASE}/users/{user_id}/mentions", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"mentions": data.get("data", []), "meta": data.get("meta", {})})
        except Exception as e:
            return _handle_error("twitter_get_mentions", e)

    def unfollow_user(self, inp: dict) -> str:
        """Requires OAuth2 user token (not app-only bearer token)."""
        permission_error, target_user_id = self._check(self.agent_id, self.PROVIDER_ID, "twitter_unfollow_user", inp, "target_user_id")
        if permission_error: return permission_error
        try:
            user_id = inp.get("user_id") or self._get_own_user_id()
            resp = httpx.delete(
                f"{_BASE}/users/{user_id}/following/{target_user_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return json.dumps({"following": data.get("following", False), "target_user_id": target_user_id})
        except Exception as e:
            return _handle_error("twitter_unfollow_user", e)

    def hide_reply(self, inp: dict) -> str:
        """Requires OAuth2 user token (not app-only bearer token)."""
        permission_error, tweet_id = self._check(self.agent_id, self.PROVIDER_ID, "twitter_hide_reply", inp, "tweet_id")
        if permission_error: return permission_error
        hidden = inp.get("hidden", True)
        try:
            resp = httpx.put(
                f"{_BASE}/tweets/{tweet_id}/hidden",
                headers=self._auth_headers,
                json={"hidden": hidden},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return json.dumps({"tweet_id": tweet_id, "hidden": data.get("hidden", hidden)})
        except Exception as e:
            return _handle_error("twitter_hide_reply", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "twitter_get_me",
                    "description": "Get the authenticated user's Twitter/X profile including name, username, bio, and public metrics.",
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
                    "name": "twitter_get_user_tweets",
                    "description": "Get recent tweets posted by a specific Twitter/X user by their numeric user ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "Numeric Twitter user ID (e.g. '44196397'). Use twitter_get_me to get the authenticated user's ID."},
                            "max_results": {"type": "integer", "description": "Number of tweets to return (1-100, default 10)."},
                            "pagination_token": {"type": "string", "description": "Token from a previous response meta.next_token for pagination (optional)."},
                        },
                        "required": ["user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twitter_search_recent_tweets",
                    "description": "Search recent tweets (last 7 days) using Twitter query syntax. Supports keywords, hashtags, mentions, and operators like 'from:username' or '#hashtag'.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Twitter search query, e.g. '#AI lang:en -is:retweet' or 'from:elonmusk'."},
                            "max_results": {"type": "integer", "description": "Number of tweets to return (10-100, default 10)."},
                            "next_token": {"type": "string", "description": "Pagination token from a previous response meta.next_token (optional)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twitter_get_tweet",
                    "description": "Get full details of a single tweet by its ID, including text, metrics, and author info.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tweet_id": {"type": "string", "description": "Numeric tweet ID (e.g. '1234567890123456789')."},
                        },
                        "required": ["tweet_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twitter_get_followers",
                    "description": "Get a list of users who follow a given Twitter/X account.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "Numeric Twitter user ID whose followers to retrieve."},
                            "max_results": {"type": "integer", "description": "Number of followers to return (1-1000, default 100)."},
                            "pagination_token": {"type": "string", "description": "Pagination token from a previous response (optional)."},
                        },
                        "required": ["user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twitter_get_following",
                    "description": "Get a list of accounts that a given Twitter/X user follows.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "Numeric Twitter user ID whose following list to retrieve."},
                            "max_results": {"type": "integer", "description": "Number of accounts to return (1-1000, default 100)."},
                            "pagination_token": {"type": "string", "description": "Pagination token from a previous response (optional)."},
                        },
                        "required": ["user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twitter_get_liked_tweets",
                    "description": "Get tweets liked by a specific Twitter/X user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "Numeric Twitter user ID whose liked tweets to retrieve."},
                            "max_results": {"type": "integer", "description": "Number of liked tweets to return (1-100, default 10)."},
                            "pagination_token": {"type": "string", "description": "Pagination token from a previous response (optional)."},
                        },
                        "required": ["user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twitter_get_bookmarks",
                    "description": "Get tweets bookmarked by the authenticated Twitter/X user (requires bookmark.read scope).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "Numeric Twitter user ID (must be the authenticated user's own ID)."},
                            "max_results": {"type": "integer", "description": "Number of bookmarks to return (1-100, default 10)."},
                            "pagination_token": {"type": "string", "description": "Pagination token from a previous response (optional)."},
                        },
                        "required": ["user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twitter_create_tweet",
                    "description": "Post a new tweet. Can optionally reply to another tweet or set reply settings. Requires OAuth2 user token (not app-only bearer token).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "The text content of the tweet (required, max 280 chars)."},
                            "reply_settings": {"type": "string", "description": "Who can reply: 'mentionedUsers' or 'subscribers' (optional, default everyone)."},
                            "in_reply_to_tweet_id": {"type": "string", "description": "Tweet ID to reply to (optional)."},
                        },
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twitter_delete_tweet",
                    "description": "Delete a tweet by its ID. Only the authenticated user's own tweets can be deleted. Requires OAuth2 user token.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Numeric tweet ID to delete (required)."},
                        },
                        "required": ["id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twitter_like_tweet",
                    "description": "Like a tweet on behalf of the authenticated user. Requires OAuth2 user token (not app-only bearer token).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tweet_id": {"type": "string", "description": "Numeric tweet ID to like (required)."},
                            "user_id": {"type": "string", "description": "Numeric user ID of the authenticated user (optional, fetched automatically if omitted)."},
                        },
                        "required": ["tweet_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twitter_unlike_tweet",
                    "description": "Remove a like from a tweet on behalf of the authenticated user. Requires OAuth2 user token.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tweet_id": {"type": "string", "description": "Numeric tweet ID to unlike (required)."},
                            "user_id": {"type": "string", "description": "Numeric user ID of the authenticated user (optional, fetched automatically if omitted)."},
                        },
                        "required": ["tweet_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twitter_retweet",
                    "description": "Retweet a tweet on behalf of the authenticated user. Requires OAuth2 user token (not app-only bearer token).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tweet_id": {"type": "string", "description": "Numeric tweet ID to retweet (required)."},
                            "user_id": {"type": "string", "description": "Numeric user ID of the authenticated user (optional, fetched automatically if omitted)."},
                        },
                        "required": ["tweet_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twitter_follow_user",
                    "description": "Follow a Twitter/X user on behalf of the authenticated user. Requires OAuth2 user token (not app-only bearer token).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target_user_id": {"type": "string", "description": "Numeric user ID of the account to follow (required)."},
                            "user_id": {"type": "string", "description": "Numeric user ID of the authenticated user (optional, fetched automatically if omitted)."},
                        },
                        "required": ["target_user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twitter_get_mentions",
                    "description": "Get tweets that mention a specific Twitter/X user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "Numeric Twitter user ID whose mentions to retrieve."},
                            "max_results": {"type": "integer", "description": "Number of mentions to return (1-100, default 10)."},
                            "pagination_token": {"type": "string", "description": "Pagination token from a previous response (optional)."},
                        },
                        "required": ["user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twitter_unfollow_user",
                    "description": "Unfollow a Twitter/X user on behalf of the authenticated user. Requires OAuth2 user token.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target_user_id": {"type": "string", "description": "Numeric user ID of the account to unfollow (required)."},
                            "user_id": {"type": "string", "description": "Numeric user ID of the authenticated user (optional, fetched automatically if omitted)."},
                        },
                        "required": ["target_user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twitter_hide_reply",
                    "description": "Hide or unhide a reply to a tweet authored by the authenticated user. Requires OAuth2 user token.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tweet_id": {"type": "string", "description": "The reply tweet ID to hide or unhide (required)."},
                            "hidden": {"type": "boolean", "description": "True to hide the reply, false to unhide it (default true)."},
                        },
                        "required": ["tweet_id"],
                    },
                },
            },
        ]
        callables = {
            "twitter_get_me": self.get_me,
            "twitter_get_user_tweets": self.get_user_tweets,
            "twitter_search_recent_tweets": self.search_recent_tweets,
            "twitter_get_tweet": self.get_tweet,
            "twitter_get_followers": self.get_followers,
            "twitter_get_following": self.get_following,
            "twitter_get_liked_tweets": self.get_liked_tweets,
            "twitter_get_bookmarks": self.get_bookmarks,
            "twitter_create_tweet": self.create_tweet,
            "twitter_delete_tweet": self.delete_tweet,
            "twitter_like_tweet": self.like_tweet,
            "twitter_unlike_tweet": self.unlike_tweet,
            "twitter_retweet": self.retweet,
            "twitter_follow_user": self.follow_user,
            "twitter_get_mentions": self.get_mentions,
            "twitter_unfollow_user": self.unfollow_user,
            "twitter_hide_reply": self.hide_reply,
        }
        return tools, callables

import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://graph.microsoft.com/v1.0"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Microsoft Teams account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Teams connector with the required OAuth scopes."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


def _json_headers(auth_headers: dict) -> dict:
    return {**auth_headers, "Content-Type": "application/json"}


class TeamsConnector(BaseConnector):

    PROVIDER_ID = "teams"

    # ── Me ────────────────────────────────────────────────────────────────────

    def get_me(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "teams_get_me", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/me", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("teams_get_me", e)

    # ── Teams ─────────────────────────────────────────────────────────────────

    def list_teams(self, inp: dict) -> str:
        """List all Microsoft Teams the user has joined."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "teams_list_teams", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/me/joinedTeams", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            teams = [{"id": t["id"], "displayName": t.get("displayName"), "description": t.get("description")} for t in data.get("value", [])]
            return json.dumps(teams)
        except Exception as e:
            return _handle_error("teams_list_teams", e)

    def list_team_members(self, inp: dict) -> str:
        permission_error, team_id = self._check(self.agent_id, self.PROVIDER_ID, "teams_list_team_members", inp, "team_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/teams/{team_id}/members", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("teams_list_team_members", e)

    def get_team(self, inp: dict) -> str:
        """Get the full details of a specific Microsoft Team."""
        permission_error, team_id = self._check(self.agent_id, self.PROVIDER_ID, "teams_get_team", inp, "team_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/teams/{team_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data.get("id"),
                "displayName": data.get("displayName"),
                "description": data.get("description"),
                "visibility": data.get("visibility"),
                "isArchived": data.get("isArchived"),
                "webUrl": data.get("webUrl"),
            })
        except Exception as e:
            return _handle_error("teams_get_team", e)

    # ── Channels ─────────────────────────────────────────────────────────────

    def list_channels(self, inp: dict) -> str:
        """List channels within a specific team."""
        permission_error, team_id = self._check(self.agent_id, self.PROVIDER_ID, "teams_list_channels", inp, "team_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/teams/{team_id}/channels", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            channels = [{"id": c["id"], "displayName": c.get("displayName"), "description": c.get("description")} for c in data.get("value", [])]
            return json.dumps(channels)
        except Exception as e:
            return _handle_error("teams_list_channels", e)

    def get_channel(self, inp: dict) -> str:
        """Get the details of a specific channel within a team."""
        permission_error, team_id, channel_id = self._check(self.agent_id, self.PROVIDER_ID, "teams_get_channel", inp, "team_id", "channel_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/teams/{team_id}/channels/{channel_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data.get("id"),
                "displayName": data.get("displayName"),
                "description": data.get("description"),
                "membershipType": data.get("membershipType"),
                "webUrl": data.get("webUrl"),
            })
        except Exception as e:
            return _handle_error("teams_get_channel", e)

    def list_channel_members(self, inp: dict) -> str:
        """List all members of a specific channel (useful for private/shared channels)."""
        permission_error, team_id, channel_id = self._check(self.agent_id, self.PROVIDER_ID, "teams_list_channel_members", inp, "team_id", "channel_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/teams/{team_id}/channels/{channel_id}/members",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            members = [
                {"id": m.get("id"), "displayName": m.get("displayName"), "roles": m.get("roles", [])}
                for m in data.get("value", [])
            ]
            return json.dumps(members)
        except Exception as e:
            return _handle_error("teams_list_channel_members", e)

    def list_channel_tabs(self, inp: dict) -> str:
        """List all tabs (apps pinned to the top) in a Teams channel."""
        permission_error, team_id, channel_id = self._check(self.agent_id, self.PROVIDER_ID, "teams_list_channel_tabs", inp, "team_id", "channel_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/teams/{team_id}/channels/{channel_id}/tabs",
                headers=self._auth_headers,
                params={"$expand": "teamsApp"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            tabs = [
                {
                    "id": t.get("id"),
                    "displayName": t.get("displayName"),
                    "webUrl": t.get("webUrl"),
                    "teamsAppName": t.get("teamsApp", {}).get("displayName"),
                }
                for t in data.get("value", [])
            ]
            return json.dumps(tabs)
        except Exception as e:
            return _handle_error("teams_list_channel_tabs", e)

    def get_channel_messages(self, inp: dict) -> str:
        permission_error, team_id, channel_id = self._check(self.agent_id, self.PROVIDER_ID, "teams_get_channel_messages", inp, "team_id", "channel_id")
        if permission_error: return permission_error
        try:
            top = inp.get("top", 20)
            resp = httpx.get(
                f"{_BASE}/teams/{team_id}/channels/{channel_id}/messages",
                headers=self._auth_headers,
                params={"$top": top},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            messages = [
                {
                    "id": m["id"],
                    "from": m.get("from", {}).get("user", {}).get("displayName"),
                    "body": m.get("body", {}).get("content", "")[:2000],
                    "createdDateTime": m.get("createdDateTime"),
                    "replies_count": m.get("replies", []),
                }
                for m in data.get("value", [])
            ]
            return json.dumps(messages)
        except Exception as e:
            return _handle_error("teams_get_channel_messages", e)

    def get_message_replies(self, inp: dict) -> str:
        permission_error, team_id, channel_id, message_id = self._check(self.agent_id, self.PROVIDER_ID, "teams_get_message_replies", inp, "team_id", "channel_id", "message_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("teams_get_message_replies", e)

    def send_channel_message(self, inp: dict) -> str:
        permission_error, team_id, channel_id, text = self._check(self.agent_id, self.PROVIDER_ID, "teams_send_channel_message", inp, "team_id", "channel_id", "text")
        if permission_error: return permission_error
        content_type = "html" if inp.get("html") else "text"
        try:
            resp = httpx.post(
                f"{_BASE}/teams/{team_id}/channels/{channel_id}/messages",
                headers=_json_headers(self._auth_headers),
                json={"body": {"contentType": content_type, "content": text}},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("teams_send_channel_message", e)

    def reply_to_message(self, inp: dict) -> str:
        permission_error, team_id, channel_id, message_id, text = self._check(self.agent_id, self.PROVIDER_ID, "teams_reply_to_message", inp, "team_id", "channel_id", "message_id", "text")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies",
                headers=_json_headers(self._auth_headers),
                json={"body": {"contentType": "text", "content": text}},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("teams_reply_to_message", e)

    def update_channel_message(self, inp: dict) -> str:
        permission_error, team_id, channel_id, message_id, content = self._check(self.agent_id, self.PROVIDER_ID, "teams_update_channel_message", inp, "team_id", "channel_id", "message_id", "content")
        if permission_error: return permission_error
        try:
            resp = httpx.patch(
                f"{_BASE}/teams/{team_id}/channels/{channel_id}/messages/{message_id}",
                headers=_json_headers(self._auth_headers),
                json={"body": {"content": content}},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("teams_update_channel_message", e)

    def delete_channel_message(self, inp: dict) -> str:
        permission_error, team_id, channel_id, message_id = self._check(self.agent_id, self.PROVIDER_ID, "teams_delete_channel_message", inp, "team_id", "channel_id", "message_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(
                f"{_BASE}/teams/{team_id}/channels/{channel_id}/messages/{message_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"deleted": True, "message_id": message_id})
        except Exception as e:
            return _handle_error("teams_delete_channel_message", e)

    def add_message_reaction(self, inp: dict) -> str:
        permission_error, team_id, channel_id, message_id, reaction_type = self._check(self.agent_id, self.PROVIDER_ID, "teams_add_message_reaction", inp, "team_id", "channel_id", "message_id", "reaction_type")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/teams/{team_id}/channels/{channel_id}/messages/{message_id}/reactions",
                headers=_json_headers(self._auth_headers),
                json={"reactionType": reaction_type},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"status": "reaction_added", "reaction_type": reaction_type, "message_id": message_id})
        except Exception as e:
            return _handle_error("teams_add_message_reaction", e)

    def create_channel(self, inp: dict) -> str:
        permission_error, team_id, display_name = self._check(self.agent_id, self.PROVIDER_ID, "teams_create_channel", inp, "team_id", "display_name")
        if permission_error: return permission_error
        try:
            payload: dict = {
                "displayName": display_name,
                "membershipType": inp.get("membership_type", "standard"),
            }
            if inp.get("description"):
                payload["description"] = inp["description"]
            resp = httpx.post(
                f"{_BASE}/teams/{team_id}/channels",
                headers=_json_headers(self._auth_headers),
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "displayName": data.get("displayName"), "membershipType": data.get("membershipType")})
        except Exception as e:
            return _handle_error("teams_create_channel", e)

    def list_team_apps(self, inp: dict) -> str:
        permission_error, team_id = self._check(self.agent_id, self.PROVIDER_ID, "teams_list_team_apps", inp, "team_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/teams/{team_id}/installedApps",
                headers=self._auth_headers,
                params={"$expand": "teamsApp"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            apps = [
                {
                    "id": a.get("id"),
                    "teamsApp": {
                        "id": a.get("teamsApp", {}).get("id"),
                        "displayName": a.get("teamsApp", {}).get("displayName"),
                        "distributionMethod": a.get("teamsApp", {}).get("distributionMethod"),
                    },
                }
                for a in data.get("value", [])
            ]
            return json.dumps(apps)
        except Exception as e:
            return _handle_error("teams_list_team_apps", e)

    def create_online_meeting(self, inp: dict) -> str:
        permission_error, subject, start_datetime, end_datetime = self._check(self.agent_id, self.PROVIDER_ID, "teams_create_online_meeting", inp, "subject", "start_datetime", "end_datetime")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/me/onlineMeetings",
                headers=_json_headers(self._auth_headers),
                json={"subject": subject, "startDateTime": start_datetime, "endDateTime": end_datetime},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data.get("id"),
                "joinWebUrl": data.get("joinWebUrl"),
                "subject": data.get("subject"),
                "startDateTime": data.get("startDateTime"),
                "endDateTime": data.get("endDateTime"),
            })
        except Exception as e:
            return _handle_error("teams_create_online_meeting", e)

    # ── Chats (Direct Messages) ───────────────────────────────────────────────

    def list_chats(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "teams_list_chats", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/me/chats",
                headers=self._auth_headers,
                params={"$expand": "members", "$top": inp.get("top", 20)},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            chats = [
                {
                    "id": c["id"],
                    "chatType": c.get("chatType"),
                    "topic": c.get("topic"),
                    "members": [m.get("displayName") for m in c.get("members", [])],
                }
                for c in data.get("value", [])
            ]
            return json.dumps(chats)
        except Exception as e:
            return _handle_error("teams_list_chats", e)

    def create_chat(self, inp: dict) -> str:
        """Create a new 1:1 or group chat with other users (the signed-in user is added automatically)."""
        permission_error, user_ids = self._check(self.agent_id, self.PROVIDER_ID, "teams_create_chat", inp, "user_ids")
        if permission_error: return permission_error
        if not isinstance(user_ids, list):
            return "Error: 'user_ids' must be a list of user IDs."
        try:
            me_resp = httpx.get(f"{_BASE}/me", headers=self._auth_headers, timeout=15)
            me_resp.raise_for_status()
            me_id = me_resp.json().get("id")
            members = [
                {
                    "@odata.type": "#microsoft.graph.aadUserConversationMember",
                    "roles": ["owner"],
                    "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{me_id}')",
                }
            ]
            for uid in user_ids:
                members.append({
                    "@odata.type": "#microsoft.graph.aadUserConversationMember",
                    "roles": ["owner"],
                    "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{uid}')",
                })
            chat_type = "group" if len(user_ids) > 1 or inp.get("topic") else "oneOnOne"
            payload: dict = {"chatType": chat_type, "members": members}
            if inp.get("topic"):
                payload["topic"] = inp["topic"]
            resp = httpx.post(f"{_BASE}/chats", headers=_json_headers(self._auth_headers), json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "chatType": data.get("chatType"), "topic": data.get("topic")})
        except Exception as e:
            return _handle_error("teams_create_chat", e)

    def list_chat_members(self, inp: dict) -> str:
        """List all members of a direct message or group chat."""
        permission_error, chat_id = self._check(self.agent_id, self.PROVIDER_ID, "teams_list_chat_members", inp, "chat_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/chats/{chat_id}/members", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            members = [
                {"id": m.get("id"), "displayName": m.get("displayName"), "roles": m.get("roles", [])}
                for m in data.get("value", [])
            ]
            return json.dumps(members)
        except Exception as e:
            return _handle_error("teams_list_chat_members", e)

    def get_chat_messages(self, inp: dict) -> str:
        permission_error, chat_id = self._check(self.agent_id, self.PROVIDER_ID, "teams_get_chat_messages", inp, "chat_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/me/chats/{chat_id}/messages",
                headers=self._auth_headers,
                params={"$top": inp.get("top", 25)},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            messages = [
                {
                    "id": m["id"],
                    "from": m.get("from", {}).get("user", {}).get("displayName"),
                    "body": m.get("body", {}).get("content", "")[:2000],
                    "createdDateTime": m.get("createdDateTime"),
                }
                for m in data.get("value", [])
            ]
            return json.dumps(messages)
        except Exception as e:
            return _handle_error("teams_get_chat_messages", e)

    def send_chat_message(self, inp: dict) -> str:
        permission_error, chat_id, text = self._check(self.agent_id, self.PROVIDER_ID, "teams_send_chat_message", inp, "chat_id", "text")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/me/chats/{chat_id}/messages",
                headers=_json_headers(self._auth_headers),
                json={"body": {"contentType": "text", "content": text}},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("teams_send_chat_message", e)
            resp = httpx.post(
                f"{_BASE}/me/chats/{chat_id}/messages",
                headers=_json_headers(self._auth_headers),
                json={"body": {"contentType": "text", "content": text}},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("teams_send_chat_message", e)

    # ── Tool manifest ─────────────────────────────────────────────────────────

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "teams_get_me",
                    "description": "Get the signed-in user's Microsoft profile (display name, email, job title).",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_list_teams",
                    "description": "List all Microsoft Teams the signed-in user has joined.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_list_team_members",
                    "description": "List all members of a specific Microsoft Team.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The Teams team ID."},
                        },
                        "required": ["team_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_get_team",
                    "description": "Get full details (name, description, visibility, archived status) of a specific Microsoft Team.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The Teams team ID."},
                        },
                        "required": ["team_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_list_channels",
                    "description": "List all channels within a specific Microsoft Team.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The Teams team ID."},
                        },
                        "required": ["team_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_get_channel",
                    "description": "Get the details of a specific channel within a Microsoft Team.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The Teams team ID."},
                            "channel_id": {"type": "string", "description": "The channel ID."},
                        },
                        "required": ["team_id", "channel_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_list_channel_members",
                    "description": "List members of a specific Teams channel (most useful for private or shared channels, which can have a different membership than the team).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The Teams team ID."},
                            "channel_id": {"type": "string", "description": "The channel ID."},
                        },
                        "required": ["team_id", "channel_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_list_channel_tabs",
                    "description": "List the tabs (pinned apps/files/websites) configured in a Teams channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The Teams team ID."},
                            "channel_id": {"type": "string", "description": "The channel ID."},
                        },
                        "required": ["team_id", "channel_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_get_channel_messages",
                    "description": "Fetch recent messages from a Teams channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The Teams team ID."},
                            "channel_id": {"type": "string", "description": "The channel ID."},
                            "top": {"type": "integer", "description": "Max messages to return (default 20)."},
                        },
                        "required": ["team_id", "channel_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_get_message_replies",
                    "description": "Get all replies to a specific message in a Teams channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The Teams team ID."},
                            "channel_id": {"type": "string", "description": "The channel ID."},
                            "message_id": {"type": "string", "description": "The message ID."},
                        },
                        "required": ["team_id", "channel_id", "message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_send_channel_message",
                    "description": "Send a message to a Microsoft Teams channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The Teams team ID."},
                            "channel_id": {"type": "string", "description": "The channel ID."},
                            "text": {"type": "string", "description": "Message text (plain text or HTML)."},
                            "html": {"type": "boolean", "description": "Set to true if text is HTML (default false)."},
                        },
                        "required": ["team_id", "channel_id", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_reply_to_message",
                    "description": "Reply to an existing message in a Teams channel thread.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The Teams team ID."},
                            "channel_id": {"type": "string", "description": "The channel ID."},
                            "message_id": {"type": "string", "description": "The message ID to reply to."},
                            "text": {"type": "string", "description": "Reply text."},
                        },
                        "required": ["team_id", "channel_id", "message_id", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_update_channel_message",
                    "description": "Edit/update the content of an existing message in a Teams channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The Teams team ID."},
                            "channel_id": {"type": "string", "description": "The channel ID."},
                            "message_id": {"type": "string", "description": "The message ID to update."},
                            "content": {"type": "string", "description": "New message content."},
                        },
                        "required": ["team_id", "channel_id", "message_id", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_delete_channel_message",
                    "description": "Soft-delete a message in a Teams channel (Graph API soft-deletes; returns success on 204).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The Teams team ID."},
                            "channel_id": {"type": "string", "description": "The channel ID."},
                            "message_id": {"type": "string", "description": "The message ID to delete."},
                        },
                        "required": ["team_id", "channel_id", "message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_add_message_reaction",
                    "description": "Add a reaction (like, heart, laugh, surprised, sad, angry) to a Teams channel message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The Teams team ID."},
                            "channel_id": {"type": "string", "description": "The channel ID."},
                            "message_id": {"type": "string", "description": "The message ID."},
                            "reaction_type": {"type": "string", "description": "Reaction type: like, heart, laugh, surprised, sad, or angry."},
                        },
                        "required": ["team_id", "channel_id", "message_id", "reaction_type"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_create_channel",
                    "description": "Create a new channel in a Microsoft Team.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The Teams team ID."},
                            "display_name": {"type": "string", "description": "Name of the new channel."},
                            "description": {"type": "string", "description": "Optional description for the channel."},
                            "membership_type": {"type": "string", "description": "Channel type: standard or private (default standard)."},
                        },
                        "required": ["team_id", "display_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_list_team_apps",
                    "description": "List all apps installed in a Microsoft Team.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "team_id": {"type": "string", "description": "The Teams team ID."},
                        },
                        "required": ["team_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_create_online_meeting",
                    "description": "Create a new Microsoft Teams online meeting and get the join URL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string", "description": "Meeting subject/title."},
                            "start_datetime": {"type": "string", "description": "Meeting start time in ISO 8601 format (e.g. 2024-01-15T10:00:00Z)."},
                            "end_datetime": {"type": "string", "description": "Meeting end time in ISO 8601 format (e.g. 2024-01-15T11:00:00Z)."},
                        },
                        "required": ["subject", "start_datetime", "end_datetime"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_list_chats",
                    "description": "List the signed-in user's direct message chats (1:1 and group chats).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "top": {"type": "integer", "description": "Max chats to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_create_chat",
                    "description": "Create a new 1:1 or group chat with other users. The signed-in user is added automatically; only list the other participants.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Azure AD object IDs of the other users to add to the chat (do not include the signed-in user).",
                            },
                            "topic": {"type": "string", "description": "Optional chat title. Providing this forces a group chat even with a single other member."},
                        },
                        "required": ["user_ids"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_list_chat_members",
                    "description": "List the members of a direct message or group chat.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "The chat ID from teams_list_chats."},
                        },
                        "required": ["chat_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_get_chat_messages",
                    "description": "Fetch messages from a direct message or group chat.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "The chat ID from teams_list_chats."},
                            "top": {"type": "integer", "description": "Max messages to return (default 25)."},
                        },
                        "required": ["chat_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "teams_send_chat_message",
                    "description": "Send a message in a direct message or group chat.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "The chat ID from teams_list_chats."},
                            "text": {"type": "string", "description": "Message text."},
                        },
                        "required": ["chat_id", "text"],
                    },
                },
            },
        ]
        callables = {
            "teams_get_me": self.get_me,
            "teams_list_teams": self.list_teams,
            "teams_list_team_members": self.list_team_members,
            "teams_list_channels": self.list_channels,
            "teams_get_channel_messages": self.get_channel_messages,
            "teams_get_message_replies": self.get_message_replies,
            "teams_send_channel_message": self.send_channel_message,
            "teams_reply_to_message": self.reply_to_message,
            "teams_update_channel_message": self.update_channel_message,
            "teams_delete_channel_message": self.delete_channel_message,
            "teams_add_message_reaction": self.add_message_reaction,
            "teams_create_channel": self.create_channel,
            "teams_list_team_apps": self.list_team_apps,
            "teams_create_online_meeting": self.create_online_meeting,
            "teams_list_chats": self.list_chats,
            "teams_get_chat_messages": self.get_chat_messages,
            "teams_send_chat_message": self.send_chat_message,
        }
        return tools, callables

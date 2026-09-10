import json
import logging
import urllib.parse
import httpx

logger = logging.getLogger(__name__)

from ai.connectors.base import BaseConnector

_BASE = "https://discord.com/api/v10"

def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Discord bot lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ensure the bot has the required permissions in the server."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class DiscordConnector(BaseConnector):

    PROVIDER_ID = "discord"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id=agent_id)
        self._auth_headers = {"Authorization": f"Bot {access_token}", "Accept": "application/json"}

    def list_guilds(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "discord_list_guilds", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/users/@me/guilds", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            guilds = [{"id": g["id"], "name": g["name"], "owner": g.get("owner", False)} for g in resp.json()]
            return json.dumps(guilds)
        except Exception as e:
            return _handle_error("discord_list_guilds", e)

    def list_channels(self, inp: dict) -> str:
        permission_error, guild_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_list_channels", inp, "guild_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/guilds/{guild_id}/channels", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            channels = [
                {"id": c["id"], "name": c["name"], "type": c["type"], "position": c.get("position")}
                for c in resp.json()
                if c.get("type") in (0, 5)
            ]
            return json.dumps(sorted(channels, key=lambda x: x.get("position", 0)))
        except Exception as e:
            return _handle_error("discord_list_channels", e)

    def get_messages(self, inp: dict) -> str:
        permission_error, channel_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_get_messages", inp, "channel_id")
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            resp = httpx.get(f"{_BASE}/channels/{channel_id}/messages", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            messages = [
                {
                    "id": m["id"],
                    "author": m.get("author", {}).get("username"),
                    "content": m.get("content", ""),
                    "timestamp": m.get("timestamp"),
                }
                for m in resp.json()
            ]
            return json.dumps(messages)
        except Exception as e:
            return _handle_error("discord_get_messages", e)

    def send_message(self, inp: dict) -> str:
        permission_error, channel_id, content = self._check(self.agent_id, self.PROVIDER_ID, "discord_send_message", inp, "channel_id", "content")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"content": content}
            if inp.get("reply_to"):
                body["message_reference"] = {"message_id": inp["reply_to"]}
            resp = httpx.post(f"{_BASE}/channels/{channel_id}/messages", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "channel_id": channel_id, "status": "sent"})
        except Exception as e:
            return _handle_error("discord_send_message", e)

    def get_guild_members(self, inp: dict) -> str:
        permission_error, guild_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_get_guild_members", inp, "guild_id")
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 50)}
            resp = httpx.get(f"{_BASE}/guilds/{guild_id}/members", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            members = [
                {"id": m["user"]["id"], "username": m["user"].get("username"), "nick": m.get("nick"), "roles": m.get("roles", [])}
                for m in resp.json()
            ]
            return json.dumps(members)
        except Exception as e:
            return _handle_error("discord_get_guild_members", e)

    def get_channel(self, inp: dict) -> str:
        permission_error, channel_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_get_channel", inp, "channel_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/channels/{channel_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data["id"],
                "name": data.get("name"),
                "type": data.get("type"),
                "guild_id": data.get("guild_id"),
                "topic": data.get("topic"),
                "position": data.get("position"),
                "nsfw": data.get("nsfw", False),
            })
        except Exception as e:
            return _handle_error("discord_get_channel", e)

    def edit_message(self, inp: dict) -> str:
        permission_error, channel_id, message_id, content = self._check(self.agent_id, self.PROVIDER_ID, "discord_edit_message", inp, "channel_id", "message_id", "content")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.patch(
                f"{_BASE}/channels/{channel_id}/messages/{message_id}",
                headers=headers,
                json={"content": content},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "channel_id": channel_id, "content": data.get("content"), "status": "edited"})
        except Exception as e:
            return _handle_error("discord_edit_message", e)

    def delete_message(self, inp: dict) -> str:
        permission_error, channel_id, message_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_delete_message", inp, "channel_id", "message_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(
                f"{_BASE}/channels/{channel_id}/messages/{message_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"message_id": message_id, "channel_id": channel_id, "status": "deleted"})
        except Exception as e:
            return _handle_error("discord_delete_message", e)

    def add_reaction(self, inp: dict) -> str:
        permission_error, channel_id, message_id, emoji = self._check(self.agent_id, self.PROVIDER_ID, "discord_add_reaction", inp, "channel_id", "message_id", "emoji")
        if permission_error: return permission_error
        try:
            encoded_emoji = urllib.parse.quote(emoji, safe="")
            resp = httpx.put(
                f"{_BASE}/channels/{channel_id}/messages/{message_id}/reactions/{encoded_emoji}/@me",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"message_id": message_id, "emoji": emoji, "status": "reaction_added"})
        except Exception as e:
            return _handle_error("discord_add_reaction", e)

    def remove_reaction(self, inp: dict) -> str:
        permission_error, channel_id, message_id, emoji = self._check(self.agent_id, self.PROVIDER_ID, "discord_remove_reaction", inp, "channel_id", "message_id", "emoji")
        if permission_error: return permission_error
        try:
            encoded_emoji = urllib.parse.quote(emoji, safe="")
            resp = httpx.delete(
                f"{_BASE}/channels/{channel_id}/messages/{message_id}/reactions/{encoded_emoji}/@me",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"message_id": message_id, "emoji": emoji, "status": "reaction_removed"})
        except Exception as e:
            return _handle_error("discord_remove_reaction", e)

    def get_guild_roles(self, inp: dict) -> str:
        permission_error, guild_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_get_guild_roles", inp, "guild_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/guilds/{guild_id}/roles", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            roles = [
                {"id": r["id"], "name": r["name"], "color": r.get("color"), "position": r.get("position")}
                for r in resp.json()
            ]
            return json.dumps(sorted(roles, key=lambda x: x.get("position", 0), reverse=True))
        except Exception as e:
            return _handle_error("discord_get_guild_roles", e)

    def create_thread(self, inp: dict) -> str:
        permission_error, channel_id, name, content = self._check(self.agent_id, self.PROVIDER_ID, "discord_create_thread", inp, "channel_id", "name", "content")
        if permission_error: return permission_error
        auto_archive_duration = inp.get("auto_archive_duration", 1440)
        if auto_archive_duration not in (60, 1440, 4320, 10080):
            return "Error: 'auto_archive_duration' must be one of 60, 1440, 4320, or 10080."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "name": name,
                "message": {"content": content},
                "auto_archive_duration": auto_archive_duration,
            }
            resp = httpx.post(f"{_BASE}/channels/{channel_id}/threads", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "name": data.get("name"), "parent_id": data.get("parent_id"), "status": "created"})
        except Exception as e:
            return _handle_error("discord_create_thread", e)

    def get_guild_info(self, inp: dict) -> str:
        permission_error, guild_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_get_guild_info", inp, "guild_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/guilds/{guild_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data["id"],
                "name": data.get("name"),
                "icon": data.get("icon"),
                "owner_id": data.get("owner_id"),
                "member_count": data.get("approximate_member_count"),
            })
        except Exception as e:
            return _handle_error("discord_get_guild_info", e)

    def create_dm(self, inp: dict) -> str:
        permission_error, recipient_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_create_dm", inp, "recipient_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{_BASE}/users/@me/channels",
                headers=headers,
                json={"recipient_id": recipient_id},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"channel_id": data["id"], "recipient_id": recipient_id, "status": "dm_opened"})
        except Exception as e:
            return _handle_error("discord_create_dm", e)

    def send_embed(self, inp: dict) -> str:
        permission_error, channel_id, title = self._check(self.agent_id, self.PROVIDER_ID, "discord_send_embed", inp, "channel_id", "title")
        if permission_error: return permission_error
        description = inp.get("description", "")
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            embed: dict = {"title": title}
            if description:
                embed["description"] = description
            if "color" in inp:
                embed["color"] = int(inp["color"])
            if inp.get("fields"):
                embed["fields"] = [{"name": f["name"], "value": f["value"]} for f in inp["fields"]]
            body = {"embeds": [embed]}
            resp = httpx.post(f"{_BASE}/channels/{channel_id}/messages", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "channel_id": channel_id, "status": "embed_sent"})
        except Exception as e:
            return _handle_error("discord_send_embed", e)

    def create_channel(self, inp: dict) -> str:
        permission_error, guild_id, name = self._check(self.agent_id, self.PROVIDER_ID, "discord_create_channel", inp, "guild_id", "name")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {"name": name, "type": inp.get("type", 0)}
            if inp.get("topic"):
                body["topic"] = inp["topic"]
            if inp.get("parent_id"):
                body["parent_id"] = inp["parent_id"]
            resp = httpx.post(f"{_BASE}/guilds/{guild_id}/channels", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "name": data.get("name"), "type": data.get("type"), "status": "created"})
        except Exception as e:
            return _handle_error("discord_create_channel", e)

    def remove_guild_member(self, inp: dict) -> str:
        permission_error, guild_id, user_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_remove_guild_member", inp, "guild_id", "user_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/guilds/{guild_id}/members/{user_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"guild_id": guild_id, "user_id": user_id, "status": "kicked"})
        except Exception as e:
            return _handle_error("discord_remove_guild_member", e)

    def add_member_role(self, inp: dict) -> str:
        permission_error, guild_id, user_id, role_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_add_member_role", inp, "guild_id", "user_id", "role_id")
        if permission_error: return permission_error
        try:
            resp = httpx.put(
                f"{_BASE}/guilds/{guild_id}/members/{user_id}/roles/{role_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"guild_id": guild_id, "user_id": user_id, "role_id": role_id, "status": "role_added"})
        except Exception as e:
            return _handle_error("discord_add_member_role", e)

    def remove_member_role(self, inp: dict) -> str:
        permission_error, guild_id, user_id, role_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_remove_member_role", inp, "guild_id", "user_id", "role_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(
                f"{_BASE}/guilds/{guild_id}/members/{user_id}/roles/{role_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"guild_id": guild_id, "user_id": user_id, "role_id": role_id, "status": "role_removed"})
        except Exception as e:
            return _handle_error("discord_remove_member_role", e)

    def get_message(self, inp: dict) -> str:
        permission_error, channel_id, message_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_get_message", inp, "channel_id", "message_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/channels/{channel_id}/messages/{message_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data["id"],
                "author": data.get("author", {}).get("username"),
                "content": data.get("content", ""),
                "timestamp": data.get("timestamp"),
                "pinned": data.get("pinned", False),
            })
        except Exception as e:
            return _handle_error("discord_get_message", e)

    def bulk_delete_messages(self, inp: dict) -> str:
        permission_error, channel_id, message_ids = self._check(self.agent_id, self.PROVIDER_ID, "discord_bulk_delete_messages", inp, "channel_id", "message_ids")
        if permission_error: return permission_error
        if not (2 <= len(message_ids) <= 100):
            return "Error: 'message_ids' must contain between 2 and 100 IDs (Discord bulk-delete limit). Messages older than 14 days can't be bulk-deleted."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{_BASE}/channels/{channel_id}/messages/bulk-delete",
                headers=headers,
                json={"messages": message_ids},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"channel_id": channel_id, "deleted_count": len(message_ids), "status": "bulk_deleted"})
        except Exception as e:
            return _handle_error("discord_bulk_delete_messages", e)

    def pin_message(self, inp: dict) -> str:
        permission_error, channel_id, message_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_pin_message", inp, "channel_id", "message_id")
        if permission_error: return permission_error
        try:
            resp = httpx.put(
                f"{_BASE}/channels/{channel_id}/pins/{message_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"channel_id": channel_id, "message_id": message_id, "status": "pinned"})
        except Exception as e:
            return _handle_error("discord_pin_message", e)

    def unpin_message(self, inp: dict) -> str:
        permission_error, channel_id, message_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_unpin_message", inp, "channel_id", "message_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(
                f"{_BASE}/channels/{channel_id}/pins/{message_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"channel_id": channel_id, "message_id": message_id, "status": "unpinned"})
        except Exception as e:
            return _handle_error("discord_unpin_message", e)

    def get_pinned_messages(self, inp: dict) -> str:
        permission_error, channel_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_get_pinned_messages", inp, "channel_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/channels/{channel_id}/pins", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", data if isinstance(data, list) else [])
            messages = [
                {
                    "id": (it.get("message") or it)["id"],
                    "author": (it.get("message") or it).get("author", {}).get("username"),
                    "content": (it.get("message") or it).get("content", ""),
                }
                for it in items
            ]
            return json.dumps(messages)
        except Exception as e:
            return _handle_error("discord_get_pinned_messages", e)

    def edit_channel(self, inp: dict) -> str:
        permission_error, channel_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_edit_channel", inp, "channel_id")
        if permission_error: return permission_error
        body: dict = {}
        if "name" in inp:
            body["name"] = inp["name"]
        if "topic" in inp:
            body["topic"] = inp["topic"]
        if "nsfw" in inp:
            body["nsfw"] = inp["nsfw"]
        if not body:
            return "Error: provide at least one of 'name', 'topic', or 'nsfw' to update."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.patch(f"{_BASE}/channels/{channel_id}", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "name": data.get("name"), "topic": data.get("topic"), "status": "updated"})
        except Exception as e:
            return _handle_error("discord_edit_channel", e)

    def delete_channel(self, inp: dict) -> str:
        permission_error, channel_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_delete_channel", inp, "channel_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/channels/{channel_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"channel_id": channel_id, "status": "deleted"})
        except Exception as e:
            return _handle_error("discord_delete_channel", e)

    def ban_member(self, inp: dict) -> str:
        permission_error, guild_id, user_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_ban_member", inp, "guild_id", "user_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body: dict = {}
            if inp.get("delete_message_seconds"):
                body["delete_message_seconds"] = min(int(inp["delete_message_seconds"]), 604800)
            resp = httpx.put(
                f"{_BASE}/guilds/{guild_id}/bans/{user_id}",
                headers=headers,
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"guild_id": guild_id, "user_id": user_id, "status": "banned"})
        except Exception as e:
            return _handle_error("discord_ban_member", e)

    def unban_member(self, inp: dict) -> str:
        permission_error, guild_id, user_id = self._check(self.agent_id, self.PROVIDER_ID, "discord_unban_member", inp, "guild_id", "user_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/guilds/{guild_id}/bans/{user_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"guild_id": guild_id, "user_id": user_id, "status": "unbanned"})
        except Exception as e:
            return _handle_error("discord_unban_member", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "discord_list_guilds",
                    "description": "List all Discord servers (guilds) the bot is a member of.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_list_channels",
                    "description": "List text channels in a Discord server.",
                    "parameters": {
                        "type": "object",
                        "properties": {"guild_id": {"type": "string", "description": "The Discord server (guild) ID."}},
                        "required": ["guild_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_get_messages",
                    "description": "Get recent messages from a Discord channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID."},
                            "limit": {"type": "integer", "description": "Max messages to return (default 20)."},
                        },
                        "required": ["channel_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_send_message",
                    "description": "Send a message to a Discord channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID."},
                            "content": {"type": "string", "description": "Message content to send."},
                            "reply_to": {"type": "string", "description": "Optional message ID to reply to."},
                        },
                        "required": ["channel_id", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_get_guild_members",
                    "description": "List members of a Discord server.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "guild_id": {"type": "string", "description": "The Discord server ID."},
                            "limit": {"type": "integer", "description": "Max members to return (default 50)."},
                        },
                        "required": ["guild_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_get_channel",
                    "description": "Get information about a Discord channel including its name, type, topic, and position.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID."},
                        },
                        "required": ["channel_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_edit_message",
                    "description": "Edit the content of an existing message sent by the bot.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID."},
                            "message_id": {"type": "string", "description": "The ID of the message to edit."},
                            "content": {"type": "string", "description": "The new message content."},
                        },
                        "required": ["channel_id", "message_id", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_delete_message",
                    "description": "Delete a message from a Discord channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID."},
                            "message_id": {"type": "string", "description": "The ID of the message to delete."},
                        },
                        "required": ["channel_id", "message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_add_reaction",
                    "description": "Add a reaction emoji to a Discord message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID."},
                            "message_id": {"type": "string", "description": "The ID of the message to react to."},
                            "emoji": {"type": "string", "description": "The emoji to react with (e.g. '👍' or 'name:id' for custom emojis)."},
                        },
                        "required": ["channel_id", "message_id", "emoji"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_remove_reaction",
                    "description": "Remove the bot's reaction emoji from a Discord message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID."},
                            "message_id": {"type": "string", "description": "The ID of the message."},
                            "emoji": {"type": "string", "description": "The emoji reaction to remove (e.g. '👍' or 'name:id' for custom emojis)."},
                        },
                        "required": ["channel_id", "message_id", "emoji"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_get_guild_roles",
                    "description": "List all roles in a Discord server with their id, name, color, and position.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "guild_id": {"type": "string", "description": "The Discord server (guild) ID."},
                        },
                        "required": ["guild_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_create_thread",
                    "description": "Create a new thread in a Discord channel with an initial message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID to create the thread in."},
                            "name": {"type": "string", "description": "The name of the thread."},
                            "content": {"type": "string", "description": "The initial message content for the thread."},
                            "auto_archive_duration": {
                                "type": "integer",
                                "description": "Minutes until the thread auto-archives. Must be one of: 60, 1440, 4320, 10080 (default 1440).",
                                "enum": [60, 1440, 4320, 10080],
                            },
                        },
                        "required": ["channel_id", "name", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_get_guild_info",
                    "description": "Get information about a Discord server including its name, icon, owner, and approximate member count.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "guild_id": {"type": "string", "description": "The Discord server (guild) ID."},
                        },
                        "required": ["guild_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_create_dm",
                    "description": "Open a Direct Message channel with a Discord user and return the DM channel ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "recipient_id": {"type": "string", "description": "The Discord user ID to open a DM with."},
                        },
                        "required": ["recipient_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_send_embed",
                    "description": "Send a rich embed message to a Discord channel with a title, description, color, and optional fields.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID."},
                            "title": {"type": "string", "description": "The embed title."},
                            "description": {"type": "string", "description": "The embed description text."},
                            "color": {"type": "integer", "description": "The embed color as a decimal integer (e.g. 5814783 for blue)."},
                            "fields": {
                                "type": "array",
                                "description": "Optional list of fields to include in the embed.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string", "description": "Field name/title."},
                                        "value": {"type": "string", "description": "Field value/body."},
                                    },
                                    "required": ["name", "value"],
                                },
                            },
                        },
                        "required": ["channel_id", "title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_create_channel",
                    "description": "Create a new channel in a Discord server.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "guild_id": {"type": "string", "description": "The Discord server (guild) ID."},
                            "name": {"type": "string", "description": "Name for the new channel."},
                            "type": {"type": "integer", "description": "Channel type: 0 = text, 2 = voice, 4 = category, 5 = announcement (default 0)."},
                            "topic": {"type": "string", "description": "Optional channel topic."},
                            "parent_id": {"type": "string", "description": "Optional category channel ID to nest this channel under."},
                        },
                        "required": ["guild_id", "name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_remove_guild_member",
                    "description": "Kick (remove) a member from a Discord server.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "guild_id": {"type": "string", "description": "The Discord server (guild) ID."},
                            "user_id": {"type": "string", "description": "The Discord user ID to kick."},
                        },
                        "required": ["guild_id", "user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_add_member_role",
                    "description": "Assign a role to a member of a Discord server.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "guild_id": {"type": "string", "description": "The Discord server (guild) ID."},
                            "user_id": {"type": "string", "description": "The Discord user ID to assign the role to."},
                            "role_id": {"type": "string", "description": "The Discord role ID to assign."},
                        },
                        "required": ["guild_id", "user_id", "role_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_remove_member_role",
                    "description": "Remove a role from a member of a Discord server.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "guild_id": {"type": "string", "description": "The Discord server (guild) ID."},
                            "user_id": {"type": "string", "description": "The Discord user ID to remove the role from."},
                            "role_id": {"type": "string", "description": "The Discord role ID to remove."},
                        },
                        "required": ["guild_id", "user_id", "role_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_get_message",
                    "description": "Fetch a single message from a Discord channel by its ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID."},
                            "message_id": {"type": "string", "description": "The ID of the message to fetch."},
                        },
                        "required": ["channel_id", "message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_bulk_delete_messages",
                    "description": "Delete multiple messages (2-100) from a Discord channel in one request. Only messages newer than 14 days can be bulk-deleted.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID."},
                            "message_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of 2-100 message IDs to delete.",
                            },
                        },
                        "required": ["channel_id", "message_ids"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_pin_message",
                    "description": "Pin a message in a Discord channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID."},
                            "message_id": {"type": "string", "description": "The ID of the message to pin."},
                        },
                        "required": ["channel_id", "message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_unpin_message",
                    "description": "Unpin a message in a Discord channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID."},
                            "message_id": {"type": "string", "description": "The ID of the message to unpin."},
                        },
                        "required": ["channel_id", "message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_get_pinned_messages",
                    "description": "List all pinned messages in a Discord channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID."},
                        },
                        "required": ["channel_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_edit_channel",
                    "description": "Update a Discord channel's name, topic, or NSFW flag.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID to edit."},
                            "name": {"type": "string", "description": "New channel name."},
                            "topic": {"type": "string", "description": "New channel topic."},
                            "nsfw": {"type": "boolean", "description": "Whether the channel should be marked NSFW."},
                        },
                        "required": ["channel_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_delete_channel",
                    "description": "Permanently delete a Discord channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel_id": {"type": "string", "description": "The Discord channel ID to delete."},
                        },
                        "required": ["channel_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_ban_member",
                    "description": "Ban a member from a Discord server, optionally deleting their recent messages.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "guild_id": {"type": "string", "description": "The Discord server (guild) ID."},
                            "user_id": {"type": "string", "description": "The Discord user ID to ban."},
                            "delete_message_seconds": {
                                "type": "integer",
                                "description": "Delete the user's messages from the last N seconds (max 604800 = 7 days). Omit to keep messages.",
                            },
                        },
                        "required": ["guild_id", "user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "discord_unban_member",
                    "description": "Remove a ban for a user in a Discord server.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "guild_id": {"type": "string", "description": "The Discord server (guild) ID."},
                            "user_id": {"type": "string", "description": "The Discord user ID to unban."},
                        },
                        "required": ["guild_id", "user_id"],
                    },
                },
            },
        ]
        callables = {
            "discord_list_guilds": self.list_guilds,
            "discord_list_channels": self.list_channels,
            "discord_get_messages": self.get_messages,
            "discord_send_message": self.send_message,
            "discord_get_guild_members": self.get_guild_members,
            "discord_get_channel": self.get_channel,
            "discord_edit_message": self.edit_message,
            "discord_delete_message": self.delete_message,
            "discord_add_reaction": self.add_reaction,
            "discord_remove_reaction": self.remove_reaction,
            "discord_get_guild_roles": self.get_guild_roles,
            "discord_create_thread": self.create_thread,
            "discord_get_guild_info": self.get_guild_info,
            "discord_create_dm": self.create_dm,
            "discord_send_embed": self.send_embed,
            "discord_create_channel": self.create_channel,
            "discord_remove_guild_member": self.remove_guild_member,
            "discord_add_member_role": self.add_member_role,
            "discord_remove_member_role": self.remove_member_role,
            "discord_get_message": self.get_message,
            "discord_bulk_delete_messages": self.bulk_delete_messages,
            "discord_pin_message": self.pin_message,
            "discord_unpin_message": self.unpin_message,
            "discord_get_pinned_messages": self.get_pinned_messages,
            "discord_edit_channel": self.edit_channel,
            "discord_delete_channel": self.delete_channel,
            "discord_ban_member": self.ban_member,
            "discord_unban_member": self.unban_member,
        }
        return tools, callables

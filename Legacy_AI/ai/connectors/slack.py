import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://slack.com/api"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Slack workspace lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Slack connector with the required OAuth scopes."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


def _slack_post(url: str, headers: dict, payload: dict) -> dict:
    resp = httpx.post(url, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _check_ok(data: dict, tool_name: str) -> str | None:
    """Return an error string if Slack returned ok=false, else None."""
    if not data.get("ok"):
        err = data.get("error", "unknown_error")
        if err in ("token_revoked", "invalid_auth", "not_authed", "missing_scope"):
            return (
                f"Authorization error in {tool_name}: Slack token is invalid or missing required scope ({err}). "
                "Ask the user to reconnect their Slack connector."
            )
        return f"API error in {tool_name}: {err}"
    return None


class SlackConnector(BaseConnector):

    PROVIDER_ID = "slack"

    # ── Channels ─────────────────────────────────────────────────────────────

    def list_channels(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "slack_list_channels", inp)
        if permission_error: return permission_error
        try:
            params = {
                "limit": inp.get("limit", 100),
                "types": inp.get("types", "public_channel"),
            }
            resp = httpx.get(f"{_BASE}/conversations.list", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if err := _check_ok(data, "slack_list_channels"):
                return err
            channels = [{"id": c["id"], "name": c["name"], "is_private": c.get("is_private", False), "num_members": c.get("num_members", 0)} for c in data.get("channels", [])]
            return json.dumps(channels)
        except Exception as e:
            return _handle_error("slack_list_channels", e)

    def get_channel_info(self, inp: dict) -> str:
        permission_error, channel = self._check(self.agent_id, self.PROVIDER_ID, "slack_get_channel_info", inp, "channel")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/conversations.info", headers=self._auth_headers, params={"channel": channel}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if err := _check_ok(data, "slack_get_channel_info"):
                return err
            return json.dumps(data.get("channel", {}))
        except Exception as e:
            return _handle_error("slack_get_channel_info", e)

    def get_channel_members(self, inp: dict) -> str:
        permission_error, channel = self._check(self.agent_id, self.PROVIDER_ID, "slack_get_channel_members", inp, "channel")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/conversations.members", headers=self._auth_headers, params={"channel": channel, "limit": inp.get("limit", 100)}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if err := _check_ok(data, "slack_get_channel_members"):
                return err
            return json.dumps({"channel": channel, "members": data.get("members", [])})
        except Exception as e:
            return _handle_error("slack_get_channel_members", e)

    def create_channel(self, inp: dict) -> str:
        permission_error, name = self._check(self.agent_id, self.PROVIDER_ID, "slack_create_channel", inp, "name")
        if permission_error: return permission_error
        try:
            payload: dict = {"name": name}
            if inp.get("is_private") is not None:
                payload["is_private"] = bool(inp["is_private"])
            data = _slack_post(
                f"{_BASE}/conversations.create",
                {**self._auth_headers, "Content-Type": "application/json"},
                payload,
            )
            if err := _check_ok(data, "slack_create_channel"):
                return err
            channel = data.get("channel", {})
            return json.dumps({"id": channel.get("id"), "name": channel.get("name"), "is_private": channel.get("is_private", False)})
        except Exception as e:
            return _handle_error("slack_create_channel", e)

    def invite_to_channel(self, inp: dict) -> str:
        permission_error, channel, users = self._check(self.agent_id, self.PROVIDER_ID, "slack_invite_to_channel", inp, "channel", "users")
        if permission_error: return permission_error
        try:
            data = _slack_post(
                f"{_BASE}/conversations.invite",
                {**self._auth_headers, "Content-Type": "application/json"},
                {"channel": channel, "users": users},
            )
            if err := _check_ok(data, "slack_invite_to_channel"):
                return err
            return json.dumps({"ok": True, "channel": channel})
        except Exception as e:
            return _handle_error("slack_invite_to_channel", e)

    def open_dm(self, inp: dict) -> str:
        permission_error, users = self._check(self.agent_id, self.PROVIDER_ID, "slack_open_dm", inp, "users")
        if permission_error: return permission_error
        try:
            data = _slack_post(
                f"{_BASE}/conversations.open",
                {**self._auth_headers, "Content-Type": "application/json"},
                {"users": users},
            )
            if err := _check_ok(data, "slack_open_dm"):
                return err
            return json.dumps({"ok": True, "channel_id": data.get("channel", {}).get("id")})
        except Exception as e:
            return _handle_error("slack_open_dm", e)

    # ── Messages ─────────────────────────────────────────────────────────────

    def get_channel_history(self, inp: dict) -> str:
        permission_error, channel = self._check(self.agent_id, self.PROVIDER_ID, "slack_get_channel_history", inp, "channel")
        if permission_error: return permission_error
        try:
            params = {"channel": channel, "limit": inp.get("limit", 25)}
            if inp.get("oldest"):
                params["oldest"] = inp["oldest"]
            if inp.get("latest"):
                params["latest"] = inp["latest"]
            resp = httpx.get(f"{_BASE}/conversations.history", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if err := _check_ok(data, "slack_get_channel_history"):
                return err
            messages = [
                {"ts": m.get("ts"), "user": m.get("user"), "text": m.get("text", ""), "thread_ts": m.get("thread_ts"), "reply_count": m.get("reply_count", 0)}
                for m in data.get("messages", [])
            ]
            return json.dumps({"channel": channel, "messages": messages})
        except Exception as e:
            return _handle_error("slack_get_channel_history", e)

    def get_thread(self, inp: dict) -> str:
        permission_error, channel, thread_ts = self._check(self.agent_id, self.PROVIDER_ID, "slack_get_thread", inp, "channel", "thread_ts")
        if permission_error: return permission_error
        try:
            params = {"channel": channel, "ts": thread_ts, "limit": inp.get("limit", 50)}
            resp = httpx.get(f"{_BASE}/conversations.replies", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if err := _check_ok(data, "slack_get_thread"):
                return err
            return json.dumps({"channel": channel, "thread_ts": thread_ts, "messages": data.get("messages", [])})
        except Exception as e:
            return _handle_error("slack_get_thread", e)

    def send_message(self, inp: dict) -> str:
        permission_error, channel, text = self._check(self.agent_id, self.PROVIDER_ID, "slack_send_message", inp, "channel", "text")
        if permission_error: return permission_error
        try:
            payload: dict = {"channel": channel, "text": text}
            if inp.get("blocks"):
                payload["blocks"] = inp["blocks"]
            data = _slack_post(f"{_BASE}/chat.postMessage", {**self._auth_headers, "Content-Type": "application/json"}, payload)
            if err := _check_ok(data, "slack_send_message"):
                return err
            return json.dumps({"ok": True, "ts": data.get("ts"), "channel": data.get("channel")})
        except Exception as e:
            return _handle_error("slack_send_message", e)

    def reply_to_thread(self, inp: dict) -> str:
        permission_error, channel, thread_ts, text = self._check(self.agent_id, self.PROVIDER_ID, "slack_reply_to_thread", inp, "channel", "thread_ts", "text")
        if permission_error: return permission_error
        try:
            data = _slack_post(
                f"{_BASE}/chat.postMessage",
                {**self._auth_headers, "Content-Type": "application/json"},
                {"channel": channel, "thread_ts": thread_ts, "text": text},
            )
            if err := _check_ok(data, "slack_reply_to_thread"):
                return err
            return json.dumps({"ok": True, "ts": data.get("ts")})
        except Exception as e:
            return _handle_error("slack_reply_to_thread", e)

    def update_message(self, inp: dict) -> str:
        permission_error, channel, ts, text = self._check(self.agent_id, self.PROVIDER_ID, "slack_update_message", inp, "channel", "ts", "text")
        if permission_error: return permission_error
        try:
            data = _slack_post(
                f"{_BASE}/chat.update",
                {**self._auth_headers, "Content-Type": "application/json"},
                {"channel": channel, "ts": ts, "text": text},
            )
            if err := _check_ok(data, "slack_update_message"):
                return err
            return json.dumps({"ok": True, "ts": data.get("ts")})
        except Exception as e:
            return _handle_error("slack_update_message", e)

    def delete_message(self, inp: dict) -> str:
        permission_error, channel, ts = self._check(self.agent_id, self.PROVIDER_ID, "slack_delete_message", inp, "channel", "ts")
        if permission_error: return permission_error
        try:
            data = _slack_post(
                f"{_BASE}/chat.delete",
                {**self._auth_headers, "Content-Type": "application/json"},
                {"channel": channel, "ts": ts},
            )
            if err := _check_ok(data, "slack_delete_message"):
                return err
            return json.dumps({"ok": True})
        except Exception as e:
            return _handle_error("slack_delete_message", e)

    def schedule_message(self, inp: dict) -> str:
        permission_error, channel, text, post_at = self._check(self.agent_id, self.PROVIDER_ID, "slack_schedule_message", inp, "channel", "text", "post_at")
        if permission_error: return permission_error
        try:
            data = _slack_post(
                f"{_BASE}/chat.scheduleMessage",
                {**self._auth_headers, "Content-Type": "application/json"},
                {"channel": channel, "text": text, "post_at": int(post_at)},
            )
            if err := _check_ok(data, "slack_schedule_message"):
                return err
            return json.dumps({"ok": True, "scheduled_message_id": data.get("scheduled_message_id"), "post_at": data.get("post_at")})
        except Exception as e:
            return _handle_error("slack_schedule_message", e)

    def post_ephemeral(self, inp: dict) -> str:
        permission_error, channel, user, text = self._check(self.agent_id, self.PROVIDER_ID, "slack_post_ephemeral", inp, "channel", "user", "text")
        if permission_error: return permission_error
        try:
            data = _slack_post(
                f"{_BASE}/chat.postEphemeral",
                {**self._auth_headers, "Content-Type": "application/json"},
                {"channel": channel, "user": user, "text": text},
            )
            if err := _check_ok(data, "slack_post_ephemeral"):
                return err
            return json.dumps({"ok": True, "message_ts": data.get("message_ts")})
        except Exception as e:
            return _handle_error("slack_post_ephemeral", e)

    def search_messages(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "slack_search_messages", inp, "query")
        if permission_error: return permission_error
        try:
            params = {"query": query, "count": inp.get("count", 20)}
            resp = httpx.get(f"{_BASE}/search.messages", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if err := _check_ok(data, "slack_search_messages"):
                return err
            matches = [
                {"channel": m.get("channel", {}).get("id"), "user": m.get("user"), "text": m.get("text", ""), "ts": m.get("ts"), "permalink": m.get("permalink")}
                for m in data.get("messages", {}).get("matches", [])
            ]
            return json.dumps({"query": query, "matches": matches, "total": data.get("messages", {}).get("total", len(matches))})
        except Exception as e:
            return _handle_error("slack_search_messages", e)

    def add_reaction(self, inp: dict) -> str:
        permission_error, channel, ts, emoji = self._check(self.agent_id, self.PROVIDER_ID, "slack_add_reaction", inp, "channel", "ts", "emoji")
        if permission_error: return permission_error
        emoji = emoji.strip(":")
        try:
            data = _slack_post(
                f"{_BASE}/reactions.add",
                {**self._auth_headers, "Content-Type": "application/json"},
                {"channel": channel, "timestamp": ts, "name": emoji},
            )
            if err := _check_ok(data, "slack_add_reaction"):
                return err
            return json.dumps({"ok": True})
        except Exception as e:
            return _handle_error("slack_add_reaction", e)

    def remove_reaction(self, inp: dict) -> str:
        permission_error, channel, ts, emoji = self._check(self.agent_id, self.PROVIDER_ID, "slack_remove_reaction", inp, "channel", "ts", "emoji")
        if permission_error: return permission_error
        emoji = emoji.strip(":")
        try:
            data = _slack_post(
                f"{_BASE}/reactions.remove",
                {**self._auth_headers, "Content-Type": "application/json"},
                {"channel": channel, "timestamp": ts, "name": emoji},
            )
            if err := _check_ok(data, "slack_remove_reaction"):
                return err
            return json.dumps({"ok": True})
        except Exception as e:
            return _handle_error("slack_remove_reaction", e)

    def pin_message(self, inp: dict) -> str:
        permission_error, channel, ts = self._check(self.agent_id, self.PROVIDER_ID, "slack_pin_message", inp, "channel", "ts")
        if permission_error: return permission_error
        try:
            data = _slack_post(
                f"{_BASE}/pins.add",
                {**self._auth_headers, "Content-Type": "application/json"},
                {"channel": channel, "timestamp": ts},
            )
            if err := _check_ok(data, "slack_pin_message"):
                return err
            return json.dumps({"ok": True})
        except Exception as e:
            return _handle_error("slack_pin_message", e)

    # ── Users ─────────────────────────────────────────────────────────────────

    def list_users(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "slack_list_users", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/users.list", headers=self._auth_headers, params={"limit": inp.get("limit", 100)}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if err := _check_ok(data, "slack_list_users"):
                return err
            members = [
                {"id": u["id"], "name": u.get("name"), "real_name": u.get("real_name"), "is_bot": u.get("is_bot", False)}
                for u in data.get("members", [])
                if not u.get("deleted")
            ]
            return json.dumps(members)
        except Exception as e:
            return _handle_error("slack_list_users", e)

    def get_user_info(self, inp: dict) -> str:
        permission_error, user_id = self._check(self.agent_id, self.PROVIDER_ID, "slack_get_user_info", inp, "user_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/users.info", headers=self._auth_headers, params={"user": user_id}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if err := _check_ok(data, "slack_get_user_info"):
                return err
            return json.dumps(data.get("user", {}))
        except Exception as e:
            return _handle_error("slack_get_user_info", e)

    # ── Files ─────────────────────────────────────────────────────────────────

    def upload_file(self, inp: dict) -> str:
        permission_error, content = self._check(self.agent_id, self.PROVIDER_ID, "slack_upload_file", inp, "content")
        if permission_error: return permission_error
        filename = inp.get("filename", "file.txt")
        channel = inp.get("channel", "")
        try:
            body = content.encode() if isinstance(content, str) else content
            # Step 1: get upload URL
            url_resp = httpx.post(
                f"{_BASE}/files.getUploadURLExternal",
                headers={**self._auth_headers, "Content-Type": "application/x-www-form-urlencoded"},
                data={"filename": filename, "length": str(len(body))},
                timeout=15,
            )
            url_resp.raise_for_status()
            url_data = url_resp.json()
            if err := _check_ok(url_data, "slack_upload_file"):
                return err
            upload_url = url_data["upload_url"]
            file_id = url_data["file_id"]
            # Step 2: upload content
            httpx.post(upload_url, content=body, timeout=30).raise_for_status()
            # Step 3: complete
            complete_payload: dict = {"files": [{"id": file_id}]}
            if channel:
                complete_payload["channel_id"] = channel
            complete_data = _slack_post(
                f"{_BASE}/files.completeUploadExternal",
                {**self._auth_headers, "Content-Type": "application/json"},
                complete_payload,
            )
            if err := _check_ok(complete_data, "slack_upload_file"):
                return err
            files = complete_data.get("files", [{}])
            return json.dumps({"ok": True, "file_id": file_id, "permalink": files[0].get("permalink") if files else None})
        except Exception as e:
            return _handle_error("slack_upload_file", e)

    def list_files(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "slack_list_files", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"count": inp.get("count", 20)}
            if inp.get("channel"):
                params["channel"] = inp["channel"]
            if inp.get("types"):
                params["types"] = inp["types"]
            resp = httpx.get(f"{_BASE}/files.list", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if err := _check_ok(data, "slack_list_files"):
                return err
            return json.dumps(data.get("files", []))
        except Exception as e:
            return _handle_error("slack_list_files", e)

    # ── Tool manifest ─────────────────────────────────────────────────────────

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "slack_list_channels",
                    "description": "List public Slack channels the bot has access to.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max channels to return (default 100)."},
                            "types": {"type": "string", "description": "Comma-separated channel types: public_channel, private_channel, im, mpim (default: public_channel,private_channel)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_get_channel_info",
                    "description": "Get details about a specific Slack channel (name, topic, purpose, member count).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Channel ID (e.g. C0123456789)."},
                        },
                        "required": ["channel"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_get_channel_members",
                    "description": "List all member user IDs in a Slack channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Channel ID."},
                            "limit": {"type": "integer", "description": "Max members to return (default 100)."},
                        },
                        "required": ["channel"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_create_channel",
                    "description": "Create a new Slack channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Channel name (lowercase letters, numbers, hyphens, underscores; max 80 characters)."},
                            "is_private": {"type": "boolean", "description": "Create as a private channel instead of public (default false)."},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_invite_to_channel",
                    "description": "Invite one or more users to a Slack channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Channel ID to invite users to."},
                            "users": {"type": "string", "description": "Comma-separated user IDs to invite (up to 100)."},
                        },
                        "required": ["channel", "users"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_open_dm",
                    "description": "Open (or resume) a direct message conversation with one or more users.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "users": {"type": "string", "description": "Comma-separated user IDs (1-8) to open a DM/MPDM with."},
                        },
                        "required": ["users"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_get_channel_history",
                    "description": "Fetch recent messages from a Slack channel or DM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Channel or DM ID."},
                            "limit": {"type": "integer", "description": "Max messages to return (default 25)."},
                            "oldest": {"type": "string", "description": "Only messages after this Unix timestamp (optional)."},
                            "latest": {"type": "string", "description": "Only messages before this Unix timestamp (optional)."},
                        },
                        "required": ["channel"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_get_thread",
                    "description": "Fetch all replies in a message thread.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Channel ID where the thread lives."},
                            "thread_ts": {"type": "string", "description": "Timestamp of the parent message (e.g. '1512085950.000216')."},
                            "limit": {"type": "integer", "description": "Max replies to return (default 50)."},
                        },
                        "required": ["channel", "thread_ts"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_send_message",
                    "description": "Send a message to a Slack channel or DM.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Channel ID or name (e.g. '#general' or 'C0123456789')."},
                            "text": {"type": "string", "description": "Message text (supports Slack markdown: *bold*, _italic_, `code`, <URL|label>)."},
                        },
                        "required": ["channel", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_reply_to_thread",
                    "description": "Post a reply inside an existing message thread.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Channel ID."},
                            "thread_ts": {"type": "string", "description": "Timestamp of the parent message to reply to."},
                            "text": {"type": "string", "description": "Reply text."},
                        },
                        "required": ["channel", "thread_ts", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_update_message",
                    "description": "Edit the text of a previously sent message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Channel ID."},
                            "ts": {"type": "string", "description": "Timestamp of the message to edit."},
                            "text": {"type": "string", "description": "New message text."},
                        },
                        "required": ["channel", "ts", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_delete_message",
                    "description": "Delete a message from a Slack channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Channel ID."},
                            "ts": {"type": "string", "description": "Timestamp of the message to delete."},
                        },
                        "required": ["channel", "ts"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_schedule_message",
                    "description": "Schedule a message to be sent to a Slack channel at a future time.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Channel ID or name to post to."},
                            "text": {"type": "string", "description": "Message text."},
                            "post_at": {"type": "integer", "description": "Unix timestamp of when the message should be posted."},
                        },
                        "required": ["channel", "text", "post_at"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_post_ephemeral",
                    "description": "Post a message visible only to a specific user in a channel (not saved as a real message).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Channel ID."},
                            "user": {"type": "string", "description": "User ID who should see the ephemeral message."},
                            "text": {"type": "string", "description": "Message text."},
                        },
                        "required": ["channel", "user", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_search_messages",
                    "description": "Search for messages across the Slack workspace matching a query.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query text (supports Slack search modifiers like 'from:', 'in:', 'before:')."},
                            "count": {"type": "integer", "description": "Max results to return (default 20)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_add_reaction",
                    "description": "Add an emoji reaction to a message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Channel ID."},
                            "ts": {"type": "string", "description": "Timestamp of the message."},
                            "emoji": {"type": "string", "description": "Emoji name without colons (e.g. 'thumbsup', 'white_check_mark')."},
                        },
                        "required": ["channel", "ts", "emoji"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_remove_reaction",
                    "description": "Remove an emoji reaction from a message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Channel ID."},
                            "ts": {"type": "string", "description": "Timestamp of the message."},
                            "emoji": {"type": "string", "description": "Emoji name to remove (without colons)."},
                        },
                        "required": ["channel", "ts", "emoji"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_pin_message",
                    "description": "Pin a message in a channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Channel ID."},
                            "ts": {"type": "string", "description": "Timestamp of the message to pin."},
                        },
                        "required": ["channel", "ts"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_list_users",
                    "description": "List all members of the Slack workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max users to return (default 100)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_get_user_info",
                    "description": "Get profile information for a specific Slack user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "The Slack user ID (e.g. 'U0123456789')."},
                        },
                        "required": ["user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_upload_file",
                    "description": "Upload a text file or code snippet to Slack, optionally sharing it in a channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "Text content of the file."},
                            "filename": {"type": "string", "description": "File name (e.g. 'report.txt', 'script.py')."},
                            "channel": {"type": "string", "description": "Channel ID to share the file in (optional)."},
                        },
                        "required": ["content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_list_files",
                    "description": "List files uploaded to the Slack workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Filter by channel ID (optional)."},
                            "types": {"type": "string", "description": "File types to filter (e.g. 'images', 'pdfs', 'snippets')."},
                            "count": {"type": "integer", "description": "Max files to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
        ]
        callables = {
            "slack_list_channels": self.list_channels,
            "slack_get_channel_info": self.get_channel_info,
            "slack_get_channel_members": self.get_channel_members,
            "slack_create_channel": self.create_channel,
            "slack_invite_to_channel": self.invite_to_channel,
            "slack_open_dm": self.open_dm,
            "slack_get_channel_history": self.get_channel_history,
            "slack_get_thread": self.get_thread,
            "slack_send_message": self.send_message,
            "slack_reply_to_thread": self.reply_to_thread,
            "slack_update_message": self.update_message,
            "slack_delete_message": self.delete_message,
            "slack_schedule_message": self.schedule_message,
            "slack_post_ephemeral": self.post_ephemeral,
            "slack_search_messages": self.search_messages,
            "slack_add_reaction": self.add_reaction,
            "slack_remove_reaction": self.remove_reaction,
            "slack_pin_message": self.pin_message,
            "slack_list_users": self.list_users,
            "slack_get_user_info": self.get_user_info,
            "slack_upload_file": self.upload_file,
            "slack_list_files": self.list_files,
        }
        return tools, callables

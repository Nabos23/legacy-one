import json
import httpx

from ai.connectors.base import BaseConnector


def _base(token: str) -> str:
    return f"https://api.telegram.org/bot{token}"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class TelegramConnector(BaseConnector):

    PROVIDER_ID = "telegram"

    def send_message(self, inp: dict) -> str:
        permission_error, chat_id, text = self._check(self.agent_id, self.PROVIDER_ID, "telegram_send_message", inp, "chat_id", "text")
        if permission_error: return permission_error
        try:
            body = {"chat_id": chat_id, "text": text, "parse_mode": inp.get("parse_mode", "HTML")}
            resp = httpx.post(f"{_base(self._token)}/sendMessage", json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("result", {})
            return json.dumps({"message_id": msg.get("message_id"), "date": msg.get("date"), "status": "sent"})
        except Exception as e:
            return _handle_error("telegram_send_message", e)

    def get_updates(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "telegram_get_updates", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 10), "offset": inp.get("offset")}
            params = {k: v for k, v in params.items() if v is not None}
            resp = httpx.get(f"{_base(self._token)}/getUpdates", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            updates = []
            for u in data.get("result", []):
                msg = u.get("message", {})
                updates.append({
                    "update_id": u.get("update_id"),
                    "from": msg.get("from", {}).get("username"),
                    "chat_id": msg.get("chat", {}).get("id"),
                    "text": msg.get("text", ""),
                    "date": msg.get("date"),
                })
            return json.dumps(updates)
        except Exception as e:
            return _handle_error("telegram_get_updates", e)

    def get_bot_info(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "telegram_get_bot_info", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_base(self._token)}/getMe", timeout=15)
            resp.raise_for_status()
            data = resp.json().get("result", {})
            return json.dumps({"id": data.get("id"), "username": data.get("username"), "first_name": data.get("first_name")})
        except Exception as e:
            return _handle_error("telegram_get_bot_info", e)

    def send_photo(self, inp: dict) -> str:
        permission_error, chat_id, photo_url = self._check(self.agent_id, self.PROVIDER_ID, "telegram_send_photo", inp, "chat_id", "photo_url")
        if permission_error: return permission_error
        try:
            body = {"chat_id": chat_id, "photo": photo_url}
            if inp.get("caption"):
                body["caption"] = inp["caption"]
            resp = httpx.post(f"{_base(self._token)}/sendPhoto", json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "sent"})
        except Exception as e:
            return _handle_error("telegram_send_photo", e)

    def send_document(self, inp: dict) -> str:
        permission_error, chat_id, document = self._check(self.agent_id, self.PROVIDER_ID, "telegram_send_document", inp, "chat_id", "document")
        if permission_error: return permission_error
        try:
            body = {"chat_id": chat_id, "document": document}
            if inp.get("caption"):
                body["caption"] = inp["caption"]
            resp = httpx.post(f"{_base(self._token)}/sendDocument", json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("result", {})
            return json.dumps({"message_id": msg.get("message_id"), "date": msg.get("date"), "status": "sent"})
        except Exception as e:
            return _handle_error("telegram_send_document", e)

    def send_location(self, inp: dict) -> str:
        permission_error, chat_id, latitude, longitude = self._check(self.agent_id, self.PROVIDER_ID, "telegram_send_location", inp, "chat_id", "latitude", "longitude")
        if permission_error: return permission_error
        try:
            body = {"chat_id": chat_id, "latitude": latitude, "longitude": longitude}
            resp = httpx.post(f"{_base(self._token)}/sendLocation", json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("result", {})
            return json.dumps({"message_id": msg.get("message_id"), "date": msg.get("date"), "status": "sent"})
        except Exception as e:
            return _handle_error("telegram_send_location", e)

    def edit_message(self, inp: dict) -> str:
        permission_error, chat_id, message_id, text = self._check(self.agent_id, self.PROVIDER_ID, "telegram_edit_message", inp, "chat_id", "message_id", "text")
        if permission_error: return permission_error
        try:
            body = {"chat_id": chat_id, "message_id": message_id, "text": text}
            resp = httpx.post(f"{_base(self._token)}/editMessageText", json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("result", {})
            return json.dumps({"message_id": msg.get("message_id"), "status": "edited"})
        except Exception as e:
            return _handle_error("telegram_edit_message", e)

    def delete_message(self, inp: dict) -> str:
        permission_error, chat_id, message_id = self._check(self.agent_id, self.PROVIDER_ID, "telegram_delete_message", inp, "chat_id", "message_id")
        if permission_error: return permission_error
        try:
            body = {"chat_id": chat_id, "message_id": message_id}
            resp = httpx.post(f"{_base(self._token)}/deleteMessage", json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "deleted"})
        except Exception as e:
            return _handle_error("telegram_delete_message", e)

    def forward_message(self, inp: dict) -> str:
        permission_error, chat_id, from_chat_id, message_id = self._check(self.agent_id, self.PROVIDER_ID, "telegram_forward_message", inp, "chat_id", "from_chat_id", "message_id")
        if permission_error: return permission_error
        try:
            body = {"chat_id": chat_id, "from_chat_id": from_chat_id, "message_id": message_id}
            resp = httpx.post(f"{_base(self._token)}/forwardMessage", json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("result", {})
            return json.dumps({"message_id": msg.get("message_id"), "date": msg.get("date"), "status": "forwarded"})
        except Exception as e:
            return _handle_error("telegram_forward_message", e)

    def get_chat(self, inp: dict) -> str:
        permission_error, chat_id = self._check(self.agent_id, self.PROVIDER_ID, "telegram_get_chat", inp, "chat_id")
        if permission_error: return permission_error
        try:
            body = {"chat_id": chat_id}
            resp = httpx.post(f"{_base(self._token)}/getChat", json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("result", {})
            return json.dumps({
                "id": data.get("id"),
                "title": data.get("title"),
                "type": data.get("type"),
                "username": data.get("username"),
            })
        except Exception as e:
            return _handle_error("telegram_get_chat", e)

    def send_poll(self, inp: dict) -> str:
        permission_error, chat_id, question, options = self._check(self.agent_id, self.PROVIDER_ID, "telegram_send_poll", inp, "chat_id", "question", "options")
        if permission_error: return permission_error
        try:
            body = {
                "chat_id": chat_id,
                "question": question,
                "options": options,
                "is_anonymous": inp.get("is_anonymous", True),
            }
            resp = httpx.post(f"{_base(self._token)}/sendPoll", json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("result", {})
            return json.dumps({"message_id": msg.get("message_id"), "date": msg.get("date"), "status": "sent"})
        except Exception as e:
            return _handle_error("telegram_send_poll", e)

    def pin_chat_message(self, inp: dict) -> str:
        permission_error, chat_id, message_id = self._check(self.agent_id, self.PROVIDER_ID, "telegram_pin_chat_message", inp, "chat_id", "message_id")
        if permission_error: return permission_error
        try:
            body = {"chat_id": chat_id, "message_id": message_id}
            resp = httpx.post(f"{_base(self._token)}/pinChatMessage", json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "pinned"})
        except Exception as e:
            return _handle_error("telegram_pin_chat_message", e)

    def unpin_chat_message(self, inp: dict) -> str:
        permission_error, chat_id = self._check(self.agent_id, self.PROVIDER_ID, "telegram_unpin_chat_message", inp, "chat_id")
        if permission_error: return permission_error
        try:
            body = {"chat_id": chat_id}
            if inp.get("message_id") is not None:
                body["message_id"] = inp["message_id"]
            resp = httpx.post(f"{_base(self._token)}/unpinChatMessage", json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "unpinned"})
        except Exception as e:
            return _handle_error("telegram_unpin_chat_message", e)

    def get_chat_members_count(self, inp: dict) -> str:
        permission_error, chat_id = self._check(self.agent_id, self.PROVIDER_ID, "telegram_get_chat_members_count", inp, "chat_id")
        if permission_error: return permission_error
        try:
            body = {"chat_id": chat_id}
            resp = httpx.post(f"{_base(self._token)}/getChatMemberCount", json=body, timeout=15)
            resp.raise_for_status()
            count = resp.json().get("result", 0)
            return json.dumps({"chat_id": chat_id, "member_count": count})
        except Exception as e:
            return _handle_error("telegram_get_chat_members_count", e)

    def kick_chat_member(self, inp: dict) -> str:
        permission_error, chat_id, user_id = self._check(self.agent_id, self.PROVIDER_ID, "telegram_kick_chat_member", inp, "chat_id", "user_id")
        if permission_error: return permission_error
        try:
            body: dict = {"chat_id": chat_id, "user_id": user_id}
            if inp.get("until_date"):
                body["until_date"] = inp["until_date"]
            resp = httpx.post(f"{_base(self._token)}/banChatMember", json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"chat_id": chat_id, "user_id": user_id, "status": "banned"})
        except Exception as e:
            return _handle_error("telegram_kick_chat_member", e)

    def set_chat_title(self, inp: dict) -> str:
        permission_error, chat_id, title = self._check(self.agent_id, self.PROVIDER_ID, "telegram_set_chat_title", inp, "chat_id", "title")
        if permission_error: return permission_error
        try:
            body = {"chat_id": chat_id, "title": title}
            resp = httpx.post(f"{_base(self._token)}/setChatTitle", json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"chat_id": chat_id, "title": title, "status": "updated"})
        except Exception as e:
            return _handle_error("telegram_set_chat_title", e)

    def get_file(self, inp: dict) -> str:
        permission_error, file_id = self._check(self.agent_id, self.PROVIDER_ID, "telegram_get_file", inp, "file_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_base(self._token)}/getFile", params={"file_id": file_id}, timeout=15)
            resp.raise_for_status()
            f = resp.json().get("result", {})
            file_path = f.get("file_path", "")
            download_url = f"https://api.telegram.org/file/bot{self._token}/{file_path}" if file_path else None
            return json.dumps({"file_id": f.get("file_id"), "file_size": f.get("file_size"), "file_path": file_path, "download_url": download_url})
        except Exception as e:
            return _handle_error("telegram_get_file", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "telegram_send_message",
                    "description": "Send a text message via the Telegram bot.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "Telegram chat ID or username to send to."},
                            "text": {"type": "string", "description": "Message text (supports HTML formatting)."},
                            "parse_mode": {"type": "string", "description": "'HTML' or 'Markdown' (default HTML)."},
                        },
                        "required": ["chat_id", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_get_updates",
                    "description": "Get recent messages sent to the Telegram bot.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max updates to return (default 10)."},
                            "offset": {"type": "integer", "description": "Offset for pagination."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_get_bot_info",
                    "description": "Get information about the connected Telegram bot.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_send_photo",
                    "description": "Send a photo via the Telegram bot.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "Telegram chat ID to send to."},
                            "photo_url": {"type": "string", "description": "URL of the photo to send."},
                            "caption": {"type": "string", "description": "Optional caption for the photo."},
                        },
                        "required": ["chat_id", "photo_url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_send_document",
                    "description": "Send a document (file) via the Telegram bot using a URL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "Telegram chat ID to send to."},
                            "document": {"type": "string", "description": "URL of the document to send."},
                            "caption": {"type": "string", "description": "Optional caption for the document."},
                        },
                        "required": ["chat_id", "document"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_send_location",
                    "description": "Send a geographic location via the Telegram bot.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "Telegram chat ID to send to."},
                            "latitude": {"type": "number", "description": "Latitude of the location."},
                            "longitude": {"type": "number", "description": "Longitude of the location."},
                        },
                        "required": ["chat_id", "latitude", "longitude"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_edit_message",
                    "description": "Edit the text of an existing message sent by the bot.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "Telegram chat ID where the message resides."},
                            "message_id": {"type": "integer", "description": "ID of the message to edit."},
                            "text": {"type": "string", "description": "New text content for the message."},
                        },
                        "required": ["chat_id", "message_id", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_delete_message",
                    "description": "Delete a message in a Telegram chat.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "Telegram chat ID where the message resides."},
                            "message_id": {"type": "integer", "description": "ID of the message to delete."},
                        },
                        "required": ["chat_id", "message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_forward_message",
                    "description": "Forward a message from one chat to another via the Telegram bot.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "Destination chat ID to forward the message to."},
                            "from_chat_id": {"type": "string", "description": "Source chat ID where the message originates."},
                            "message_id": {"type": "integer", "description": "ID of the message to forward."},
                        },
                        "required": ["chat_id", "from_chat_id", "message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_get_chat",
                    "description": "Get information about a Telegram chat (id, title, type, username).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "Telegram chat ID or username to look up."},
                        },
                        "required": ["chat_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_send_poll",
                    "description": "Send a poll to a Telegram chat.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "Telegram chat ID to send the poll to."},
                            "question": {"type": "string", "description": "Poll question text."},
                            "options": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of answer options (2-10 strings).",
                            },
                            "is_anonymous": {"type": "boolean", "description": "Whether the poll is anonymous (default true)."},
                        },
                        "required": ["chat_id", "question", "options"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_pin_chat_message",
                    "description": "Pin a message in a Telegram chat.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "Telegram chat ID where the message resides."},
                            "message_id": {"type": "integer", "description": "ID of the message to pin."},
                        },
                        "required": ["chat_id", "message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_unpin_chat_message",
                    "description": "Unpin a message in a Telegram chat. If message_id is omitted, unpins the most recent pinned message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "Telegram chat ID to unpin the message in."},
                            "message_id": {"type": "integer", "description": "ID of the message to unpin (optional; omit to unpin most recent)."},
                        },
                        "required": ["chat_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_get_chat_members_count",
                    "description": "Get the number of members in a Telegram chat.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "Telegram chat ID to get member count for."},
                        },
                        "required": ["chat_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_kick_chat_member",
                    "description": "Ban (remove) a member from a Telegram group or supergroup chat.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "Telegram chat ID (group/supergroup)."},
                            "user_id": {"type": "integer", "description": "User ID to ban/remove."},
                            "until_date": {"type": "integer", "description": "Unix timestamp when the ban is lifted (optional; omit for permanent ban)."},
                        },
                        "required": ["chat_id", "user_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_set_chat_title",
                    "description": "Change the title of a Telegram group, supergroup, or channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string", "description": "Telegram chat ID."},
                            "title": {"type": "string", "description": "New chat title."},
                        },
                        "required": ["chat_id", "title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "telegram_get_file",
                    "description": "Get download info for a file previously sent to the Telegram bot, given its file_id.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string", "description": "The Telegram file_id to resolve."},
                        },
                        "required": ["file_id"],
                    },
                },
            },
        ]
        callables = {
            "telegram_send_message": self.send_message,
            "telegram_get_updates": self.get_updates,
            "telegram_get_bot_info": self.get_bot_info,
            "telegram_send_photo": self.send_photo,
            "telegram_send_document": self.send_document,
            "telegram_send_location": self.send_location,
            "telegram_edit_message": self.edit_message,
            "telegram_delete_message": self.delete_message,
            "telegram_forward_message": self.forward_message,
            "telegram_get_chat": self.get_chat,
            "telegram_send_poll": self.send_poll,
            "telegram_pin_chat_message": self.pin_chat_message,
            "telegram_unpin_chat_message": self.unpin_chat_message,
            "telegram_get_chat_members_count": self.get_chat_members_count,
            "telegram_kick_chat_member": self.kick_chat_member,
            "telegram_set_chat_title": self.set_chat_title,
            "telegram_get_file": self.get_file,
        }
        return tools, callables

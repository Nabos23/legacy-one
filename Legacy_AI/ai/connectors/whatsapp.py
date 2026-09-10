import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://graph.facebook.com/v19.0"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected WhatsApp Business account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their WhatsApp connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class WhatsAppConnector(BaseConnector):
    """
    WhatsApp Business API connector.
    access_token format: "ACCESS_TOKEN:PHONE_NUMBER_ID"
    """

    PROVIDER_ID = "whatsapp"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        parts = access_token.split(":", 1)
        self._token = parts[0]
        self._phone_number_id = parts[1] if len(parts) > 1 else ""
        super().__init__(self._token, agent_id=agent_id)

    def send_message(self, inp: dict) -> str:
        permission_error, to, text = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_send_message", inp, "to", "text")
        if permission_error: return permission_error
        if not self._phone_number_id:
            return "Error: Phone number ID not configured. Reconnect the WhatsApp connector."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {"preview_url": False, "body": text},
            }
            resp = httpx.post(f"{_BASE}/{self._phone_number_id}/messages", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            messages = data.get("messages", [{}])
            return json.dumps({"status": "sent", "message_id": messages[0].get("id") if messages else None, "to": to})
        except Exception as e:
            return _handle_error("whatsapp_send_message", e)

    def send_template_message(self, inp: dict) -> str:
        permission_error, to, template_name = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_send_template_message", inp, "to", "template_name")
        if permission_error: return permission_error
        language_code = inp.get("language_code", "en_US")
        if not self._phone_number_id:
            return "Error: Phone number ID not configured. Reconnect the WhatsApp connector."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "template",
                "template": {"name": template_name, "language": {"code": language_code}},
            }
            components = inp.get("components", [])
            if components:
                body["template"]["components"] = components
            resp = httpx.post(f"{_BASE}/{self._phone_number_id}/messages", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            messages = data.get("messages", [{}])
            return json.dumps({"status": "sent", "message_id": messages[0].get("id") if messages else None, "to": to})
        except Exception as e:
            return _handle_error("whatsapp_send_template_message", e)

    def get_phone_number_info(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_get_phone_number_info", inp)
        if permission_error: return permission_error
        if not self._phone_number_id:
            return "Error: Phone number ID not configured."
        try:
            params = {"fields": "display_phone_number,verified_name,quality_rating,status"}
            resp = httpx.get(f"{_BASE}/{self._phone_number_id}", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data.get("id"),
                "display_phone_number": data.get("display_phone_number"),
                "verified_name": data.get("verified_name"),
                "quality_rating": data.get("quality_rating"),
                "status": data.get("status"),
            })
        except Exception as e:
            return _handle_error("whatsapp_get_phone_number_info", e)

    def list_templates(self, inp: dict) -> str:
        permission_error, business_account_id = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_list_templates", inp, "business_account_id")
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("status"):
                params["status"] = inp["status"]
            resp = httpx.get(f"{_BASE}/{business_account_id}/message_templates", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            templates = [
                {"id": t["id"], "name": t["name"], "status": t.get("status"), "category": t.get("category"), "language": t.get("language")}
                for t in data.get("data", [])
            ]
            return json.dumps({"templates": templates, "count": len(templates)})
        except Exception as e:
            return _handle_error("whatsapp_list_templates", e)

    def mark_message_read(self, inp: dict) -> str:
        permission_error, message_id = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_mark_message_read", inp, "message_id")
        if permission_error: return permission_error
        if not self._phone_number_id:
            return "Error: Phone number ID not configured."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}
            resp = httpx.post(f"{_BASE}/{self._phone_number_id}/messages", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "marked_read", "message_id": message_id})
        except Exception as e:
            return _handle_error("whatsapp_mark_message_read", e)

    def send_image(self, inp: dict) -> str:
        permission_error, to, image_url = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_send_image", inp, "to", "image_url")
        if permission_error: return permission_error
        if not self._phone_number_id:
            return "Error: Phone number ID not configured. Reconnect the WhatsApp connector."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            image: dict = {"link": image_url}
            if inp.get("caption"):
                image["caption"] = inp["caption"]
            body = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "image",
                "image": image,
            }
            resp = httpx.post(f"{_BASE}/{self._phone_number_id}/messages", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            messages = data.get("messages", [{}])
            return json.dumps({"status": "sent", "message_id": messages[0].get("id") if messages else None, "to": to})
        except Exception as e:
            return _handle_error("whatsapp_send_image", e)

    def send_document(self, inp: dict) -> str:
        permission_error, to, document_url, filename = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_send_document", inp, "to", "document_url", "filename")
        if permission_error: return permission_error
        if not self._phone_number_id:
            return "Error: Phone number ID not configured. Reconnect the WhatsApp connector."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            document: dict = {"link": document_url, "filename": filename}
            if inp.get("caption"):
                document["caption"] = inp["caption"]
            body = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "document",
                "document": document,
            }
            resp = httpx.post(f"{_BASE}/{self._phone_number_id}/messages", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            messages = data.get("messages", [{}])
            return json.dumps({"status": "sent", "message_id": messages[0].get("id") if messages else None, "to": to})
        except Exception as e:
            return _handle_error("whatsapp_send_document", e)

    def send_location(self, inp: dict) -> str:
        permission_error, to, latitude, longitude = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_send_location", inp, "to", "latitude", "longitude")
        if permission_error: return permission_error
        if not self._phone_number_id:
            return "Error: Phone number ID not configured. Reconnect the WhatsApp connector."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            location: dict = {"latitude": latitude, "longitude": longitude}
            if inp.get("name"):
                location["name"] = inp["name"]
            if inp.get("address"):
                location["address"] = inp["address"]
            body = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "location",
                "location": location,
            }
            resp = httpx.post(f"{_BASE}/{self._phone_number_id}/messages", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            messages = data.get("messages", [{}])
            return json.dumps({"status": "sent", "message_id": messages[0].get("id") if messages else None, "to": to})
        except Exception as e:
            return _handle_error("whatsapp_send_location", e)

    def send_interactive_buttons(self, inp: dict) -> str:
        permission_error, to, body_text, buttons = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_send_interactive_buttons", inp, "to", "body_text", "buttons")
        if permission_error: return permission_error
        if len(buttons) > 3:
            return "Error: Maximum 3 buttons allowed."
        if not self._phone_number_id:
            return "Error: Phone number ID not configured. Reconnect the WhatsApp connector."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": body_text},
                    "action": {
                        "buttons": [
                            {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                            for b in buttons
                        ]
                    },
                },
            }
            resp = httpx.post(f"{_BASE}/{self._phone_number_id}/messages", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            messages = data.get("messages", [{}])
            return json.dumps({"status": "sent", "message_id": messages[0].get("id") if messages else None, "to": to})
        except Exception as e:
            return _handle_error("whatsapp_send_interactive_buttons", e)

    def react_to_message(self, inp: dict) -> str:
        permission_error, to, message_id, emoji = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_react_to_message", inp, "to", "message_id", "emoji")
        if permission_error: return permission_error
        if not self._phone_number_id:
            return "Error: Phone number ID not configured. Reconnect the WhatsApp connector."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "reaction",
                "reaction": {"message_id": message_id, "emoji": emoji},
            }
            resp = httpx.post(f"{_BASE}/{self._phone_number_id}/messages", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            messages = data.get("messages", [{}])
            return json.dumps({"status": "sent", "message_id": messages[0].get("id") if messages else None, "to": to})
        except Exception as e:
            return _handle_error("whatsapp_react_to_message", e)

    def send_video(self, inp: dict) -> str:
        permission_error, to, video_url = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_send_video", inp, "to", "video_url")
        if permission_error: return permission_error
        if not self._phone_number_id:
            return "Error: Phone number ID not configured. Reconnect the WhatsApp connector."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            video: dict = {"link": video_url}
            if inp.get("caption"):
                video["caption"] = inp["caption"]
            body = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "video",
                "video": video,
            }
            resp = httpx.post(f"{_BASE}/{self._phone_number_id}/messages", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            messages = data.get("messages", [{}])
            return json.dumps({"status": "sent", "message_id": messages[0].get("id") if messages else None, "to": to})
        except Exception as e:
            return _handle_error("whatsapp_send_video", e)

    def send_audio(self, inp: dict) -> str:
        permission_error, to, audio_url = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_send_audio", inp, "to", "audio_url")
        if permission_error: return permission_error
        if not self._phone_number_id:
            return "Error: Phone number ID not configured. Reconnect the WhatsApp connector."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "audio",
                "audio": {"link": audio_url},
            }
            resp = httpx.post(f"{_BASE}/{self._phone_number_id}/messages", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            messages = data.get("messages", [{}])
            return json.dumps({"status": "sent", "message_id": messages[0].get("id") if messages else None, "to": to})
        except Exception as e:
            return _handle_error("whatsapp_send_audio", e)

    def send_interactive_list(self, inp: dict) -> str:
        permission_error, to, body_text, button_text, sections = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_send_interactive_list", inp, "to", "body_text", "button_text", "sections")
        if permission_error: return permission_error
        if not self._phone_number_id:
            return "Error: Phone number ID not configured. Reconnect the WhatsApp connector."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "interactive",
                "interactive": {
                    "type": "list",
                    "body": {"text": body_text},
                    "action": {
                        "button": button_text,
                        "sections": sections,
                    },
                },
            }
            resp = httpx.post(f"{_BASE}/{self._phone_number_id}/messages", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            messages = data.get("messages", [{}])
            return json.dumps({"status": "sent", "message_id": messages[0].get("id") if messages else None, "to": to})
        except Exception as e:
            return _handle_error("whatsapp_send_interactive_list", e)

    def upload_media(self, inp: dict) -> str:
        permission_error, media_url, mime_type = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_upload_media", inp, "media_url", "mime_type")
        if permission_error: return permission_error
        if not self._phone_number_id:
            return "Error: Phone number ID not configured. Reconnect the WhatsApp connector."
        try:
            download = httpx.get(media_url, timeout=30)
            download.raise_for_status()
            files = {"file": ("upload", download.content, mime_type)}
            data = {"messaging_product": "whatsapp", "type": mime_type}
            resp = httpx.post(f"{_BASE}/{self._phone_number_id}/media", headers=self._auth_headers, data=data, files=files, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            return json.dumps({"media_id": result.get("id"), "status": "uploaded"})
        except Exception as e:
            return _handle_error("whatsapp_upload_media", e)

    def get_media_url(self, inp: dict) -> str:
        permission_error, media_id = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_get_media_url", inp, "media_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/{media_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "media_id": data.get("id"),
                "url": data.get("url"),
                "mime_type": data.get("mime_type"),
                "file_size": data.get("file_size"),
                "sha256": data.get("sha256"),
                "note": "URL expires in 5 minutes; call this again if it has expired.",
            })
        except Exception as e:
            return _handle_error("whatsapp_get_media_url", e)

    def delete_media(self, inp: dict) -> str:
        permission_error, media_id = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_delete_media", inp, "media_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/{media_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"deleted": bool(data.get("success")), "media_id": media_id})
        except Exception as e:
            return _handle_error("whatsapp_delete_media", e)

    def get_business_profile(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_get_business_profile", inp)
        if permission_error: return permission_error
        if not self._phone_number_id:
            return "Error: Phone number ID not configured."
        try:
            params = {"fields": "about,address,description,email,profile_picture_url,websites,vertical"}
            resp = httpx.get(f"{_BASE}/{self._phone_number_id}/whatsapp_business_profile", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            entries = resp.json().get("data", [{}])
            profile = entries[0] if entries else {}
            return json.dumps({
                "about": profile.get("about"),
                "address": profile.get("address"),
                "description": profile.get("description"),
                "email": profile.get("email"),
                "profile_picture_url": profile.get("profile_picture_url"),
                "websites": profile.get("websites"),
                "vertical": profile.get("vertical"),
            })
        except Exception as e:
            return _handle_error("whatsapp_get_business_profile", e)

    def update_business_profile(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "whatsapp_update_business_profile", inp)
        if permission_error: return permission_error
        if not self._phone_number_id:
            return "Error: Phone number ID not configured. Reconnect the WhatsApp connector."
        updates: dict = {"messaging_product": "whatsapp"}
        for field in ("about", "address", "description", "email", "vertical"):
            if inp.get(field) is not None:
                updates[field] = inp[field]
        if inp.get("websites") is not None:
            updates["websites"] = inp["websites"]
        if len(updates) == 1:
            return "Error: at least one profile field (about, address, description, email, vertical, websites) is required."
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(f"{_BASE}/{self._phone_number_id}/whatsapp_business_profile", headers=headers, json=updates, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"status": "updated", "success": data.get("success", True)})
        except Exception as e:
            return _handle_error("whatsapp_update_business_profile", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "whatsapp_send_message",
                    "description": "Send a WhatsApp text message to a phone number.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient phone number with country code, e.g. '+14155552671'."},
                            "text": {"type": "string", "description": "Message text to send."},
                        },
                        "required": ["to", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "whatsapp_send_template_message",
                    "description": "Send a pre-approved WhatsApp template message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient phone number with country code."},
                            "template_name": {"type": "string", "description": "Name of the approved message template."},
                            "language_code": {"type": "string", "description": "Language code (default 'en_US')."},
                            "components": {"type": "array", "description": "Optional template component variables.", "items": {"type": "object"}},
                        },
                        "required": ["to", "template_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "whatsapp_get_phone_number_info",
                    "description": "Get info about the connected WhatsApp Business phone number.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "whatsapp_list_templates",
                    "description": "List approved WhatsApp message templates for a Business Account.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "business_account_id": {"type": "string", "description": "WhatsApp Business Account ID (WABA ID)."},
                            "status": {"type": "string", "description": "Filter by status: APPROVED, PENDING, REJECTED."},
                            "limit": {"type": "integer", "description": "Max templates to return (default 20)."},
                        },
                        "required": ["business_account_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "whatsapp_mark_message_read",
                    "description": "Mark an incoming WhatsApp message as read.",
                    "parameters": {
                        "type": "object",
                        "properties": {"message_id": {"type": "string", "description": "The WhatsApp message ID to mark as read."}},
                        "required": ["message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "whatsapp_send_image",
                    "description": "Send an image to a WhatsApp recipient via a URL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient phone number with country code, e.g. '+14155552671'."},
                            "image_url": {"type": "string", "description": "Publicly accessible URL of the image to send."},
                            "caption": {"type": "string", "description": "Optional caption text for the image."},
                        },
                        "required": ["to", "image_url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "whatsapp_send_document",
                    "description": "Send a document (PDF, DOCX, etc.) to a WhatsApp recipient via a URL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient phone number with country code, e.g. '+14155552671'."},
                            "document_url": {"type": "string", "description": "Publicly accessible URL of the document to send."},
                            "filename": {"type": "string", "description": "Filename to display for the document (e.g. 'report.pdf')."},
                            "caption": {"type": "string", "description": "Optional caption text for the document."},
                        },
                        "required": ["to", "document_url", "filename"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "whatsapp_send_location",
                    "description": "Send a location pin to a WhatsApp recipient.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient phone number with country code, e.g. '+14155552671'."},
                            "latitude": {"type": "number", "description": "Latitude of the location."},
                            "longitude": {"type": "number", "description": "Longitude of the location."},
                            "name": {"type": "string", "description": "Optional name/label for the location."},
                            "address": {"type": "string", "description": "Optional address text for the location."},
                        },
                        "required": ["to", "latitude", "longitude"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "whatsapp_send_interactive_buttons",
                    "description": "Send an interactive message with up to 3 reply buttons to a WhatsApp recipient.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient phone number with country code, e.g. '+14155552671'."},
                            "body_text": {"type": "string", "description": "Main body text of the interactive message."},
                            "buttons": {
                                "type": "array",
                                "description": "List of up to 3 buttons. Each button must have 'id' and 'title' fields.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string", "description": "Unique button ID."},
                                        "title": {"type": "string", "description": "Button label text (max 20 characters)."},
                                    },
                                    "required": ["id", "title"],
                                },
                                "maxItems": 3,
                            },
                        },
                        "required": ["to", "body_text", "buttons"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "whatsapp_react_to_message",
                    "description": "React to a WhatsApp message with an emoji.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient phone number with country code, e.g. '+14155552671'."},
                            "message_id": {"type": "string", "description": "The ID of the message to react to."},
                            "emoji": {"type": "string", "description": "A single emoji character to react with (e.g. '\U0001f44d')."},
                        },
                        "required": ["to", "message_id", "emoji"],
                    },
                },
            },
        ]
        callables = {
            "whatsapp_send_message": self.send_message,
            "whatsapp_send_template_message": self.send_template_message,
            "whatsapp_get_phone_number_info": self.get_phone_number_info,
            "whatsapp_list_templates": self.list_templates,
            "whatsapp_mark_message_read": self.mark_message_read,
            "whatsapp_send_image": self.send_image,
            "whatsapp_send_document": self.send_document,
            "whatsapp_send_location": self.send_location,
            "whatsapp_send_interactive_buttons": self.send_interactive_buttons,
            "whatsapp_react_to_message": self.react_to_message,
        }
        return tools, callables

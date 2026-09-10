import os
import json
import base64
import httpx
from backend.core.uploads import delete_report_file, resolve_local_attachment_path
from ai.connectors.base import BaseConnector

_BASE = "https://graph.microsoft.com/v1.0/me"

def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Outlook account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Outlook connector with the required OAuth scopes."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


def _parse_message(msg: dict) -> dict:
    body_content = msg.get("body", {}).get("content", "")
    return {
        "id": msg.get("id"),
        "subject": msg.get("subject", ""),
        "from": msg.get("from", {}).get("emailAddress", {}).get("address", ""),
        "to": [r["emailAddress"]["address"] for r in msg.get("toRecipients", [])],
        "cc": [r["emailAddress"]["address"] for r in msg.get("ccRecipients", [])],
        "received": msg.get("receivedDateTime", ""),
        "is_read": msg.get("isRead", False),
        "is_flagged": msg.get("flag", {}).get("flagStatus") == "flagged",
        "conversation_id": msg.get("conversationId", ""),
        "body": body_content[:4000],
        "has_attachments": msg.get("hasAttachments", False),
    }


def _recipients(addresses: str) -> list:
    return [{"emailAddress": {"address": a.strip()}} for a in addresses.split(",") if a.strip()]


def _parse_attachment(att: dict) -> dict:
    return {
        "id": att.get("id"),
        "name": att.get("name", ""),
        "content_type": att.get("contentType", ""),
        "size": att.get("size"),
        "is_inline": att.get("isInline", False),
    }


class OutlookConnector(BaseConnector):

    PROVIDER_ID = "outlook"

    # ── Profile ──────────────────────────────────────────────────────────────

    def get_profile(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "outlook_get_profile", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}",
                headers=self._auth_headers,
                params={"$select": "displayName,mail,userPrincipalName,id"},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("outlook_get_profile", e)

    # ── Folders ───────────────────────────────────────────────────────────────

    def list_folders(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "outlook_list_folders", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/mailFolders", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("outlook_list_folders", e)

    # ── Messages ─────────────────────────────────────────────────────────────

    def list_messages(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "outlook_list_messages", inp)
        if permission_error: return permission_error
        try:
            top = inp.get("top", 25)
            folder = inp.get("folder", "")
            filter_str = inp.get("filter", "")
            order_by = inp.get("order_by", "receivedDateTime desc")
            base = f"{_BASE}/mailFolders/{folder}/messages" if folder else f"{_BASE}/messages"
            params: dict = {
                "$top": top,
                "$select": "id,subject,from,toRecipients,receivedDateTime,isRead,hasAttachments,bodyPreview",
                "$orderby": order_by,
            }
            if filter_str:
                params["$filter"] = filter_str
            resp = httpx.get(base, headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("outlook_list_messages", e)

    def search_messages(self, inp: dict) -> str:
        """Full-text search across all mail using $search."""
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "outlook_search_messages", inp, "query")
        if permission_error: return permission_error
        top = inp.get("top", 25)
        try:
            params = {
                "$search": f'"{query}"',
                "$top": top,
                "$select": "id,subject,from,toRecipients,receivedDateTime,isRead,bodyPreview",
            }
            resp = httpx.get(f"{_BASE}/messages", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("outlook_search_messages", e)

    def get_message(self, inp: dict) -> str:
        permission_error, message_id = self._check(self.agent_id, self.PROVIDER_ID, "outlook_get_message", inp, "message_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/messages/{message_id}",
                headers=self._auth_headers,
                params={"$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,isRead,body,hasAttachments,flag,conversationId"},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(_parse_message(resp.json()))
        except Exception as e:
            return _handle_error("outlook_get_message", e)

    def modify_message(self, inp: dict) -> str:
        """Update read status, flag, or categories on a message."""
        permission_error, message_id = self._check(self.agent_id, self.PROVIDER_ID, "outlook_modify_message", inp, "message_id")
        if permission_error: return permission_error
        patch: dict = {}
        if "is_read" in inp:
            patch["isRead"] = inp["is_read"]
        if "flag" in inp:
            patch["flag"] = {"flagStatus": inp["flag"]}
        if not patch:
            return "Error: provide at least one field to update (is_read, flag)."
        try:
            resp = httpx.patch(
                f"{_BASE}/messages/{message_id}",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=patch,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"ok": True, "id": message_id})
        except Exception as e:
            return _handle_error("outlook_modify_message", e)

    def move_message(self, inp: dict) -> str:
        permission_error, message_id, destination = self._check(self.agent_id, self.PROVIDER_ID, "outlook_move_message", inp, "message_id", "destination_folder_id")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/messages/{message_id}/move",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"destinationId": destination},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("outlook_move_message", e)

    def delete_message(self, inp: dict) -> str:
        permission_error, message_id = self._check(self.agent_id, self.PROVIDER_ID, "outlook_delete_message", inp, "message_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/messages/{message_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"ok": True, "deleted": message_id})
        except Exception as e:
            return _handle_error("outlook_delete_message", e)

    # ── Send / Compose ───────────────────────────────────────────────────────

    def send_email(self, inp: dict) -> str:
        permission_error, to = self._check(self.agent_id, self.PROVIDER_ID, "outlook_send_email", inp, "to")
        if permission_error: return permission_error
        subject = inp.get("subject", "")
        body = inp.get("body", "")
        cc = inp.get("cc", "")
        bcc = inp.get("bcc", "")
        html = inp.get("html", False)
        # Handles /chat/reports/xxx.pdf, chat/reports/xxx.pdf, or just xxx.pdf
        attachment_path = (inp.get("attachment_path") or inp.get("attachment") or inp.get("path") or "").strip()

        payload: dict = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML" if html else "Text", "content": body},
                "toRecipients": _recipients(to),
            }
        }

        if cc:
            payload["message"]["ccRecipients"] = _recipients(cc)
        if bcc:
            payload["message"]["bccRecipients"] = _recipients(bcc)

        # Handle Local Report Attachments
        if attachment_path:
            safe_name = os.path.basename(attachment_path)
            filepath = resolve_local_attachment_path(safe_name)

            if not filepath:
                return f"Error: attachment not found or invalid: '{attachment_path}'"
            
            try:
                with open(filepath, "rb") as f:
                    file_bytes = f.read()
                
                # Convert binary data to base64 string
                b64_content = base64.b64encode(file_bytes).decode("utf-8")
                # Attach to Outlook's payload structure
                payload["message"]["attachments"] = [
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": safe_name,
                        "contentType": "application/pdf",
                        "contentBytes": b64_content
                    }
                ]
            except Exception as e:
                return f"Error: Failed to process attachment: {str(e)}"

        try:
            resp = httpx.post(
                f"{_BASE}/sendMail",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            if attachment_path:
                delete_report_file(safe_name)
            return json.dumps({"ok": True})
        except Exception as e:
            return _handle_error("outlook_send_email", e)

    def reply_email(self, inp: dict) -> str:
        permission_error, message_id, body = self._check(self.agent_id, self.PROVIDER_ID, "outlook_reply_email", inp, "message_id", "body")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/messages/{message_id}/reply",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"comment": body},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"ok": True})
        except Exception as e:
            return _handle_error("outlook_reply_email", e)

    def reply_all(self, inp: dict) -> str:
        permission_error, message_id, body = self._check(self.agent_id, self.PROVIDER_ID, "outlook_reply_all", inp, "message_id", "body")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/messages/{message_id}/replyAll",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"comment": body},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"ok": True})
        except Exception as e:
            return _handle_error("outlook_reply_all", e)

    def forward_email(self, inp: dict) -> str:
        permission_error, message_id, to = self._check(self.agent_id, self.PROVIDER_ID, "outlook_forward_email", inp, "message_id", "to")
        if permission_error: return permission_error
        comment = inp.get("comment", "")
        try:
            resp = httpx.post(
                f"{_BASE}/messages/{message_id}/forward",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"comment": comment, "toRecipients": _recipients(to)},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"ok": True})
        except Exception as e:
            return _handle_error("outlook_forward_email", e)

    # ── Drafts ───────────────────────────────────────────────────────────────

    def create_draft(self, inp: dict) -> str:
        permission_error, to = self._check(self.agent_id, self.PROVIDER_ID, "outlook_create_draft", inp, "to")
        if permission_error: return permission_error
        subject = inp.get("subject", "")
        body = inp.get("body", "")
        cc = inp.get("cc", "")
        payload: dict = {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": _recipients(to),
        }
        if cc:
            payload["ccRecipients"] = _recipients(cc)
        try:
            resp = httpx.post(
                f"{_BASE}/messages",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("outlook_create_draft", e)

    def list_drafts(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "outlook_list_drafts", inp)
        if permission_error: return permission_error
        top = inp.get("top", 25)
        try:
            params = {
                "$top": top,
                "$select": "id,subject,toRecipients,createdDateTime,lastModifiedDateTime",
                "$orderby": "lastModifiedDateTime desc",
            }
            resp = httpx.get(
                f"{_BASE}/mailFolders/Drafts/messages",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("outlook_list_drafts", e)

    def send_draft(self, inp: dict) -> str:
        permission_error, message_id = self._check(self.agent_id, self.PROVIDER_ID, "outlook_send_draft", inp, "message_id")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/messages/{message_id}/send",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"ok": True})
        except Exception as e:
            return _handle_error("outlook_send_draft", e)

    # ── Attachments ──────────────────────────────────────────────────────────

    def list_attachments(self, inp: dict) -> str:
        """List attachments on a message (metadata only, no file contents)."""
        permission_error, message_id = self._check(self.agent_id, self.PROVIDER_ID, "outlook_list_attachments", inp, "message_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/messages/{message_id}/attachments",
                headers=self._auth_headers,
                params={"$select": "id,name,contentType,size,isInline"},
                timeout=15,
            )
            resp.raise_for_status()
            attachments = [_parse_attachment(a) for a in resp.json().get("value", [])]
            return json.dumps({"attachments": attachments, "count": len(attachments)})
        except Exception as e:
            return _handle_error("outlook_list_attachments", e)

    def add_attachment(self, inp: dict) -> str:
        """Attach a small file (under 3 MB) to an existing message, e.g. a draft created with outlook_create_draft."""
        permission_error, message_id, name, content_base64 = self._check(self.agent_id, self.PROVIDER_ID, "outlook_add_attachment", inp, "message_id", "name", "content_base64")
        if permission_error: return permission_error
        payload = {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": name,
            "contentBytes": content_base64,
        }
        if inp.get("content_type"):
            payload["contentType"] = inp["content_type"]
        try:
            resp = httpx.post(
                f"{_BASE}/messages/{message_id}/attachments",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "name": data.get("name"), "status": "attached"})
        except Exception as e:
            return _handle_error("outlook_add_attachment", e)

    # ── Folders ───────────────────────────────────────────────────────────────

    def create_folder(self, inp: dict) -> str:
        """Create a new mail folder, optionally as a child of an existing folder."""
        permission_error, display_name = self._check(self.agent_id, self.PROVIDER_ID, "outlook_create_folder", inp, "display_name")
        if permission_error: return permission_error
        parent_folder_id = inp.get("parent_folder_id", "")
        base = f"{_BASE}/mailFolders/{parent_folder_id}/childFolders" if parent_folder_id else f"{_BASE}/mailFolders"
        try:
            resp = httpx.post(
                base,
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"displayName": display_name},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "display_name": data.get("displayName"), "status": "created"})
        except Exception as e:
            return _handle_error("outlook_create_folder", e)

    # ── Mailbox settings ─────────────────────────────────────────────────────

    def get_automatic_replies(self, inp: dict) -> str:
        """Get the current out-of-office / automatic-replies configuration for the mailbox."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "outlook_get_automatic_replies", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/mailboxSettings",
                headers=self._auth_headers,
                params={"$select": "automaticRepliesSetting"},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json().get("automaticRepliesSetting", {}))
        except Exception as e:
            return _handle_error("outlook_get_automatic_replies", e)

    def set_automatic_replies(self, inp: dict) -> str:
        """Enable, schedule, or disable out-of-office automatic replies for the mailbox."""
        permission_error, status = self._check(self.agent_id, self.PROVIDER_ID, "outlook_set_automatic_replies", inp, "status")
        if permission_error: return permission_error
        if status not in ("disabled", "alwaysEnabled", "scheduled"):
            return "Error: 'status' must be one of 'disabled', 'alwaysEnabled', 'scheduled'."
        setting: dict = {"status": status}
        if inp.get("internal_message") is not None:
            setting["internalReplyMessage"] = inp["internal_message"]
        if inp.get("external_message") is not None:
            setting["externalReplyMessage"] = inp["external_message"]
        if inp.get("external_audience"):
            setting["externalAudience"] = inp["external_audience"]
        if status == "scheduled":
            if not inp.get("start") or not inp.get("end"):
                return "Error: 'start' and 'end' (ISO datetimes) are required when status is 'scheduled'."
            time_zone = inp.get("time_zone", "UTC")
            setting["scheduledStartDateTime"] = {"dateTime": inp["start"], "timeZone": time_zone}
            setting["scheduledEndDateTime"] = {"dateTime": inp["end"], "timeZone": time_zone}
        try:
            resp = httpx.patch(
                f"{_BASE}/mailboxSettings",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"automaticRepliesSetting": setting},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"ok": True, "automatic_replies_setting": resp.json().get("automaticRepliesSetting", {})})
        except Exception as e:
            return _handle_error("outlook_set_automatic_replies", e)

    # ── Categories ───────────────────────────────────────────────────────────

    def list_categories(self, inp: dict) -> str:
        """List the user's master category list (used to tag/color-code messages and events)."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "outlook_list_categories", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/outlook/masterCategories", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            categories = [{"id": c.get("id"), "display_name": c.get("displayName"), "color": c.get("color")} for c in resp.json().get("value", [])]
            return json.dumps({"categories": categories, "count": len(categories)})
        except Exception as e:
            return _handle_error("outlook_list_categories", e)

    # ── Tool manifest ─────────────────────────────────────────────────────────

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "outlook_get_profile",
                    "description": "Get the signed-in user's Outlook profile: display name, email address, and user ID.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_list_folders",
                    "description": "List all mail folders in the Outlook mailbox (Inbox, Sent, Drafts, custom folders, etc.).",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_list_messages",
                    "description": (
                        "List emails from Outlook. Optionally filter by folder or OData filter expression. "
                        "Example filters: 'isRead eq false', 'from/emailAddress/address eq \\'alice@example.com\\'', "
                        "'receivedDateTime ge 2024-01-01T00:00:00Z'."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "top": {"type": "integer", "description": "Max messages to return (default 25)."},
                            "folder": {"type": "string", "description": "Mail folder ID (e.g. 'Inbox', 'SentItems', or a custom folder ID)."},
                            "filter": {"type": "string", "description": "OData filter expression (e.g. 'isRead eq false')."},
                            "order_by": {"type": "string", "description": "OData orderby (default 'receivedDateTime desc')."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_search_messages",
                    "description": "Full-text search across all mail (subject, body, sender, recipients).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search text (e.g. 'invoice', 'from:alice project')."},
                            "top": {"type": "integer", "description": "Max results to return (default 25)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_get_message",
                    "description": "Fetch the full content of a specific email: subject, from, to, body, read status, and attachments flag.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The Outlook message ID."},
                        },
                        "required": ["message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_modify_message",
                    "description": "Mark a message as read/unread or flag/unflag it.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The Outlook message ID."},
                            "is_read": {"type": "boolean", "description": "Set to true to mark as read, false for unread."},
                            "flag": {"type": "string", "description": "Flag status: 'flagged', 'notFlagged', or 'complete'."},
                        },
                        "required": ["message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_move_message",
                    "description": "Move a message to a different mail folder.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The Outlook message ID."},
                            "destination_folder_id": {"type": "string", "description": "Target folder ID or well-known name (e.g. 'Archive', 'DeletedItems')."},
                        },
                        "required": ["message_id", "destination_folder_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_delete_message",
                    "description": "Permanently delete a message from Outlook.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The Outlook message ID to delete."},
                        },
                        "required": ["message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_send_email",
                    "description": "Send a new email via Outlook. Supports CC, BCC, and HTML body.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient email(s), comma-separated."},
                            "subject": {"type": "string", "description": "Email subject."},
                            "body": {"type": "string", "description": "Email body (plain text or HTML)."},
                            "cc": {"type": "string", "description": "CC recipients, comma-separated (optional)."},
                            "bcc": {"type": "string", "description": "BCC recipients, comma-separated (optional)."},
                            "html": {"type": "boolean", "description": "Set to true if body is HTML (default false)."},
                            "attachment_path": {"type": "string", "description": "Local path to the report PDF to attach to the email (optional)."},
                        },
                        "required": ["to", "subject", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_reply_email",
                    "description": "Reply to a specific email message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The message ID to reply to."},
                            "body": {"type": "string", "description": "Reply body text."},
                        },
                        "required": ["message_id", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_reply_all",
                    "description": "Reply to all recipients of an email.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The message ID to reply-all to."},
                            "body": {"type": "string", "description": "Reply body text."},
                        },
                        "required": ["message_id", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_forward_email",
                    "description": "Forward an email to new recipients.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The message ID to forward."},
                            "to": {"type": "string", "description": "Recipient email(s), comma-separated."},
                            "comment": {"type": "string", "description": "Note to prepend before the forwarded message (optional)."},
                        },
                        "required": ["message_id", "to"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_create_draft",
                    "description": "Save an email as a draft without sending.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient email(s), comma-separated."},
                            "subject": {"type": "string", "description": "Email subject."},
                            "body": {"type": "string", "description": "Email body."},
                            "cc": {"type": "string", "description": "CC recipients (optional)."},
                        },
                        "required": ["to", "subject", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_list_drafts",
                    "description": "List saved email drafts in Outlook.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "top": {"type": "integer", "description": "Max drafts to return (default 25)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_send_draft",
                    "description": "Send an existing draft message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The draft message ID to send."},
                        },
                        "required": ["message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_list_attachments",
                    "description": "List the attachments on a message (names, content types, sizes) without downloading their content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The Outlook message ID."},
                        },
                        "required": ["message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_add_attachment",
                    "description": (
                        "Attach a file (under 3 MB) to an existing message, typically a draft created with "
                        "outlook_create_draft, before sending it with outlook_send_draft."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The message ID (usually a draft) to attach the file to."},
                            "name": {"type": "string", "description": "File name, including extension (e.g. 'invoice.pdf')."},
                            "content_base64": {"type": "string", "description": "The file content, base64-encoded."},
                            "content_type": {"type": "string", "description": "MIME type of the file (e.g. 'application/pdf'). Optional."},
                        },
                        "required": ["message_id", "name", "content_base64"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_create_folder",
                    "description": "Create a new mail folder, optionally nested inside an existing folder.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "display_name": {"type": "string", "description": "Name of the new folder."},
                            "parent_folder_id": {"type": "string", "description": "Optional parent folder ID to create the folder inside (default: mailbox root)."},
                        },
                        "required": ["display_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_get_automatic_replies",
                    "description": "Get the mailbox's current out-of-office / automatic-replies configuration.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_set_automatic_replies",
                    "description": "Enable, schedule, or disable out-of-office automatic replies for the mailbox.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "One of 'disabled', 'alwaysEnabled', 'scheduled'."},
                            "internal_message": {"type": "string", "description": "Reply text sent to people inside the organization."},
                            "external_message": {"type": "string", "description": "Reply text sent to people outside the organization."},
                            "external_audience": {"type": "string", "description": "Who receives the external reply: 'none', 'contactsOnly', or 'all'."},
                            "start": {"type": "string", "description": "ISO 8601 datetime when replies start (required if status is 'scheduled')."},
                            "end": {"type": "string", "description": "ISO 8601 datetime when replies end (required if status is 'scheduled')."},
                            "time_zone": {"type": "string", "description": "Time zone for start/end, e.g. 'UTC' (default 'UTC')."},
                        },
                        "required": ["status"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "outlook_list_categories",
                    "description": "List the user's master category list used to color-code and tag messages and events.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
        ]
        callables = {
            "outlook_get_profile": self.get_profile,
            "outlook_list_folders": self.list_folders,
            "outlook_list_messages": self.list_messages,
            "outlook_search_messages": self.search_messages,
            "outlook_get_message": self.get_message,
            "outlook_modify_message": self.modify_message,
            "outlook_move_message": self.move_message,
            "outlook_delete_message": self.delete_message,
            "outlook_send_email": self.send_email,
            "outlook_reply_email": self.reply_email,
            "outlook_reply_all": self.reply_all,
            "outlook_forward_email": self.forward_email,
            "outlook_create_draft": self.create_draft,
            "outlook_list_drafts": self.list_drafts,
            "outlook_send_draft": self.send_draft,
            "outlook_list_attachments": self.list_attachments,
            "outlook_add_attachment": self.add_attachment,
            "outlook_create_folder": self.create_folder,
            "outlook_get_automatic_replies": self.get_automatic_replies,
            "outlook_set_automatic_replies": self.set_automatic_replies,
            "outlook_list_categories": self.list_categories,
        }
        return tools, callables

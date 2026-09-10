import json
import logging
import re
import base64
import httpx
import os
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from urllib.parse import urlparse
from backend.core.uploads import delete_report_file, resolve_local_attachment_path
from ai.connectors.base import BaseConnector

logger = logging.getLogger(__name__)

_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Gmail account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Gmail connector with the required OAuth scopes."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


def _extract_body(payload: dict) -> str:
    """Recursively extract readable text from a message payload (prefers text/plain)."""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    if mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
            return re.sub(r"<[^>]+>", " ", html)
    # multipart: recurse into parts, prefer first text/plain hit
    plain_fallback = ""
    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text and not plain_fallback:
            plain_fallback = text
    return plain_fallback


def _parse_message(msg: dict) -> dict:
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    body = _extract_body(msg.get("payload", {}))
    return {
        "id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "subject": headers.get("subject", ""),
        "date": headers.get("date", ""),
        "snippet": msg.get("snippet", ""),
        "body": body[:4000],
        "label_ids": msg.get("labelIds", []),
    }


class GmailConnector(BaseConnector):

    PROVIDER_ID = "gmail"

    # ── Profile ──────────────────────────────────────────────────────────────

    def get_profile(self, inp: dict) -> str:
        """Return the user's Gmail address, total messages, and thread count."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "gmail_get_profile", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/profile", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("gmail_get_profile", e)

    # ── Labels ───────────────────────────────────────────────────────────────

    def list_labels(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "gmail_list_labels", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/labels", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            labels = resp.json().get("labels", [])
            return json.dumps([{"id": l["id"], "name": l["name"]} for l in labels])
        except Exception as e:
            return _handle_error("gmail_list_labels", e)

    def create_label(self, inp: dict) -> str:
        """Create a new Gmail label for organizing mail."""
        permission_error, name = self._check(self.agent_id, self.PROVIDER_ID, "gmail_create_label", inp, "name")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/labels",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={
                    "name": name,
                    "labelListVisibility": inp.get("label_list_visibility", "labelShow"),
                    "messageListVisibility": inp.get("message_list_visibility", "show"),
                },
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("gmail_create_label", e)

    # ── Messages ─────────────────────────────────────────────────────────────

    def list_messages(self, inp: dict) -> str:
        """List message IDs/snippets; use gmail_get_message to read the full body."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "gmail_list_messages", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"maxResults": inp.get("max_results", 10)}
            if inp.get("query"):
                params["q"] = inp["query"]
            if inp.get("label_ids"):
                params["labelIds"] = inp["label_ids"]
            resp = httpx.get(f"{_BASE}/messages", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("gmail_list_messages", e)

    def get_message(self, inp: dict) -> str:
        """Fetch the full content (headers + decoded body) of a single message."""
        permission_error, message_id = self._check(self.agent_id, self.PROVIDER_ID, "gmail_get_message", inp, "message_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/messages/{message_id}",
                headers=self._auth_headers,
                params={"format": "full"},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(_parse_message(resp.json()))
        except Exception as e:
            return _handle_error("gmail_get_message", e)

    def modify_message(self, inp: dict) -> str:
        """Add or remove labels on a message (e.g. mark read, star, archive, move to label)."""
        permission_error, message_id = self._check(self.agent_id, self.PROVIDER_ID, "gmail_modify_message", inp, "message_id")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/messages/{message_id}/modify",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={
                    "addLabelIds": inp.get("add_labels", []),
                    "removeLabelIds": inp.get("remove_labels", []),
                },
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("gmail_modify_message", e)

    def trash_message(self, inp: dict) -> str:
        """Move a message to Trash (recoverable)."""
        permission_error, message_id = self._check(self.agent_id, self.PROVIDER_ID, "gmail_trash_message", inp, "message_id")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/messages/{message_id}/trash",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"status": "trashed", "id": message_id})
        except Exception as e:
            return _handle_error("gmail_trash_message", e)

    def delete_message(self, inp: dict) -> str:
        """Permanently delete a message. Requires full Gmail access scope."""
        permission_error, message_id = self._check(self.agent_id, self.PROVIDER_ID, "gmail_delete_message", inp, "message_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(
                f"{_BASE}/messages/{message_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"status": "deleted", "id": message_id})
        except Exception as e:
            return _handle_error("gmail_delete_message", e)

    def untrash_message(self, inp: dict) -> str:
        """Restore a message out of Trash back to the inbox/its original labels."""
        permission_error, message_id = self._check(self.agent_id, self.PROVIDER_ID, "gmail_untrash_message", inp, "message_id")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/messages/{message_id}/untrash",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"status": "untrashed", "id": message_id})
        except Exception as e:
            return _handle_error("gmail_untrash_message", e)

    def batch_modify_messages(self, inp: dict) -> str:
        """Add or remove labels on many messages at once (bulk archive, mark read, move label, etc.)."""
        permission_error, message_ids = self._check(self.agent_id, self.PROVIDER_ID, "gmail_batch_modify_messages", inp, "message_ids")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/messages/batchModify",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={
                    "ids": message_ids,
                    "addLabelIds": inp.get("add_labels", []),
                    "removeLabelIds": inp.get("remove_labels", []),
                },
                timeout=30,
            )
            resp.raise_for_status()
            return json.dumps({"status": "modified", "count": len(message_ids)})
        except Exception as e:
            return _handle_error("gmail_batch_modify_messages", e)

    def get_attachment(self, inp: dict) -> str:
        """Download an attachment's raw content (base64url-encoded) from a message."""
        permission_error, message_id, attachment_id = self._check(self.agent_id, self.PROVIDER_ID, "gmail_get_attachment", inp, "message_id", "attachment_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/messages/{message_id}/attachments/{attachment_id}",
                headers=self._auth_headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "size": data.get("size"),
                "data": data.get("data", ""),
                "encoding": "base64url",
            })
        except Exception as e:
            return _handle_error("gmail_get_attachment", e)

    # ── Threads ──────────────────────────────────────────────────────────────

    def list_threads(self, inp: dict) -> str:
        """List conversation threads, optionally filtered by a search query."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "gmail_list_threads", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"maxResults": inp.get("max_results", 10)}
            if inp.get("query"):
                params["q"] = inp["query"]
            resp = httpx.get(f"{_BASE}/threads", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("gmail_list_threads", e)

    def get_thread(self, inp: dict) -> str:
        """Fetch all messages in a conversation thread."""
        permission_error, thread_id = self._check(self.agent_id, self.PROVIDER_ID, "gmail_get_thread", inp, "thread_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/threads/{thread_id}",
                headers=self._auth_headers,
                params={"format": "full"},
                timeout=15,
            )
            resp.raise_for_status()
            thread = resp.json()
            return json.dumps({
                "thread_id": thread_id,
                "messages": [_parse_message(m) for m in thread.get("messages", [])],
            })
        except Exception as e:
            return _handle_error("gmail_get_thread", e)

    # ── Send / Compose ───────────────────────────────────────────────────────

    def send_email(self, inp: dict) -> str:
        permission_error, to = self._check(self.agent_id, self.PROVIDER_ID, "gmail_send_email", inp, "to")
        if permission_error: return permission_error
        subject = inp.get("subject", "")
        body = inp.get("body", "")
        cc = inp.get("cc", "")
        attachment_path = (inp.get("attachment_path") or inp.get("attachment") or inp.get("path") or "").strip()

        msg = MIMEMultipart()
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        msg.attach(MIMEText(body, "plain"))

        if attachment_path:
            is_url = attachment_path.startswith(("http://", "https://"))
            
            if is_url:
                parsed_url = urlparse(attachment_path)
                safe_name = os.path.basename(parsed_url.path)
                if not safe_name or "." not in safe_name:
                    safe_name = "document.pdf"  # fallback default
                
                try:
                    # Download the external file
                    response = httpx.get(attachment_path, timeout=10)
                    response.raise_for_status()
                    file_bytes = response.content
                except Exception as e:
                    return f"Error: Failed to download external attachment from '{attachment_path}': {str(e)}"
            else:
                safe_name = os.path.basename(attachment_path)
                filepath = resolve_local_attachment_path(safe_name)

                if not filepath:
                    return f"Error: attachment '{safe_name}' not found in storage."

                if not filepath and os.path.isfile(attachment_path):
                    filepath = attachment_path

                if not filepath:
                    return f"Error: attachment '{safe_name}' not found in storage."
                
                try:
                    with open(filepath, "rb") as f:
                        file_bytes = f.read()
                except Exception as e:
                    return f"Error reading attachment: {str(e)}"

            mime_type, _ = mimetypes.guess_type(safe_name)
            if mime_type is None:
                mime_type = "application/octet-stream"
                
            main_type, sub_type = mime_type.split("/", 1)

            part = MIMEApplication(file_bytes, _subtype=sub_type)
            part.add_header("Content-Disposition", "attachment", filename=safe_name)
            msg.attach(part)

        encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        try:
            resp = httpx.post(
                f"{_BASE}/messages/send",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"raw": encoded},
                timeout=15,
            )
            resp.raise_for_status()
            if attachment_path and not is_url:
                delete_report_file(safe_name)
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("gmail_send_email", e)

    def reply_email(self, inp: dict) -> str:
        """Reply to an existing conversation thread."""
        permission_error, thread_id, to, body = self._check(self.agent_id, self.PROVIDER_ID, "gmail_reply_email", inp, "thread_id", "to", "body")
        if permission_error: return permission_error
        subject = inp.get("subject", "")
        in_reply_to = inp.get("in_reply_to", "")
        headers_str = f"To: {to}\r\nSubject: {subject}\r\nContent-Type: text/plain\r\n"
        if in_reply_to:
            headers_str += f"In-Reply-To: {in_reply_to}\r\nReferences: {in_reply_to}\r\n"
        raw_msg = headers_str + f"\r\n{body}"
        encoded = base64.urlsafe_b64encode(raw_msg.encode()).decode()
        try:
            resp = httpx.post(
                f"{_BASE}/messages/send",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"raw": encoded, "threadId": thread_id},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("gmail_reply_email", e)

    def forward_email(self, inp: dict) -> str:
        """Forward an existing message to one or more recipients."""
        permission_error, message_id, to = self._check(self.agent_id, self.PROVIDER_ID, "gmail_forward_email", inp, "message_id", "to")
        if permission_error: return permission_error
        extra_note = inp.get("note", "")
        try:
            orig_resp = httpx.get(
                f"{_BASE}/messages/{message_id}",
                headers=self._auth_headers,
                params={"format": "full"},
                timeout=15,
            )
            orig_resp.raise_for_status()
            orig = _parse_message(orig_resp.json())
            fwd_subject = orig["subject"]
            if not fwd_subject.lower().startswith("fwd:"):
                fwd_subject = f"Fwd: {fwd_subject}"
            fwd_body = ""
            if extra_note:
                fwd_body = extra_note + "\r\n\r\n"
            fwd_body += (
                f"---------- Forwarded message ----------\r\n"
                f"From: {orig['from']}\r\n"
                f"Date: {orig['date']}\r\n"
                f"Subject: {orig['subject']}\r\n"
                f"To: {orig['to']}\r\n\r\n"
                f"{orig['body']}"
            )
            raw_msg = f"To: {to}\r\nSubject: {fwd_subject}\r\nContent-Type: text/plain\r\n\r\n{fwd_body}"
            encoded = base64.urlsafe_b64encode(raw_msg.encode()).decode()
            resp = httpx.post(
                f"{_BASE}/messages/send",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"raw": encoded},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("gmail_forward_email", e)

    # ── Drafts ───────────────────────────────────────────────────────────────

    def create_draft(self, inp: dict) -> str:
        permission_error, to = self._check(self.agent_id, self.PROVIDER_ID, "gmail_create_draft", inp, "to")
        if permission_error: return permission_error
        subject = inp.get("subject", "")
        body = inp.get("body", "")
        cc = inp.get("cc", "")
        headers_str = f"To: {to}\r\nSubject: {subject}\r\nContent-Type: text/plain\r\n"
        if cc:
            headers_str += f"Cc: {cc}\r\n"
        raw_msg = headers_str + f"\r\n{body}"
        encoded = base64.urlsafe_b64encode(raw_msg.encode()).decode()
        try:
            resp = httpx.post(
                f"{_BASE}/drafts",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"message": {"raw": encoded}},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("gmail_create_draft", e)

    def list_drafts(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "gmail_list_drafts", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"maxResults": inp.get("max_results", 10)}
            resp = httpx.get(f"{_BASE}/drafts", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("gmail_list_drafts", e)

    def send_draft(self, inp: dict) -> str:
        """Send an existing draft by its draft ID."""
        permission_error, draft_id = self._check(self.agent_id, self.PROVIDER_ID, "gmail_send_draft", inp, "draft_id")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/drafts/send",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json={"id": draft_id},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("gmail_send_draft", e)

    # ── Settings ─────────────────────────────────────────────────────────────

    def list_filters(self, inp: dict) -> str:
        """List the mail filter rules configured on the account (auto-labeling, auto-forwarding, etc.)."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "gmail_list_filters", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/settings/filters", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("gmail_list_filters", e)

    def get_vacation_settings(self, inp: dict) -> str:
        """Get the current vacation responder (out-of-office auto-reply) configuration."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "gmail_get_vacation_settings", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/settings/vacation", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("gmail_get_vacation_settings", e)

    def update_vacation_settings(self, inp: dict) -> str:
        """Enable/disable and configure the vacation responder (out-of-office auto-reply)."""
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "gmail_update_vacation_settings", inp)
        if permission_error: return permission_error
        try:
            body: dict = {"enableAutoReply": inp.get("enable", True)}
            if inp.get("response_subject"):
                body["responseSubject"] = inp["response_subject"]
            if inp.get("response_body"):
                body["responseBodyPlainText"] = inp["response_body"]
            if inp.get("start_time"):
                body["startTime"] = inp["start_time"]
            if inp.get("end_time"):
                body["endTime"] = inp["end_time"]
            if inp.get("restrict_to_contacts") is not None:
                body["restrictToContacts"] = inp["restrict_to_contacts"]
            if inp.get("restrict_to_domain") is not None:
                body["restrictToDomain"] = inp["restrict_to_domain"]
            resp = httpx.put(
                f"{_BASE}/settings/vacation",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("gmail_update_vacation_settings", e)

    # ── Tool manifest ─────────────────────────────────────────────────────────

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "gmail_get_profile",
                    "description": "Get the user's Gmail profile: email address, total messages, total threads.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_list_labels",
                    "description": "List all Gmail labels (inbox, sent, custom labels, etc.) in the user's mailbox.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_create_label",
                    "description": "Create a new custom Gmail label for organizing mail.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Label name (use '/' for nested labels, e.g. 'Clients/Acme')."},
                            "label_list_visibility": {"type": "string", "description": "Visibility in the label list: 'labelShow', 'labelShowIfUnread', or 'labelHide' (default 'labelShow')."},
                            "message_list_visibility": {"type": "string", "description": "Visibility in the message list: 'show' or 'hide' (default 'show')."},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_list_messages",
                    "description": (
                        "List Gmail messages. Returns IDs and snippets. "
                        "Use gmail_get_message to read a full email body. "
                        "Supports Gmail search syntax: 'is:unread', 'from:alice@example.com', "
                        "'subject:invoice', 'after:2024/01/01', 'has:attachment', etc."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Gmail search query string."},
                            "label_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Filter by label IDs (e.g. ['INBOX', 'UNREAD']).",
                            },
                            "max_results": {"type": "integer", "description": "Max messages to return (default 10, max 500)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_get_message",
                    "description": "Fetch the full content of a specific email: headers, decoded body, and labels.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The Gmail message ID."},
                        },
                        "required": ["message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_modify_message",
                    "description": (
                        "Add or remove labels on a message. "
                        "Common uses: mark as read (remove 'UNREAD'), mark as unread (add 'UNREAD'), "
                        "star (add 'STARRED'), archive (remove 'INBOX'), mark important (add 'IMPORTANT')."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The Gmail message ID."},
                            "add_labels": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Label IDs to add (e.g. ['UNREAD', 'STARRED']).",
                            },
                            "remove_labels": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Label IDs to remove (e.g. ['UNREAD', 'INBOX']).",
                            },
                        },
                        "required": ["message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_trash_message",
                    "description": "Move a message to Trash. The message can be recovered within 30 days.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The Gmail message ID."},
                        },
                        "required": ["message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_delete_message",
                    "description": "Permanently delete a message. This cannot be undone. Requires full Gmail access scope.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The Gmail message ID."},
                        },
                        "required": ["message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_untrash_message",
                    "description": "Restore a message out of Trash back to its original labels.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The Gmail message ID."},
                        },
                        "required": ["message_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_batch_modify_messages",
                    "description": "Add or remove labels on multiple messages in one call (bulk archive, mark read/unread, move to label, etc.).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "The Gmail message IDs to modify.",
                            },
                            "add_labels": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Label IDs to add to all messages.",
                            },
                            "remove_labels": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Label IDs to remove from all messages.",
                            },
                        },
                        "required": ["message_ids"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_get_attachment",
                    "description": "Download the raw content (base64url-encoded) of a message attachment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The Gmail message ID containing the attachment."},
                            "attachment_id": {"type": "string", "description": "The attachment ID (found on the message part's body.attachmentId)."},
                        },
                        "required": ["message_id", "attachment_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_list_threads",
                    "description": (
                        "List conversation threads. Each thread groups all replies together. "
                        "Use gmail_get_thread to read the full conversation."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Gmail search query string."},
                            "max_results": {"type": "integer", "description": "Max threads to return (default 10)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_get_thread",
                    "description": "Fetch all messages in a conversation thread in order.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "thread_id": {"type": "string", "description": "The Gmail thread ID."},
                        },
                        "required": ["thread_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_send_email",
                    "description": "Send a new email.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient email address (or comma-separated list)."},
                            "subject": {"type": "string", "description": "Email subject."},
                            "body": {"type": "string", "description": "Plain-text email body."},
                            "cc": {"type": "string", "description": "CC recipients (comma-separated, optional)."},
                            "attachment_path": {"type": "string", "description": "Local path to the report PDF or other file to attach to the email (optional)."},
                        },
                        "required": ["to", "subject", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_reply_email",
                    "description": "Reply to an existing email thread.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "thread_id": {"type": "string", "description": "The thread ID to reply in."},
                            "to": {"type": "string", "description": "Recipient email address."},
                            "subject": {"type": "string", "description": "Email subject (usually 'Re: original subject')."},
                            "body": {"type": "string", "description": "Reply body text."},
                            "in_reply_to": {"type": "string", "description": "Message ID of the email being replied to (optional but recommended for proper threading)."},
                        },
                        "required": ["thread_id", "to", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_forward_email",
                    "description": "Forward an existing email to a new recipient.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string", "description": "The message ID to forward."},
                            "to": {"type": "string", "description": "Recipient to forward to."},
                            "note": {"type": "string", "description": "Optional note to prepend before the forwarded message."},
                        },
                        "required": ["message_id", "to"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_create_draft",
                    "description": "Save an email as a draft without sending it.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient email address."},
                            "subject": {"type": "string", "description": "Email subject."},
                            "body": {"type": "string", "description": "Plain-text email body."},
                            "cc": {"type": "string", "description": "CC recipients (optional)."},
                        },
                        "required": ["to", "subject", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_list_drafts",
                    "description": "List saved email drafts.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "max_results": {"type": "integer", "description": "Max drafts to return (default 10)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_send_draft",
                    "description": "Send an existing draft by its draft ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "draft_id": {"type": "string", "description": "The draft ID to send."},
                        },
                        "required": ["draft_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_list_filters",
                    "description": "List the mail filter rules configured on the account (auto-labeling, auto-archiving, auto-forwarding, etc.).",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_get_vacation_settings",
                    "description": "Get the current vacation responder (out-of-office auto-reply) configuration.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gmail_update_vacation_settings",
                    "description": "Enable, disable, or configure the vacation responder (out-of-office auto-reply).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "enable": {"type": "boolean", "description": "Whether the auto-reply is enabled (default true)."},
                            "response_subject": {"type": "string", "description": "Subject line of the auto-reply."},
                            "response_body": {"type": "string", "description": "Plain-text body of the auto-reply."},
                            "start_time": {"type": "string", "description": "Start time as epoch milliseconds (optional)."},
                            "end_time": {"type": "string", "description": "End time as epoch milliseconds (optional)."},
                            "restrict_to_contacts": {"type": "boolean", "description": "Only send auto-reply to contacts (optional)."},
                            "restrict_to_domain": {"type": "boolean", "description": "Only send auto-reply to senders in the same domain (optional)."},
                        },
                        "required": [],
                    },
                },
            },
        ]
        callables = {
            "gmail_get_profile": self.get_profile,
            "gmail_list_labels": self.list_labels,
            "gmail_create_label": self.create_label,
            "gmail_list_messages": self.list_messages,
            "gmail_get_message": self.get_message,
            "gmail_modify_message": self.modify_message,
            "gmail_trash_message": self.trash_message,
            "gmail_untrash_message": self.untrash_message,
            "gmail_delete_message": self.delete_message,
            "gmail_batch_modify_messages": self.batch_modify_messages,
            "gmail_get_attachment": self.get_attachment,
            "gmail_list_threads": self.list_threads,
            "gmail_get_thread": self.get_thread,
            "gmail_send_email": self.send_email,
            "gmail_reply_email": self.reply_email,
            "gmail_forward_email": self.forward_email,
            "gmail_create_draft": self.create_draft,
            "gmail_list_drafts": self.list_drafts,
            "gmail_send_draft": self.send_draft,
            "gmail_list_filters": self.list_filters,
            "gmail_get_vacation_settings": self.get_vacation_settings,
            "gmail_update_vacation_settings": self.update_vacation_settings,
        }
        return tools, callables

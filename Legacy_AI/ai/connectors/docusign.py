import base64
import json
import httpx

from ai.connectors.base import BaseConnector

_AUTH_BASE = "https://account.docusign.com"
_API_VERSION = "v2.1"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected DocuSign account lacks permission "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their DocuSign connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class DocuSignConnector(BaseConnector):
    """
    DocuSign connector.
    access_token format: "ACCESS_TOKEN:ACCOUNT_ID"
    ACCOUNT_ID is the DocuSign account ID (UUID).
    """

    PROVIDER_ID = "docusign"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        parts = access_token.split(":", 1)
        self._token = parts[0]
        self._account_id = parts[1] if len(parts) > 1 else ""
        super().__init__(self._token, agent_id=agent_id)
        self._base = f"https://na4.docusign.net/restapi/{_API_VERSION}/accounts/{self._account_id}"

    def _get_base_url(self) -> str:
        try:
            resp = httpx.get(f"{_AUTH_BASE}/oauth/userinfo", headers=self._auth_headers, timeout=10)
            resp.raise_for_status()
            accounts = resp.json().get("accounts", [])
            for acc in accounts:
                if acc.get("account_id") == self._account_id or not self._account_id:
                    base_uri = acc.get("base_uri", "https://na4.docusign.net")
                    if not self._account_id:
                        self._account_id = acc.get("account_id", "")
                    return f"{base_uri}/restapi/{_API_VERSION}/accounts/{self._account_id}"
        except Exception:
            pass
        return self._base

    def list_envelopes(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "docusign_list_envelopes", inp)
        if permission_error: return permission_error
        try:
            base = self._get_base_url()
            params: dict = {"count": inp.get("limit", 20), "order_by": "last_modified", "order": "desc"}
            if inp.get("status"):
                params["status"] = inp["status"]
            if inp.get("from_date"):
                params["from_date"] = inp["from_date"]
            resp = httpx.get(f"{base}/envelopes", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            envelopes = [
                {
                    "envelope_id": e["envelopeId"],
                    "status": e["status"],
                    "subject": e.get("emailSubject"),
                    "sent_date_time": e.get("sentDateTime"),
                    "last_modified": e.get("lastModifiedDateTime"),
                    "completed_date_time": e.get("completedDateTime"),
                }
                for e in data.get("envelopes", [])
            ]
            return json.dumps({"envelopes": envelopes, "total": data.get("totalSetSize"), "count": len(envelopes)})
        except Exception as e:
            return _handle_error("docusign_list_envelopes", e)

    def get_envelope(self, inp: dict) -> str:
        permission_error, envelope_id = self._check(self.agent_id, self.PROVIDER_ID, "docusign_get_envelope", inp, "envelope_id")
        if permission_error: return permission_error
        try:
            base = self._get_base_url()
            resp = httpx.get(f"{base}/envelopes/{envelope_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            e = resp.json()
            recipients_resp = httpx.get(f"{base}/envelopes/{envelope_id}/recipients", headers=self._auth_headers, timeout=15)
            recipients_resp.raise_for_status()
            signers = [
                {
                    "name": s.get("name"),
                    "email": s.get("email"),
                    "status": s.get("status"),
                    "signed_date_time": s.get("signedDateTime"),
                }
                for s in recipients_resp.json().get("signers", [])
            ]
            return json.dumps({
                "envelope_id": e["envelopeId"],
                "status": e["status"],
                "subject": e.get("emailSubject"),
                "sent_date_time": e.get("sentDateTime"),
                "completed_date_time": e.get("completedDateTime"),
                "signers": signers,
            })
        except Exception as e:
            return _handle_error("docusign_get_envelope", e)

    def send_envelope(self, inp: dict) -> str:
        permission_error, template_id, subject, signers = self._check(self.agent_id, self.PROVIDER_ID, "docusign_send_envelope", inp, "template_id", "subject", "signers")
        if permission_error: return permission_error
        try:
            base = self._get_base_url()
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            template_roles = [
                {"name": s.get("name"), "email": s.get("email"), "roleName": s.get("role_name", "Signer")}
                for s in signers
            ]
            body = {
                "templateId": template_id,
                "templateRoles": template_roles,
                "emailSubject": subject,
                "status": "sent",
            }
            resp = httpx.post(f"{base}/envelopes", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"envelope_id": data["envelopeId"], "status": data["status"], "uri": data.get("uri")})
        except Exception as e:
            return _handle_error("docusign_send_envelope", e)

    def void_envelope(self, inp: dict) -> str:
        permission_error, envelope_id = self._check(self.agent_id, self.PROVIDER_ID, "docusign_void_envelope", inp, "envelope_id")
        if permission_error: return permission_error
        reason = inp.get("reason", "Voided by AI agent")
        try:
            base = self._get_base_url()
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"status": "voided", "voidedReason": reason}
            resp = httpx.put(f"{base}/envelopes/{envelope_id}", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            return json.dumps({"envelope_id": envelope_id, "status": "voided"})
        except Exception as e:
            return _handle_error("docusign_void_envelope", e)

    def list_templates(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "docusign_list_templates", inp)
        if permission_error: return permission_error
        try:
            base = self._get_base_url()
            params = {"count": inp.get("limit", 20)}
            if inp.get("search"):
                params["search_text"] = inp["search"]
            resp = httpx.get(f"{base}/templates", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            templates = [
                {"template_id": t["templateId"], "name": t.get("name"), "description": t.get("description"), "last_modified": t.get("lastModified")}
                for t in data.get("envelopeTemplates", [])
            ]
            return json.dumps({"templates": templates, "count": len(templates)})
        except Exception as e:
            return _handle_error("docusign_list_templates", e)

    def list_recipients(self, inp: dict) -> str:
        permission_error, envelope_id = self._check(self.agent_id, self.PROVIDER_ID, "docusign_list_recipients", inp, "envelope_id")
        if permission_error: return permission_error
        try:
            base = self._get_base_url()
            resp = httpx.get(f"{base}/envelopes/{envelope_id}/recipients", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            def _fmt(r: dict) -> dict:
                return {
                    "name": r.get("name"),
                    "email": r.get("email"),
                    "status": r.get("status"),
                    "routing_order": r.get("routingOrder"),
                    "delivered_date_time": r.get("deliveredDateTime"),
                    "signed_date_time": r.get("signedDateTime"),
                }

            recipients = {
                "signers": [_fmt(r) for r in data.get("signers", [])],
                "carbon_copies": [_fmt(r) for r in data.get("carbonCopies", [])],
                "certified_deliveries": [_fmt(r) for r in data.get("certifiedDeliveries", [])],
            }
            return json.dumps(recipients)
        except Exception as e:
            return _handle_error("docusign_list_recipients", e)

    def send_reminder(self, inp: dict) -> str:
        permission_error, envelope_id = self._check(self.agent_id, self.PROVIDER_ID, "docusign_send_reminder", inp, "envelope_id")
        if permission_error: return permission_error
        try:
            base = self._get_base_url()
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            recipients_resp = httpx.get(f"{base}/envelopes/{envelope_id}/recipients", headers=self._auth_headers, timeout=15)
            recipients_resp.raise_for_status()
            resp = httpx.put(
                f"{base}/envelopes/{envelope_id}/recipients",
                headers=headers,
                params={"resend_envelope": "true"},
                json=recipients_resp.json(),
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"envelope_id": envelope_id, "status": "reminder_sent"})
        except Exception as e:
            return _handle_error("docusign_send_reminder", e)

    def list_documents(self, inp: dict) -> str:
        permission_error, envelope_id = self._check(self.agent_id, self.PROVIDER_ID, "docusign_list_documents", inp, "envelope_id")
        if permission_error: return permission_error
        try:
            base = self._get_base_url()
            resp = httpx.get(f"{base}/envelopes/{envelope_id}/documents", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            documents = [
                {
                    "document_id": d.get("documentId"),
                    "name": d.get("name"),
                    "type": d.get("type"),
                }
                for d in data.get("envelopeDocuments", [])
            ]
            return json.dumps({"envelope_id": envelope_id, "documents": documents, "count": len(documents)})
        except Exception as e:
            return _handle_error("docusign_list_documents", e)

    def download_document(self, inp: dict) -> str:
        permission_error, envelope_id = self._check(self.agent_id, self.PROVIDER_ID, "docusign_download_document", inp, "envelope_id")
        if permission_error: return permission_error
        document_id = inp.get("document_id", "combined")
        try:
            base = self._get_base_url()
            resp = httpx.get(f"{base}/envelopes/{envelope_id}/documents/{document_id}", headers=self._auth_headers, timeout=30)
            resp.raise_for_status()
            content = resp.content
            encoded = base64.b64encode(content).decode("utf-8")
            return json.dumps({
                "envelope_id": envelope_id,
                "document_id": document_id,
                "content_type": resp.headers.get("Content-Type", "application/pdf"),
                "size_bytes": len(content),
                "base64_content": encoded,
            })
        except Exception as e:
            return _handle_error("docusign_download_document", e)

    def get_audit_events(self, inp: dict) -> str:
        permission_error, envelope_id = self._check(self.agent_id, self.PROVIDER_ID, "docusign_get_audit_events", inp, "envelope_id")
        if permission_error: return permission_error
        try:
            base = self._get_base_url()
            resp = httpx.get(f"{base}/envelopes/{envelope_id}/audit_events", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            events = []
            for ev in data.get("auditEvents", []):
                fields = {f.get("name"): f.get("value") for f in ev.get("eventFields", [])}
                events.append(fields)
            return json.dumps({"envelope_id": envelope_id, "audit_events": events, "count": len(events)})
        except Exception as e:
            return _handle_error("docusign_get_audit_events", e)

    def get_template(self, inp: dict) -> str:
        permission_error, template_id = self._check(self.agent_id, self.PROVIDER_ID, "docusign_get_template", inp, "template_id")
        if permission_error: return permission_error
        try:
            base = self._get_base_url()
            resp = httpx.get(f"{base}/templates/{template_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            t = resp.json()
            roles = [
                {"role_name": r.get("roleName"), "name": r.get("name"), "email": r.get("email")}
                for r in (t.get("recipients") or {}).get("signers", [])
            ]
            return json.dumps({
                "template_id": t.get("templateId"),
                "name": t.get("name"),
                "description": t.get("description"),
                "roles": roles,
            })
        except Exception as e:
            return _handle_error("docusign_get_template", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "docusign_list_envelopes",
                    "description": "List DocuSign envelopes (documents sent for signature).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by status: sent, delivered, completed, declined, voided."},
                            "from_date": {"type": "string", "description": "Filter envelopes from this date (YYYY-MM-DD)."},
                            "limit": {"type": "integer", "description": "Max envelopes (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docusign_get_envelope",
                    "description": "Get details and signing status of a specific DocuSign envelope.",
                    "parameters": {
                        "type": "object",
                        "properties": {"envelope_id": {"type": "string", "description": "DocuSign envelope ID."}},
                        "required": ["envelope_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docusign_send_envelope",
                    "description": "Send a document for signature using a DocuSign template.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "template_id": {"type": "string", "description": "DocuSign template ID to use."},
                            "subject": {"type": "string", "description": "Email subject for the signing request."},
                            "signers": {
                                "type": "array",
                                "description": "List of signers with name, email, and optional role_name.",
                                "items": {"type": "object", "properties": {"name": {"type": "string"}, "email": {"type": "string"}, "role_name": {"type": "string"}}},
                            },
                        },
                        "required": ["template_id", "subject", "signers"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docusign_void_envelope",
                    "description": "Void/cancel a sent DocuSign envelope.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "envelope_id": {"type": "string", "description": "DocuSign envelope ID to void."},
                            "reason": {"type": "string", "description": "Reason for voiding."},
                        },
                        "required": ["envelope_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docusign_list_templates",
                    "description": "List available DocuSign templates.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "search": {"type": "string", "description": "Search term to filter templates by name."},
                            "limit": {"type": "integer", "description": "Max templates (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docusign_list_recipients",
                    "description": "List all recipients (signers, CC'd contacts, certified deliveries) of a DocuSign envelope along with their signing status.",
                    "parameters": {
                        "type": "object",
                        "properties": {"envelope_id": {"type": "string", "description": "DocuSign envelope ID."}},
                        "required": ["envelope_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docusign_send_reminder",
                    "description": "Resend the signing notification email / reminder to all pending recipients of a DocuSign envelope.",
                    "parameters": {
                        "type": "object",
                        "properties": {"envelope_id": {"type": "string", "description": "DocuSign envelope ID to send a reminder for."}},
                        "required": ["envelope_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docusign_list_documents",
                    "description": "List the documents attached to a DocuSign envelope (document IDs, names, types).",
                    "parameters": {
                        "type": "object",
                        "properties": {"envelope_id": {"type": "string", "description": "DocuSign envelope ID."}},
                        "required": ["envelope_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docusign_download_document",
                    "description": "Download a document from a DocuSign envelope as base64-encoded content. Use document_id 'combined' (default) to get all documents merged into a single PDF, including the certificate of completion if requested.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "envelope_id": {"type": "string", "description": "DocuSign envelope ID."},
                            "document_id": {"type": "string", "description": "Document ID to download, or 'combined' for all documents merged (default)."},
                        },
                        "required": ["envelope_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docusign_get_audit_events",
                    "description": "Get the audit trail (who viewed, signed, or took action, and when) for a DocuSign envelope.",
                    "parameters": {
                        "type": "object",
                        "properties": {"envelope_id": {"type": "string", "description": "DocuSign envelope ID."}},
                        "required": ["envelope_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "docusign_get_template",
                    "description": "Get details of a specific DocuSign template, including its signer roles, so an envelope can be built from it accurately.",
                    "parameters": {
                        "type": "object",
                        "properties": {"template_id": {"type": "string", "description": "DocuSign template ID."}},
                        "required": ["template_id"],
                    },
                },
            },
        ]
        callables = {
            "docusign_list_envelopes": self.list_envelopes,
            "docusign_get_envelope": self.get_envelope,
            "docusign_send_envelope": self.send_envelope,
            "docusign_void_envelope": self.void_envelope,
            "docusign_list_templates": self.list_templates,
            "docusign_list_recipients": self.list_recipients,
            "docusign_send_reminder": self.send_reminder,
            "docusign_list_documents": self.list_documents,
            "docusign_download_document": self.download_document,
            "docusign_get_audit_events": self.get_audit_events,
            "docusign_get_template": self.get_template,
        }
        return tools, callables

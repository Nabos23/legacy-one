import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api-m.paypal.com"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector (HTTP {e.response.status_code})."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class PaypalConnector(BaseConnector):
    """PayPal connector using OAuth2 Bearer token."""

    PROVIDER_ID = "paypal"

    def __init__(self, access_token: str, agent_id: str = "") -> None:
        super().__init__(access_token, agent_id=agent_id)
        self._token = access_token
        self._auth_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def get_user_profile(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "paypal_get_user_profile", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/v1/identity/openidconnect/userinfo",
                headers=self._auth_headers,
                params={"schema": "openid"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "user_id": data.get("user_id"),
                "name": data.get("name"),
                "given_name": data.get("given_name"),
                "family_name": data.get("family_name"),
                "email": data.get("email"),
                "verified_account": data.get("verified_account"),
                "account_type": data.get("account_type"),
                "payer_id": data.get("payer_id"),
                "address": data.get("address"),
            })
        except Exception as e:
            return _handle_error("paypal_get_user_profile", e)

    def list_transactions(self, inp: dict) -> str:
        permission_error, start_date = self._check(self.agent_id, self.PROVIDER_ID, "paypal_list_transactions", inp, "start_date")
        if permission_error: return permission_error
        try:
            params = {
                "fields": "all",
                "page_size": inp.get("page_size", 20),
                "start_date": start_date,
            }
            if inp.get("end_date"):
                params["end_date"] = inp["end_date"]
            if inp.get("transaction_status"):
                params["transaction_status"] = inp["transaction_status"]
            resp = httpx.get(
                f"{_BASE}/v1/reporting/transactions",
                headers=self._auth_headers,
                params=params,
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            transactions = [
                {
                    "transaction_id": t.get("transaction_info", {}).get("transaction_id"),
                    "transaction_status": t.get("transaction_info", {}).get("transaction_status"),
                    "transaction_amount": t.get("transaction_info", {}).get("transaction_amount"),
                    "transaction_initiation_date": t.get("transaction_info", {}).get("transaction_initiation_date"),
                    "payer_name": t.get("payer_info", {}).get("payer_name", {}).get("alternate_full_name"),
                    "payer_email": t.get("payer_info", {}).get("email_address"),
                }
                for t in data.get("transaction_details", [])
            ]
            return json.dumps({
                "transactions": transactions,
                "total_items": data.get("total_items"),
                "total_pages": data.get("total_pages"),
            })
        except Exception as e:
            return _handle_error("paypal_list_transactions", e)

    def get_balances(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "paypal_get_balances", inp)
        if permission_error: return permission_error
        try:
            params = {}
            if inp.get("as_of_time"):
                params["as_of_time"] = inp["as_of_time"]
            if inp.get("currency_code"):
                params["currency_code"] = inp["currency_code"]
            resp = httpx.get(
                f"{_BASE}/v1/reporting/balances",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "balances": data.get("balances", []),
                "account_id": data.get("account_id"),
                "as_of_time": data.get("as_of_time"),
                "last_refresh_time": data.get("last_refresh_time"),
            })
        except Exception as e:
            return _handle_error("paypal_get_balances", e)

    def list_invoices(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "paypal_list_invoices", inp)
        if permission_error: return permission_error
        try:
            params = {
                "page": inp.get("page", 1),
                "page_size": inp.get("page_size", 20),
                "total_required": True,
            }
            if inp.get("status"):
                params["status"] = inp["status"]
            resp = httpx.get(
                f"{_BASE}/v2/invoicing/invoices",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            invoices = [
                {
                    "id": inv.get("id"),
                    "status": inv.get("status"),
                    "detail": {
                        "invoice_number": inv.get("detail", {}).get("invoice_number"),
                        "invoice_date": inv.get("detail", {}).get("invoice_date"),
                        "currency_code": inv.get("detail", {}).get("currency_code"),
                    },
                    "invoicer": inv.get("invoicer", {}).get("name", {}).get("full_name"),
                    "primary_recipients": [
                        r.get("billing_info", {}).get("email_address")
                        for r in inv.get("primary_recipients", [])
                    ],
                    "amount": inv.get("amount"),
                    "due_amount": inv.get("due_amount"),
                    "link": next((l["href"] for l in inv.get("links", []) if l.get("rel") == "self"), None),
                }
                for inv in data.get("items", [])
            ]
            return json.dumps({
                "invoices": invoices,
                "total_items": data.get("total_items"),
                "total_pages": data.get("total_pages"),
            })
        except Exception as e:
            return _handle_error("paypal_list_invoices", e)

    def get_invoice(self, inp: dict) -> str:
        permission_error, invoice_id = self._check(self.agent_id, self.PROVIDER_ID, "paypal_get_invoice", inp, "invoice_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/v2/invoicing/invoices/{invoice_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            inv = resp.json()
            return json.dumps({
                "id": inv.get("id"),
                "status": inv.get("status"),
                "detail": inv.get("detail"),
                "invoicer": inv.get("invoicer"),
                "primary_recipients": inv.get("primary_recipients"),
                "items": inv.get("items"),
                "amount": inv.get("amount"),
                "due_amount": inv.get("due_amount"),
                "payments": inv.get("payments"),
            })
        except Exception as e:
            return _handle_error("paypal_get_invoice", e)

    def get_payment_capture(self, inp: dict) -> str:
        permission_error, capture_id = self._check(self.agent_id, self.PROVIDER_ID, "paypal_get_payment_capture", inp, "capture_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/v2/payments/captures/{capture_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            cap = resp.json()
            return json.dumps({
                "id": cap.get("id"),
                "status": cap.get("status"),
                "amount": cap.get("amount"),
                "final_capture": cap.get("final_capture"),
                "seller_protection": cap.get("seller_protection"),
                "seller_receivable_breakdown": cap.get("seller_receivable_breakdown"),
                "create_time": cap.get("create_time"),
                "update_time": cap.get("update_time"),
            })
        except Exception as e:
            return _handle_error("paypal_get_payment_capture", e)

    def search_transactions(self, inp: dict) -> str:
        permission_error, start_date = self._check(self.agent_id, self.PROVIDER_ID, "paypal_search_transactions", inp, "start_date")
        if permission_error: return permission_error
        try:
            params = {
                "fields": "all",
                "page_size": inp.get("page_size", 20),
                "start_date": start_date,
            }
            if inp.get("end_date"):
                params["end_date"] = inp["end_date"]
            if inp.get("transaction_id"):
                params["transaction_id"] = inp["transaction_id"]
            if inp.get("transaction_type"):
                params["transaction_type"] = inp["transaction_type"]
            if inp.get("transaction_amount"):
                params["transaction_amount"] = inp["transaction_amount"]
            if inp.get("transaction_currency"):
                params["transaction_currency"] = inp["transaction_currency"]
            resp = httpx.get(
                f"{_BASE}/v1/reporting/transactions",
                headers=self._auth_headers,
                params=params,
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            transactions = [
                {
                    "transaction_id": t.get("transaction_info", {}).get("transaction_id"),
                    "transaction_event_code": t.get("transaction_info", {}).get("transaction_event_code"),
                    "transaction_status": t.get("transaction_info", {}).get("transaction_status"),
                    "transaction_amount": t.get("transaction_info", {}).get("transaction_amount"),
                    "fee_amount": t.get("transaction_info", {}).get("fee_amount"),
                    "transaction_initiation_date": t.get("transaction_info", {}).get("transaction_initiation_date"),
                    "payer_name": t.get("payer_info", {}).get("payer_name", {}).get("alternate_full_name"),
                    "payer_email": t.get("payer_info", {}).get("email_address"),
                    "item_details": t.get("cart_info", {}).get("item_details", []),
                }
                for t in data.get("transaction_details", [])
            ]
            return json.dumps({
                "transactions": transactions,
                "total_items": data.get("total_items"),
                "total_pages": data.get("total_pages"),
            })
        except Exception as e:
            return _handle_error("paypal_search_transactions", e)

    def create_order(self, inp: dict) -> str:
        permission_error, amount = self._check(self.agent_id, self.PROVIDER_ID, "paypal_create_order", inp, "amount")
        if permission_error: return permission_error
        currency = inp.get("currency_code", "USD")
        payload: dict = {
            "intent": inp.get("intent", "CAPTURE"),
            "purchase_units": [
                {
                    "amount": {"currency_code": currency, "value": str(amount)},
                    **({"description": inp["description"]} if inp.get("description") else {}),
                }
            ],
        }
        try:
            resp = httpx.post(
                f"{_BASE}/v2/checkout/orders",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            order = resp.json()
            return json.dumps({
                "id": order.get("id"),
                "status": order.get("status"),
                "approve_link": next((l["href"] for l in order.get("links", []) if l.get("rel") == "approve"), None),
            })
        except Exception as e:
            return _handle_error("paypal_create_order", e)

    def capture_order(self, inp: dict) -> str:
        permission_error, order_id = self._check(self.agent_id, self.PROVIDER_ID, "paypal_capture_order", inp, "order_id")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{_BASE}/v2/checkout/orders/{order_id}/capture",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("paypal_capture_order", e)

    def refund_capture(self, inp: dict) -> str:
        permission_error, capture_id = self._check(self.agent_id, self.PROVIDER_ID, "paypal_refund_capture", inp, "capture_id")
        if permission_error: return permission_error
        payload: dict = {}
        if inp.get("amount"):
            payload["amount"] = {"value": str(inp["amount"]), "currency_code": inp.get("currency_code", "USD")}
        if inp.get("note_to_payer"):
            payload["note_to_payer"] = inp["note_to_payer"]
        try:
            resp = httpx.post(
                f"{_BASE}/v2/payments/captures/{capture_id}/refund",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=payload if payload else None,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("paypal_refund_capture", e)

    def create_payout(self, inp: dict) -> str:
        permission_error, receiver_email, amount = self._check(self.agent_id, self.PROVIDER_ID, "paypal_create_payout", inp, "receiver_email", "amount")
        if permission_error: return permission_error
        payload: dict = {
            "sender_batch_header": {
                "sender_batch_id": inp.get("sender_batch_id") or f"batch_{receiver_email}",
                "email_subject": inp.get("email_subject", "You have a payout!"),
            },
            "items": [
                {
                    "recipient_type": "EMAIL",
                    "amount": {"value": str(amount), "currency": inp.get("currency_code", "USD")},
                    "receiver": receiver_email,
                    "note": inp.get("note", "Payout"),
                }
            ],
        }
        try:
            resp = httpx.post(
                f"{_BASE}/v1/payments/payouts",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=payload,
                timeout=20,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("paypal_create_payout", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "paypal_get_user_profile",
                    "description": "Get the authenticated PayPal user's profile information including name, email, and account details.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "paypal_list_transactions",
                    "description": "List PayPal transactions within a date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "description": "Start date in ISO 8601 format (e.g. 2024-01-01T00:00:00-0700). Required by PayPal."},
                            "end_date": {"type": "string", "description": "End date in ISO 8601 format. Defaults to now if omitted."},
                            "transaction_status": {"type": "string", "description": "Filter by status: D (denied), P (pending), S (success), V (reversed)."},
                            "page_size": {"type": "integer", "description": "Number of transactions to return (default 20, max 500)."},
                        },
                        "required": ["start_date"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "paypal_get_balances",
                    "description": "Get PayPal account balances as of a specific time or current balances.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "as_of_time": {"type": "string", "description": "ISO 8601 datetime to get balances as of that time."},
                            "currency_code": {"type": "string", "description": "Filter by currency code (e.g. USD, EUR)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "paypal_list_invoices",
                    "description": "List PayPal invoices, optionally filtered by status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by invoice status: DRAFT, SENT, SCHEDULED, PAYMENT_PENDING, PAID, MARKED_AS_PAID, CANCELLED, REFUNDED, PARTIALLY_PAID, PARTIALLY_REFUNDED, MARKED_AS_REFUNDED, UNPAID, PAYMENT_INITIATED."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                            "page_size": {"type": "integer", "description": "Invoices per page (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "paypal_get_invoice",
                    "description": "Get full details of a specific PayPal invoice.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "invoice_id": {"type": "string", "description": "PayPal invoice ID."},
                        },
                        "required": ["invoice_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "paypal_get_payment_capture",
                    "description": "Get details of a specific PayPal payment capture.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "capture_id": {"type": "string", "description": "PayPal payment capture ID."},
                        },
                        "required": ["capture_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "paypal_search_transactions",
                    "description": "Search PayPal transactions with filters such as transaction ID, type, amount, or currency.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "description": "Start date in ISO 8601 format. Required by PayPal."},
                            "end_date": {"type": "string", "description": "End date in ISO 8601 format."},
                            "transaction_id": {"type": "string", "description": "Filter by specific transaction ID."},
                            "transaction_type": {"type": "string", "description": "Filter by transaction event code (e.g. T0001 for PayPal transfers)."},
                            "transaction_amount": {"type": "string", "description": "Filter by transaction amount (e.g. '10.00')."},
                            "transaction_currency": {"type": "string", "description": "Filter by currency code (e.g. USD)."},
                            "page_size": {"type": "integer", "description": "Number of results (default 20, max 500)."},
                        },
                        "required": ["start_date"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "paypal_create_order",
                    "description": "Create a new PayPal checkout order for a payment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": "string", "description": "Order amount (e.g. '19.99')."},
                            "currency_code": {"type": "string", "description": "3-letter currency code (default USD)."},
                            "description": {"type": "string", "description": "Optional description of the purchase."},
                            "intent": {"type": "string", "description": "CAPTURE or AUTHORIZE (default CAPTURE).", "enum": ["CAPTURE", "AUTHORIZE"]},
                        },
                        "required": ["amount"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "paypal_capture_order",
                    "description": "Capture payment for an approved PayPal order.",
                    "parameters": {
                        "type": "object",
                        "properties": {"order_id": {"type": "string", "description": "The PayPal order ID to capture."}},
                        "required": ["order_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "paypal_refund_capture",
                    "description": "Refund a captured PayPal payment, fully or partially.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "capture_id": {"type": "string", "description": "The PayPal capture ID to refund."},
                            "amount": {"type": "string", "description": "Amount to refund (omit for full refund)."},
                            "currency_code": {"type": "string", "description": "3-letter currency code (default USD, used with amount)."},
                            "note_to_payer": {"type": "string", "description": "Optional note shown to the payer."},
                        },
                        "required": ["capture_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "paypal_create_payout",
                    "description": "Send a PayPal payout to a recipient's email address.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "receiver_email": {"type": "string", "description": "Recipient's PayPal email address."},
                            "amount": {"type": "string", "description": "Payout amount (e.g. '50.00')."},
                            "currency_code": {"type": "string", "description": "3-letter currency code (default USD)."},
                            "note": {"type": "string", "description": "Note shown to the recipient."},
                            "email_subject": {"type": "string", "description": "Subject of the payout notification email."},
                            "sender_batch_id": {"type": "string", "description": "Unique ID for this payout batch to prevent duplicates."},
                        },
                        "required": ["receiver_email", "amount"],
                    },
                },
            },
        ]
        callables = {
            "paypal_get_user_profile": self.get_user_profile,
            "paypal_list_transactions": self.list_transactions,
            "paypal_get_balances": self.get_balances,
            "paypal_list_invoices": self.list_invoices,
            "paypal_get_invoice": self.get_invoice,
            "paypal_get_payment_capture": self.get_payment_capture,
            "paypal_search_transactions": self.search_transactions,
            "paypal_create_order": self.create_order,
            "paypal_capture_order": self.capture_order,
            "paypal_refund_capture": self.refund_capture,
            "paypal_create_payout": self.create_payout,
        }
        return tools, callables

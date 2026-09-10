import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.freshbooks.com"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector (HTTP {e.response.status_code})."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class FreshBooksConnector(BaseConnector):
    """FreshBooks connector. access_token format: 'TOKEN:ACCOUNT_ID'."""

    PROVIDER_ID = "freshbooks"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id=agent_id)
        parts = access_token.split(":", 1)
        self._token = parts[0]
        self._account_id = parts[1] if len(parts) > 1 else ""

    @property
    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}

    @_auth_headers.setter
    def _auth_headers(self, value: dict) -> None:
        pass

    def _acct_url(self, path: str) -> str:
        return f"{_BASE}/accounting/account/{self._account_id}/{path}"

    def get_identity(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "freshbooks_get_identity", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/auth/api/v1/users/me", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("response", {})
            memberships = [
                {
                    "business_name": m.get("business", {}).get("name"),
                    "account_id": m.get("account_id"),
                    "business_id": m.get("business", {}).get("id"),
                    "role": m.get("role"),
                }
                for m in data.get("business_memberships", [])
            ]
            return json.dumps({
                "id": data.get("id"),
                "email": data.get("email"),
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "business_memberships": memberships,
            })
        except Exception as e:
            return _handle_error("freshbooks_get_identity", e)

    def list_invoices(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "freshbooks_list_invoices", inp)
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("limit", 25), "page": inp.get("page", 1)}
            if inp.get("status"):
                params["invoice_status[]"] = inp["status"]
            resp = httpx.get(self._acct_url("invoices/invoices"), headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            result = resp.json().get("response", {}).get("result", {})
            invoices = [
                {
                    "id": inv.get("id"),
                    "invoice_number": inv.get("invoice_number"),
                    "client_id": inv.get("customerid"),
                    "status": inv.get("v3_status"),
                    "amount": inv.get("amount", {}).get("amount"),
                    "currency": inv.get("currency_code"),
                    "due_date": inv.get("due_date"),
                    "create_date": inv.get("create_date"),
                    "paid": inv.get("paid", {}).get("amount"),
                    "outstanding": inv.get("outstanding", {}).get("amount"),
                }
                for inv in result.get("invoices", [])
            ]
            return json.dumps({"invoices": invoices, "count": len(invoices), "total": result.get("total", 0)})
        except Exception as e:
            return _handle_error("freshbooks_list_invoices", e)

    def get_invoice(self, inp: dict) -> str:
        permission_error, invoice_id = self._check(self.agent_id, self.PROVIDER_ID, "freshbooks_get_invoice", inp, "invoice_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(self._acct_url(f"invoices/invoices/{invoice_id}"), headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            inv = resp.json().get("response", {}).get("result", {}).get("invoice", {})
            return json.dumps({
                "id": inv.get("id"),
                "invoice_number": inv.get("invoice_number"),
                "client_id": inv.get("customerid"),
                "status": inv.get("v3_status"),
                "amount": inv.get("amount", {}).get("amount"),
                "currency": inv.get("currency_code"),
                "due_date": inv.get("due_date"),
                "create_date": inv.get("create_date"),
                "paid": inv.get("paid", {}).get("amount"),
                "outstanding": inv.get("outstanding", {}).get("amount"),
                "notes": inv.get("notes"),
                "lines": [
                    {
                        "description": line.get("description"),
                        "quantity": line.get("qty"),
                        "unit_cost": line.get("unit_cost", {}).get("amount"),
                        "amount": line.get("amount", {}).get("amount"),
                    }
                    for line in inv.get("lines", [])
                ],
            })
        except Exception as e:
            return _handle_error("freshbooks_get_invoice", e)

    def list_payments(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "freshbooks_list_payments", inp)
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("limit", 25), "page": inp.get("page", 1)}
            if inp.get("start_date"):
                params["updated_min"] = inp["start_date"]
            if inp.get("end_date"):
                params["updated_max"] = inp["end_date"]
            resp = httpx.get(self._acct_url("payments/payments"), headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            result = resp.json().get("response", {}).get("result", {})
            payments = [
                {
                    "id": p.get("id"),
                    "invoice_id": p.get("invoiceid"),
                    "client_id": p.get("clientid"),
                    "amount": p.get("amount", {}).get("amount"),
                    "currency": p.get("currency_code"),
                    "date": p.get("date"),
                    "type": p.get("type"),
                    "note": p.get("note"),
                }
                for p in result.get("payments", [])
            ]
            return json.dumps({"payments": payments, "count": len(payments), "total": result.get("total", 0)})
        except Exception as e:
            return _handle_error("freshbooks_list_payments", e)

    def list_expenses(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "freshbooks_list_expenses", inp)
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("limit", 25), "page": inp.get("page", 1)}
            if inp.get("start_date"):
                params["date_min"] = inp["start_date"]
            if inp.get("end_date"):
                params["date_max"] = inp["end_date"]
            resp = httpx.get(self._acct_url("expenses/expenses"), headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            result = resp.json().get("response", {}).get("result", {})
            expenses = [
                {
                    "id": exp.get("id"),
                    "amount": exp.get("amount", {}).get("amount"),
                    "currency": exp.get("currency_code"),
                    "date": exp.get("date"),
                    "vendor": exp.get("vendor"),
                    "category_id": exp.get("categoryid"),
                    "notes": exp.get("notes"),
                    "client_id": exp.get("clientid"),
                    "status": exp.get("status"),
                }
                for exp in result.get("expenses", [])
            ]
            return json.dumps({"expenses": expenses, "count": len(expenses), "total": result.get("total", 0)})
        except Exception as e:
            return _handle_error("freshbooks_list_expenses", e)

    def get_balance_sheet(self, inp: dict) -> str:
        permission_error, start, end = self._check(self.agent_id, self.PROVIDER_ID, "freshbooks_get_balance_sheet", inp, "start_date", "end_date")
        if permission_error: return permission_error
        try:
            params = {"date_min": start, "date_max": end}
            resp = httpx.get(
                self._acct_url("reports/accounting/balancesheet"),
                headers=self._auth_headers,
                params=params,
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json().get("response", {}).get("result", {}).get("balancesheet", {})
            return json.dumps({
                "start_date": start,
                "end_date": end,
                "assets": data.get("assets"),
                "liabilities": data.get("liabilities"),
                "equity": data.get("equity"),
                "currency": data.get("currency_code"),
            })
        except Exception as e:
            return _handle_error("freshbooks_get_balance_sheet", e)

    def list_clients(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "freshbooks_list_clients", inp)
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("limit", 25), "page": inp.get("page", 1)}
            if inp.get("search"):
                params["search[email]"] = inp["search"]
            resp = httpx.get(self._acct_url("users/clients"), headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            result = resp.json().get("response", {}).get("result", {})
            clients = [
                {
                    "id": c.get("id"),
                    "full_name": f"{c.get('fname', '')} {c.get('lname', '')}".strip(),
                    "organization": c.get("organization"),
                    "email": c.get("email"),
                    "currency": c.get("currency_code"),
                    "outstanding": c.get("outstanding", {}).get("amount"),
                    "overall_outstanding": c.get("s_outstanding", {}).get("amount"),
                }
                for c in result.get("clients", [])
            ]
            return json.dumps({"clients": clients, "count": len(clients), "total": result.get("total", 0)})
        except Exception as e:
            return _handle_error("freshbooks_list_clients", e)

    def create_client(self, inp: dict) -> str:
        permission_error, email = self._check(self.agent_id, self.PROVIDER_ID, "freshbooks_create_client", inp, "email")
        if permission_error: return permission_error
        client: dict = {"email": email}
        if inp.get("first_name"):
            client["fname"] = inp["first_name"]
        if inp.get("last_name"):
            client["lname"] = inp["last_name"]
        if inp.get("organization"):
            client["organization"] = inp["organization"]
        try:
            resp = httpx.post(
                self._acct_url("users/clients"),
                headers=self._auth_headers,
                json={"client": client},
                timeout=15,
            )
            resp.raise_for_status()
            c = resp.json().get("response", {}).get("result", {}).get("client", {})
            return json.dumps({"id": c.get("id"), "email": c.get("email"), "status": "created"})
        except Exception as e:
            return _handle_error("freshbooks_create_client", e)

    def create_invoice(self, inp: dict) -> str:
        permission_error, client_id, lines = self._check(self.agent_id, self.PROVIDER_ID, "freshbooks_create_invoice", inp, "client_id", "lines")
        if permission_error: return permission_error
        invoice: dict = {
            "customerid": client_id,
            "create_date": inp.get("create_date"),
            "lines": [
                {
                    "name": line.get("name", ""),
                    "description": line.get("description", ""),
                    "qty": line.get("quantity", 1),
                    "unit_cost": {"amount": str(line.get("unit_cost", "0")), "code": inp.get("currency_code", "USD")},
                }
                for line in lines
            ],
        }
        try:
            resp = httpx.post(
                self._acct_url("invoices/invoices"),
                headers=self._auth_headers,
                json={"invoice": invoice},
                timeout=15,
            )
            resp.raise_for_status()
            inv = resp.json().get("response", {}).get("result", {}).get("invoice", {})
            return json.dumps({"id": inv.get("id"), "invoice_number": inv.get("invoice_number"), "status": "created"})
        except Exception as e:
            return _handle_error("freshbooks_create_invoice", e)

    def create_expense(self, inp: dict) -> str:
        permission_error, amount, category_id = self._check(self.agent_id, self.PROVIDER_ID, "freshbooks_create_expense", inp, "amount", "category_id")
        if permission_error: return permission_error
        expense: dict = {
            "amount": {"amount": str(amount), "code": inp.get("currency_code", "USD")},
            "categoryid": category_id,
            "date": inp.get("date"),
        }
        if inp.get("vendor"):
            expense["vendor"] = inp["vendor"]
        if inp.get("notes"):
            expense["notes"] = inp["notes"]
        if inp.get("client_id"):
            expense["clientid"] = inp["client_id"]
        try:
            resp = httpx.post(
                self._acct_url("expenses/expenses"),
                headers=self._auth_headers,
                json={"expense": expense},
                timeout=15,
            )
            resp.raise_for_status()
            exp = resp.json().get("response", {}).get("result", {}).get("expense", {})
            return json.dumps({"id": exp.get("id"), "amount": exp.get("amount", {}).get("amount"), "status": "created"})
        except Exception as e:
            return _handle_error("freshbooks_create_expense", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "freshbooks_get_identity",
                    "description": "Get the authenticated FreshBooks user's profile and list of business memberships with account IDs.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "freshbooks_list_invoices",
                    "description": "List invoices from FreshBooks with optional status filter.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by invoice status: draft, sent, viewed, paid, overdue, partial."},
                            "limit": {"type": "integer", "description": "Max invoices per page (default 25)."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "freshbooks_get_invoice",
                    "description": "Get details of a single FreshBooks invoice including line items.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "invoice_id": {"type": "string", "description": "The FreshBooks invoice ID."},
                        },
                        "required": ["invoice_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "freshbooks_list_payments",
                    "description": "List payments recorded in FreshBooks, optionally filtered by date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "description": "Filter payments updated from this date (YYYY-MM-DD)."},
                            "end_date": {"type": "string", "description": "Filter payments updated until this date (YYYY-MM-DD)."},
                            "limit": {"type": "integer", "description": "Max payments per page (default 25)."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "freshbooks_list_expenses",
                    "description": "List expenses from FreshBooks, optionally filtered by date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "description": "Expenses from this date (YYYY-MM-DD)."},
                            "end_date": {"type": "string", "description": "Expenses until this date (YYYY-MM-DD)."},
                            "limit": {"type": "integer", "description": "Max expenses per page (default 25)."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "freshbooks_get_balance_sheet",
                    "description": "Get a balance sheet report from FreshBooks for a given date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "description": "Report start date (YYYY-MM-DD)."},
                            "end_date": {"type": "string", "description": "Report end date (YYYY-MM-DD)."},
                        },
                        "required": ["start_date", "end_date"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "freshbooks_list_clients",
                    "description": "List clients in FreshBooks with optional email search.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "search": {"type": "string", "description": "Filter clients by email address."},
                            "limit": {"type": "integer", "description": "Max clients per page (default 25)."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "freshbooks_create_client",
                    "description": "Create a new client in FreshBooks.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string", "description": "Client's email address."},
                            "first_name": {"type": "string", "description": "Client's first name (optional)."},
                            "last_name": {"type": "string", "description": "Client's last name (optional)."},
                            "organization": {"type": "string", "description": "Client's organization/company name (optional)."},
                        },
                        "required": ["email"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "freshbooks_create_invoice",
                    "description": "Create a new invoice in FreshBooks for a client.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "client_id": {"type": "string", "description": "FreshBooks client ID to bill."},
                            "create_date": {"type": "string", "description": "Invoice date (YYYY-MM-DD, optional)."},
                            "currency_code": {"type": "string", "description": "3-letter currency code (default USD)."},
                            "lines": {
                                "type": "array",
                                "description": "Invoice line items.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string", "description": "Line item name."},
                                        "description": {"type": "string", "description": "Line item description."},
                                        "quantity": {"type": "number", "description": "Quantity (default 1)."},
                                        "unit_cost": {"type": "number", "description": "Unit price."},
                                    },
                                    "required": ["unit_cost"],
                                },
                            },
                        },
                        "required": ["client_id", "lines"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "freshbooks_create_expense",
                    "description": "Record a new expense in FreshBooks.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": "string", "description": "Expense amount."},
                            "category_id": {"type": "string", "description": "FreshBooks expense category ID."},
                            "currency_code": {"type": "string", "description": "3-letter currency code (default USD)."},
                            "date": {"type": "string", "description": "Expense date (YYYY-MM-DD, optional)."},
                            "vendor": {"type": "string", "description": "Vendor name (optional)."},
                            "notes": {"type": "string", "description": "Notes about the expense (optional)."},
                            "client_id": {"type": "string", "description": "Associate expense with a billable client (optional)."},
                        },
                        "required": ["amount", "category_id"],
                    },
                },
            },
        ]
        callables = {
            "freshbooks_get_identity": self.get_identity,
            "freshbooks_list_invoices": self.list_invoices,
            "freshbooks_get_invoice": self.get_invoice,
            "freshbooks_list_payments": self.list_payments,
            "freshbooks_list_expenses": self.list_expenses,
            "freshbooks_get_balance_sheet": self.get_balance_sheet,
            "freshbooks_list_clients": self.list_clients,
            "freshbooks_create_client": self.create_client,
            "freshbooks_create_invoice": self.create_invoice,
            "freshbooks_create_expense": self.create_expense,
        }
        return tools, callables

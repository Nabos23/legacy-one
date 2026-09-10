import json
import httpx

from ai.connectors.base import BaseConnector

_DISCOVERY = "https://developer.api.intuit.com/.well-known/openid_configuration"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the QuickBooks token is invalid or expired "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their QuickBooks connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class QuickBooksConnector(BaseConnector):
    """
    QuickBooks Online connector.
    access_token format: "ACCESS_TOKEN:REALM_ID"
    REALM_ID is the QuickBooks company ID.
    """

    PROVIDER_ID = "quickbooks"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        parts = access_token.split(":", 1)
        self._token = parts[0]
        self._realm_id = parts[1] if len(parts) > 1 else ""
        super().__init__(self._token, agent_id=agent_id)
        self._base = f"https://quickbooks.api.intuit.com/v3/company/{self._realm_id}"

    @property
    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}

    @_auth_headers.setter
    def _auth_headers(self, value: dict) -> None:
        pass

    def _query(self, sql: str) -> dict:
        resp = httpx.get(f"{self._base}/query", headers=self._auth_headers, params={"query": sql, "minorversion": "65"}, timeout=15)
        resp.raise_for_status()
        return resp.json().get("QueryResponse", {})

    def get_company_info(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_get_company_info", inp)
        if permission_error: return permission_error
        try:
            data = self._query("SELECT * FROM CompanyInfo")
            info = data.get("CompanyInfo", [{}])[0]
            return json.dumps({
                "company_name": info.get("CompanyName"),
                "legal_name": info.get("LegalName"),
                "country": info.get("Country"),
                "fiscal_year_start": info.get("FiscalYearStartMonth"),
                "email": info.get("Email", {}).get("Address"),
            })
        except Exception as e:
            return _handle_error("quickbooks_get_company_info", e)

    def list_invoices(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_list_invoices", inp)
        if permission_error: return permission_error
        try:
            limit = inp.get("limit", 20)
            where = ""
            if inp.get("status") == "unpaid":
                where = "WHERE Balance > '0'"
            sql = f"SELECT * FROM Invoice {where} ORDER BY TxnDate DESC MAXRESULTS {limit}"
            data = self._query(sql)
            invoices = [
                {
                    "id": inv["Id"],
                    "doc_number": inv.get("DocNumber"),
                    "customer": inv.get("CustomerRef", {}).get("name"),
                    "total": inv.get("TotalAmt"),
                    "balance": inv.get("Balance"),
                    "due_date": inv.get("DueDate"),
                    "txn_date": inv.get("TxnDate"),
                }
                for inv in data.get("Invoice", [])
            ]
            return json.dumps({"invoices": invoices, "count": len(invoices)})
        except Exception as e:
            return _handle_error("quickbooks_list_invoices", e)

    def list_customers(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_list_customers", inp)
        if permission_error: return permission_error
        try:
            limit = inp.get("limit", 25)
            sql = f"SELECT * FROM Customer WHERE Active = true MAXRESULTS {limit}"
            data = self._query(sql)
            customers = [
                {
                    "id": c["Id"],
                    "display_name": c.get("DisplayName"),
                    "email": c.get("PrimaryEmailAddr", {}).get("Address"),
                    "phone": c.get("PrimaryPhone", {}).get("FreeFormNumber"),
                    "balance": c.get("Balance"),
                    "currency": c.get("CurrencyRef", {}).get("value"),
                }
                for c in data.get("Customer", [])
            ]
            return json.dumps({"customers": customers, "count": len(customers)})
        except Exception as e:
            return _handle_error("quickbooks_list_customers", e)

    def list_expenses(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_list_expenses", inp)
        if permission_error: return permission_error
        try:
            limit = inp.get("limit", 20)
            sql = f"SELECT * FROM Purchase ORDER BY TxnDate DESC MAXRESULTS {limit}"
            data = self._query(sql)
            expenses = [
                {
                    "id": exp["Id"],
                    "total": exp.get("TotalAmt"),
                    "txn_date": exp.get("TxnDate"),
                    "account": exp.get("AccountRef", {}).get("name"),
                    "payment_method": exp.get("PaymentMethodRef", {}).get("name"),
                    "memo": exp.get("PrivateNote"),
                }
                for exp in data.get("Purchase", [])
            ]
            return json.dumps({"expenses": expenses, "count": len(expenses)})
        except Exception as e:
            return _handle_error("quickbooks_list_expenses", e)

    def get_profit_and_loss(self, inp: dict) -> str:
        permission_error, start, end = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_get_profit_and_loss", inp, "start_date", "end_date")
        if permission_error: return permission_error
        try:
            params = {"start_date": start, "end_date": end, "minorversion": "65"}
            resp = httpx.get(f"{self._base}/reports/ProfitAndLoss", headers=self._auth_headers, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            header = data.get("Header", {})
            rows = data.get("Rows", {}).get("Row", [])
            summary = {}
            for row in rows:
                if row.get("type") == "Section" and row.get("group") in ("Income", "Expenses", "NetIncome"):
                    cols = row.get("Summary", {}).get("ColData", [])
                    if len(cols) > 1:
                        summary[row["group"]] = cols[1].get("value", "0")
            return json.dumps({
                "period": f"{header.get('StartPeriod')} to {header.get('EndPeriod')}",
                "currency": header.get("Currency"),
                "summary": summary,
            })
        except Exception as e:
            return _handle_error("quickbooks_get_profit_and_loss", e)

    def list_accounts(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_list_accounts", inp)
        if permission_error: return permission_error
        try:
            limit = inp.get("limit", 30)
            account_type = inp.get("account_type", "")
            where = f"WHERE AccountType = '{account_type}'" if account_type else ""
            sql = f"SELECT * FROM Account {where} MAXRESULTS {limit}"
            data = self._query(sql)
            accounts = [
                {
                    "id": a["Id"],
                    "name": a.get("Name"),
                    "account_type": a.get("AccountType"),
                    "account_sub_type": a.get("AccountSubType"),
                    "current_balance": a.get("CurrentBalance"),
                    "currency": a.get("CurrencyRef", {}).get("value"),
                }
                for a in data.get("Account", [])
            ]
            return json.dumps({"accounts": accounts, "count": len(accounts)})
        except Exception as e:
            return _handle_error("quickbooks_list_accounts", e)

    def create_invoice(self, inp: dict) -> str:
        permission_error, customer_id, line_items = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_create_invoice", inp, "customer_id", "line_items")
        if permission_error: return permission_error
        due_date = inp.get("due_date")
        body = {
            "CustomerRef": {"value": customer_id},
            "Line": [
                {
                    "Amount": item["amount"],
                    "DetailType": "SalesItemLineDetail",
                    "Description": item.get("description", ""),
                    "SalesItemLineDetail": {"ItemRef": {"value": "1", "name": "Services"}},
                }
                for item in line_items
            ],
        }
        if due_date:
            body["DueDate"] = due_date
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{self._base}/invoice",
                headers=headers,
                params={"minorversion": "65"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            inv = resp.json().get("Invoice", {})
            return json.dumps({
                "id": inv.get("Id"),
                "doc_number": inv.get("DocNumber"),
                "total_amount": inv.get("TotalAmt"),
                "due_date": inv.get("DueDate"),
                "status": inv.get("EmailStatus"),
            })
        except Exception as e:
            return _handle_error("quickbooks_create_invoice", e)

    def list_vendors(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_list_vendors", inp)
        if permission_error: return permission_error
        try:
            limit = inp.get("limit", 20)
            sql = f"SELECT * FROM Vendor MAXRESULTS {limit}"
            data = self._query(sql)
            vendors = [
                {
                    "id": v["Id"],
                    "name": v.get("DisplayName"),
                    "email": v.get("PrimaryEmailAddr", {}).get("Address"),
                    "balance": v.get("Balance"),
                }
                for v in data.get("Vendor", [])
            ]
            return json.dumps({"vendors": vendors, "count": len(vendors)})
        except Exception as e:
            return _handle_error("quickbooks_list_vendors", e)

    def create_expense(self, inp: dict) -> str:
        permission_error, account_id, amount = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_create_expense", inp, "account_id", "amount")
        if permission_error: return permission_error
        vendor_name = inp.get("vendor_name")
        memo = inp.get("memo")
        payment_type = inp.get("payment_type", "Cash")
        body: dict = {
            "PaymentType": payment_type,
            "AccountRef": {"value": account_id},
            "Line": [
                {
                    "Amount": amount,
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail": {"AccountRef": {"value": account_id}},
                }
            ],
        }
        if vendor_name:
            body["EntityRef"] = {"name": vendor_name, "type": "Vendor"}
        if memo:
            body["PrivateNote"] = memo
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{self._base}/purchase",
                headers=headers,
                params={"minorversion": "65"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            purchase = resp.json().get("Purchase", {})
            return json.dumps({
                "id": purchase.get("Id"),
                "total": purchase.get("TotalAmt"),
                "txn_date": purchase.get("TxnDate"),
                "payment_type": purchase.get("PaymentType"),
            })
        except Exception as e:
            return _handle_error("quickbooks_create_expense", e)

    def get_invoice(self, inp: dict) -> str:
        permission_error, invoice_id = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_get_invoice", inp, "invoice_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{self._base}/invoice/{invoice_id}",
                headers=self._auth_headers,
                params={"minorversion": "65"},
                timeout=15,
            )
            resp.raise_for_status()
            inv = resp.json().get("Invoice", {})
            return json.dumps({
                "id": inv.get("Id"),
                "doc_number": inv.get("DocNumber"),
                "customer": inv.get("CustomerRef", {}).get("name"),
                "total_amount": inv.get("TotalAmt"),
                "balance": inv.get("Balance"),
                "due_date": inv.get("DueDate"),
                "txn_date": inv.get("TxnDate"),
                "status": inv.get("EmailStatus"),
            })
        except Exception as e:
            return _handle_error("quickbooks_get_invoice", e)

    def create_customer(self, inp: dict) -> str:
        permission_error, display_name = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_create_customer", inp, "display_name")
        if permission_error: return permission_error
        email = inp.get("email")
        phone = inp.get("phone")
        body: dict = {"DisplayName": display_name}
        if email:
            body["PrimaryEmailAddr"] = {"Address": email}
        if phone:
            body["PrimaryPhone"] = {"FreeFormNumber": phone}
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{self._base}/customer",
                headers=headers,
                params={"minorversion": "65"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            c = resp.json().get("Customer", {})
            return json.dumps({
                "id": c.get("Id"),
                "display_name": c.get("DisplayName"),
                "email": c.get("PrimaryEmailAddr", {}).get("Address"),
                "phone": c.get("PrimaryPhone", {}).get("FreeFormNumber"),
            })
        except Exception as e:
            return _handle_error("quickbooks_create_customer", e)

    def get_customer(self, inp: dict) -> str:
        permission_error, customer_id = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_get_customer", inp, "customer_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{self._base}/customer/{customer_id}",
                headers=self._auth_headers,
                params={"minorversion": "65"},
                timeout=15,
            )
            resp.raise_for_status()
            c = resp.json().get("Customer", {})
            return json.dumps({
                "id": c.get("Id"),
                "display_name": c.get("DisplayName"),
                "email": c.get("PrimaryEmailAddr", {}).get("Address"),
                "phone": c.get("PrimaryPhone", {}).get("FreeFormNumber"),
                "balance": c.get("Balance"),
                "currency": c.get("CurrencyRef", {}).get("value"),
            })
        except Exception as e:
            return _handle_error("quickbooks_get_customer", e)

    def record_payment(self, inp: dict) -> str:
        permission_error, customer_id, amount = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_record_payment", inp, "customer_id", "amount")
        if permission_error: return permission_error
        invoice_id = inp.get("invoice_id")
        body: dict = {
            "CustomerRef": {"value": customer_id},
            "TotalAmt": amount,
        }
        if invoice_id:
            body["Line"] = [
                {
                    "Amount": amount,
                    "LinkedTxn": [{"TxnId": invoice_id, "TxnType": "Invoice"}],
                }
            ]
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{self._base}/payment",
                headers=headers,
                params={"minorversion": "65"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            p = resp.json().get("Payment", {})
            return json.dumps({
                "id": p.get("Id"),
                "customer": p.get("CustomerRef", {}).get("name"),
                "total_amount": p.get("TotalAmt"),
                "txn_date": p.get("TxnDate"),
                "unapplied_amount": p.get("UnappliedAmt"),
            })
        except Exception as e:
            return _handle_error("quickbooks_record_payment", e)

    def list_bills(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_list_bills", inp)
        if permission_error: return permission_error
        try:
            limit = inp.get("limit", 20)
            where = ""
            if inp.get("status") == "unpaid":
                where = "WHERE Balance > '0'"
            sql = f"SELECT * FROM Bill {where} ORDER BY TxnDate DESC MAXRESULTS {limit}"
            data = self._query(sql)
            bills = [
                {
                    "id": b["Id"],
                    "vendor": b.get("VendorRef", {}).get("name"),
                    "total": b.get("TotalAmt"),
                    "balance": b.get("Balance"),
                    "due_date": b.get("DueDate"),
                    "txn_date": b.get("TxnDate"),
                }
                for b in data.get("Bill", [])
            ]
            return json.dumps({"bills": bills, "count": len(bills)})
        except Exception as e:
            return _handle_error("quickbooks_list_bills", e)

    def create_bill(self, inp: dict) -> str:
        permission_error, vendor_id, account_id, amount = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_create_bill", inp, "vendor_id", "account_id", "amount")
        if permission_error: return permission_error
        due_date = inp.get("due_date")
        memo = inp.get("memo")
        body: dict = {
            "VendorRef": {"value": vendor_id},
            "Line": [
                {
                    "Amount": amount,
                    "DetailType": "AccountBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail": {"AccountRef": {"value": account_id}},
                }
            ],
        }
        if due_date:
            body["DueDate"] = due_date
        if memo:
            body["PrivateNote"] = memo
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{self._base}/bill",
                headers=headers,
                params={"minorversion": "65"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            bill = resp.json().get("Bill", {})
            return json.dumps({
                "id": bill.get("Id"),
                "vendor": bill.get("VendorRef", {}).get("name"),
                "total": bill.get("TotalAmt"),
                "balance": bill.get("Balance"),
                "due_date": bill.get("DueDate"),
            })
        except Exception as e:
            return _handle_error("quickbooks_create_bill", e)

    def create_estimate(self, inp: dict) -> str:
        permission_error, customer_id, line_items = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_create_estimate", inp, "customer_id", "line_items")
        if permission_error: return permission_error
        body = {
            "CustomerRef": {"value": customer_id},
            "Line": [
                {
                    "Amount": item["amount"],
                    "DetailType": "SalesItemLineDetail",
                    "Description": item.get("description", ""),
                    "SalesItemLineDetail": {"ItemRef": {"value": "1", "name": "Services"}},
                }
                for item in line_items
            ],
        }
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{self._base}/estimate",
                headers=headers,
                params={"minorversion": "65"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            est = resp.json().get("Estimate", {})
            return json.dumps({
                "id": est.get("Id"),
                "doc_number": est.get("DocNumber"),
                "customer": est.get("CustomerRef", {}).get("name"),
                "total_amount": est.get("TotalAmt"),
                "txn_status": est.get("TxnStatus"),
            })
        except Exception as e:
            return _handle_error("quickbooks_create_estimate", e)

    def get_balance_sheet(self, inp: dict) -> str:
        permission_error, start, end = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_get_balance_sheet", inp, "start_date", "end_date")
        if permission_error: return permission_error
        try:
            params = {"start_date": start, "end_date": end, "minorversion": "65"}
            resp = httpx.get(f"{self._base}/reports/BalanceSheet", headers=self._auth_headers, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            header = data.get("Header", {})
            rows = data.get("Rows", {}).get("Row", [])
            summary = {}
            for row in rows:
                if row.get("type") == "Section" and row.get("group") in ("Assets", "Liabilities", "Equity", "LiabilitiesAndEquity"):
                    cols = row.get("Summary", {}).get("ColData", [])
                    if len(cols) > 1:
                        summary[row["group"]] = cols[1].get("value", "0")
            return json.dumps({
                "as_of": header.get("EndPeriod"),
                "currency": header.get("Currency"),
                "summary": summary,
            })
        except Exception as e:
            return _handle_error("quickbooks_get_balance_sheet", e)

    def send_invoice(self, inp: dict) -> str:
        permission_error, invoice_id, email = self._check(self.agent_id, self.PROVIDER_ID, "quickbooks_send_invoice", inp, "invoice_id", "email")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/octet-stream"}
            resp = httpx.post(
                f"{self._base}/invoice/{invoice_id}/send",
                headers=headers,
                params={"sendTo": email, "minorversion": "65"},
                timeout=15,
            )
            resp.raise_for_status()
            inv = resp.json().get("Invoice", {})
            return json.dumps({
                "id": inv.get("Id"),
                "doc_number": inv.get("DocNumber"),
                "email_status": inv.get("EmailStatus"),
                "sent_to": email,
            })
        except Exception as e:
            return _handle_error("quickbooks_send_invoice", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_get_company_info",
                    "description": "Get basic QuickBooks company information.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_list_invoices",
                    "description": "List invoices from QuickBooks Online.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by status: 'unpaid' to show only invoices with outstanding balance."},
                            "limit": {"type": "integer", "description": "Max invoices to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_list_customers",
                    "description": "List customers from QuickBooks Online.",
                    "parameters": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "description": "Max customers (default 25)."}},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_list_expenses",
                    "description": "List recent expenses/purchases from QuickBooks Online.",
                    "parameters": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "description": "Max expenses (default 20)."}},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_get_profit_and_loss",
                    "description": "Get a Profit & Loss report for a date range from QuickBooks.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format."},
                            "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format."},
                        },
                        "required": ["start_date", "end_date"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_list_accounts",
                    "description": "List chart of accounts from QuickBooks Online.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "account_type": {"type": "string", "description": "Filter by type: Bank, Accounts Receivable, Accounts Payable, Credit Card, Expense, Income, etc."},
                            "limit": {"type": "integer", "description": "Max accounts (default 30)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_create_invoice",
                    "description": "Create a new invoice in QuickBooks Online.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "The QuickBooks customer ID to bill."},
                            "line_items": {
                                "type": "array",
                                "description": "List of line items for the invoice.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "description": {"type": "string", "description": "Description of the line item."},
                                        "amount": {"type": "number", "description": "Amount for this line item."},
                                    },
                                    "required": ["amount"],
                                },
                            },
                            "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format (optional)."},
                        },
                        "required": ["customer_id", "line_items"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_list_vendors",
                    "description": "List vendors from QuickBooks Online.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max vendors to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_create_expense",
                    "description": "Create a new expense/purchase in QuickBooks Online.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "account_id": {"type": "string", "description": "The QuickBooks account ID to charge the expense to."},
                            "amount": {"type": "number", "description": "Total expense amount."},
                            "vendor_name": {"type": "string", "description": "Vendor name (optional)."},
                            "memo": {"type": "string", "description": "Private memo/note for the expense (optional)."},
                            "payment_type": {"type": "string", "description": "Payment type: Cash, Check, or CreditCard (default Cash)."},
                        },
                        "required": ["account_id", "amount"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_get_invoice",
                    "description": "Get details of a specific invoice by ID from QuickBooks Online.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "invoice_id": {"type": "string", "description": "The QuickBooks invoice ID."},
                        },
                        "required": ["invoice_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_send_invoice",
                    "description": "Send a QuickBooks invoice to a customer via email.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "invoice_id": {"type": "string", "description": "The QuickBooks invoice ID to send."},
                            "email": {"type": "string", "description": "The recipient email address."},
                        },
                        "required": ["invoice_id", "email"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_create_customer",
                    "description": "Create a new customer in QuickBooks Online.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "display_name": {"type": "string", "description": "The customer's display name."},
                            "email": {"type": "string", "description": "Customer's primary email address (optional)."},
                            "phone": {"type": "string", "description": "Customer's primary phone number (optional)."},
                        },
                        "required": ["display_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_get_customer",
                    "description": "Get details of a specific customer by ID from QuickBooks Online.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "The QuickBooks customer ID."},
                        },
                        "required": ["customer_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_record_payment",
                    "description": "Record a customer payment in QuickBooks Online, optionally applying it to an existing invoice.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "The QuickBooks customer ID making the payment."},
                            "amount": {"type": "number", "description": "Payment amount."},
                            "invoice_id": {"type": "string", "description": "Invoice ID to apply the payment to (optional; if omitted the payment is left unapplied)."},
                        },
                        "required": ["customer_id", "amount"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_list_bills",
                    "description": "List vendor bills from QuickBooks Online.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by status: 'unpaid' to show only bills with outstanding balance."},
                            "limit": {"type": "integer", "description": "Max bills to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_create_bill",
                    "description": "Create a new vendor bill in QuickBooks Online.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "vendor_id": {"type": "string", "description": "The QuickBooks vendor ID being billed."},
                            "account_id": {"type": "string", "description": "The QuickBooks expense account ID to charge."},
                            "amount": {"type": "number", "description": "Total bill amount."},
                            "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format (optional)."},
                            "memo": {"type": "string", "description": "Private memo/note for the bill (optional)."},
                        },
                        "required": ["vendor_id", "account_id", "amount"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_create_estimate",
                    "description": "Create a new estimate/quote for a customer in QuickBooks Online.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "The QuickBooks customer ID to send the estimate to."},
                            "line_items": {
                                "type": "array",
                                "description": "List of line items for the estimate.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "description": {"type": "string", "description": "Description of the line item."},
                                        "amount": {"type": "number", "description": "Amount for this line item."},
                                    },
                                    "required": ["amount"],
                                },
                            },
                        },
                        "required": ["customer_id", "line_items"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "quickbooks_get_balance_sheet",
                    "description": "Get a Balance Sheet report as of a date range from QuickBooks.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format."},
                            "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format (the as-of date)."},
                        },
                        "required": ["start_date", "end_date"],
                    },
                },
            },
        ]
        callables = {
            "quickbooks_get_company_info": self.get_company_info,
            "quickbooks_list_invoices": self.list_invoices,
            "quickbooks_list_customers": self.list_customers,
            "quickbooks_list_expenses": self.list_expenses,
            "quickbooks_get_profit_and_loss": self.get_profit_and_loss,
            "quickbooks_list_accounts": self.list_accounts,
            "quickbooks_create_invoice": self.create_invoice,
            "quickbooks_list_vendors": self.list_vendors,
            "quickbooks_create_expense": self.create_expense,
            "quickbooks_get_invoice": self.get_invoice,
            "quickbooks_send_invoice": self.send_invoice,
            "quickbooks_create_customer": self.create_customer,
            "quickbooks_get_customer": self.get_customer,
            "quickbooks_record_payment": self.record_payment,
            "quickbooks_list_bills": self.list_bills,
            "quickbooks_create_bill": self.create_bill,
            "quickbooks_create_estimate": self.create_estimate,
            "quickbooks_get_balance_sheet": self.get_balance_sheet,
        }
        return tools, callables

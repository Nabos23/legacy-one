import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.xero.com/api.xro/2.0"
_CONNECTIONS_URL = "https://api.xero.com/connections"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector (HTTP {e.response.status_code})."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class XeroConnector(BaseConnector):
    """Xero accounting connector. access_token format: 'ACCESS_TOKEN:TENANT_ID'."""

    PROVIDER_ID = "xero"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        parts = access_token.split(":", 1)
        self._token = parts[0]
        self._tenant_id = parts[1] if len(parts) > 1 else ""
        super().__init__(access_token, agent_id=agent_id)

    @property
    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Xero-tenant-id": self._tenant_id,
        }

    def list_connections(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "xero_list_connections", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                _CONNECTIONS_URL,
                headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            connections = [
                {
                    "tenant_id": c.get("tenantId"),
                    "tenant_name": c.get("tenantName"),
                    "tenant_type": c.get("tenantType"),
                    "created_date_utc": c.get("createdDateUtc"),
                }
                for c in resp.json()
            ]
            return json.dumps({"connections": connections, "count": len(connections)})
        except Exception as e:
            return _handle_error("xero_list_connections", e)

    def list_invoices(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "xero_list_invoices", inp)
        if permission_error: return permission_error
        try:
            params = {}
            if inp.get("status"):
                params["Statuses"] = inp["status"].upper()
            if inp.get("contact_id"):
                params["ContactIDs"] = inp["contact_id"]
            params["page"] = inp.get("page", 1)
            resp = httpx.get(f"{_BASE}/Invoices", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            invoices = [
                {
                    "invoice_id": inv.get("InvoiceID"),
                    "invoice_number": inv.get("InvoiceNumber"),
                    "type": inv.get("Type"),
                    "status": inv.get("Status"),
                    "contact": inv.get("Contact", {}).get("Name"),
                    "date": inv.get("DateString"),
                    "due_date": inv.get("DueDateString"),
                    "total": inv.get("Total"),
                    "amount_due": inv.get("AmountDue"),
                    "currency_code": inv.get("CurrencyCode"),
                }
                for inv in resp.json().get("Invoices", [])
            ]
            return json.dumps({"invoices": invoices, "count": len(invoices)})
        except Exception as e:
            return _handle_error("xero_list_invoices", e)

    def get_invoice(self, inp: dict) -> str:
        permission_error, invoice_id = self._check(self.agent_id, self.PROVIDER_ID, "xero_get_invoice", inp, "invoice_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/Invoices/{invoice_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            invoices = resp.json().get("Invoices", [])
            if not invoices:
                return "Invoice not found."
            inv = invoices[0]
            return json.dumps({
                "invoice_id": inv.get("InvoiceID"),
                "invoice_number": inv.get("InvoiceNumber"),
                "type": inv.get("Type"),
                "status": inv.get("Status"),
                "contact": inv.get("Contact", {}).get("Name"),
                "date": inv.get("DateString"),
                "due_date": inv.get("DueDateString"),
                "sub_total": inv.get("SubTotal"),
                "total_tax": inv.get("TotalTax"),
                "total": inv.get("Total"),
                "amount_due": inv.get("AmountDue"),
                "amount_paid": inv.get("AmountPaid"),
                "currency_code": inv.get("CurrencyCode"),
                "line_items": [
                    {
                        "description": li.get("Description"),
                        "quantity": li.get("Quantity"),
                        "unit_amount": li.get("UnitAmount"),
                        "account_code": li.get("AccountCode"),
                        "line_amount": li.get("LineAmount"),
                    }
                    for li in inv.get("LineItems", [])
                ],
            })
        except Exception as e:
            return _handle_error("xero_get_invoice", e)

    def list_bank_transactions(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "xero_list_bank_transactions", inp)
        if permission_error: return permission_error
        try:
            params = {}
            if inp.get("bank_account_id"):
                params["BankAccountID"] = inp["bank_account_id"]
            if inp.get("from_date"):
                params["fromDate"] = inp["from_date"]
            if inp.get("to_date"):
                params["toDate"] = inp["to_date"]
            params["page"] = inp.get("page", 1)
            resp = httpx.get(f"{_BASE}/BankTransactions", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            transactions = [
                {
                    "bank_transaction_id": tx.get("BankTransactionID"),
                    "type": tx.get("Type"),
                    "status": tx.get("Status"),
                    "contact": tx.get("Contact", {}).get("Name"),
                    "date": tx.get("DateString"),
                    "bank_account": tx.get("BankAccount", {}).get("Name"),
                    "total": tx.get("Total"),
                    "currency_code": tx.get("CurrencyCode"),
                    "reference": tx.get("Reference"),
                }
                for tx in resp.json().get("BankTransactions", [])
            ]
            return json.dumps({"bank_transactions": transactions, "count": len(transactions)})
        except Exception as e:
            return _handle_error("xero_list_bank_transactions", e)

    def list_accounts(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "xero_list_accounts", inp)
        if permission_error: return permission_error
        try:
            params = {}
            account_type = inp.get("account_type", "")
            if account_type:
                params["where"] = f'Type=="{account_type.upper()}"'
            resp = httpx.get(f"{_BASE}/Accounts", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            accounts = [
                {
                    "account_id": a.get("AccountID"),
                    "code": a.get("Code"),
                    "name": a.get("Name"),
                    "type": a.get("Type"),
                    "status": a.get("Status"),
                    "description": a.get("Description"),
                    "currency_code": a.get("CurrencyCode"),
                    "enable_payments_to_account": a.get("EnablePaymentsToAccount"),
                }
                for a in resp.json().get("Accounts", [])
            ]
            return json.dumps({"accounts": accounts, "count": len(accounts)})
        except Exception as e:
            return _handle_error("xero_list_accounts", e)

    def get_balance_sheet(self, inp: dict) -> str:
        permission_error, date = self._check(self.agent_id, self.PROVIDER_ID, "xero_get_balance_sheet", inp, "date")
        if permission_error: return permission_error
        try:
            params = {"date": date}
            resp = httpx.get(f"{_BASE}/Reports/BalanceSheet", headers=self._auth_headers, params=params, timeout=20)
            resp.raise_for_status()
            reports = resp.json().get("Reports", [])
            if not reports:
                return "No balance sheet data returned."
            report = reports[0]
            rows_summary = []
            for row in report.get("Rows", []):
                if row.get("RowType") == "Section":
                    section_title = row.get("Title", "")
                    for r in row.get("Rows", []):
                        if r.get("RowType") == "SummaryRow":
                            cells = r.get("Cells", [])
                            rows_summary.append({
                                "section": section_title,
                                "label": cells[0].get("Value") if cells else "",
                                "value": cells[1].get("Value") if len(cells) > 1 else "",
                            })
            return json.dumps({
                "report_name": report.get("ReportName"),
                "report_date": report.get("ReportDate"),
                "updated_date_utc": report.get("UpdatedDateUTC"),
                "summary": rows_summary,
            })
        except Exception as e:
            return _handle_error("xero_get_balance_sheet", e)

    def get_bank_summary(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "xero_get_bank_summary", inp)
        if permission_error: return permission_error
        try:
            params = {}
            if inp.get("from_date"):
                params["fromDate"] = inp["from_date"]
            if inp.get("to_date"):
                params["toDate"] = inp["to_date"]
            resp = httpx.get(f"{_BASE}/Reports/BankSummary", headers=self._auth_headers, params=params, timeout=20)
            resp.raise_for_status()
            reports = resp.json().get("Reports", [])
            if not reports:
                return "No bank summary data returned."
            report = reports[0]
            rows_data = []
            for row in report.get("Rows", []):
                if row.get("RowType") == "Section":
                    for r in row.get("Rows", []):
                        if r.get("RowType") == "Row":
                            cells = r.get("Cells", [])
                            rows_data.append({
                                "account": cells[0].get("Value") if cells else "",
                                "opening_balance": cells[1].get("Value") if len(cells) > 1 else "",
                                "cash_received": cells[2].get("Value") if len(cells) > 2 else "",
                                "cash_spent": cells[3].get("Value") if len(cells) > 3 else "",
                                "closing_balance": cells[4].get("Value") if len(cells) > 4 else "",
                            })
            return json.dumps({
                "report_name": report.get("ReportName"),
                "report_date": report.get("ReportDate"),
                "accounts": rows_data,
            })
        except Exception as e:
            return _handle_error("xero_get_bank_summary", e)

    def list_contacts(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "xero_list_contacts", inp)
        if permission_error: return permission_error
        try:
            params = {}
            if inp.get("contact_type"):
                contact_type = inp["contact_type"].lower()
                if contact_type == "customer":
                    params["where"] = "IsCustomer==true"
                elif contact_type == "supplier":
                    params["where"] = "IsSupplier==true"
            if inp.get("search"):
                params["searchTerm"] = inp["search"]
            params["page"] = inp.get("page", 1)
            resp = httpx.get(f"{_BASE}/Contacts", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            contacts = [
                {
                    "contact_id": c.get("ContactID"),
                    "name": c.get("Name"),
                    "email": c.get("EmailAddress"),
                    "is_customer": c.get("IsCustomer"),
                    "is_supplier": c.get("IsSupplier"),
                    "account_number": c.get("AccountNumber"),
                    "outstanding_invoices": c.get("Balances", {}).get("AccountsReceivable", {}).get("Outstanding"),
                    "overdue_invoices": c.get("Balances", {}).get("AccountsReceivable", {}).get("Overdue"),
                }
                for c in resp.json().get("Contacts", [])
            ]
            return json.dumps({"contacts": contacts, "count": len(contacts)})
        except Exception as e:
            return _handle_error("xero_list_contacts", e)

    def create_contact(self, inp: dict) -> str:
        permission_error, name = self._check(self.agent_id, self.PROVIDER_ID, "xero_create_contact", inp, "name")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            contact: dict = {"Name": name}
            if inp.get("email"):
                contact["EmailAddress"] = inp["email"]
            if inp.get("is_customer"):
                contact["IsCustomer"] = True
            if inp.get("is_supplier"):
                contact["IsSupplier"] = True
            if inp.get("phone"):
                contact["Phones"] = [{"PhoneType": "DEFAULT", "PhoneNumber": inp["phone"]}]
            resp = httpx.post(f"{_BASE}/Contacts", headers=headers, json={"Contacts": [contact]}, timeout=15)
            resp.raise_for_status()
            contacts = resp.json().get("Contacts", [])
            if not contacts:
                return "No contact returned by Xero."
            c = contacts[0]
            return json.dumps({
                "contact_id": c.get("ContactID"),
                "name": c.get("Name"),
                "email": c.get("EmailAddress"),
                "status": "created",
            })
        except Exception as e:
            return _handle_error("xero_create_contact", e)

    def create_invoice(self, inp: dict) -> str:
        permission_error, contact_id, line_items = self._check(self.agent_id, self.PROVIDER_ID, "xero_create_invoice", inp, "contact_id", "line_items")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            invoice: dict = {
                "Type": inp.get("type", "ACCREC").upper(),
                "Contact": {"ContactID": contact_id},
                "LineItems": [
                    {
                        "Description": li.get("description", ""),
                        "Quantity": li.get("quantity", 1),
                        "UnitAmount": li.get("unit_amount", 0),
                        "AccountCode": li.get("account_code", ""),
                    }
                    for li in line_items
                ],
                "Status": inp.get("status", "DRAFT").upper(),
            }
            if inp.get("date"):
                invoice["Date"] = inp["date"]
            if inp.get("due_date"):
                invoice["DueDate"] = inp["due_date"]
            if inp.get("reference"):
                invoice["Reference"] = inp["reference"]
            resp = httpx.post(f"{_BASE}/Invoices", headers=headers, json={"Invoices": [invoice]}, timeout=15)
            resp.raise_for_status()
            invoices = resp.json().get("Invoices", [])
            if not invoices:
                return "No invoice returned by Xero."
            inv = invoices[0]
            return json.dumps({
                "invoice_id": inv.get("InvoiceID"),
                "invoice_number": inv.get("InvoiceNumber"),
                "status": inv.get("Status"),
                "total": inv.get("Total"),
                "outcome": "created",
            })
        except Exception as e:
            return _handle_error("xero_create_invoice", e)

    def create_payment(self, inp: dict) -> str:
        permission_error, invoice_id, account_id, amount = self._check(self.agent_id, self.PROVIDER_ID, "xero_create_payment", inp, "invoice_id", "account_id", "amount")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            payment: dict = {
                "Invoice": {"InvoiceID": invoice_id},
                "Account": {"AccountID": account_id},
                "Amount": amount,
            }
            if inp.get("date"):
                payment["Date"] = inp["date"]
            resp = httpx.post(f"{_BASE}/Payments", headers=headers, json={"Payments": [payment]}, timeout=15)
            resp.raise_for_status()
            payments = resp.json().get("Payments", [])
            if not payments:
                return "No payment returned by Xero."
            p = payments[0]
            return json.dumps({
                "payment_id": p.get("PaymentID"),
                "amount": p.get("Amount"),
                "status": p.get("Status"),
                "outcome": "created",
            })
        except Exception as e:
            return _handle_error("xero_create_payment", e)

    def create_credit_note(self, inp: dict) -> str:
        permission_error, contact_id, line_items = self._check(self.agent_id, self.PROVIDER_ID, "xero_create_credit_note", inp, "contact_id", "line_items")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            credit_note: dict = {
                "Type": inp.get("type", "ACCRECCREDIT").upper(),
                "Contact": {"ContactID": contact_id},
                "LineItems": [
                    {
                        "Description": li.get("description", ""),
                        "Quantity": li.get("quantity", 1),
                        "UnitAmount": li.get("unit_amount", 0),
                        "AccountCode": li.get("account_code", ""),
                    }
                    for li in line_items
                ],
                "Status": inp.get("status", "DRAFT").upper(),
            }
            if inp.get("date"):
                credit_note["Date"] = inp["date"]
            resp = httpx.post(f"{_BASE}/CreditNotes", headers=headers, json={"CreditNotes": [credit_note]}, timeout=15)
            resp.raise_for_status()
            credit_notes = resp.json().get("CreditNotes", [])
            if not credit_notes:
                return "No credit note returned by Xero."
            cn = credit_notes[0]
            return json.dumps({
                "credit_note_id": cn.get("CreditNoteID"),
                "credit_note_number": cn.get("CreditNoteNumber"),
                "status": cn.get("Status"),
                "total": cn.get("Total"),
                "outcome": "created",
            })
        except Exception as e:
            return _handle_error("xero_create_credit_note", e)

    def list_quotes(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "xero_list_quotes", inp)
        if permission_error: return permission_error
        try:
            params = {}
            if inp.get("status"):
                params["Status"] = inp["status"].upper()
            if inp.get("contact_id"):
                params["ContactID"] = inp["contact_id"]
            params["page"] = inp.get("page", 1)
            resp = httpx.get(f"{_BASE}/Quotes", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            quotes = [
                {
                    "quote_id": q.get("QuoteID"),
                    "quote_number": q.get("QuoteNumber"),
                    "status": q.get("Status"),
                    "contact": q.get("Contact", {}).get("Name"),
                    "date": q.get("DateString"),
                    "expiry_date": q.get("ExpiryDateString"),
                    "total": q.get("Total"),
                    "currency_code": q.get("CurrencyCode"),
                }
                for q in resp.json().get("Quotes", [])
            ]
            return json.dumps({"quotes": quotes, "count": len(quotes)})
        except Exception as e:
            return _handle_error("xero_list_quotes", e)

    def get_profit_and_loss(self, inp: dict) -> str:
        permission_error, from_date, to_date = self._check(self.agent_id, self.PROVIDER_ID, "xero_get_profit_and_loss", inp, "from_date", "to_date")
        if permission_error: return permission_error
        try:
            params = {"fromDate": from_date, "toDate": to_date}
            resp = httpx.get(f"{_BASE}/Reports/ProfitAndLoss", headers=self._auth_headers, params=params, timeout=20)
            resp.raise_for_status()
            reports = resp.json().get("Reports", [])
            if not reports:
                return "No profit and loss data returned."
            report = reports[0]
            rows_summary = []
            for row in report.get("Rows", []):
                if row.get("RowType") == "Section":
                    section_title = row.get("Title", "")
                    for r in row.get("Rows", []):
                        if r.get("RowType") == "SummaryRow":
                            cells = r.get("Cells", [])
                            rows_summary.append({
                                "section": section_title,
                                "label": cells[0].get("Value") if cells else "",
                                "value": cells[1].get("Value") if len(cells) > 1 else "",
                            })
            return json.dumps({
                "report_name": report.get("ReportName"),
                "report_date": report.get("ReportDate"),
                "summary": rows_summary,
            })
        except Exception as e:
            return _handle_error("xero_get_profit_and_loss", e)

    def get_aged_receivables(self, inp: dict) -> str:
        permission_error, contact_id = self._check(self.agent_id, self.PROVIDER_ID, "xero_get_aged_receivables", inp, "contact_id")
        if permission_error: return permission_error
        try:
            params = {"contactId": contact_id}
            if inp.get("date"):
                params["date"] = inp["date"]
            resp = httpx.get(f"{_BASE}/Reports/AgedReceivablesByContact", headers=self._auth_headers, params=params, timeout=20)
            resp.raise_for_status()
            reports = resp.json().get("Reports", [])
            if not reports:
                return "No aged receivables data returned."
            report = reports[0]
            rows_data = []
            for row in report.get("Rows", []):
                if row.get("RowType") == "Row":
                    cells = row.get("Cells", [])
                    rows_data.append({
                        "invoice_number": cells[0].get("Value") if cells else "",
                        "due_date": cells[2].get("Value") if len(cells) > 2 else "",
                        "total": cells[4].get("Value") if len(cells) > 4 else "",
                        "due": cells[9].get("Value") if len(cells) > 9 else "",
                    })
            return json.dumps({
                "report_name": report.get("ReportName"),
                "report_date": report.get("ReportDate"),
                "rows": rows_data,
            })
        except Exception as e:
            return _handle_error("xero_get_aged_receivables", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "xero_list_connections",
                    "description": "List all Xero organisations (tenants) connected to this account, returning their tenant IDs and names.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "xero_list_invoices",
                    "description": "List invoices from Xero. Supports filtering by status and contact.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by status: DRAFT, SUBMITTED, AUTHORISED, PAID, VOIDED, DELETED."},
                            "contact_id": {"type": "string", "description": "Filter by Xero contact ID."},
                            "page": {"type": "integer", "description": "Page number for pagination (default 1, 100 records per page)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "xero_get_invoice",
                    "description": "Get full details of a single Xero invoice by its ID, including line items.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "invoice_id": {"type": "string", "description": "The Xero invoice UUID."},
                        },
                        "required": ["invoice_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "xero_list_bank_transactions",
                    "description": "List bank transactions from Xero, optionally filtered by bank account and date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bank_account_id": {"type": "string", "description": "Filter by bank account UUID."},
                            "from_date": {"type": "string", "description": "Start date in YYYY-MM-DD format."},
                            "to_date": {"type": "string", "description": "End date in YYYY-MM-DD format."},
                            "page": {"type": "integer", "description": "Page number for pagination (default 1)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "xero_list_accounts",
                    "description": "List chart of accounts from Xero. Optionally filter by account type (e.g. BANK, REVENUE, EXPENSE).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "account_type": {"type": "string", "description": "Filter by account type: BANK, CURRENT, CURRLIAB, DEPRECIATN, DIRECTCOSTS, EQUITY, EXPENSE, FIXED, INVENTORY, LIABILITY, NONCURRENT, OTHERINCOME, OVERHEADS, PREPAYMENT, REVENUE, SALES, TERMLIAB, PAYGLIABILITY, SUPERANNUATIONEXPENSE, SUPERANNUATIONLIABILITY, WAGESEXPENSE."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "xero_get_balance_sheet",
                    "description": "Get the Balance Sheet report from Xero for a given date.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Report date in YYYY-MM-DD format."},
                        },
                        "required": ["date"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "xero_get_bank_summary",
                    "description": "Get the Bank Summary report from Xero showing opening balances, cash in/out, and closing balances per bank account.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from_date": {"type": "string", "description": "Start date in YYYY-MM-DD format."},
                            "to_date": {"type": "string", "description": "End date in YYYY-MM-DD format."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "xero_list_contacts",
                    "description": "List contacts (customers and suppliers) from Xero, with optional filtering by type or search term.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "contact_type": {"type": "string", "description": "Filter by type: 'customer' or 'supplier'."},
                            "search": {"type": "string", "description": "Search term to filter contacts by name or email."},
                            "page": {"type": "integer", "description": "Page number for pagination (default 1)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "xero_create_contact",
                    "description": "Create a new contact (customer or supplier) in Xero.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Contact/organisation name."},
                            "email": {"type": "string", "description": "Contact email address."},
                            "phone": {"type": "string", "description": "Contact phone number."},
                            "is_customer": {"type": "boolean", "description": "Whether this contact is a customer."},
                            "is_supplier": {"type": "boolean", "description": "Whether this contact is a supplier."},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "xero_create_invoice",
                    "description": "Create a new invoice (accounts receivable or payable) in Xero with one or more line items.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "contact_id": {"type": "string", "description": "The Xero contact UUID to bill."},
                            "type": {"type": "string", "description": "Invoice type: ACCREC (sales invoice, default) or ACCPAY (bill)."},
                            "status": {"type": "string", "description": "Invoice status: DRAFT (default), SUBMITTED, or AUTHORISED."},
                            "date": {"type": "string", "description": "Invoice date in YYYY-MM-DD format."},
                            "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format."},
                            "reference": {"type": "string", "description": "Optional reference text for the invoice."},
                            "line_items": {
                                "type": "array",
                                "description": "List of invoice line items.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "description": {"type": "string", "description": "Line item description."},
                                        "quantity": {"type": "number", "description": "Quantity (default 1)."},
                                        "unit_amount": {"type": "number", "description": "Unit price."},
                                        "account_code": {"type": "string", "description": "Xero account code to allocate the line to."},
                                    },
                                },
                            },
                        },
                        "required": ["contact_id", "line_items"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "xero_create_payment",
                    "description": "Record a payment against an existing Xero invoice.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "invoice_id": {"type": "string", "description": "The Xero invoice UUID being paid."},
                            "account_id": {"type": "string", "description": "The Xero bank account UUID the payment is made from/to."},
                            "amount": {"type": "number", "description": "Payment amount."},
                            "date": {"type": "string", "description": "Payment date in YYYY-MM-DD format."},
                        },
                        "required": ["invoice_id", "account_id", "amount"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "xero_create_credit_note",
                    "description": "Create a credit note in Xero for a contact, with one or more line items.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "contact_id": {"type": "string", "description": "The Xero contact UUID the credit note is for."},
                            "type": {"type": "string", "description": "Credit note type: ACCRECCREDIT (sales credit note, default) or ACCPAYCREDIT (supplier credit note)."},
                            "status": {"type": "string", "description": "Credit note status: DRAFT (default), SUBMITTED, or AUTHORISED."},
                            "date": {"type": "string", "description": "Credit note date in YYYY-MM-DD format."},
                            "line_items": {
                                "type": "array",
                                "description": "List of credit note line items.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "description": {"type": "string", "description": "Line item description."},
                                        "quantity": {"type": "number", "description": "Quantity (default 1)."},
                                        "unit_amount": {"type": "number", "description": "Unit price."},
                                        "account_code": {"type": "string", "description": "Xero account code to allocate the line to."},
                                    },
                                },
                            },
                        },
                        "required": ["contact_id", "line_items"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "xero_list_quotes",
                    "description": "List quotes from Xero. Supports filtering by status and contact.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by status: DRAFT, SENT, DECLINED, ACCEPTED, INVOICED, DELETED."},
                            "contact_id": {"type": "string", "description": "Filter by Xero contact ID."},
                            "page": {"type": "integer", "description": "Page number for pagination (default 1)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "xero_get_profit_and_loss",
                    "description": "Get the Profit and Loss report from Xero for a given date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "from_date": {"type": "string", "description": "Start date in YYYY-MM-DD format."},
                            "to_date": {"type": "string", "description": "End date in YYYY-MM-DD format."},
                        },
                        "required": ["from_date", "to_date"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "xero_get_aged_receivables",
                    "description": "Get the Aged Receivables By Contact report from Xero, showing outstanding invoices and how overdue they are for a specific customer.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "contact_id": {"type": "string", "description": "The Xero contact UUID to report on."},
                            "date": {"type": "string", "description": "Report as-of date in YYYY-MM-DD format."},
                        },
                        "required": ["contact_id"],
                    },
                },
            },
        ]
        callables = {
            "xero_list_connections": self.list_connections,
            "xero_list_invoices": self.list_invoices,
            "xero_get_invoice": self.get_invoice,
            "xero_list_bank_transactions": self.list_bank_transactions,
            "xero_list_accounts": self.list_accounts,
            "xero_get_balance_sheet": self.get_balance_sheet,
            "xero_get_bank_summary": self.get_bank_summary,
            "xero_list_contacts": self.list_contacts,
            "xero_create_contact": self.create_contact,
            "xero_create_invoice": self.create_invoice,
            "xero_create_payment": self.create_payment,
            "xero_create_credit_note": self.create_credit_note,
            "xero_list_quotes": self.list_quotes,
            "xero_get_profit_and_loss": self.get_profit_and_loss,
            "xero_get_aged_receivables": self.get_aged_receivables,
        }
        return tools, callables

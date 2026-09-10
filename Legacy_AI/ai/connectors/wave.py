import json
import httpx

from ai.connectors.base import BaseConnector

_GQL = "https://gql.waveapps.com/graphql/public"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector (HTTP {e.response.status_code})."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class WaveConnector(BaseConnector):
    """Wave Accounting connector — GraphQL-only API."""

    PROVIDER_ID = "wave"

    def _gql(self, query: str, variables: dict | None = None) -> dict:
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables
        resp = httpx.post(_GQL, headers=self._auth_headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(data["errors"][0].get("message", "GraphQL error"))
        return data.get("data", {})

    def get_user(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "wave_get_user", inp)
        if permission_error: return permission_error
        query = """
        query {
          user {
            id
            firstName
            lastName
            email
            createdAt
            defaultEmail
          }
        }
        """
        try:
            data = self._gql(query)
            return json.dumps(data.get("user", {}))
        except Exception as e:
            return _handle_error("wave_get_user", e)

    def list_businesses(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "wave_list_businesses", inp)
        if permission_error: return permission_error
        page = inp.get("page", 1)
        page_size = inp.get("page_size", 10)
        query = """
        query($page: Int!, $pageSize: Int!) {
          businesses(page: $page, pageSize: $pageSize) {
            pageInfo { currentPage totalPages totalCount }
            edges {
              node {
                id
                name
                isPersonal
                isClassicAccounting
                currency { code symbol }
                createdAt
              }
            }
          }
        }
        """
        try:
            data = self._gql(query, {"page": page, "pageSize": page_size})
            result = data.get("businesses", {})
            businesses = [e["node"] for e in result.get("edges", [])]
            return json.dumps({"businesses": businesses, "page_info": result.get("pageInfo", {})})
        except Exception as e:
            return _handle_error("wave_list_businesses", e)

    def list_invoices(self, inp: dict) -> str:
        permission_error, business_id = self._check(self.agent_id, self.PROVIDER_ID, "wave_list_invoices", inp, "business_id")
        if permission_error: return permission_error
        page = inp.get("page", 1)
        page_size = inp.get("page_size", 20)
        status = inp.get("status", "")
        query = """
        query($businessId: ID!, $page: Int!, $pageSize: Int!, $invoiceStatus: InvoiceStatus) {
          business(id: $businessId) {
            invoices(page: $page, pageSize: $pageSize, invoiceStatus: $invoiceStatus) {
              pageInfo { currentPage totalPages totalCount }
              edges {
                node {
                  id
                  invoiceNumber
                  status
                  invoiceDate
                  dueDate
                  amountDue { value currency { code } }
                  amountPaid { value }
                  total { value }
                  customer { id name }
                }
              }
            }
          }
        }
        """
        variables: dict = {"businessId": business_id, "page": page, "pageSize": page_size}
        if status:
            variables["invoiceStatus"] = status.upper()
        else:
            variables["invoiceStatus"] = None
        try:
            data = self._gql(query, variables)
            result = data.get("business", {}).get("invoices", {})
            invoices = [e["node"] for e in result.get("edges", [])]
            return json.dumps({"invoices": invoices, "page_info": result.get("pageInfo", {})})
        except Exception as e:
            return _handle_error("wave_list_invoices", e)

    def list_transactions(self, inp: dict) -> str:
        permission_error, business_id = self._check(self.agent_id, self.PROVIDER_ID, "wave_list_transactions", inp, "business_id")
        if permission_error: return permission_error
        page = inp.get("page", 1)
        page_size = inp.get("page_size", 20)
        query = """
        query($businessId: ID!, $page: Int!, $pageSize: Int!) {
          business(id: $businessId) {
            transactions(page: $page, pageSize: $pageSize) {
              pageInfo { currentPage totalPages totalCount }
              edges {
                node {
                  id
                  description
                  amount { value currency { code } }
                  date
                  account { id name normalBalanceType }
                  anchor
                }
              }
            }
          }
        }
        """
        try:
            data = self._gql(query, {"businessId": business_id, "page": page, "pageSize": page_size})
            result = data.get("business", {}).get("transactions", {})
            transactions = [e["node"] for e in result.get("edges", [])]
            return json.dumps({"transactions": transactions, "page_info": result.get("pageInfo", {})})
        except Exception as e:
            return _handle_error("wave_list_transactions", e)

    def list_accounts(self, inp: dict) -> str:
        permission_error, business_id = self._check(self.agent_id, self.PROVIDER_ID, "wave_list_accounts", inp, "business_id")
        if permission_error: return permission_error
        query = """
        query($businessId: ID!) {
          business(id: $businessId) {
            accounts {
              id
              name
              description
              displayId
              type { name normalBalanceType }
              subtype { name normalBalanceType }
              isArchived
              balance
              currency { code symbol }
            }
          }
        }
        """
        try:
            data = self._gql(query, {"businessId": business_id})
            accounts = data.get("business", {}).get("accounts", [])
            return json.dumps({"accounts": accounts, "count": len(accounts)})
        except Exception as e:
            return _handle_error("wave_list_accounts", e)

    def list_customers(self, inp: dict) -> str:
        permission_error, business_id = self._check(self.agent_id, self.PROVIDER_ID, "wave_list_customers", inp, "business_id")
        if permission_error: return permission_error
        page = inp.get("page", 1)
        page_size = inp.get("page_size", 25)
        query = """
        query($businessId: ID!, $page: Int!, $pageSize: Int!) {
          business(id: $businessId) {
            customers(page: $page, pageSize: $pageSize) {
              pageInfo { currentPage totalPages totalCount }
              edges {
                node {
                  id
                  name
                  email
                  mobile
                  phone
                  fax
                  tollFree
                  website
                  currency { code }
                }
              }
            }
          }
        }
        """
        try:
            data = self._gql(query, {"businessId": business_id, "page": page, "pageSize": page_size})
            result = data.get("business", {}).get("customers", {})
            customers = [e["node"] for e in result.get("edges", [])]
            return json.dumps({"customers": customers, "page_info": result.get("pageInfo", {})})
        except Exception as e:
            return _handle_error("wave_list_customers", e)

    def create_invoice(self, inp: dict) -> str:
        permission_error, business_id, customer_id, items = self._check(self.agent_id, self.PROVIDER_ID, "wave_create_invoice", inp, "business_id", "customer_id", "items")
        if permission_error: return permission_error
        invoice_date = inp.get("invoice_date", "")
        due_date = inp.get("due_date", "")
        mutation = """
        mutation($input: InvoiceCreateInput!) {
          invoiceCreate(input: $input) {
            didSucceed
            inputErrors { code message path }
            invoice {
              id
              invoiceNumber
              status
              total { value currency { code } }
              invoiceDate
              dueDate
            }
          }
        }
        """
        line_items = []
        for item in items:
            li: dict = {
                "productId": item.get("product_id"),
                "description": item.get("description", ""),
                "quantity": item.get("quantity", 1),
                "unitAmount": item.get("unit_amount"),
            }
            if item.get("taxes"):
                li["taxes"] = [{"salesTaxId": t} for t in item["taxes"]]
            line_items.append(li)
        invoice_input: dict = {
            "businessId": business_id,
            "customerId": customer_id,
            "items": line_items,
        }
        if invoice_date:
            invoice_input["invoiceDate"] = invoice_date
        if due_date:
            invoice_input["dueDate"] = due_date
        if inp.get("memo"):
            invoice_input["memo"] = inp["memo"]
        try:
            data = self._gql(mutation, {"input": invoice_input})
            result = data.get("invoiceCreate", {})
            if not result.get("didSucceed"):
                errors = result.get("inputErrors", [])
                return json.dumps({"success": False, "errors": errors})
            return json.dumps({"success": True, "invoice": result.get("invoice", {})})
        except Exception as e:
            return _handle_error("wave_create_invoice", e)

    def send_invoice(self, inp: dict) -> str:
        permission_error, invoice_id, to_email = self._check(self.agent_id, self.PROVIDER_ID, "wave_send_invoice", inp, "invoice_id", "to_email")
        if permission_error: return permission_error
        mutation = """
        mutation($input: InvoiceSendInput!) {
          invoiceSend(input: $input) {
            didSucceed
            inputErrors { code message path }
          }
        }
        """
        send_input: dict = {
            "invoiceId": invoice_id,
            "to": [{"email": to_email, "name": inp.get("to_name", "")}],
        }
        if inp.get("subject"):
            send_input["subject"] = inp["subject"]
        if inp.get("message"):
            send_input["message"] = inp["message"]
        try:
            data = self._gql(mutation, {"input": send_input})
            result = data.get("invoiceSend", {})
            if not result.get("didSucceed"):
                errors = result.get("inputErrors", [])
                return json.dumps({"success": False, "errors": errors})
            return json.dumps({"success": True})
        except Exception as e:
            return _handle_error("wave_send_invoice", e)

    def create_customer(self, inp: dict) -> str:
        permission_error, business_id, name = self._check(self.agent_id, self.PROVIDER_ID, "wave_create_customer", inp, "business_id", "name")
        if permission_error: return permission_error
        mutation = """
        mutation($input: CustomerCreateInput!) {
          customerCreate(input: $input) {
            didSucceed
            inputErrors { code message path }
            customer { id name email }
          }
        }
        """
        customer_input: dict = {"businessId": business_id, "name": name}
        if inp.get("email"):
            customer_input["email"] = inp["email"]
        if inp.get("first_name"):
            customer_input["firstName"] = inp["first_name"]
        if inp.get("last_name"):
            customer_input["lastName"] = inp["last_name"]
        try:
            data = self._gql(mutation, {"input": customer_input})
            result = data.get("customerCreate", {})
            if not result.get("didSucceed"):
                return json.dumps({"success": False, "errors": result.get("inputErrors", [])})
            return json.dumps({"success": True, "customer": result.get("customer", {})})
        except Exception as e:
            return _handle_error("wave_create_customer", e)

    def create_product(self, inp: dict) -> str:
        permission_error, business_id, name, unit_price = self._check(self.agent_id, self.PROVIDER_ID, "wave_create_product", inp, "business_id", "name", "unit_price")
        if permission_error: return permission_error
        mutation = """
        mutation($input: ProductCreateInput!) {
          productCreate(input: $input) {
            didSucceed
            inputErrors { code message path }
            product { id name unitPrice }
          }
        }
        """
        product_input: dict = {"businessId": business_id, "name": name, "unitPrice": str(unit_price)}
        if inp.get("description"):
            product_input["description"] = inp["description"]
        if inp.get("income_account_id"):
            product_input["incomeAccountId"] = inp["income_account_id"]
        if inp.get("expense_account_id"):
            product_input["expenseAccountId"] = inp["expense_account_id"]
        try:
            data = self._gql(mutation, {"input": product_input})
            result = data.get("productCreate", {})
            if not result.get("didSucceed"):
                return json.dumps({"success": False, "errors": result.get("inputErrors", [])})
            return json.dumps({"success": True, "product": result.get("product", {})})
        except Exception as e:
            return _handle_error("wave_create_product", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "wave_get_user",
                    "description": "Get the authenticated Wave user's profile information.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "wave_list_businesses",
                    "description": "List all Wave businesses accessible to the authenticated user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                            "page_size": {"type": "integer", "description": "Results per page (default 10)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "wave_list_invoices",
                    "description": "List invoices for a Wave business.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "business_id": {"type": "string", "description": "Wave business ID."},
                            "status": {"type": "string", "description": "Filter by status: DRAFT, UNPAID, OVERDUE, PAID, VIEWED, PARTIAL."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                            "page_size": {"type": "integer", "description": "Results per page (default 20)."},
                        },
                        "required": ["business_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "wave_list_transactions",
                    "description": "List accounting transactions for a Wave business.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "business_id": {"type": "string", "description": "Wave business ID."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                            "page_size": {"type": "integer", "description": "Results per page (default 20)."},
                        },
                        "required": ["business_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "wave_list_accounts",
                    "description": "List chart of accounts (with balances) for a Wave business.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "business_id": {"type": "string", "description": "Wave business ID."},
                        },
                        "required": ["business_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "wave_list_customers",
                    "description": "List customers for a Wave business.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "business_id": {"type": "string", "description": "Wave business ID."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                            "page_size": {"type": "integer", "description": "Results per page (default 25)."},
                        },
                        "required": ["business_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "wave_create_invoice",
                    "description": "Create a new invoice in Wave for a specific business and customer.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "business_id": {"type": "string", "description": "Wave business ID."},
                            "customer_id": {"type": "string", "description": "Wave customer ID."},
                            "items": {
                                "type": "array",
                                "description": "Line items for the invoice.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "product_id": {"type": "string", "description": "Wave product/service ID (optional)."},
                                        "description": {"type": "string", "description": "Line item description."},
                                        "quantity": {"type": "number", "description": "Quantity (default 1)."},
                                        "unit_amount": {"type": "number", "description": "Unit price amount."},
                                        "taxes": {"type": "array", "items": {"type": "string"}, "description": "List of sales tax IDs to apply."},
                                    },
                                    "required": ["description", "unit_amount"],
                                },
                            },
                            "invoice_date": {"type": "string", "description": "Invoice date in YYYY-MM-DD format."},
                            "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format."},
                            "memo": {"type": "string", "description": "Optional memo/note on the invoice."},
                        },
                        "required": ["business_id", "customer_id", "items"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "wave_send_invoice",
                    "description": "Send an existing Wave invoice to a customer via email.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "invoice_id": {"type": "string", "description": "Wave invoice ID to send."},
                            "to_email": {"type": "string", "description": "Recipient email address."},
                            "to_name": {"type": "string", "description": "Recipient display name."},
                            "subject": {"type": "string", "description": "Email subject line (optional)."},
                            "message": {"type": "string", "description": "Email body message (optional)."},
                        },
                        "required": ["invoice_id", "to_email"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "wave_create_customer",
                    "description": "Create a new customer in a Wave business.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "business_id": {"type": "string", "description": "Wave business ID."},
                            "name": {"type": "string", "description": "Customer's display name."},
                            "email": {"type": "string", "description": "Customer's email address (optional)."},
                            "first_name": {"type": "string", "description": "Customer's first name (optional)."},
                            "last_name": {"type": "string", "description": "Customer's last name (optional)."},
                        },
                        "required": ["business_id", "name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "wave_create_product",
                    "description": "Create a new product or service in a Wave business.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "business_id": {"type": "string", "description": "Wave business ID."},
                            "name": {"type": "string", "description": "Product/service name."},
                            "unit_price": {"type": "string", "description": "Unit price (e.g. '19.99')."},
                            "description": {"type": "string", "description": "Optional product description."},
                            "income_account_id": {"type": "string", "description": "Account ID to track sales income (optional, use if selling this product)."},
                            "expense_account_id": {"type": "string", "description": "Account ID to track purchase expense (optional, use if buying this product)."},
                        },
                        "required": ["business_id", "name", "unit_price"],
                    },
                },
            },
        ]
        callables = {
            "wave_get_user": self.get_user,
            "wave_list_businesses": self.list_businesses,
            "wave_list_invoices": self.list_invoices,
            "wave_list_transactions": self.list_transactions,
            "wave_list_accounts": self.list_accounts,
            "wave_list_customers": self.list_customers,
            "wave_create_invoice": self.create_invoice,
            "wave_send_invoice": self.send_invoice,
            "wave_create_customer": self.create_customer,
            "wave_create_product": self.create_product,
        }
        return tools, callables

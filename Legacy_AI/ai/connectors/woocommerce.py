import json
import httpx

from ai.connectors.base import BaseConnector


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected WooCommerce credentials lack permission "
                f"(HTTP {e.response.status_code}). Check Consumer Key/Secret and store permissions."
            )
        if e.response.status_code == 404:
            return f"Not found in {tool_name} (HTTP 404): {e.response.text[:300]}"
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class WooCommerceConnector(BaseConnector):
    """
    WooCommerce REST API v3 connector for system status, products, orders, customers, coupons, categories, and sales reports.
    access_token format: "CONSUMER_KEY:CONSUMER_SECRET:STORE_URL"
    e.g. "ck_12345:cs_67890:https://mywoostore.com"
    """

    PROVIDER_ID = "woocommerce"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id)
        parts = access_token.split(":", 2)
        self._key = parts[0].strip()
        self._secret = parts[1].strip() if len(parts) > 1 else ""
        url = parts[2].strip() if len(parts) > 2 else ""
        if url and not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        self._store_url = url.rstrip("/")
        self._base = f"{self._store_url}/wp-json/wc/v3" if self._store_url else ""
        self._auth = (self._key, self._secret)

    def _get(self, endpoint: str, params: dict = None) -> httpx.Response:
        url = f"{self._base}{endpoint}"
        return httpx.get(url, auth=self._auth, params=params or {}, timeout=15)

    def _post(self, endpoint: str, json_data: dict) -> httpx.Response:
        url = f"{self._base}{endpoint}"
        return httpx.post(url, auth=self._auth, json=json_data, timeout=15)

    def _put(self, endpoint: str, json_data: dict) -> httpx.Response:
        url = f"{self._base}{endpoint}"
        return httpx.put(url, auth=self._auth, json=json_data, timeout=15)

    def _delete(self, endpoint: str, params: dict = None) -> httpx.Response:
        url = f"{self._base}{endpoint}"
        return httpx.delete(url, auth=self._auth, params=params or {}, timeout=15)

    # ── System Status ─────────────────────────────────────────────────────────

    def get_system_status(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "woocommerce_get_system_status", inp)
        if permission_error:
            return permission_error
        try:
            resp = self._get("/system_status")
            resp.raise_for_status()
            data = resp.json()
            environment = data.get("environment", {})
            return json.dumps({
                "home_url": environment.get("home_url"),
                "site_url": environment.get("site_url"),
                "version": environment.get("version"),
                "wp_version": environment.get("wp_version"),
                "secure_connection": environment.get("secure_connection"),
            })
        except Exception as e:
            return _handle_error("woocommerce_get_system_status", e)

    # ── Products ──────────────────────────────────────────────────────────────

    def list_products(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "woocommerce_list_products", inp)
        if permission_error:
            return permission_error
        try:
            params: dict = {"per_page": inp.get("limit", 20)}
            if inp.get("search"):
                params["search"] = inp["search"]
            if inp.get("category"):
                params["category"] = inp["category"]
            if inp.get("status"):
                params["status"] = inp["status"]
            if inp.get("type"):
                params["type"] = inp["type"]
            resp = self._get("/products", params=params)
            resp.raise_for_status()
            products = [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "slug": p.get("slug"),
                    "type": p.get("type"),
                    "status": p.get("status"),
                    "price": p.get("price"),
                    "regular_price": p.get("regular_price"),
                    "sale_price": p.get("sale_price"),
                    "stock_quantity": p.get("stock_quantity"),
                    "stock_status": p.get("stock_status"),
                    "categories": [c.get("name") for c in p.get("categories", [])],
                }
                for p in resp.json()
            ]
            return json.dumps({"products": products, "count": len(products)})
        except Exception as e:
            return _handle_error("woocommerce_list_products", e)

    def get_product(self, inp: dict) -> str:
        permission_error, product_id = self._check(
            self.agent_id, self.PROVIDER_ID, "woocommerce_get_product", inp, "product_id"
        )
        if permission_error:
            return permission_error
        try:
            resp = self._get(f"/products/{product_id}")
            resp.raise_for_status()
            p = resp.json()
            return json.dumps({
                "id": p["id"],
                "name": p["name"],
                "slug": p.get("slug"),
                "permalink": p.get("permalink"),
                "type": p.get("type"),
                "status": p.get("status"),
                "description": p.get("description", "")[:500],
                "short_description": p.get("short_description", "")[:300],
                "sku": p.get("sku"),
                "price": p.get("price"),
                "regular_price": p.get("regular_price"),
                "sale_price": p.get("sale_price"),
                "on_sale": p.get("on_sale"),
                "stock_quantity": p.get("stock_quantity"),
                "stock_status": p.get("stock_status"),
                "categories": [c.get("name") for c in p.get("categories", [])],
                "tags": [t.get("name") for t in p.get("tags", [])],
                "attributes": p.get("attributes", []),
            })
        except Exception as e:
            return _handle_error("woocommerce_get_product", e)

    def create_product(self, inp: dict) -> str:
        permission_error, name = self._check(
            self.agent_id, self.PROVIDER_ID, "woocommerce_create_product", inp, "name"
        )
        if permission_error:
            return permission_error
        try:
            payload: dict = {"name": name}
            if inp.get("type"):
                payload["type"] = inp["type"]
            if inp.get("regular_price"):
                payload["regular_price"] = str(inp["regular_price"])
            if inp.get("sale_price"):
                payload["sale_price"] = str(inp["sale_price"])
            if inp.get("description"):
                payload["description"] = inp["description"]
            if inp.get("short_description"):
                payload["short_description"] = inp["short_description"]
            if inp.get("sku"):
                payload["sku"] = inp["sku"]
            if inp.get("manage_stock") is not None:
                payload["manage_stock"] = inp["manage_stock"]
            if inp.get("stock_quantity") is not None:
                payload["stock_quantity"] = inp["stock_quantity"]
            if inp.get("categories"):
                cats = inp["categories"] if isinstance(inp["categories"], list) else [{"id": inp["categories"]}]
                payload["categories"] = [{"id": c} if isinstance(c, int) else c for c in cats]

            resp = self._post("/products", payload)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data["id"],
                "name": data["name"],
                "permalink": data.get("permalink"),
                "price": data.get("price"),
                "status": data.get("status"),
            })
        except Exception as e:
            return _handle_error("woocommerce_create_product", e)

    def update_product(self, inp: dict) -> str:
        permission_error, product_id = self._check(
            self.agent_id, self.PROVIDER_ID, "woocommerce_update_product", inp, "product_id"
        )
        if permission_error:
            return permission_error
        try:
            payload: dict = {}
            for k in ("name", "type", "status", "regular_price", "sale_price", "description", "short_description", "sku", "stock_quantity", "stock_status"):
                if inp.get(k) is not None:
                    payload[k] = str(inp[k]) if k in ("regular_price", "sale_price") else inp[k]

            resp = self._put(f"/products/{product_id}", payload)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data["id"],
                "name": data["name"],
                "price": data.get("price"),
                "status": data.get("status"),
                "stock_quantity": data.get("stock_quantity"),
            })
        except Exception as e:
            return _handle_error("woocommerce_update_product", e)

    def delete_product(self, inp: dict) -> str:
        permission_error, product_id = self._check(
            self.agent_id, self.PROVIDER_ID, "woocommerce_delete_product", inp, "product_id"
        )
        if permission_error:
            return permission_error
        try:
            force = "true" if inp.get("force", True) else "false"
            resp = self._delete(f"/products/{product_id}", params={"force": force})
            resp.raise_for_status()
            return json.dumps({"status": "success", "id": product_id, "message": "Product deleted successfully."})
        except Exception as e:
            return _handle_error("woocommerce_delete_product", e)

    # ── Orders ────────────────────────────────────────────────────────────────

    def list_orders(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "woocommerce_list_orders", inp)
        if permission_error:
            return permission_error
        try:
            params: dict = {"per_page": inp.get("limit", 20)}
            if inp.get("status"):
                params["status"] = inp["status"]
            if inp.get("customer"):
                params["customer"] = inp["customer"]
            if inp.get("search"):
                params["search"] = inp["search"]
            resp = self._get("/orders", params=params)
            resp.raise_for_status()
            orders = [
                {
                    "id": o["id"],
                    "number": o.get("number"),
                    "status": o.get("status"),
                    "currency": o.get("currency"),
                    "total": o.get("total"),
                    "customer_id": o.get("customer_id"),
                    "billing": o.get("billing", {}),
                    "line_items_count": len(o.get("line_items", [])),
                    "date_created": o.get("date_created"),
                }
                for o in resp.json()
            ]
            return json.dumps({"orders": orders, "count": len(orders)})
        except Exception as e:
            return _handle_error("woocommerce_list_orders", e)

    def get_order(self, inp: dict) -> str:
        permission_error, order_id = self._check(
            self.agent_id, self.PROVIDER_ID, "woocommerce_get_order", inp, "order_id"
        )
        if permission_error:
            return permission_error
        try:
            resp = self._get(f"/orders/{order_id}")
            resp.raise_for_status()
            o = resp.json()
            line_items = [
                {
                    "id": li["id"],
                    "name": li.get("name"),
                    "product_id": li.get("product_id"),
                    "quantity": li.get("quantity"),
                    "subtotal": li.get("subtotal"),
                    "total": li.get("total"),
                }
                for li in o.get("line_items", [])
            ]
            return json.dumps({
                "id": o["id"],
                "number": o.get("number"),
                "status": o.get("status"),
                "currency": o.get("currency"),
                "total": o.get("total"),
                "customer_id": o.get("customer_id"),
                "billing": o.get("billing"),
                "shipping": o.get("shipping"),
                "payment_method_title": o.get("payment_method_title"),
                "line_items": line_items,
                "date_created": o.get("date_created"),
                "date_paid": o.get("date_paid"),
                "date_completed": o.get("date_completed"),
            })
        except Exception as e:
            return _handle_error("woocommerce_get_order", e)

    def create_order(self, inp: dict) -> str:
        permission_error, line_items = self._check(
            self.agent_id, self.PROVIDER_ID, "woocommerce_create_order", inp, "line_items"
        )
        if permission_error:
            return permission_error
        try:
            payload: dict = {"line_items": line_items}
            if inp.get("payment_method"):
                payload["payment_method"] = inp["payment_method"]
            if inp.get("payment_method_title"):
                payload["payment_method_title"] = inp["payment_method_title"]
            if inp.get("set_paid") is not None:
                payload["set_paid"] = inp["set_paid"]
            if inp.get("billing"):
                payload["billing"] = inp["billing"]
            if inp.get("shipping"):
                payload["shipping"] = inp["shipping"]

            resp = self._post("/orders", payload)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data["id"],
                "number": data.get("number"),
                "status": data.get("status"),
                "total": data.get("total"),
            })
        except Exception as e:
            return _handle_error("woocommerce_create_order", e)

    def update_order(self, inp: dict) -> str:
        permission_error, order_id = self._check(
            self.agent_id, self.PROVIDER_ID, "woocommerce_update_order", inp, "order_id"
        )
        if permission_error:
            return permission_error
        try:
            payload: dict = {}
            if inp.get("status"):
                payload["status"] = inp["status"]
            if inp.get("customer_note"):
                payload["customer_note"] = inp["customer_note"]

            resp = self._put(f"/orders/{order_id}", payload)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data["id"],
                "status": data.get("status"),
                "total": data.get("total"),
            })
        except Exception as e:
            return _handle_error("woocommerce_update_order", e)

    # ── Customers ─────────────────────────────────────────────────────────────

    def list_customers(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "woocommerce_list_customers", inp)
        if permission_error:
            return permission_error
        try:
            params: dict = {"per_page": inp.get("limit", 20)}
            if inp.get("search"):
                params["search"] = inp["search"]
            if inp.get("role"):
                params["role"] = inp["role"]
            resp = self._get("/customers", params=params)
            resp.raise_for_status()
            customers = [
                {
                    "id": c["id"],
                    "email": c.get("email"),
                    "first_name": c.get("first_name"),
                    "last_name": c.get("last_name"),
                    "username": c.get("username"),
                    "orders_count": c.get("orders_count"),
                    "total_spent": c.get("total_spent"),
                    "avatar_url": c.get("avatar_url"),
                }
                for c in resp.json()
            ]
            return json.dumps({"customers": customers, "count": len(customers)})
        except Exception as e:
            return _handle_error("woocommerce_list_customers", e)

    def get_customer(self, inp: dict) -> str:
        permission_error, customer_id = self._check(
            self.agent_id, self.PROVIDER_ID, "woocommerce_get_customer", inp, "customer_id"
        )
        if permission_error:
            return permission_error
        try:
            resp = self._get(f"/customers/{customer_id}")
            resp.raise_for_status()
            c = resp.json()
            return json.dumps({
                "id": c["id"],
                "email": c.get("email"),
                "first_name": c.get("first_name"),
                "last_name": c.get("last_name"),
                "username": c.get("username"),
                "billing": c.get("billing"),
                "shipping": c.get("shipping"),
                "is_paying_customer": c.get("is_paying_customer"),
                "orders_count": c.get("orders_count"),
                "total_spent": c.get("total_spent"),
            })
        except Exception as e:
            return _handle_error("woocommerce_get_customer", e)

    # ── Coupons ───────────────────────────────────────────────────────────────

    def list_coupons(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "woocommerce_list_coupons", inp)
        if permission_error:
            return permission_error
        try:
            params: dict = {"per_page": inp.get("limit", 20)}
            if inp.get("code"):
                params["code"] = inp["code"]
            resp = self._get("/coupons", params=params)
            resp.raise_for_status()
            coupons = [
                {
                    "id": c["id"],
                    "code": c["code"],
                    "amount": c.get("amount"),
                    "discount_type": c.get("discount_type"),
                    "description": c.get("description"),
                    "usage_count": c.get("usage_count"),
                    "usage_limit": c.get("usage_limit"),
                }
                for c in resp.json()
            ]
            return json.dumps({"coupons": coupons, "count": len(coupons)})
        except Exception as e:
            return _handle_error("woocommerce_list_coupons", e)

    def create_coupon(self, inp: dict) -> str:
        permission_error, code, amount = self._check(
            self.agent_id, self.PROVIDER_ID, "woocommerce_create_coupon", inp, "code", "amount"
        )
        if permission_error:
            return permission_error
        try:
            payload: dict = {
                "code": code,
                "amount": str(amount),
                "discount_type": inp.get("discount_type", "percent"),
            }
            if inp.get("description"):
                payload["description"] = inp["description"]
            if inp.get("individual_use") is not None:
                payload["individual_use"] = inp["individual_use"]
            if inp.get("usage_limit") is not None:
                payload["usage_limit"] = inp["usage_limit"]

            resp = self._post("/coupons", payload)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data["id"],
                "code": data["code"],
                "amount": data.get("amount"),
                "discount_type": data.get("discount_type"),
            })
        except Exception as e:
            return _handle_error("woocommerce_create_coupon", e)

    # ── Categories & Reports ──────────────────────────────────────────────────

    def list_categories(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "woocommerce_list_categories", inp)
        if permission_error:
            return permission_error
        try:
            params: dict = {"per_page": inp.get("limit", 50)}
            resp = self._get("/products/categories", params=params)
            resp.raise_for_status()
            categories = [
                {
                    "id": cat["id"],
                    "name": cat["name"],
                    "slug": cat.get("slug"),
                    "count": cat.get("count"),
                }
                for cat in resp.json()
            ]
            return json.dumps({"categories": categories, "count": len(categories)})
        except Exception as e:
            return _handle_error("woocommerce_list_categories", e)

    def get_sales_report(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "woocommerce_get_sales_report", inp)
        if permission_error:
            return permission_error
        try:
            params: dict = {}
            if inp.get("period"):
                params["period"] = inp["period"]
            if inp.get("date_min"):
                params["date_min"] = inp["date_min"]
            if inp.get("date_max"):
                params["date_max"] = inp["date_max"]

            resp = self._get("/reports/sales", params=params)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("woocommerce_get_sales_report", e)

    # ── OpenAI Tools Definition ───────────────────────────────────────────────

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_get_system_status",
                    "description": "Get WooCommerce store system status and environment info.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_list_products",
                    "description": "List products in WooCommerce store with optional filters.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max items to return (default: 20)."},
                            "search": {"type": "string", "description": "Search term."},
                            "category": {"type": "string", "description": "Category ID or slug."},
                            "status": {"type": "string", "description": "Product status: draft, pending, private, publish."},
                            "type": {"type": "string", "description": "Product type: simple, grouped, external, variable."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_get_product",
                    "description": "Get detailed information for a specific WooCommerce product.",
                    "parameters": {
                        "type": "object",
                        "properties": {"product_id": {"type": "integer", "description": "Product ID."}},
                        "required": ["product_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_create_product",
                    "description": "Create a new product in WooCommerce store.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Product name."},
                            "type": {"type": "string", "description": "Product type (simple, grouped, variable)."},
                            "regular_price": {"type": "string", "description": "Regular price."},
                            "sale_price": {"type": "string", "description": "Sale price."},
                            "description": {"type": "string", "description": "Product description."},
                            "short_description": {"type": "string", "description": "Short description."},
                            "sku": {"type": "string", "description": "SKU."},
                            "manage_stock": {"type": "boolean", "description": "Enable stock management."},
                            "stock_quantity": {"type": "integer", "description": "Stock quantity."},
                            "categories": {"type": "array", "items": {"type": "integer"}, "description": "List of category IDs."},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_update_product",
                    "description": "Update an existing WooCommerce product.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "integer", "description": "Product ID."},
                            "name": {"type": "string", "description": "Product name."},
                            "status": {"type": "string", "description": "Product status."},
                            "regular_price": {"type": "string", "description": "Regular price."},
                            "sale_price": {"type": "string", "description": "Sale price."},
                            "description": {"type": "string", "description": "Product description."},
                            "sku": {"type": "string", "description": "SKU."},
                            "stock_quantity": {"type": "integer", "description": "Stock quantity."},
                        },
                        "required": ["product_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_delete_product",
                    "description": "Delete a WooCommerce product.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "integer", "description": "Product ID."},
                            "force": {"type": "boolean", "description": "Force permanent deletion (default: true)."},
                        },
                        "required": ["product_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_list_orders",
                    "description": "List WooCommerce store orders with optional status/search filters.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max items (default: 20)."},
                            "status": {"type": "string", "description": "Order status: pending, processing, on-hold, completed, cancelled, refunded, failed."},
                            "customer": {"type": "integer", "description": "Customer ID filter."},
                            "search": {"type": "string", "description": "Search term."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_get_order",
                    "description": "Get detailed WooCommerce order information by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {"order_id": {"type": "integer", "description": "Order ID."}},
                        "required": ["order_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_create_order",
                    "description": "Create a new order in WooCommerce store.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "line_items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "product_id": {"type": "integer"},
                                        "quantity": {"type": "integer"},
                                    },
                                    "required": ["product_id", "quantity"],
                                },
                                "description": "List of line items with product_id and quantity.",
                            },
                            "payment_method": {"type": "string", "description": "Payment method code (e.g. cod, paypal, stripe)."},
                            "payment_method_title": {"type": "string", "description": "Payment method display title."},
                            "set_paid": {"type": "boolean", "description": "Mark order as paid immediately."},
                            "billing": {"type": "object", "description": "Billing address object."},
                            "shipping": {"type": "object", "description": "Shipping address object."},
                        },
                        "required": ["line_items"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_update_order",
                    "description": "Update status or notes of a WooCommerce order.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "integer", "description": "Order ID."},
                            "status": {"type": "string", "description": "New order status: pending, processing, on-hold, completed, cancelled, refunded, failed."},
                            "customer_note": {"type": "string", "description": "Customer note."},
                        },
                        "required": ["order_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_list_customers",
                    "description": "List customers in WooCommerce store.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max items to return (default: 20)."},
                            "search": {"type": "string", "description": "Search query."},
                            "role": {"type": "string", "description": "Customer role filter."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_get_customer",
                    "description": "Get detailed info for a WooCommerce customer by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {"customer_id": {"type": "integer", "description": "Customer ID."}},
                        "required": ["customer_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_list_coupons",
                    "description": "List discount coupons in WooCommerce store.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max items (default: 20)."},
                            "code": {"type": "string", "description": "Search by coupon code."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_create_coupon",
                    "description": "Create a new discount coupon in WooCommerce.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "Coupon code."},
                            "amount": {"type": "string", "description": "Discount amount/percentage."},
                            "discount_type": {"type": "string", "description": "Discount type: percent, fixed_cart, fixed_product."},
                            "description": {"type": "string", "description": "Coupon description."},
                            "individual_use": {"type": "boolean", "description": "Individual use only."},
                            "usage_limit": {"type": "integer", "description": "Max usage count."},
                        },
                        "required": ["code", "amount"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_list_categories",
                    "description": "List product categories in WooCommerce store.",
                    "parameters": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "description": "Max items (default: 50)."}},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "woocommerce_get_sales_report",
                    "description": "Get WooCommerce store sales report/analytics.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "period": {"type": "string", "description": "Period: week, month, last_month, year."},
                            "date_min": {"type": "string", "description": "Min date (YYYY-MM-DD)."},
                            "date_max": {"type": "string", "description": "Max date (YYYY-MM-DD)."},
                        },
                        "required": [],
                    },
                },
            },
        ]
        callables = {
            "woocommerce_get_system_status": self.get_system_status,
            "woocommerce_list_products": self.list_products,
            "woocommerce_get_product": self.get_product,
            "woocommerce_create_product": self.create_product,
            "woocommerce_update_product": self.update_product,
            "woocommerce_delete_product": self.delete_product,
            "woocommerce_list_orders": self.list_orders,
            "woocommerce_get_order": self.get_order,
            "woocommerce_create_order": self.create_order,
            "woocommerce_update_order": self.update_order,
            "woocommerce_list_customers": self.list_customers,
            "woocommerce_get_customer": self.get_customer,
            "woocommerce_list_coupons": self.list_coupons,
            "woocommerce_create_coupon": self.create_coupon,
            "woocommerce_list_categories": self.list_categories,
            "woocommerce_get_sales_report": self.get_sales_report,
        }
        return tools, callables

import json
import httpx

from ai.connectors.base import BaseConnector


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Shopify account lacks permission "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their Shopify connector."
            )
        if e.response.status_code == 404:
            return f"Not found in {tool_name}: the requested resource does not exist."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class ShopifyConnector(BaseConnector):
    """
    Shopify connector.
    access_token format: "ACCESS_TOKEN:SHOP_DOMAIN"
    where SHOP_DOMAIN is the myshopify.com subdomain (e.g. "mystore" → mystore.myshopify.com)
    """

    PROVIDER_ID = "shopify"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        self._token = access_token
        self.agent_id = agent_id
        if ":" in access_token:
            parts = access_token.split(":", 1)
            token_val = parts[0]
            self._shop = parts[1]
        else:
            token_val = access_token
            self._shop = ""

        if self._shop:
            self._base = f"https://{self._shop}.myshopify.com/admin/api/2024-01"
        else:
            self._base = "https://admin.shopify.com/api/2024-01"

        self._auth_headers = {
            "X-Shopify-Access-Token": token_val,
            "Authorization": f"Bearer {token_val}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_shop(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "shopify_get_shop", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/shop.json", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            s = resp.json().get("shop", {})
            return json.dumps({
                "name": s.get("name"),
                "email": s.get("email"),
                "domain": s.get("domain"),
                "myshopify_domain": s.get("myshopify_domain"),
                "currency": s.get("currency"),
                "timezone": s.get("timezone"),
                "plan_name": s.get("plan_name"),
                "country": s.get("country_name"),
            })
        except Exception as e:
            return _handle_error("shopify_get_shop", e)

    def list_products(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "shopify_list_products", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"limit": inp.get("limit", 20)}
            if inp.get("status"):
                params["status"] = inp["status"]
            if inp.get("title"):
                params["title"] = inp["title"]
            if inp.get("vendor"):
                params["vendor"] = inp["vendor"]
            if inp.get("product_type"):
                params["product_type"] = inp["product_type"]
            resp = httpx.get(f"{self._base}/products.json", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            products = [
                {
                    "id": p["id"],
                    "title": p["title"],
                    "vendor": p.get("vendor"),
                    "product_type": p.get("product_type"),
                    "status": p.get("status"),
                    "variants_count": len(p.get("variants", [])),
                    "published_at": p.get("published_at"),
                }
                for p in resp.json().get("products", [])
            ]
            return json.dumps({"products": products, "count": len(products)})
        except Exception as e:
            return _handle_error("shopify_list_products", e)

    def get_product(self, inp: dict) -> str:
        permission_error, product_id = self._check(self.agent_id, self.PROVIDER_ID, "shopify_get_product", inp, "product_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/products/{product_id}.json", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            p = resp.json().get("product", {})
            variants = [
                {
                    "id": v["id"],
                    "title": v.get("title"),
                    "price": v.get("price"),
                    "sku": v.get("sku"),
                    "inventory_quantity": v.get("inventory_quantity"),
                }
                for v in p.get("variants", [])
            ]
            return json.dumps({
                "id": p["id"],
                "title": p.get("title"),
                "body_html": p.get("body_html", "")[:500],
                "vendor": p.get("vendor"),
                "product_type": p.get("product_type"),
                "status": p.get("status"),
                "tags": p.get("tags"),
                "variants": variants,
            })
        except Exception as e:
            return _handle_error("shopify_get_product", e)

    def create_product(self, inp: dict) -> str:
        permission_error, title = self._check(self.agent_id, self.PROVIDER_ID, "shopify_create_product", inp, "title")
        if permission_error: return permission_error
        try:
            product: dict = {"title": title, "status": inp.get("status", "active")}
            if inp.get("body_html"):
                product["body_html"] = inp["body_html"]
            if inp.get("vendor"):
                product["vendor"] = inp["vendor"]
            if inp.get("product_type"):
                product["product_type"] = inp["product_type"]
            if inp.get("tags"):
                product["tags"] = inp["tags"]
            if inp.get("variants"):
                product["variants"] = inp["variants"]
            resp = httpx.post(
                f"{self._base}/products.json",
                headers=self._auth_headers,
                json={"product": product},
                timeout=15,
            )
            resp.raise_for_status()
            p = resp.json().get("product", {})
            return json.dumps({
                "id": p.get("id"),
                "title": p.get("title"),
                "status": p.get("status"),
                "vendor": p.get("vendor"),
                "product_type": p.get("product_type"),
                "variants_count": len(p.get("variants", [])),
                "created_at": p.get("created_at"),
            })
        except Exception as e:
            return _handle_error("shopify_create_product", e)

    def update_product(self, inp: dict) -> str:
        permission_error, product_id = self._check(self.agent_id, self.PROVIDER_ID, "shopify_update_product", inp, "product_id")
        if permission_error: return permission_error
        try:
            product: dict = {}
            if inp.get("title"):
                product["title"] = inp["title"]
            if inp.get("body_html") is not None:
                product["body_html"] = inp["body_html"]
            if inp.get("status"):
                product["status"] = inp["status"]
            if inp.get("tags") is not None:
                product["tags"] = inp["tags"]
            if not product:
                return "Error: at least one of 'title', 'body_html', 'status', or 'tags' must be provided."
            resp = httpx.put(
                f"{self._base}/products/{product_id}.json",
                headers=self._auth_headers,
                json={"product": product},
                timeout=15,
            )
            resp.raise_for_status()
            p = resp.json().get("product", {})
            return json.dumps({
                "id": p.get("id"),
                "title": p.get("title"),
                "status": p.get("status"),
                "tags": p.get("tags"),
                "updated_at": p.get("updated_at"),
            })
        except Exception as e:
            return _handle_error("shopify_update_product", e)

    def list_orders(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "shopify_list_orders", inp)
        if permission_error: return permission_error
        try:
            params: dict = {
                "limit": inp.get("limit", 20),
                "status": inp.get("status", "any"),
            }
            if inp.get("financial_status"):
                params["financial_status"] = inp["financial_status"]
            if inp.get("fulfillment_status"):
                params["fulfillment_status"] = inp["fulfillment_status"]
            resp = httpx.get(f"{self._base}/orders.json", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            orders = [
                {
                    "id": o["id"],
                    "name": o.get("name"),
                    "email": o.get("email"),
                    "financial_status": o.get("financial_status"),
                    "fulfillment_status": o.get("fulfillment_status"),
                    "total_price": o.get("total_price"),
                    "currency": o.get("currency"),
                    "created_at": o.get("created_at"),
                    "line_items_count": len(o.get("line_items", [])),
                }
                for o in resp.json().get("orders", [])
            ]
            return json.dumps({"orders": orders, "count": len(orders)})
        except Exception as e:
            return _handle_error("shopify_list_orders", e)

    def get_order(self, inp: dict) -> str:
        permission_error, order_id = self._check(self.agent_id, self.PROVIDER_ID, "shopify_get_order", inp, "order_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/orders/{order_id}.json", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            o = resp.json().get("order", {})
            line_items = [
                {
                    "name": item.get("name"),
                    "quantity": item.get("quantity"),
                    "price": item.get("price"),
                    "sku": item.get("sku"),
                }
                for item in o.get("line_items", [])
            ]
            shipping = o.get("shipping_address", {})
            return json.dumps({
                "id": o["id"],
                "name": o.get("name"),
                "email": o.get("email"),
                "financial_status": o.get("financial_status"),
                "fulfillment_status": o.get("fulfillment_status"),
                "total_price": o.get("total_price"),
                "subtotal_price": o.get("subtotal_price"),
                "total_tax": o.get("total_tax"),
                "currency": o.get("currency"),
                "created_at": o.get("created_at"),
                "line_items": line_items,
                "shipping_address": {
                    "name": shipping.get("name"),
                    "address1": shipping.get("address1"),
                    "city": shipping.get("city"),
                    "country": shipping.get("country"),
                },
            })
        except Exception as e:
            return _handle_error("shopify_get_order", e)

    def create_order(self, inp: dict) -> str:
        permission_error, line_items = self._check(self.agent_id, self.PROVIDER_ID, "shopify_create_order", inp, "line_items")
        if permission_error: return permission_error
        try:
            order: dict = {
                "line_items": line_items,
                "financial_status": inp.get("financial_status", "pending"),
            }
            if inp.get("customer"):
                order["customer"] = inp["customer"]
            if inp.get("note"):
                order["note"] = inp["note"]
            resp = httpx.post(
                f"{self._base}/orders.json",
                headers=self._auth_headers,
                json={"order": order},
                timeout=15,
            )
            resp.raise_for_status()
            o = resp.json().get("order", {})
            return json.dumps({
                "id": o.get("id"),
                "name": o.get("name"),
                "email": o.get("email"),
                "financial_status": o.get("financial_status"),
                "total_price": o.get("total_price"),
                "currency": o.get("currency"),
                "created_at": o.get("created_at"),
                "line_items_count": len(o.get("line_items", [])),
            })
        except Exception as e:
            return _handle_error("shopify_create_order", e)

    def update_order(self, inp: dict) -> str:
        permission_error, order_id = self._check(self.agent_id, self.PROVIDER_ID, "shopify_update_order", inp, "order_id")
        if permission_error: return permission_error
        try:
            order: dict = {}
            if inp.get("note") is not None:
                order["note"] = inp["note"]
            if inp.get("tags") is not None:
                order["tags"] = inp["tags"]
            if inp.get("email"):
                order["email"] = inp["email"]
            if not order:
                return "Error: at least one of 'note', 'tags', or 'email' must be provided."
            resp = httpx.put(
                f"{self._base}/orders/{order_id}.json",
                headers=self._auth_headers,
                json={"order": order},
                timeout=15,
            )
            resp.raise_for_status()
            o = resp.json().get("order", {})
            return json.dumps({
                "id": o.get("id"),
                "name": o.get("name"),
                "note": o.get("note"),
                "tags": o.get("tags"),
                "email": o.get("email"),
                "updated_at": o.get("updated_at"),
            })
        except Exception as e:
            return _handle_error("shopify_update_order", e)

    def list_customers(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "shopify_list_customers", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"limit": inp.get("limit", 20)}
            if inp.get("query"):
                params["query"] = inp["query"]
            resp = httpx.get(f"{self._base}/customers.json", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            customers = [
                {
                    "id": c["id"],
                    "first_name": c.get("first_name"),
                    "last_name": c.get("last_name"),
                    "email": c.get("email"),
                    "phone": c.get("phone"),
                    "orders_count": c.get("orders_count"),
                    "total_spent": c.get("total_spent"),
                    "created_at": c.get("created_at"),
                }
                for c in resp.json().get("customers", [])
            ]
            return json.dumps({"customers": customers, "count": len(customers)})
        except Exception as e:
            return _handle_error("shopify_list_customers", e)

    def get_inventory(self, inp: dict) -> str:
        permission_error, product_id = self._check(self.agent_id, self.PROVIDER_ID, "shopify_get_inventory", inp, "product_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/products/{product_id}.json", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            p = resp.json().get("product", {})
            inventory = [
                {
                    "variant_id": v["id"],
                    "title": v.get("title"),
                    "sku": v.get("sku"),
                    "inventory_quantity": v.get("inventory_quantity"),
                    "inventory_management": v.get("inventory_management"),
                }
                for v in p.get("variants", [])
            ]
            return json.dumps({"product": p.get("title"), "inventory": inventory})
        except Exception as e:
            return _handle_error("shopify_get_inventory", e)

    def list_discounts(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "shopify_list_discounts", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"limit": inp.get("limit", 20)}
            resp = httpx.get(f"{self._base}/price_rules.json", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            rules = resp.json().get("price_rules", [])
            discounts = [
                {
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "value_type": r.get("value_type"),
                    "value": r.get("value"),
                    "target_type": r.get("target_type"),
                    "target_selection": r.get("target_selection"),
                    "starts_at": r.get("starts_at"),
                    "ends_at": r.get("ends_at"),
                    "usage_limit": r.get("usage_limit"),
                    "created_at": r.get("created_at"),
                }
                for r in rules
            ]
            return json.dumps({"discounts": discounts, "count": len(discounts)})
        except Exception as e:
            return _handle_error("shopify_list_discounts", e)

    def get_inventory_levels(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "shopify_get_inventory_levels", inp)
        if permission_error: return permission_error
        inventory_item_ids = inp.get("inventory_item_ids", "")
        location_ids = inp.get("location_ids", "")
        if not inventory_item_ids and not location_ids:
            return "Error: at least one of 'inventory_item_ids' or 'location_ids' is required (comma-separated)."
        try:
            params: dict = {}
            if inventory_item_ids:
                params["inventory_item_ids"] = inventory_item_ids
            if location_ids:
                params["location_ids"] = location_ids
            resp = httpx.get(
                f"{self._base}/inventory_levels.json",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            levels = resp.json().get("inventory_levels", [])
            return json.dumps({"inventory_levels": levels, "count": len(levels)})
        except Exception as e:
            return _handle_error("shopify_get_inventory_levels", e)

    def list_transactions(self, inp: dict) -> str:
        permission_error, order_id = self._check(self.agent_id, self.PROVIDER_ID, "shopify_list_transactions", inp, "order_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{self._base}/orders/{order_id}/transactions.json",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            transactions = resp.json().get("transactions", [])
            result = [
                {
                    "id": t.get("id"),
                    "order_id": t.get("order_id"),
                    "kind": t.get("kind"),
                    "status": t.get("status"),
                    "amount": t.get("amount"),
                    "currency": t.get("currency"),
                    "gateway": t.get("gateway"),
                    "created_at": t.get("created_at"),
                    "error_code": t.get("error_code"),
                }
                for t in transactions
            ]
            return json.dumps({"transactions": result, "count": len(result)})
        except Exception as e:
            return _handle_error("shopify_list_transactions", e)

    def list_collections(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "shopify_list_collections", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"limit": inp.get("limit", 20)}
            if inp.get("title"):
                params["title"] = inp["title"]
            custom_resp = httpx.get(f"{self._base}/custom_collections.json", headers=self._auth_headers, params=params, timeout=15)
            custom_resp.raise_for_status()
            smart_resp = httpx.get(f"{self._base}/smart_collections.json", headers=self._auth_headers, params=params, timeout=15)
            smart_resp.raise_for_status()
            collections = [
                {"id": c["id"], "title": c.get("title"), "handle": c.get("handle"), "type": "custom", "published_at": c.get("published_at")}
                for c in custom_resp.json().get("custom_collections", [])
            ] + [
                {"id": c["id"], "title": c.get("title"), "handle": c.get("handle"), "type": "smart", "published_at": c.get("published_at")}
                for c in smart_resp.json().get("smart_collections", [])
            ]
            return json.dumps({"collections": collections, "count": len(collections)})
        except Exception as e:
            return _handle_error("shopify_list_collections", e)

    def get_customer(self, inp: dict) -> str:
        permission_error, customer_id = self._check(self.agent_id, self.PROVIDER_ID, "shopify_get_customer", inp, "customer_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/customers/{customer_id}.json", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            c = resp.json().get("customer", {})
            default_address = c.get("default_address") or {}
            return json.dumps({
                "id": c.get("id"),
                "first_name": c.get("first_name"),
                "last_name": c.get("last_name"),
                "email": c.get("email"),
                "phone": c.get("phone"),
                "orders_count": c.get("orders_count"),
                "total_spent": c.get("total_spent"),
                "tags": c.get("tags"),
                "note": c.get("note"),
                "state": c.get("state"),
                "default_address": {
                    "city": default_address.get("city"),
                    "province": default_address.get("province"),
                    "country": default_address.get("country"),
                },
                "created_at": c.get("created_at"),
            })
        except Exception as e:
            return _handle_error("shopify_get_customer", e)

    def list_locations(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "shopify_list_locations", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/locations.json", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            locations = [
                {
                    "id": loc["id"],
                    "name": loc.get("name"),
                    "city": loc.get("city"),
                    "country": loc.get("country"),
                    "active": loc.get("active"),
                    "legacy": loc.get("legacy"),
                }
                for loc in resp.json().get("locations", [])
            ]
            return json.dumps({"locations": locations, "count": len(locations)})
        except Exception as e:
            return _handle_error("shopify_list_locations", e)

    def set_inventory_level(self, inp: dict) -> str:
        permission_error, location_id, inventory_item_id, available = self._check(self.agent_id, self.PROVIDER_ID, "shopify_set_inventory_level", inp, "location_id", "inventory_item_id", "available")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{self._base}/inventory_levels/set.json",
                headers=self._auth_headers,
                json={"location_id": location_id, "inventory_item_id": inventory_item_id, "available": available},
                timeout=15,
            )
            resp.raise_for_status()
            level = resp.json().get("inventory_level", {})
            return json.dumps({
                "inventory_item_id": level.get("inventory_item_id"),
                "location_id": level.get("location_id"),
                "available": level.get("available"),
                "updated_at": level.get("updated_at"),
            })
        except Exception as e:
            return _handle_error("shopify_set_inventory_level", e)

    def adjust_inventory_level(self, inp: dict) -> str:
        permission_error, location_id, inventory_item_id, available_adjustment = self._check(self.agent_id, self.PROVIDER_ID, "shopify_adjust_inventory_level", inp, "location_id", "inventory_item_id", "available_adjustment")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{self._base}/inventory_levels/adjust.json",
                headers=self._auth_headers,
                json={
                    "location_id": location_id,
                    "inventory_item_id": inventory_item_id,
                    "available_adjustment": available_adjustment,
                },
                timeout=15,
            )
            resp.raise_for_status()
            level = resp.json().get("inventory_level", {})
            return json.dumps({
                "inventory_item_id": level.get("inventory_item_id"),
                "location_id": level.get("location_id"),
                "available": level.get("available"),
                "updated_at": level.get("updated_at"),
            })
        except Exception as e:
            return _handle_error("shopify_adjust_inventory_level", e)

    def create_price_rule(self, inp: dict) -> str:
        permission_error, title, value_type, value = self._check(self.agent_id, self.PROVIDER_ID, "shopify_create_price_rule", inp, "title", "value_type", "value")
        if permission_error: return permission_error
        try:
            price_rule: dict = {
                "title": title,
                "value_type": value_type,
                "value": value,
                "target_type": inp.get("target_type", "line_item"),
                "target_selection": inp.get("target_selection", "all"),
                "allocation_method": inp.get("allocation_method", "across"),
                "customer_selection": inp.get("customer_selection", "all"),
                "starts_at": inp.get("starts_at") or "2024-01-01T00:00:00Z",
            }
            if inp.get("ends_at"):
                price_rule["ends_at"] = inp["ends_at"]
            if inp.get("usage_limit"):
                price_rule["usage_limit"] = inp["usage_limit"]
            if inp.get("once_per_customer") is not None:
                price_rule["once_per_customer"] = inp["once_per_customer"]
            resp = httpx.post(
                f"{self._base}/price_rules.json",
                headers=self._auth_headers,
                json={"price_rule": price_rule},
                timeout=15,
            )
            resp.raise_for_status()
            r = resp.json().get("price_rule", {})
            return json.dumps({
                "id": r.get("id"),
                "title": r.get("title"),
                "value_type": r.get("value_type"),
                "value": r.get("value"),
                "starts_at": r.get("starts_at"),
                "ends_at": r.get("ends_at"),
                "created_at": r.get("created_at"),
            })
        except Exception as e:
            return _handle_error("shopify_create_price_rule", e)

    def create_discount_code(self, inp: dict) -> str:
        permission_error, price_rule_id, code = self._check(self.agent_id, self.PROVIDER_ID, "shopify_create_discount_code", inp, "price_rule_id", "code")
        if permission_error: return permission_error
        try:
            resp = httpx.post(
                f"{self._base}/price_rules/{price_rule_id}/discount_codes.json",
                headers=self._auth_headers,
                json={"discount_code": {"code": code}},
                timeout=15,
            )
            resp.raise_for_status()
            d = resp.json().get("discount_code", {})
            return json.dumps({
                "id": d.get("id"),
                "price_rule_id": d.get("price_rule_id"),
                "code": d.get("code"),
                "usage_count": d.get("usage_count"),
                "created_at": d.get("created_at"),
            })
        except Exception as e:
            return _handle_error("shopify_create_discount_code", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "shopify_get_shop",
                    "description": "Get general information about the connected Shopify store.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shopify_list_products",
                    "description": "List products in the Shopify store with optional filtering.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by status: active, archived, draft (default all)."},
                            "title": {"type": "string", "description": "Filter by product title."},
                            "vendor": {"type": "string", "description": "Filter by vendor name."},
                            "product_type": {"type": "string", "description": "Filter by product type."},
                            "limit": {"type": "integer", "description": "Max products to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shopify_get_product",
                    "description": "Get full details of a specific Shopify product including variants and pricing.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string", "description": "Shopify product ID."},
                        },
                        "required": ["product_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shopify_create_product",
                    "description": "Create a new product in the Shopify store.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Product title (required)."},
                            "body_html": {"type": "string", "description": "Product description in HTML (optional)."},
                            "vendor": {"type": "string", "description": "Vendor or brand name (optional)."},
                            "product_type": {"type": "string", "description": "Product type/category (optional)."},
                            "tags": {"type": "string", "description": "Comma-separated tags (optional)."},
                            "status": {"type": "string", "description": "Product status: 'active' or 'draft' (default 'active')."},
                            "variants": {
                                "type": "array",
                                "description": "List of variant objects with optional price and sku fields (optional).",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "price": {"type": "string", "description": "Variant price as a string (e.g. '9.99')."},
                                        "sku": {"type": "string", "description": "Stock keeping unit identifier."},
                                    },
                                },
                            },
                        },
                        "required": ["title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shopify_update_product",
                    "description": "Update an existing Shopify product's title, description, status, or tags.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string", "description": "Shopify product ID to update (required)."},
                            "title": {"type": "string", "description": "New product title (optional)."},
                            "body_html": {"type": "string", "description": "New product description in HTML (optional)."},
                            "status": {"type": "string", "description": "New status: 'active', 'draft', or 'archived' (optional)."},
                            "tags": {"type": "string", "description": "New comma-separated tags, replaces existing tags (optional)."},
                        },
                        "required": ["product_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shopify_list_orders",
                    "description": "List Shopify orders with optional status filtering.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Order status: open, closed, cancelled, any (default any)."},
                            "financial_status": {"type": "string", "description": "Payment status: paid, pending, refunded, etc."},
                            "fulfillment_status": {"type": "string", "description": "Fulfillment status: shipped, unshipped, partial, etc."},
                            "limit": {"type": "integer", "description": "Max orders to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shopify_get_order",
                    "description": "Get full details of a specific Shopify order including line items and shipping.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "Shopify order ID."},
                        },
                        "required": ["order_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shopify_create_order",
                    "description": "Create a new order in the Shopify store.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "line_items": {
                                "type": "array",
                                "description": "List of line items to include in the order (required). Each item needs variant_id and quantity.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "variant_id": {"type": "integer", "description": "Shopify variant ID."},
                                        "quantity": {"type": "integer", "description": "Quantity to order."},
                                    },
                                    "required": ["variant_id", "quantity"],
                                },
                            },
                            "customer": {
                                "type": "object",
                                "description": "Customer info (optional): first_name, last_name, email.",
                                "properties": {
                                    "first_name": {"type": "string"},
                                    "last_name": {"type": "string"},
                                    "email": {"type": "string"},
                                },
                            },
                            "note": {"type": "string", "description": "Internal note for the order (optional)."},
                            "financial_status": {"type": "string", "description": "Financial status of the order (default 'pending')."},
                        },
                        "required": ["line_items"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shopify_update_order",
                    "description": "Update an existing Shopify order's note, tags, or email.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "Shopify order ID to update (required)."},
                            "note": {"type": "string", "description": "Internal note for the order (optional)."},
                            "tags": {"type": "string", "description": "Comma-separated tags for the order (optional)."},
                            "email": {"type": "string", "description": "Customer email address for the order (optional)."},
                        },
                        "required": ["order_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shopify_list_customers",
                    "description": "List Shopify customers with optional search query.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search by name, email, or phone."},
                            "limit": {"type": "integer", "description": "Max customers to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shopify_get_inventory",
                    "description": "Get inventory levels for all variants of a Shopify product.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string", "description": "Shopify product ID."},
                        },
                        "required": ["product_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shopify_list_discounts",
                    "description": "List price rules (discounts) in the Shopify store.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max discounts to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shopify_get_inventory_levels",
                    "description": "Get inventory levels across locations by inventory item IDs or location IDs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "inventory_item_ids": {"type": "string", "description": "Comma-separated inventory item IDs to query (optional if location_ids provided)."},
                            "location_ids": {"type": "string", "description": "Comma-separated location IDs to query (optional if inventory_item_ids provided)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shopify_list_transactions",
                    "description": "List all payment transactions for a specific Shopify order.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "Shopify order ID whose transactions to retrieve (required)."},
                        },
                        "required": ["order_id"],
                    },
                },
            },
        ]
        callables = {
            "shopify_get_shop": self.get_shop,
            "shopify_list_products": self.list_products,
            "shopify_get_product": self.get_product,
            "shopify_create_product": self.create_product,
            "shopify_update_product": self.update_product,
            "shopify_list_orders": self.list_orders,
            "shopify_get_order": self.get_order,
            "shopify_create_order": self.create_order,
            "shopify_update_order": self.update_order,
            "shopify_list_customers": self.list_customers,
            "shopify_get_inventory": self.get_inventory,
            "shopify_list_discounts": self.list_discounts,
            "shopify_get_inventory_levels": self.get_inventory_levels,
            "shopify_list_transactions": self.list_transactions,
        }
        return tools, callables

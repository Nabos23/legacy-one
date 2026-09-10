import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.stripe.com/v1"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the Stripe API key is invalid or lacks permission "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their Stripe connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class StripeConnector(BaseConnector):
    """Stripe connector using Bearer token (secret key)."""

    PROVIDER_ID = "stripe"

    def get_balance(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_get_balance", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/balance", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            available = [{"amount": f["amount"] / 100, "currency": f["currency"].upper()} for f in data.get("available", [])]
            pending = [{"amount": f["amount"] / 100, "currency": f["currency"].upper()} for f in data.get("pending", [])]
            return json.dumps({"available": available, "pending": pending})
        except Exception as e:
            return _handle_error("stripe_get_balance", e)

    def list_customers(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_customers", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("email"):
                params["email"] = inp["email"]
            resp = httpx.get(f"{_BASE}/customers", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            customers = [
                {
                    "id": c["id"],
                    "name": c.get("name"),
                    "email": c.get("email"),
                    "created": c.get("created"),
                    "currency": c.get("currency"),
                    "balance": (c.get("balance", 0) or 0) / 100,
                }
                for c in data.get("data", [])
            ]
            return json.dumps({"customers": customers, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_customers", e)

    def get_customer(self, inp: dict) -> str:
        permission_error, customer_id = self._check(self.agent_id, self.PROVIDER_ID, "stripe_get_customer", inp, "customer_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/customers/{customer_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            c = resp.json()
            return json.dumps({
                "id": c["id"],
                "name": c.get("name"),
                "email": c.get("email"),
                "phone": c.get("phone"),
                "created": c.get("created"),
                "currency": c.get("currency"),
                "balance": (c.get("balance", 0) or 0) / 100,
                "metadata": c.get("metadata", {}),
            })
        except Exception as e:
            return _handle_error("stripe_get_customer", e)

    def list_charges(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_charges", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("customer_id"):
                params["customer"] = inp["customer_id"]
            resp = httpx.get(f"{_BASE}/charges", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            charges = [
                {
                    "id": ch["id"],
                    "amount": ch["amount"] / 100,
                    "currency": ch["currency"].upper(),
                    "status": ch["status"],
                    "customer": ch.get("customer"),
                    "description": ch.get("description"),
                    "created": ch.get("created"),
                    "receipt_url": ch.get("receipt_url"),
                }
                for ch in data.get("data", [])
            ]
            return json.dumps({"charges": charges, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_charges", e)

    def list_subscriptions(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_subscriptions", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("customer_id"):
                params["customer"] = inp["customer_id"]
            if inp.get("status"):
                params["status"] = inp["status"]
            resp = httpx.get(f"{_BASE}/subscriptions", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            subs = [
                {
                    "id": s["id"],
                    "status": s["status"],
                    "customer": s.get("customer"),
                    "current_period_start": s.get("current_period_start"),
                    "current_period_end": s.get("current_period_end"),
                    "cancel_at_period_end": s.get("cancel_at_period_end"),
                    "items": [{"price_id": i["price"]["id"], "amount": i["price"]["unit_amount"] / 100 if i["price"].get("unit_amount") else None} for i in s.get("items", {}).get("data", [])],
                }
                for s in data.get("data", [])
            ]
            return json.dumps({"subscriptions": subs, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_subscriptions", e)

    def list_invoices(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_invoices", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("customer_id"):
                params["customer"] = inp["customer_id"]
            if inp.get("status"):
                params["status"] = inp["status"]
            resp = httpx.get(f"{_BASE}/invoices", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            invoices = [
                {
                    "id": inv["id"],
                    "number": inv.get("number"),
                    "status": inv.get("status"),
                    "amount_due": (inv.get("amount_due", 0) or 0) / 100,
                    "amount_paid": (inv.get("amount_paid", 0) or 0) / 100,
                    "currency": (inv.get("currency") or "").upper(),
                    "customer": inv.get("customer"),
                    "due_date": inv.get("due_date"),
                    "created": inv.get("created"),
                    "hosted_invoice_url": inv.get("hosted_invoice_url"),
                }
                for inv in data.get("data", [])
            ]
            return json.dumps({"invoices": invoices, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_invoices", e)

    def delete_customer(self, inp: dict) -> str:
        permission_error, customer_id = self._check(self.agent_id, self.PROVIDER_ID, "stripe_delete_customer", inp, "customer_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/customers/{customer_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"deleted": data.get("deleted"), "id": data.get("id")})
        except Exception as e:
            return _handle_error("stripe_delete_customer", e)

    def create_customer(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_create_customer", inp)
        if permission_error: return permission_error
        try:
            payload = {}
            if inp.get("name"):
                payload["name"] = inp["name"]
            if inp.get("email"):
                payload["email"] = inp["email"]
            if inp.get("phone"):
                payload["phone"] = inp["phone"]
            if inp.get("description"):
                payload["description"] = inp["description"]
            resp = httpx.post(f"{_BASE}/customers", headers=self._auth_headers, data=payload, timeout=15)
            resp.raise_for_status()
            c = resp.json()
            return json.dumps({"id": c["id"], "name": c.get("name"), "email": c.get("email"), "created": c.get("created")})
        except Exception as e:
            return _handle_error("stripe_create_customer", e)

    def create_payment_intent(self, inp: dict) -> str:
        permission_error, amount = self._check(self.agent_id, self.PROVIDER_ID, "stripe_create_payment_intent", inp, "amount")
        if permission_error: return permission_error
        currency = inp.get("currency", "usd")
        try:
            payload = {"amount": int(amount), "currency": currency.lower()}
            if inp.get("customer_id"):
                payload["customer"] = inp["customer_id"]
            if inp.get("description"):
                payload["description"] = inp["description"]
            resp = httpx.post(f"{_BASE}/payment_intents", headers=self._auth_headers, data=payload, timeout=15)
            resp.raise_for_status()
            pi = resp.json()
            return json.dumps({
                "id": pi["id"],
                "amount": pi["amount"] / 100,
                "currency": pi["currency"].upper(),
                "status": pi["status"],
                "client_secret": pi.get("client_secret"),
            })
        except Exception as e:
            return _handle_error("stripe_create_payment_intent", e)

    def refund_charge(self, inp: dict) -> str:
        permission_error, charge_id = self._check(self.agent_id, self.PROVIDER_ID, "stripe_refund_charge", inp, "charge_id")
        if permission_error: return permission_error
        try:
            payload = {"charge": charge_id}
            if inp.get("amount"):
                payload["amount"] = int(inp["amount"])
            if inp.get("reason"):
                payload["reason"] = inp["reason"]
            resp = httpx.post(f"{_BASE}/refunds", headers=self._auth_headers, data=payload, timeout=15)
            resp.raise_for_status()
            r = resp.json()
            return json.dumps({
                "id": r["id"],
                "amount": r["amount"] / 100,
                "currency": r["currency"].upper(),
                "status": r["status"],
                "charge": r.get("charge"),
                "reason": r.get("reason"),
            })
        except Exception as e:
            return _handle_error("stripe_refund_charge", e)

    def list_payment_intents(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_payment_intents", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("customer_id"):
                params["customer"] = inp["customer_id"]
            resp = httpx.get(f"{_BASE}/payment_intents", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            pis = [
                {
                    "id": pi["id"],
                    "amount": pi["amount"] / 100,
                    "currency": pi["currency"].upper(),
                    "status": pi["status"],
                    "customer": pi.get("customer"),
                    "description": pi.get("description"),
                    "created": pi.get("created"),
                }
                for pi in data.get("data", [])
            ]
            return json.dumps({"payment_intents": pis, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_payment_intents", e)

    def list_refunds(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_refunds", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("charge_id"):
                params["charge"] = inp["charge_id"]
            resp = httpx.get(f"{_BASE}/refunds", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            refunds = [
                {
                    "id": r["id"],
                    "amount": r["amount"] / 100,
                    "currency": r["currency"].upper(),
                    "status": r["status"],
                    "charge": r.get("charge"),
                    "reason": r.get("reason"),
                    "created": r.get("created"),
                }
                for r in data.get("data", [])
            ]
            return json.dumps({"refunds": refunds, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_refunds", e)

    def list_products(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_products", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("active") is not None:
                params["active"] = str(inp["active"]).lower()
            resp = httpx.get(f"{_BASE}/products", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            products = [
                {
                    "id": p["id"],
                    "name": p.get("name"),
                    "description": p.get("description"),
                    "active": p.get("active"),
                    "created": p.get("created"),
                }
                for p in data.get("data", [])
            ]
            return json.dumps({"products": products, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_products", e)

    def list_prices(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_prices", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("product_id"):
                params["product"] = inp["product_id"]
            if inp.get("active") is not None:
                params["active"] = str(inp["active"]).lower()
            resp = httpx.get(f"{_BASE}/prices", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            prices = [
                {
                    "id": p["id"],
                    "product": p.get("product"),
                    "unit_amount": (p.get("unit_amount") or 0) / 100,
                    "currency": (p.get("currency") or "").upper(),
                    "recurring": p.get("recurring"),
                    "active": p.get("active"),
                }
                for p in data.get("data", [])
            ]
            return json.dumps({"prices": prices, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_prices", e)

    def list_payouts(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_payouts", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("status"):
                params["status"] = inp["status"]
            resp = httpx.get(f"{_BASE}/payouts", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            payouts = [
                {
                    "id": p["id"],
                    "amount": p["amount"] / 100,
                    "currency": p["currency"].upper(),
                    "status": p["status"],
                    "arrival_date": p.get("arrival_date"),
                    "description": p.get("description"),
                    "created": p.get("created"),
                }
                for p in data.get("data", [])
            ]
            return json.dumps({"payouts": payouts, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_payouts", e)

    def cancel_subscription(self, inp: dict) -> str:
        permission_error, sub_id = self._check(self.agent_id, self.PROVIDER_ID, "stripe_cancel_subscription", inp, "subscription_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/subscriptions/{sub_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            s = resp.json()
            return json.dumps({"id": s["id"], "status": s["status"], "canceled_at": s.get("canceled_at")})
        except Exception as e:
            return _handle_error("stripe_cancel_subscription", e)

    def get_payment_intent(self, inp: dict) -> str:
        permission_error, pi_id = self._check(self.agent_id, self.PROVIDER_ID, "stripe_get_payment_intent", inp, "payment_intent_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/payment_intents/{pi_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            pi = resp.json()
            return json.dumps({
                "id": pi["id"],
                "amount": pi["amount"] / 100,
                "currency": pi["currency"].upper(),
                "status": pi["status"],
                "customer": pi.get("customer"),
                "description": pi.get("description"),
                "created": pi.get("created"),
            })
        except Exception as e:
            return _handle_error("stripe_get_payment_intent", e)

    def get_account(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_get_account", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/account", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            a = resp.json()
            return json.dumps({
                "id": a["id"],
                "display_name": a.get("settings", {}).get("dashboard", {}).get("display_name"),
                "email": a.get("email"),
                "country": a.get("country"),
                "default_currency": a.get("default_currency"),
                "charges_enabled": a.get("charges_enabled"),
                "payouts_enabled": a.get("payouts_enabled"),
                "business_type": a.get("business_type"),
            })
        except Exception as e:
            return _handle_error("stripe_get_account", e)

    def list_balance_transactions(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_balance_transactions", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("type"):
                params["type"] = inp["type"]
            resp = httpx.get(f"{_BASE}/balance_transactions", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            txns = [
                {
                    "id": t["id"],
                    "amount": t["amount"] / 100,
                    "fee": t["fee"] / 100,
                    "net": t["net"] / 100,
                    "currency": t["currency"].upper(),
                    "type": t["type"],
                    "status": t["status"],
                    "description": t.get("description"),
                    "created": t.get("created"),
                }
                for t in data.get("data", [])
            ]
            return json.dumps({"transactions": txns, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_balance_transactions", e)

    def list_disputes(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_disputes", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("charge_id"):
                params["charge"] = inp["charge_id"]
            resp = httpx.get(f"{_BASE}/disputes", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            disputes = [
                {
                    "id": d["id"],
                    "amount": d["amount"] / 100,
                    "currency": d["currency"].upper(),
                    "status": d["status"],
                    "reason": d.get("reason"),
                    "charge": d.get("charge"),
                    "created": d.get("created"),
                    "due_by": d.get("evidence_details", {}).get("due_by"),
                }
                for d in data.get("data", [])
            ]
            return json.dumps({"disputes": disputes, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_disputes", e)

    def list_events(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_events", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("type"):
                params["type"] = inp["type"]
            resp = httpx.get(f"{_BASE}/events", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            events = [
                {
                    "id": e["id"],
                    "type": e["type"],
                    "created": e.get("created"),
                    "livemode": e.get("livemode"),
                    "object_id": e.get("data", {}).get("object", {}).get("id"),
                }
                for e in data.get("data", [])
            ]
            return json.dumps({"events": events, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_events", e)

    def list_payment_methods(self, inp: dict) -> str:
        permission_error, customer_id = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_payment_methods", inp, "customer_id")
        if permission_error: return permission_error
        try:
            params = {"type": inp.get("type", "card"), "limit": inp.get("limit", 20)}
            resp = httpx.get(f"{_BASE}/customers/{customer_id}/payment_methods", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            methods = []
            for pm in data.get("data", []):
                entry = {"id": pm["id"], "type": pm["type"], "created": pm.get("created")}
                if pm["type"] == "card" and pm.get("card"):
                    entry["card"] = {"brand": pm["card"]["brand"], "last4": pm["card"]["last4"], "exp_month": pm["card"]["exp_month"], "exp_year": pm["card"]["exp_year"]}
                methods.append(entry)
            return json.dumps({"payment_methods": methods, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_payment_methods", e)

    def list_checkout_sessions(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_checkout_sessions", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("customer_id"):
                params["customer"] = inp["customer_id"]
            if inp.get("status"):
                params["status"] = inp["status"]
            resp = httpx.get(f"{_BASE}/checkout/sessions", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            sessions = [
                {
                    "id": s["id"],
                    "status": s.get("status"),
                    "payment_status": s.get("payment_status"),
                    "amount_total": (s.get("amount_total") or 0) / 100,
                    "currency": (s.get("currency") or "").upper(),
                    "customer": s.get("customer"),
                    "customer_email": s.get("customer_email"),
                    "url": s.get("url"),
                    "created": s.get("created"),
                    "expires_at": s.get("expires_at"),
                }
                for s in data.get("data", [])
            ]
            return json.dumps({"sessions": sessions, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_checkout_sessions", e)

    def list_coupons(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_coupons", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            resp = httpx.get(f"{_BASE}/coupons", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            coupons = [
                {
                    "id": c["id"],
                    "name": c.get("name"),
                    "percent_off": c.get("percent_off"),
                    "amount_off": (c.get("amount_off") or 0) / 100 if c.get("amount_off") else None,
                    "currency": (c.get("currency") or "").upper() if c.get("currency") else None,
                    "duration": c.get("duration"),
                    "times_redeemed": c.get("times_redeemed"),
                    "valid": c.get("valid"),
                }
                for c in data.get("data", [])
            ]
            return json.dumps({"coupons": coupons, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_coupons", e)

    def create_coupon(self, inp: dict) -> str:
        permission_error, duration = self._check(self.agent_id, self.PROVIDER_ID, "stripe_create_coupon", inp, "duration")
        if permission_error: return permission_error
        try:
            payload = {}
            if inp.get("percent_off"):
                payload["percent_off"] = inp["percent_off"]
            elif inp.get("amount_off"):
                payload["amount_off"] = int(inp["amount_off"])
                payload["currency"] = inp.get("currency", "usd").lower()
            payload["duration"] = duration
            if inp.get("duration_in_months"):
                payload["duration_in_months"] = int(inp["duration_in_months"])
            if inp.get("name"):
                payload["name"] = inp["name"]
            if inp.get("max_redemptions"):
                payload["max_redemptions"] = int(inp["max_redemptions"])
            resp = httpx.post(f"{_BASE}/coupons", headers=self._auth_headers, data=payload, timeout=15)
            resp.raise_for_status()
            c = resp.json()
            return json.dumps({"id": c["id"], "name": c.get("name"), "percent_off": c.get("percent_off"), "amount_off": c.get("amount_off"), "duration": c.get("duration"), "valid": c.get("valid")})
        except Exception as e:
            return _handle_error("stripe_create_coupon", e)

    def update_customer(self, inp: dict) -> str:
        permission_error, customer_id = self._check(self.agent_id, self.PROVIDER_ID, "stripe_update_customer", inp, "customer_id")
        if permission_error: return permission_error
        try:
            payload = {}
            if inp.get("name") is not None:
                payload["name"] = inp["name"]
            if inp.get("email") is not None:
                payload["email"] = inp["email"]
            if inp.get("phone") is not None:
                payload["phone"] = inp["phone"]
            if inp.get("description") is not None:
                payload["description"] = inp["description"]
            resp = httpx.post(f"{_BASE}/customers/{customer_id}", headers=self._auth_headers, data=payload, timeout=15)
            resp.raise_for_status()
            c = resp.json()
            return json.dumps({"id": c["id"], "name": c.get("name"), "email": c.get("email"), "phone": c.get("phone")})
        except Exception as e:
            return _handle_error("stripe_update_customer", e)

    def list_webhooks(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_webhooks", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/webhook_endpoints", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            webhooks = [
                {
                    "id": w["id"],
                    "url": w.get("url"),
                    "status": w.get("status"),
                    "enabled_events": w.get("enabled_events"),
                    "created": w.get("created"),
                }
                for w in data.get("data", [])
            ]
            return json.dumps({"webhooks": webhooks})
        except Exception as e:
            return _handle_error("stripe_list_webhooks", e)

    def list_setup_intents(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_setup_intents", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("customer_id"):
                params["customer"] = inp["customer_id"]
            resp = httpx.get(f"{_BASE}/setup_intents", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            sis = [
                {
                    "id": si["id"],
                    "status": si["status"],
                    "customer": si.get("customer"),
                    "payment_method": si.get("payment_method"),
                    "usage": si.get("usage"),
                    "created": si.get("created"),
                }
                for si in data.get("data", [])
            ]
            return json.dumps({"setup_intents": sis, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_setup_intents", e)

    def list_tax_rates(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_tax_rates", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("active") is not None:
                params["active"] = str(inp["active"]).lower()
            resp = httpx.get(f"{_BASE}/tax_rates", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            rates = [
                {
                    "id": t["id"],
                    "display_name": t.get("display_name"),
                    "percentage": t.get("percentage"),
                    "inclusive": t.get("inclusive"),
                    "country": t.get("country"),
                    "active": t.get("active"),
                }
                for t in data.get("data", [])
            ]
            return json.dumps({"tax_rates": rates, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_tax_rates", e)

    def list_promotion_codes(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "stripe_list_promotion_codes", inp)
        if permission_error: return permission_error
        try:
            params = {"limit": inp.get("limit", 20)}
            if inp.get("coupon_id"):
                params["coupon"] = inp["coupon_id"]
            if inp.get("active") is not None:
                params["active"] = str(inp["active"]).lower()
            resp = httpx.get(f"{_BASE}/promotion_codes", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            codes = [
                {
                    "id": pc["id"],
                    "code": pc.get("code"),
                    "coupon": pc.get("coupon", {}).get("id"),
                    "active": pc.get("active"),
                    "times_redeemed": pc.get("times_redeemed"),
                    "expires_at": pc.get("expires_at"),
                }
                for pc in data.get("data", [])
            ]
            return json.dumps({"promotion_codes": codes, "has_more": data.get("has_more")})
        except Exception as e:
            return _handle_error("stripe_list_promotion_codes", e)

    def create_subscription(self, inp: dict) -> str:
        permission_error, customer_id, price_id = self._check(self.agent_id, self.PROVIDER_ID, "stripe_create_subscription", inp, "customer_id", "price_id")
        if permission_error: return permission_error
        try:
            payload = {"customer": customer_id, "items[0][price]": price_id}
            if inp.get("quantity"):
                payload["items[0][quantity]"] = int(inp["quantity"])
            if inp.get("trial_period_days"):
                payload["trial_period_days"] = int(inp["trial_period_days"])
            if inp.get("coupon"):
                payload["coupon"] = inp["coupon"]
            resp = httpx.post(f"{_BASE}/subscriptions", headers=self._auth_headers, data=payload, timeout=15)
            resp.raise_for_status()
            s = resp.json()
            return json.dumps({
                "id": s["id"],
                "status": s["status"],
                "customer": s.get("customer"),
                "current_period_end": s.get("current_period_end"),
            })
        except Exception as e:
            return _handle_error("stripe_create_subscription", e)

    def update_subscription(self, inp: dict) -> str:
        permission_error, sub_id = self._check(self.agent_id, self.PROVIDER_ID, "stripe_update_subscription", inp, "subscription_id")
        if permission_error: return permission_error
        try:
            payload = {}
            if inp.get("price_id"):
                payload["items[0][price]"] = inp["price_id"]
            if inp.get("cancel_at_period_end") is not None:
                payload["cancel_at_period_end"] = str(inp["cancel_at_period_end"]).lower()
            if inp.get("proration_behavior"):
                payload["proration_behavior"] = inp["proration_behavior"]
            resp = httpx.post(f"{_BASE}/subscriptions/{sub_id}", headers=self._auth_headers, data=payload, timeout=15)
            resp.raise_for_status()
            s = resp.json()
            return json.dumps({
                "id": s["id"],
                "status": s["status"],
                "cancel_at_period_end": s.get("cancel_at_period_end"),
                "current_period_end": s.get("current_period_end"),
            })
        except Exception as e:
            return _handle_error("stripe_update_subscription", e)

    def create_invoice(self, inp: dict) -> str:
        permission_error, customer_id = self._check(self.agent_id, self.PROVIDER_ID, "stripe_create_invoice", inp, "customer_id")
        if permission_error: return permission_error
        try:
            payload = {"customer": customer_id}
            if inp.get("description"):
                payload["description"] = inp["description"]
            if inp.get("auto_advance") is not None:
                payload["auto_advance"] = str(inp["auto_advance"]).lower()
            if inp.get("days_until_due"):
                payload["days_until_due"] = int(inp["days_until_due"])
                payload["collection_method"] = "send_invoice"
            resp = httpx.post(f"{_BASE}/invoices", headers=self._auth_headers, data=payload, timeout=15)
            resp.raise_for_status()
            inv = resp.json()
            return json.dumps({
                "id": inv["id"],
                "status": inv.get("status"),
                "customer": inv.get("customer"),
                "hosted_invoice_url": inv.get("hosted_invoice_url"),
            })
        except Exception as e:
            return _handle_error("stripe_create_invoice", e)

    def finalize_invoice(self, inp: dict) -> str:
        permission_error, invoice_id = self._check(self.agent_id, self.PROVIDER_ID, "stripe_finalize_invoice", inp, "invoice_id")
        if permission_error: return permission_error
        try:
            resp = httpx.post(f"{_BASE}/invoices/{invoice_id}/finalize", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            inv = resp.json()
            return json.dumps({
                "id": inv["id"],
                "status": inv.get("status"),
                "hosted_invoice_url": inv.get("hosted_invoice_url"),
                "invoice_pdf": inv.get("invoice_pdf"),
            })
        except Exception as e:
            return _handle_error("stripe_finalize_invoice", e)

    def void_invoice(self, inp: dict) -> str:
        permission_error, invoice_id = self._check(self.agent_id, self.PROVIDER_ID, "stripe_void_invoice", inp, "invoice_id")
        if permission_error: return permission_error
        try:
            resp = httpx.post(f"{_BASE}/invoices/{invoice_id}/void", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            inv = resp.json()
            return json.dumps({"id": inv["id"], "status": inv.get("status")})
        except Exception as e:
            return _handle_error("stripe_void_invoice", e)

    def create_payment_link(self, inp: dict) -> str:
        permission_error, price_id = self._check(self.agent_id, self.PROVIDER_ID, "stripe_create_payment_link", inp, "price_id")
        if permission_error: return permission_error
        try:
            payload = {
                "line_items[0][price]": price_id,
                "line_items[0][quantity]": int(inp.get("quantity", 1)),
            }
            if inp.get("after_completion_url"):
                payload["after_completion[type]"] = "redirect"
                payload["after_completion[redirect][url]"] = inp["after_completion_url"]
            resp = httpx.post(f"{_BASE}/payment_links", headers=self._auth_headers, data=payload, timeout=15)
            resp.raise_for_status()
            pl = resp.json()
            return json.dumps({"id": pl["id"], "url": pl.get("url"), "active": pl.get("active")})
        except Exception as e:
            return _handle_error("stripe_create_payment_link", e)

    def create_product(self, inp: dict) -> str:
        permission_error, name = self._check(self.agent_id, self.PROVIDER_ID, "stripe_create_product", inp, "name")
        if permission_error: return permission_error
        try:
            payload = {"name": name}
            if inp.get("description"):
                payload["description"] = inp["description"]
            if inp.get("active") is not None:
                payload["active"] = str(inp["active"]).lower()
            resp = httpx.post(f"{_BASE}/products", headers=self._auth_headers, data=payload, timeout=15)
            resp.raise_for_status()
            p = resp.json()
            return json.dumps({"id": p["id"], "name": p.get("name"), "active": p.get("active"), "created": p.get("created")})
        except Exception as e:
            return _handle_error("stripe_create_product", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "stripe_get_balance",
                    "description": "Get the current Stripe account balance (available and pending).",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_customers",
                    "description": "List Stripe customers, optionally filtered by email.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string", "description": "Filter customers by email address."},
                            "limit": {"type": "integer", "description": "Max customers to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_get_customer",
                    "description": "Get details of a specific Stripe customer.",
                    "parameters": {
                        "type": "object",
                        "properties": {"customer_id": {"type": "string", "description": "Stripe customer ID (starts with 'cus_')."}},
                        "required": ["customer_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_charges",
                    "description": "List Stripe charges/payments.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Filter by Stripe customer ID."},
                            "limit": {"type": "integer", "description": "Max charges to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_subscriptions",
                    "description": "List Stripe subscriptions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Filter by customer ID."},
                            "status": {"type": "string", "description": "Filter by status: active, past_due, canceled, trialing, all."},
                            "limit": {"type": "integer", "description": "Max subscriptions (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_invoices",
                    "description": "List Stripe invoices.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Filter by customer ID."},
                            "status": {"type": "string", "description": "Filter by status: draft, open, paid, uncollectible, void."},
                            "limit": {"type": "integer", "description": "Max invoices to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_get_payment_intent",
                    "description": "Get details of a specific Stripe payment intent.",
                    "parameters": {
                        "type": "object",
                        "properties": {"payment_intent_id": {"type": "string", "description": "Payment intent ID (starts with 'pi_')."}},
                        "required": ["payment_intent_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_delete_customer",
                    "description": "Permanently delete a Stripe customer by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {"customer_id": {"type": "string", "description": "Stripe customer ID (starts with 'cus_')."}},
                        "required": ["customer_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_create_customer",
                    "description": "Create a new Stripe customer.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Customer full name."},
                            "email": {"type": "string", "description": "Customer email address."},
                            "phone": {"type": "string", "description": "Customer phone number."},
                            "description": {"type": "string", "description": "Internal description/notes."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_create_payment_intent",
                    "description": "Create a Stripe PaymentIntent to initiate a payment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "amount": {"type": "integer", "description": "Amount in smallest currency unit (e.g. cents for USD). E.g. 1000 = $10.00."},
                            "currency": {"type": "string", "description": "3-letter ISO currency code (default: usd)."},
                            "customer_id": {"type": "string", "description": "Stripe customer ID to attach this payment to."},
                            "description": {"type": "string", "description": "Description for this payment."},
                        },
                        "required": ["amount"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_refund_charge",
                    "description": "Issue a full or partial refund for a Stripe charge.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "charge_id": {"type": "string", "description": "Stripe charge ID (starts with 'ch_')."},
                            "amount": {"type": "integer", "description": "Amount to refund in smallest currency unit. Omit for full refund."},
                            "reason": {"type": "string", "description": "Reason: duplicate, fraudulent, or customer_request."},
                        },
                        "required": ["charge_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_payment_intents",
                    "description": "List Stripe PaymentIntents.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Filter by customer ID."},
                            "limit": {"type": "integer", "description": "Max records to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_refunds",
                    "description": "List Stripe refunds.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "charge_id": {"type": "string", "description": "Filter by charge ID."},
                            "limit": {"type": "integer", "description": "Max records to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_products",
                    "description": "List Stripe products.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "active": {"type": "boolean", "description": "Filter by active status."},
                            "limit": {"type": "integer", "description": "Max records to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_prices",
                    "description": "List Stripe prices/plans.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "string", "description": "Filter by product ID."},
                            "active": {"type": "boolean", "description": "Filter by active status."},
                            "limit": {"type": "integer", "description": "Max records to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_payouts",
                    "description": "List Stripe payouts to your bank account.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by status: paid, pending, in_transit, canceled, failed."},
                            "limit": {"type": "integer", "description": "Max records to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_cancel_subscription",
                    "description": "Cancel a Stripe subscription immediately.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscription_id": {"type": "string", "description": "Stripe subscription ID (starts with 'sub_')."},
                        },
                        "required": ["subscription_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_get_account",
                    "description": "Get the connected Stripe account details including business name, email, country, and capabilities.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_balance_transactions",
                    "description": "List all balance transactions (charges, refunds, payouts, fees, etc.).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "description": "Filter by type: charge, refund, payout, payment, transfer, adjustment, etc."},
                            "limit": {"type": "integer", "description": "Max records to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_disputes",
                    "description": "List Stripe disputes (chargebacks).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "charge_id": {"type": "string", "description": "Filter by charge ID."},
                            "limit": {"type": "integer", "description": "Max records to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_events",
                    "description": "List Stripe events (webhook event log).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "description": "Filter by event type, e.g. payment_intent.succeeded, customer.created."},
                            "limit": {"type": "integer", "description": "Max records to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_payment_methods",
                    "description": "List saved payment methods for a specific Stripe customer.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Stripe customer ID (starts with 'cus_')."},
                            "type": {"type": "string", "description": "Payment method type: card, sepa_debit, us_bank_account, etc. Default: card."},
                            "limit": {"type": "integer", "description": "Max records to return (default 20)."},
                        },
                        "required": ["customer_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_checkout_sessions",
                    "description": "List Stripe Checkout Sessions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Filter by customer ID."},
                            "status": {"type": "string", "description": "Filter by status: open, complete, expired."},
                            "limit": {"type": "integer", "description": "Max records to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_coupons",
                    "description": "List Stripe coupons (discount codes).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max records to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_create_coupon",
                    "description": "Create a Stripe coupon for discounts.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "percent_off": {"type": "number", "description": "Percentage discount (e.g. 20 for 20% off). Use this OR amount_off."},
                            "amount_off": {"type": "integer", "description": "Fixed discount in smallest currency unit. Use this OR percent_off."},
                            "currency": {"type": "string", "description": "Required if using amount_off (default: usd)."},
                            "duration": {"type": "string", "description": "once, repeating, or forever."},
                            "duration_in_months": {"type": "integer", "description": "Required if duration=repeating."},
                            "name": {"type": "string", "description": "Human-readable name for the coupon."},
                            "max_redemptions": {"type": "integer", "description": "Max number of times this coupon can be redeemed."},
                        },
                        "required": ["duration"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_update_customer",
                    "description": "Update an existing Stripe customer's details.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Stripe customer ID (starts with 'cus_')."},
                            "name": {"type": "string", "description": "Updated name."},
                            "email": {"type": "string", "description": "Updated email address."},
                            "phone": {"type": "string", "description": "Updated phone number."},
                            "description": {"type": "string", "description": "Updated description/notes."},
                        },
                        "required": ["customer_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_webhooks",
                    "description": "List configured Stripe webhook endpoints.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_setup_intents",
                    "description": "List Stripe SetupIntents (for saving payment methods without charging).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Filter by customer ID."},
                            "limit": {"type": "integer", "description": "Max records to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_tax_rates",
                    "description": "List Stripe tax rates.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "active": {"type": "boolean", "description": "Filter by active status."},
                            "limit": {"type": "integer", "description": "Max records to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_list_promotion_codes",
                    "description": "List Stripe promotion codes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "coupon_id": {"type": "string", "description": "Filter by coupon ID."},
                            "active": {"type": "boolean", "description": "Filter by active status."},
                            "limit": {"type": "integer", "description": "Max records to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_create_subscription",
                    "description": "Create a new Stripe subscription for a customer on a given price/plan.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Stripe customer ID (starts with 'cus_')."},
                            "price_id": {"type": "string", "description": "Stripe price ID to subscribe to (starts with 'price_')."},
                            "quantity": {"type": "integer", "description": "Quantity of the price item (default 1)."},
                            "trial_period_days": {"type": "integer", "description": "Number of trial days before the first charge."},
                            "coupon": {"type": "string", "description": "Coupon ID to apply to the subscription."},
                        },
                        "required": ["customer_id", "price_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_update_subscription",
                    "description": "Update an existing Stripe subscription: change its price, schedule cancellation at period end, or set proration behavior.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "subscription_id": {"type": "string", "description": "Stripe subscription ID (starts with 'sub_')."},
                            "price_id": {"type": "string", "description": "New price ID to switch the subscription's first item to."},
                            "cancel_at_period_end": {"type": "boolean", "description": "If true, cancel the subscription at the end of the current billing period instead of immediately."},
                            "proration_behavior": {"type": "string", "description": "How to prorate the change: create_prorations, none, or always_invoice."},
                        },
                        "required": ["subscription_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_create_invoice",
                    "description": "Create a draft Stripe invoice for a customer.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "string", "description": "Stripe customer ID (starts with 'cus_')."},
                            "description": {"type": "string", "description": "Description shown on the invoice."},
                            "auto_advance": {"type": "boolean", "description": "Whether Stripe should automatically finalize/collect this invoice."},
                            "days_until_due": {"type": "integer", "description": "Number of days until the invoice is due (sets collection_method to send_invoice)."},
                        },
                        "required": ["customer_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_finalize_invoice",
                    "description": "Finalize a draft Stripe invoice, making it ready to be paid or sent to the customer.",
                    "parameters": {
                        "type": "object",
                        "properties": {"invoice_id": {"type": "string", "description": "Stripe invoice ID (starts with 'in_')."}},
                        "required": ["invoice_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_void_invoice",
                    "description": "Void a finalized Stripe invoice that should no longer be collected.",
                    "parameters": {
                        "type": "object",
                        "properties": {"invoice_id": {"type": "string", "description": "Stripe invoice ID (starts with 'in_')."}},
                        "required": ["invoice_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_create_payment_link",
                    "description": "Create a shareable Stripe Payment Link for a given price, for use in checkout flows without custom integration.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "price_id": {"type": "string", "description": "Stripe price ID to sell via the link (starts with 'price_')."},
                            "quantity": {"type": "integer", "description": "Quantity of the price item (default 1)."},
                            "after_completion_url": {"type": "string", "description": "URL to redirect the customer to after a successful payment."},
                        },
                        "required": ["price_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "stripe_create_product",
                    "description": "Create a new Stripe product (used to attach prices for sale or subscription).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Product name."},
                            "description": {"type": "string", "description": "Product description."},
                            "active": {"type": "boolean", "description": "Whether the product is active (default true)."},
                        },
                        "required": ["name"],
                    },
                },
            },
        ]
        callables = {
            "stripe_get_balance": self.get_balance,
            "stripe_list_customers": self.list_customers,
            "stripe_get_customer": self.get_customer,
            "stripe_list_charges": self.list_charges,
            "stripe_list_subscriptions": self.list_subscriptions,
            "stripe_list_invoices": self.list_invoices,
            "stripe_get_payment_intent": self.get_payment_intent,
            "stripe_delete_customer": self.delete_customer,
            "stripe_create_customer": self.create_customer,
            "stripe_create_payment_intent": self.create_payment_intent,
            "stripe_refund_charge": self.refund_charge,
            "stripe_list_payment_intents": self.list_payment_intents,
            "stripe_list_refunds": self.list_refunds,
            "stripe_list_products": self.list_products,
            "stripe_list_prices": self.list_prices,
            "stripe_list_payouts": self.list_payouts,
            "stripe_cancel_subscription": self.cancel_subscription,
            "stripe_get_account": self.get_account,
            "stripe_list_balance_transactions": self.list_balance_transactions,
            "stripe_list_disputes": self.list_disputes,
            "stripe_list_events": self.list_events,
            "stripe_list_payment_methods": self.list_payment_methods,
            "stripe_list_checkout_sessions": self.list_checkout_sessions,
            "stripe_list_coupons": self.list_coupons,
            "stripe_create_coupon": self.create_coupon,
            "stripe_update_customer": self.update_customer,
            "stripe_list_webhooks": self.list_webhooks,
            "stripe_list_setup_intents": self.list_setup_intents,
            "stripe_list_tax_rates": self.list_tax_rates,
            "stripe_list_promotion_codes": self.list_promotion_codes,
            "stripe_create_subscription": self.create_subscription,
            "stripe_update_subscription": self.update_subscription,
            "stripe_create_invoice": self.create_invoice,
            "stripe_finalize_invoice": self.finalize_invoice,
            "stripe_void_invoice": self.void_invoice,
            "stripe_create_payment_link": self.create_payment_link,
            "stripe_create_product": self.create_product,
        }
        return tools, callables

import json

from ai.connectors.base import BaseConnector

_UNAVAILABLE_MSG = (
    "Fiverr does not provide a public API. "
    "This connector cannot fetch live data. "
    "Please use the Fiverr website directly at fiverr.com."
)


class FiverrConnector(BaseConnector):
    """Fiverr connector stub. Fiverr has no public REST API; all methods return an informative error."""

    PROVIDER_ID = "fiverr"

    def get_profile(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fiverr_get_profile", inp)
        if permission_error: return permission_error
        return json.dumps({"error": _UNAVAILABLE_MSG})

    def list_gigs(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fiverr_list_gigs", inp)
        if permission_error: return permission_error
        return json.dumps({"error": _UNAVAILABLE_MSG})

    def get_gig(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fiverr_get_gig", inp)
        if permission_error: return permission_error
        return json.dumps({"error": _UNAVAILABLE_MSG})

    def list_orders(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fiverr_list_orders", inp)
        if permission_error: return permission_error
        return json.dumps({"error": _UNAVAILABLE_MSG})

    def get_order(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fiverr_get_order", inp)
        if permission_error: return permission_error
        return json.dumps({"error": _UNAVAILABLE_MSG})

    def list_inbox(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fiverr_list_inbox", inp)
        if permission_error: return permission_error
        return json.dumps({"error": _UNAVAILABLE_MSG})

    def get_conversation(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fiverr_get_conversation", inp)
        if permission_error: return permission_error
        return json.dumps({"error": _UNAVAILABLE_MSG})

    def send_message(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fiverr_send_message", inp)
        if permission_error: return permission_error
        return json.dumps({"error": _UNAVAILABLE_MSG})

    def submit_delivery(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fiverr_submit_delivery", inp)
        if permission_error: return permission_error
        return json.dumps({"error": _UNAVAILABLE_MSG})

    def request_order_extension(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fiverr_request_order_extension", inp)
        if permission_error: return permission_error
        return json.dumps({"error": _UNAVAILABLE_MSG})

    def cancel_order(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fiverr_cancel_order", inp)
        if permission_error: return permission_error
        return json.dumps({"error": _UNAVAILABLE_MSG})

    def list_reviews(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fiverr_list_reviews", inp)
        if permission_error: return permission_error
        return json.dumps({"error": _UNAVAILABLE_MSG})

    def get_earnings(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fiverr_get_earnings", inp)
        if permission_error: return permission_error
        return json.dumps({"error": _UNAVAILABLE_MSG})

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "fiverr_get_profile",
                    "description": "(Unavailable - Fiverr has no public API) Get the authenticated Fiverr user's profile, seller level, and rating.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fiverr_list_gigs",
                    "description": "(Unavailable - Fiverr has no public API) List the authenticated seller's Fiverr gigs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by status: active, paused, denied, draft."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fiverr_get_gig",
                    "description": "(Unavailable - Fiverr has no public API) Get full details of a specific Fiverr gig including packages and pricing.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "gig_id": {"type": "string", "description": "Gig ID from fiverr_list_gigs."},
                        },
                        "required": ["gig_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fiverr_list_orders",
                    "description": "(Unavailable - Fiverr has no public API) List Fiverr orders as a seller or buyer.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by order status: all (default), active, completed, cancelled, late."},
                            "role": {"type": "string", "description": "Your role: seller (default) or buyer."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fiverr_get_order",
                    "description": "(Unavailable - Fiverr has no public API) Get full details of a specific Fiverr order.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "Order ID from fiverr_list_orders."},
                        },
                        "required": ["order_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fiverr_list_inbox",
                    "description": "(Unavailable - Fiverr has no public API) List Fiverr inbox conversations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "unread_only": {"type": "boolean", "description": "If true, only return unread conversations."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fiverr_get_conversation",
                    "description": "(Unavailable - Fiverr has no public API) Get messages in a specific Fiverr inbox conversation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "conversation_id": {"type": "string", "description": "Conversation ID from fiverr_list_inbox."},
                        },
                        "required": ["conversation_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fiverr_send_message",
                    "description": "(Unavailable - Fiverr has no public API) Send a message to a buyer or seller in a Fiverr inbox conversation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "conversation_id": {"type": "string", "description": "Conversation ID from fiverr_list_inbox."},
                            "message": {"type": "string", "description": "Message text to send."},
                        },
                        "required": ["conversation_id", "message"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fiverr_submit_delivery",
                    "description": "(Unavailable - Fiverr has no public API) Submit a delivery (files and/or message) for a Fiverr order.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "Order ID from fiverr_list_orders."},
                            "message": {"type": "string", "description": "Delivery message describing the completed work."},
                            "file_urls": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "URLs of files to attach to the delivery.",
                            },
                        },
                        "required": ["order_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fiverr_request_order_extension",
                    "description": "(Unavailable - Fiverr has no public API) Request additional delivery time for a Fiverr order.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "Order ID from fiverr_list_orders."},
                            "extra_days": {"type": "integer", "description": "Number of additional days requested."},
                            "reason": {"type": "string", "description": "Reason for requesting the extension."},
                        },
                        "required": ["order_id", "extra_days"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fiverr_cancel_order",
                    "description": "(Unavailable - Fiverr has no public API) Request cancellation of a Fiverr order.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "Order ID from fiverr_list_orders."},
                            "reason": {"type": "string", "description": "Reason for the cancellation request."},
                        },
                        "required": ["order_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fiverr_list_reviews",
                    "description": "(Unavailable - Fiverr has no public API) List reviews left for a specific gig or for the authenticated seller.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "gig_id": {"type": "string", "description": "Gig ID to filter reviews by (omit for all seller reviews)."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fiverr_get_earnings",
                    "description": "(Unavailable - Fiverr has no public API) Get the authenticated seller's earnings, balance, and withdrawal report.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD) for the earnings report."},
                            "end_date": {"type": "string", "description": "End date (YYYY-MM-DD) for the earnings report."},
                        },
                        "required": [],
                    },
                },
            },
        ]
        callables = {
            "fiverr_get_profile": self.get_profile,
            "fiverr_list_gigs": self.list_gigs,
            "fiverr_get_gig": self.get_gig,
            "fiverr_list_orders": self.list_orders,
            "fiverr_get_order": self.get_order,
            "fiverr_list_inbox": self.list_inbox,
            "fiverr_get_conversation": self.get_conversation,
            "fiverr_send_message": self.send_message,
            "fiverr_submit_delivery": self.submit_delivery,
            "fiverr_request_order_extension": self.request_order_extension,
            "fiverr_cancel_order": self.cancel_order,
            "fiverr_list_reviews": self.list_reviews,
            "fiverr_get_earnings": self.get_earnings,
        }
        return tools, callables

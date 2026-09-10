import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.calendly.com"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Calendly account lacks permission "
                f"for this action (HTTP {e.response.status_code}). Ask the user to reconnect their "
                "Calendly connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class CalendlyConnector(BaseConnector):

    PROVIDER_ID = "calendly"

    # ── User ──────────────────────────────────────────────────────────────────

    def get_current_user(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "calendly_get_current_user", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/users/me", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("resource", {})
            return json.dumps({
                "uri": data.get("uri"),
                "name": data.get("name"),
                "email": data.get("email"),
                "scheduling_url": data.get("scheduling_url"),
                "timezone": data.get("timezone"),
            })
        except Exception as e:
            return _handle_error("calendly_get_current_user", e)

    def _current_user_uri(self) -> str:
        resp = httpx.get(f"{_BASE}/users/me", headers=self._auth_headers, timeout=15)
        resp.raise_for_status()
        return resp.json()["resource"]["uri"]

    # ── Event types ───────────────────────────────────────────────────────────

    def list_event_types(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "calendly_list_event_types", inp)
        if permission_error: return permission_error
        try:
            user_uri = self._current_user_uri()
            params = {"user": user_uri, "count": inp.get("max_results", 20)}
            if inp.get("active_only", True):
                params["active"] = "true"
            resp = httpx.get(f"{_BASE}/event_types", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            event_types = [
                {
                    "uri": et["uri"],
                    "name": et.get("name"),
                    "duration_minutes": et.get("duration"),
                    "scheduling_url": et.get("scheduling_url"),
                    "active": et.get("active"),
                }
                for et in data.get("collection", [])
            ]
            return json.dumps(event_types)
        except Exception as e:
            return _handle_error("calendly_list_event_types", e)

    # ── Scheduled events ──────────────────────────────────────────────────────

    def list_scheduled_events(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "calendly_list_scheduled_events", inp)
        if permission_error: return permission_error
        try:
            user_uri = self._current_user_uri()
            params = {
                "user": user_uri,
                "count": inp.get("max_results", 20),
                "status": inp.get("status", "active"),
            }
            if inp.get("min_start_time"):
                params["min_start_time"] = inp["min_start_time"]
            if inp.get("max_start_time"):
                params["max_start_time"] = inp["max_start_time"]
            resp = httpx.get(f"{_BASE}/scheduled_events", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            events = [
                {
                    "uri": ev["uri"],
                    "name": ev.get("name"),
                    "status": ev.get("status"),
                    "start_time": ev.get("start_time"),
                    "end_time": ev.get("end_time"),
                    "location": ev.get("location", {}),
                }
                for ev in data.get("collection", [])
            ]
            return json.dumps(events)
        except Exception as e:
            return _handle_error("calendly_list_scheduled_events", e)

    def get_scheduled_event(self, inp: dict) -> str:
        permission_error, event_uuid = self._check(self.agent_id, self.PROVIDER_ID, "calendly_get_scheduled_event", inp, "event_uuid")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/scheduled_events/{event_uuid}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json().get("resource", {}))
        except Exception as e:
            return _handle_error("calendly_get_scheduled_event", e)

    def list_invitees(self, inp: dict) -> str:
        permission_error, event_uuid = self._check(self.agent_id, self.PROVIDER_ID, "calendly_list_invitees", inp, "event_uuid")
        if permission_error: return permission_error
        try:
            params = {"count": inp.get("max_results", 20)}
            if inp.get("status"):
                params["status"] = inp["status"]
            resp = httpx.get(
                f"{_BASE}/scheduled_events/{event_uuid}/invitees",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            invitees = [
                {
                    "uri": inv["uri"],
                    "email": inv.get("email"),
                    "name": inv.get("name"),
                    "status": inv.get("status"),
                    "cancel_url": inv.get("cancel_url"),
                    "reschedule_url": inv.get("reschedule_url"),
                }
                for inv in data.get("collection", [])
            ]
            return json.dumps(invitees)
        except Exception as e:
            return _handle_error("calendly_list_invitees", e)

    def cancel_event(self, inp: dict) -> str:
        permission_error, event_uuid = self._check(self.agent_id, self.PROVIDER_ID, "calendly_cancel_event", inp, "event_uuid")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {"reason": inp["reason"]} if inp.get("reason") else {}
            resp = httpx.post(
                f"{_BASE}/scheduled_events/{event_uuid}/cancellation",
                headers=headers,
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"status": "canceled", "event_uuid": event_uuid})
        except Exception as e:
            return _handle_error("calendly_cancel_event", e)

    # ── Booking links ─────────────────────────────────────────────────────────

    def create_scheduling_link(self, inp: dict) -> str:
        permission_error, event_type_uri = self._check(self.agent_id, self.PROVIDER_ID, "calendly_create_scheduling_link", inp, "event_type_uri")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "max_event_count": inp.get("max_event_count", 1),
                "owner": event_type_uri,
                "owner_type": "EventType",
            }
            resp = httpx.post(f"{_BASE}/scheduling_links", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("resource", {})
            return json.dumps({"booking_url": data.get("booking_url")})
        except Exception as e:
            return _handle_error("calendly_create_scheduling_link", e)

    # ── Tool manifest ─────────────────────────────────────────────────────────

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "calendly_get_current_user",
                    "description": "Get the connected Calendly user's profile (name, email, scheduling URL, timezone).",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendly_list_event_types",
                    "description": "List the user's Calendly event types (the meeting templates people book, e.g. '30 Minute Meeting').",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "max_results": {"type": "integer", "description": "Max event types to return (default 20)."},
                            "active_only": {"type": "boolean", "description": "Only return active event types (default true)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendly_list_scheduled_events",
                    "description": "List the user's booked Calendly meetings, optionally filtered by time range and status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "max_results": {"type": "integer", "description": "Max events to return (default 20)."},
                            "status": {"type": "string", "description": "'active' (default) or 'canceled'."},
                            "min_start_time": {"type": "string", "description": "Only return events starting after this RFC3339 datetime."},
                            "max_start_time": {"type": "string", "description": "Only return events starting before this RFC3339 datetime."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendly_get_scheduled_event",
                    "description": "Get full details of a specific scheduled Calendly meeting.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_uuid": {"type": "string", "description": "The scheduled event's UUID."},
                        },
                        "required": ["event_uuid"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendly_list_invitees",
                    "description": "List the invitees (attendees) for a scheduled Calendly meeting.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_uuid": {"type": "string", "description": "The scheduled event's UUID."},
                            "max_results": {"type": "integer", "description": "Max invitees to return (default 20)."},
                            "status": {"type": "string", "description": "Filter by 'active' or 'canceled'."},
                        },
                        "required": ["event_uuid"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendly_cancel_event",
                    "description": "Cancel a scheduled Calendly meeting on the user's behalf. This notifies all invitees.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_uuid": {"type": "string", "description": "The scheduled event's UUID to cancel."},
                            "reason": {"type": "string", "description": "Optional reason shown to invitees."},
                        },
                        "required": ["event_uuid"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendly_create_scheduling_link",
                    "description": "Create a single-use booking link for one of the user's event types, so someone can pick a time to meet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_type_uri": {"type": "string", "description": "The event type's URI, from calendly_list_event_types."},
                            "max_event_count": {"type": "integer", "description": "How many times the link can be used before it expires (default 1)."},
                        },
                        "required": ["event_type_uri"],
                    },
                },
            },
        ]
        callables = {
            "calendly_get_current_user": self.get_current_user,
            "calendly_list_event_types": self.list_event_types,
            "calendly_list_scheduled_events": self.list_scheduled_events,
            "calendly_get_scheduled_event": self.get_scheduled_event,
            "calendly_list_invitees": self.list_invitees,
            "calendly_cancel_event": self.cancel_event,
            "calendly_create_scheduling_link": self.create_scheduling_link,
        }
        return tools, callables

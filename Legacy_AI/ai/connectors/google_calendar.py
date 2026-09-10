import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://www.googleapis.com/calendar/v3"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Google Calendar account lacks permission "
                f"for this action (HTTP {e.response.status_code}). "
                "Ask the user to reconnect their Google Calendar connector with the required OAuth scopes."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class GoogleCalendarConnector(BaseConnector):

    PROVIDER_ID = "google-calendar"

    # ── Calendars ─────────────────────────────────────────────────────────────

    def list_calendars(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "google_calendar_list_calendars", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/users/me/calendarList", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            calendars = [
                {
                    "id": c["id"],
                    "summary": c.get("summary", ""),
                    "description": c.get("description", ""),
                    "primary": c.get("primary", False),
                    "timeZone": c.get("timeZone", ""),
                }
                for c in data.get("items", [])
            ]
            return json.dumps(calendars)
        except Exception as e:
            return _handle_error("google_calendar_list_calendars", e)

    # ── Events ────────────────────────────────────────────────────────────────

    def list_events(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "google_calendar_list_events", inp)
        if permission_error: return permission_error
        calendar_id = inp.get("calendar_id", "primary")
        try:
            params = {
                "maxResults": inp.get("max_results", 20),
                "orderBy": "startTime",
                "singleEvents": "true",
            }
            if inp.get("time_min"):
                params["timeMin"] = inp["time_min"]
            if inp.get("time_max"):
                params["timeMax"] = inp["time_max"]
            if inp.get("query"):
                params["q"] = inp["query"]
            resp = httpx.get(
                f"{_BASE}/calendars/{calendar_id}/events",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            events = [
                {
                    "id": e["id"],
                    "summary": e.get("summary", "(No title)"),
                    "description": e.get("description", ""),
                    "start": e.get("start", {}),
                    "end": e.get("end", {}),
                    "location": e.get("location", ""),
                    "status": e.get("status", ""),
                    "htmlLink": e.get("htmlLink", ""),
                    "attendees": [a.get("email") for a in e.get("attendees", [])],
                }
                for e in data.get("items", [])
            ]
            return json.dumps(events)
        except Exception as e:
            return _handle_error("google_calendar_list_events", e)

    def get_event(self, inp: dict) -> str:
        permission_error, event_id = self._check(self.agent_id, self.PROVIDER_ID, "google_calendar_get_event", inp, "event_id")
        if permission_error: return permission_error
        calendar_id = inp.get("calendar_id", "primary")
        try:
            resp = httpx.get(
                f"{_BASE}/calendars/{calendar_id}/events/{event_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_calendar_get_event", e)

    def create_event(self, inp: dict) -> str:
        permission_error, summary, start, end = self._check(self.agent_id, self.PROVIDER_ID, "google_calendar_create_event", inp, "summary", "start", "end")
        if permission_error: return permission_error
        calendar_id = inp.get("calendar_id", "primary")
        try:
            body: dict = {
                "summary": summary,
                "start": {"dateTime": start, "timeZone": inp.get("time_zone", "UTC")},
                "end": {"dateTime": end, "timeZone": inp.get("time_zone", "UTC")},
            }
            if inp.get("description"):
                body["description"] = inp["description"]
            if inp.get("location"):
                body["location"] = inp["location"]
            if inp.get("attendees"):
                body["attendees"] = [{"email": e} for e in inp["attendees"]]
            if inp.get("recurrence"):
                body["recurrence"] = inp["recurrence"]
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.post(
                f"{_BASE}/calendars/{calendar_id}/events",
                headers=headers,
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data["id"], "summary": data.get("summary"), "htmlLink": data.get("htmlLink")})
        except Exception as e:
            return _handle_error("google_calendar_create_event", e)

    def update_event(self, inp: dict) -> str:
        permission_error, event_id = self._check(self.agent_id, self.PROVIDER_ID, "google_calendar_update_event", inp, "event_id")
        if permission_error: return permission_error
        calendar_id = inp.get("calendar_id", "primary")
        try:
            get_resp = httpx.get(
                f"{_BASE}/calendars/{calendar_id}/events/{event_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            get_resp.raise_for_status()
            body = get_resp.json()
            if inp.get("summary"):
                body["summary"] = inp["summary"]
            if inp.get("description"):
                body["description"] = inp["description"]
            if inp.get("location"):
                body["location"] = inp["location"]
            if inp.get("start"):
                body["start"] = {"dateTime": inp["start"], "timeZone": inp.get("time_zone", body.get("start", {}).get("timeZone", "UTC"))}
            if inp.get("end"):
                body["end"] = {"dateTime": inp["end"], "timeZone": inp.get("time_zone", body.get("end", {}).get("timeZone", "UTC"))}
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.put(
                f"{_BASE}/calendars/{calendar_id}/events/{event_id}",
                headers=headers,
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"id": event_id, "status": "updated"})
        except Exception as e:
            return _handle_error("google_calendar_update_event", e)

    def delete_event(self, inp: dict) -> str:
        permission_error, event_id = self._check(self.agent_id, self.PROVIDER_ID, "google_calendar_delete_event", inp, "event_id")
        if permission_error: return permission_error
        calendar_id = inp.get("calendar_id", "primary")
        try:
            resp = httpx.delete(
                f"{_BASE}/calendars/{calendar_id}/events/{event_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"status": "deleted", "event_id": event_id})
        except Exception as e:
            return _handle_error("google_calendar_delete_event", e)

    def get_free_busy(self, inp: dict) -> str:
        permission_error, time_min, time_max = self._check(self.agent_id, self.PROVIDER_ID, "google_calendar_get_free_busy", inp, "time_min", "time_max")
        if permission_error: return permission_error
        calendar_ids = inp.get("calendar_ids", ["primary"])
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            body = {
                "timeMin": time_min,
                "timeMax": time_max,
                "items": [{"id": cid} for cid in calendar_ids],
            }
            resp = httpx.post(f"{_BASE}/freeBusy", headers=headers, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            calendars = {
                cid: {"busy": info.get("busy", []), "errors": info.get("errors", [])}
                for cid, info in data.get("calendars", {}).items()
            }
            return json.dumps({"calendars": calendars})
        except Exception as e:
            return _handle_error("google_calendar_get_free_busy", e)

    def quick_add_event(self, inp: dict) -> str:
        permission_error, text = self._check(self.agent_id, self.PROVIDER_ID, "google_calendar_quick_add_event", inp, "text")
        if permission_error: return permission_error
        calendar_id = inp.get("calendar_id", "primary")
        try:
            resp = httpx.post(
                f"{_BASE}/calendars/{calendar_id}/events/quickAdd",
                headers=self._auth_headers,
                params={"text": text},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "summary": data.get("summary"), "htmlLink": data.get("htmlLink")})
        except Exception as e:
            return _handle_error("google_calendar_quick_add_event", e)

    def move_event(self, inp: dict) -> str:
        permission_error, event_id, destination_calendar_id = self._check(self.agent_id, self.PROVIDER_ID, "google_calendar_move_event", inp, "event_id", "destination_calendar_id")
        if permission_error: return permission_error
        calendar_id = inp.get("calendar_id", "primary")
        try:
            resp = httpx.post(
                f"{_BASE}/calendars/{calendar_id}/events/{event_id}/move",
                headers=self._auth_headers,
                params={"destination": destination_calendar_id},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"id": data.get("id"), "status": "moved", "destination_calendar_id": destination_calendar_id})
        except Exception as e:
            return _handle_error("google_calendar_move_event", e)

    def respond_to_event(self, inp: dict) -> str:
        permission_error, event_id, response_status = self._check(self.agent_id, self.PROVIDER_ID, "google_calendar_respond_to_event", inp, "event_id", "response_status")
        if permission_error: return permission_error
        if response_status not in ("accepted", "declined", "tentative"):
            return "Error: 'response_status' must be 'accepted', 'declined', or 'tentative'."
        calendar_id = inp.get("calendar_id", "primary")
        try:
            get_resp = httpx.get(
                f"{_BASE}/calendars/{calendar_id}/events/{event_id}",
                headers=self._auth_headers,
                timeout=15,
            )
            get_resp.raise_for_status()
            event = get_resp.json()
            attendees = event.get("attendees", [])
            me = inp.get("attendee_email", "")
            updated = False
            for a in attendees:
                if a.get("self") or (me and a.get("email") == me):
                    a["responseStatus"] = response_status
                    updated = True
            if not updated:
                return "Error: could not find the current user in the event's attendee list. Provide 'attendee_email'."
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            resp = httpx.patch(
                f"{_BASE}/calendars/{calendar_id}/events/{event_id}",
                headers=headers,
                json={"attendees": attendees},
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"id": event_id, "response_status": response_status, "status": "updated"})
        except Exception as e:
            return _handle_error("google_calendar_respond_to_event", e)

    def list_event_instances(self, inp: dict) -> str:
        permission_error, event_id = self._check(self.agent_id, self.PROVIDER_ID, "google_calendar_list_event_instances", inp, "event_id")
        if permission_error: return permission_error
        calendar_id = inp.get("calendar_id", "primary")
        try:
            params = {"maxResults": inp.get("max_results", 20)}
            if inp.get("time_min"):
                params["timeMin"] = inp["time_min"]
            if inp.get("time_max"):
                params["timeMax"] = inp["time_max"]
            resp = httpx.get(
                f"{_BASE}/calendars/{calendar_id}/events/{event_id}/instances",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            instances = [
                {
                    "id": e["id"],
                    "start": e.get("start", {}),
                    "end": e.get("end", {}),
                    "status": e.get("status", ""),
                }
                for e in data.get("items", [])
            ]
            return json.dumps({"instances": instances, "count": len(instances)})
        except Exception as e:
            return _handle_error("google_calendar_list_event_instances", e)

    # ── Tool manifest ─────────────────────────────────────────────────────────

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "google_calendar_list_calendars",
                    "description": "List all calendars in the user's Google Calendar account.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_calendar_list_events",
                    "description": "List events from a Google Calendar. Defaults to the primary calendar.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "calendar_id": {"type": "string", "description": "Calendar ID (default: 'primary')."},
                            "max_results": {"type": "integer", "description": "Max events to return (default 20)."},
                            "time_min": {"type": "string", "description": "Start of time range in RFC3339 format (e.g. 2026-07-01T00:00:00Z)."},
                            "time_max": {"type": "string", "description": "End of time range in RFC3339 format."},
                            "query": {"type": "string", "description": "Free-text search query to filter events."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_calendar_get_event",
                    "description": "Get details of a specific Google Calendar event.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_id": {"type": "string", "description": "The event ID."},
                            "calendar_id": {"type": "string", "description": "Calendar ID (default: 'primary')."},
                        },
                        "required": ["event_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_calendar_create_event",
                    "description": "Create a new event in Google Calendar.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string", "description": "Event title."},
                            "start": {"type": "string", "description": "Start datetime in RFC3339 format (e.g. 2026-07-01T10:00:00Z)."},
                            "end": {"type": "string", "description": "End datetime in RFC3339 format."},
                            "description": {"type": "string", "description": "Event description."},
                            "location": {"type": "string", "description": "Event location."},
                            "attendees": {"type": "array", "items": {"type": "string"}, "description": "List of attendee email addresses."},
                            "calendar_id": {"type": "string", "description": "Calendar ID (default: 'primary')."},
                            "time_zone": {"type": "string", "description": "Timezone (default: UTC)."},
                            "recurrence": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional recurrence rules in RFC5545 RRULE format (e.g. ['RRULE:FREQ=WEEKLY;COUNT=10']) to make this a recurring event.",
                            },
                        },
                        "required": ["summary", "start", "end"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_calendar_update_event",
                    "description": "Update an existing Google Calendar event.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_id": {"type": "string", "description": "The event ID to update."},
                            "summary": {"type": "string", "description": "New event title."},
                            "start": {"type": "string", "description": "New start datetime in RFC3339 format."},
                            "end": {"type": "string", "description": "New end datetime in RFC3339 format."},
                            "description": {"type": "string", "description": "New description."},
                            "location": {"type": "string", "description": "New location."},
                            "calendar_id": {"type": "string", "description": "Calendar ID (default: 'primary')."},
                            "time_zone": {"type": "string", "description": "Timezone."},
                        },
                        "required": ["event_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_calendar_delete_event",
                    "description": "Delete an event from Google Calendar.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_id": {"type": "string", "description": "The event ID to delete."},
                            "calendar_id": {"type": "string", "description": "Calendar ID (default: 'primary')."},
                        },
                        "required": ["event_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_calendar_get_free_busy",
                    "description": "Query free/busy time ranges for one or more calendars over a time window.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "calendar_ids": {"type": "array", "items": {"type": "string"}, "description": "Calendar IDs to query (default: ['primary'])."},
                            "time_min": {"type": "string", "description": "Start of interval in RFC3339 format."},
                            "time_max": {"type": "string", "description": "End of interval in RFC3339 format."},
                        },
                        "required": ["time_min", "time_max"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_calendar_quick_add_event",
                    "description": "Create an event from natural-language text (e.g. 'Dinner with Sam Friday at 8pm'), letting Google parse the date/time.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Natural-language description of the event."},
                            "calendar_id": {"type": "string", "description": "Calendar ID (default: 'primary')."},
                        },
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_calendar_move_event",
                    "description": "Move an event from one calendar to another.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_id": {"type": "string", "description": "The event ID to move."},
                            "calendar_id": {"type": "string", "description": "Source calendar ID (default: 'primary')."},
                            "destination_calendar_id": {"type": "string", "description": "Calendar ID to move the event to."},
                        },
                        "required": ["event_id", "destination_calendar_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_calendar_respond_to_event",
                    "description": "Set the current user's RSVP status (accepted, declined, tentative) on a Google Calendar event invitation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_id": {"type": "string", "description": "The event ID."},
                            "response_status": {"type": "string", "description": "'accepted', 'declined', or 'tentative'."},
                            "calendar_id": {"type": "string", "description": "Calendar ID (default: 'primary')."},
                            "attendee_email": {"type": "string", "description": "Email of the attendee to update, if not the authenticated self-attendee."},
                        },
                        "required": ["event_id", "response_status"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_calendar_list_event_instances",
                    "description": "List the individual occurrences (instances) of a recurring Google Calendar event.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_id": {"type": "string", "description": "The recurring event's ID."},
                            "calendar_id": {"type": "string", "description": "Calendar ID (default: 'primary')."},
                            "time_min": {"type": "string", "description": "Only return instances starting after this RFC3339 datetime."},
                            "time_max": {"type": "string", "description": "Only return instances starting before this RFC3339 datetime."},
                            "max_results": {"type": "integer", "description": "Max instances to return (default 20)."},
                        },
                        "required": ["event_id"],
                    },
                },
            },
        ]
        callables = {
            "google_calendar_list_calendars": self.list_calendars,
            "google_calendar_list_events": self.list_events,
            "google_calendar_get_event": self.get_event,
            "google_calendar_create_event": self.create_event,
            "google_calendar_update_event": self.update_event,
            "google_calendar_delete_event": self.delete_event,
            "google_calendar_get_free_busy": self.get_free_busy,
            "google_calendar_quick_add_event": self.quick_add_event,
            "google_calendar_move_event": self.move_event,
            "google_calendar_respond_to_event": self.respond_to_event,
            "google_calendar_list_event_instances": self.list_event_instances,
        }
        return tools, callables

import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.zoom.us/v2"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class ZoomConnector(BaseConnector):
    """Connector for Zoom — meetings, webinars, recordings, users, and reports."""

    PROVIDER_ID = "zoom"

    def get_current_user(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zoom_get_current_user", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/users/me", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            d = resp.json()
            return json.dumps({
                "id": d.get("id"),
                "email": d.get("email"),
                "first_name": d.get("first_name"),
                "last_name": d.get("last_name"),
                "type": d.get("type"),
                "status": d.get("status"),
                "timezone": d.get("timezone"),
                "account_id": d.get("account_id"),
            })
        except Exception as e:
            return _handle_error("zoom_get_current_user", e)

    def list_meetings(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zoom_list_meetings", inp)
        if permission_error: return permission_error
        user_id = inp.get("user_id", "me")
        try:
            params = {
                "type": inp.get("type", "scheduled"),
                "page_size": inp.get("page_size", 30),
            }
            if inp.get("next_page_token"):
                params["next_page_token"] = inp["next_page_token"]
            resp = httpx.get(f"{_BASE}/users/{user_id}/meetings", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            meetings = [
                {
                    "id": m.get("id"),
                    "uuid": m.get("uuid"),
                    "topic": m.get("topic"),
                    "type": m.get("type"),
                    "start_time": m.get("start_time"),
                    "duration": m.get("duration"),
                    "timezone": m.get("timezone"),
                    "join_url": m.get("join_url"),
                }
                for m in (data.get("meetings") or [])
            ]
            return json.dumps({
                "meetings": meetings,
                "count": len(meetings),
                "total_records": data.get("total_records"),
                "next_page_token": data.get("next_page_token"),
            })
        except Exception as e:
            return _handle_error("zoom_list_meetings", e)

    def get_meeting(self, inp: dict) -> str:
        permission_error, meeting_id = self._check(self.agent_id, self.PROVIDER_ID, "zoom_get_meeting", inp, "meeting_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/meetings/{meeting_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            d = resp.json()
            return json.dumps({
                "id": d.get("id"),
                "uuid": d.get("uuid"),
                "topic": d.get("topic"),
                "type": d.get("type"),
                "status": d.get("status"),
                "start_time": d.get("start_time"),
                "duration": d.get("duration"),
                "timezone": d.get("timezone"),
                "agenda": d.get("agenda"),
                "join_url": d.get("join_url"),
                "password": d.get("password"),
                "host_id": d.get("host_id"),
                "participants_count": d.get("participants_count"),
            })
        except Exception as e:
            return _handle_error("zoom_get_meeting", e)

    def list_webinars(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zoom_list_webinars", inp)
        if permission_error: return permission_error
        user_id = inp.get("user_id", "me")
        try:
            params = {"page_size": inp.get("page_size", 30)}
            if inp.get("next_page_token"):
                params["next_page_token"] = inp["next_page_token"]
            resp = httpx.get(f"{_BASE}/users/{user_id}/webinars", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            webinars = [
                {
                    "id": w.get("id"),
                    "uuid": w.get("uuid"),
                    "topic": w.get("topic"),
                    "type": w.get("type"),
                    "start_time": w.get("start_time"),
                    "duration": w.get("duration"),
                    "timezone": w.get("timezone"),
                    "join_url": w.get("join_url"),
                }
                for w in (data.get("webinars") or [])
            ]
            return json.dumps({
                "webinars": webinars,
                "count": len(webinars),
                "total_records": data.get("total_records"),
                "next_page_token": data.get("next_page_token"),
            })
        except Exception as e:
            return _handle_error("zoom_list_webinars", e)

    def list_recordings(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zoom_list_recordings", inp)
        if permission_error: return permission_error
        user_id = inp.get("user_id", "me")
        try:
            params = {"page_size": inp.get("page_size", 30)}
            if inp.get("from_date"):
                params["from"] = inp["from_date"]
            if inp.get("to_date"):
                params["to"] = inp["to_date"]
            if inp.get("next_page_token"):
                params["next_page_token"] = inp["next_page_token"]
            resp = httpx.get(f"{_BASE}/users/{user_id}/recordings", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            meetings = [
                {
                    "id": m.get("id"),
                    "uuid": m.get("uuid"),
                    "topic": m.get("topic"),
                    "start_time": m.get("start_time"),
                    "duration": m.get("duration"),
                    "total_size": m.get("total_size"),
                    "recording_count": m.get("recording_count"),
                    "share_url": m.get("share_url"),
                    "recording_files": [
                        {
                            "id": f.get("id"),
                            "file_type": f.get("file_type"),
                            "file_size": f.get("file_size"),
                            "download_url": f.get("download_url"),
                            "status": f.get("status"),
                        }
                        for f in (m.get("recording_files") or [])
                    ],
                }
                for m in (data.get("meetings") or [])
            ]
            return json.dumps({
                "recordings": meetings,
                "count": len(meetings),
                "total_records": data.get("total_records"),
                "next_page_token": data.get("next_page_token"),
            })
        except Exception as e:
            return _handle_error("zoom_list_recordings", e)

    def get_meeting_report(self, inp: dict) -> str:
        permission_error, from_date, to_date = self._check(self.agent_id, self.PROVIDER_ID, "zoom_get_meeting_report", inp, "from_date", "to_date")
        if permission_error: return permission_error
        user_id = inp.get("user_id", "me")
        try:
            params = {"from": from_date, "to": to_date, "page_size": inp.get("page_size", 30)}
            if inp.get("next_page_token"):
                params["next_page_token"] = inp["next_page_token"]
            resp = httpx.get(f"{_BASE}/report/users/{user_id}/meetings", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            meetings = [
                {
                    "id": m.get("id"),
                    "uuid": m.get("uuid"),
                    "topic": m.get("topic"),
                    "start_time": m.get("start_time"),
                    "end_time": m.get("end_time"),
                    "duration": m.get("duration"),
                    "participants_count": m.get("participants_count"),
                    "total_minutes": m.get("total_minutes"),
                    "source": m.get("source"),
                }
                for m in (data.get("meetings") or [])
            ]
            return json.dumps({
                "meetings": meetings,
                "count": len(meetings),
                "total_records": data.get("total_records"),
                "next_page_token": data.get("next_page_token"),
            })
        except Exception as e:
            return _handle_error("zoom_get_meeting_report", e)

    def list_users(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "zoom_list_users", inp)
        if permission_error: return permission_error
        try:
            params = {
                "status": inp.get("status", "active"),
                "page_size": inp.get("page_size", 30),
            }
            if inp.get("next_page_token"):
                params["next_page_token"] = inp["next_page_token"]
            resp = httpx.get(f"{_BASE}/users", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            users = [
                {
                    "id": u.get("id"),
                    "email": u.get("email"),
                    "first_name": u.get("first_name"),
                    "last_name": u.get("last_name"),
                    "type": u.get("type"),
                    "status": u.get("status"),
                    "timezone": u.get("timezone"),
                    "created_at": u.get("created_at"),
                    "last_login_time": u.get("last_login_time"),
                }
                for u in (data.get("users") or [])
            ]
            return json.dumps({
                "users": users,
                "count": len(users),
                "total_records": data.get("total_records"),
                "next_page_token": data.get("next_page_token"),
            })
        except Exception as e:
            return _handle_error("zoom_list_users", e)

    def create_meeting(self, inp: dict) -> str:
        permission_error, topic = self._check(self.agent_id, self.PROVIDER_ID, "zoom_create_meeting", inp, "topic")
        if permission_error: return permission_error
        try:
            body: dict = {
                "topic": topic,
                "type": inp.get("type", 2),
                "duration": inp.get("duration", 60),
                "timezone": inp.get("timezone", "UTC"),
            }
            if inp.get("start_time"):
                body["start_time"] = inp["start_time"]
            if inp.get("agenda"):
                body["agenda"] = inp["agenda"]
            if inp.get("password"):
                body["password"] = inp["password"]
            resp = httpx.post(
                f"{_BASE}/users/me/meetings",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            d = resp.json()
            return json.dumps({
                "id": d.get("id"),
                "uuid": d.get("uuid"),
                "topic": d.get("topic"),
                "type": d.get("type"),
                "start_time": d.get("start_time"),
                "duration": d.get("duration"),
                "timezone": d.get("timezone"),
                "agenda": d.get("agenda"),
                "join_url": d.get("join_url"),
                "password": d.get("password"),
                "host_id": d.get("host_id"),
            })
        except Exception as e:
            return _handle_error("zoom_create_meeting", e)

    def delete_meeting(self, inp: dict) -> str:
        permission_error, meeting_id = self._check(self.agent_id, self.PROVIDER_ID, "zoom_delete_meeting", inp, "meeting_id")
        if permission_error: return permission_error
        try:
            resp = httpx.delete(f"{_BASE}/meetings/{meeting_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps({"success": True, "meeting_id": meeting_id})
        except Exception as e:
            return _handle_error("zoom_delete_meeting", e)

    def update_meeting(self, inp: dict) -> str:
        permission_error, meeting_id = self._check(self.agent_id, self.PROVIDER_ID, "zoom_update_meeting", inp, "meeting_id")
        if permission_error: return permission_error
        try:
            body: dict = {}
            if inp.get("topic"):
                body["topic"] = inp["topic"]
            if inp.get("start_time"):
                body["start_time"] = inp["start_time"]
            if inp.get("duration"):
                body["duration"] = inp["duration"]
            if inp.get("agenda"):
                body["agenda"] = inp["agenda"]
            resp = httpx.patch(
                f"{_BASE}/meetings/{meeting_id}",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            return json.dumps({"success": True, "meeting_id": meeting_id})
        except Exception as e:
            return _handle_error("zoom_update_meeting", e)

    def list_meeting_participants(self, inp: dict) -> str:
        permission_error, meeting_id = self._check(self.agent_id, self.PROVIDER_ID, "zoom_list_meeting_participants", inp, "meeting_id")
        if permission_error: return permission_error
        try:
            params = {"page_size": inp.get("limit", 30)}
            if inp.get("next_page_token"):
                params["next_page_token"] = inp["next_page_token"]
            resp = httpx.get(
                f"{_BASE}/report/meetings/{meeting_id}/participants",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            participants = [
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "user_email": p.get("user_email"),
                    "join_time": p.get("join_time"),
                    "leave_time": p.get("leave_time"),
                    "duration": p.get("duration"),
                    "attentiveness_score": p.get("attentiveness_score"),
                }
                for p in (data.get("participants") or [])
            ]
            return json.dumps({
                "participants": participants,
                "count": len(participants),
                "total_records": data.get("total_records"),
                "next_page_token": data.get("next_page_token"),
            })
        except Exception as e:
            return _handle_error("zoom_list_meeting_participants", e)

    def get_recording_download_urls(self, inp: dict) -> str:
        permission_error, meeting_id = self._check(self.agent_id, self.PROVIDER_ID, "zoom_get_recording_download_urls", inp, "meeting_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/meetings/{meeting_id}/recordings",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            recording_files = [
                {
                    "id": f.get("id"),
                    "file_type": f.get("file_type"),
                    "download_url": f.get("download_url"),
                    "recording_start": f.get("recording_start"),
                    "recording_end": f.get("recording_end"),
                    "file_size": f.get("file_size"),
                    "status": f.get("status"),
                }
                for f in (data.get("recording_files") or [])
            ]
            return json.dumps({
                "meeting_id": data.get("id"),
                "topic": data.get("topic"),
                "start_time": data.get("start_time"),
                "recording_files": recording_files,
                "count": len(recording_files),
            })
        except Exception as e:
            return _handle_error("zoom_get_recording_download_urls", e)

    def add_meeting_registrant(self, inp: dict) -> str:
        permission_error, meeting_id, email, first_name = self._check(self.agent_id, self.PROVIDER_ID, "zoom_add_meeting_registrant", inp, "meeting_id", "email", "first_name")
        if permission_error: return permission_error
        try:
            body: dict = {"email": email, "first_name": first_name}
            if inp.get("last_name"):
                body["last_name"] = inp["last_name"]
            resp = httpx.post(
                f"{_BASE}/meetings/{meeting_id}/registrants",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            d = resp.json()
            return json.dumps({
                "registrant_id": d.get("registrant_id"),
                "id": d.get("id"),
                "join_url": d.get("join_url"),
                "topic": d.get("topic"),
            })
        except Exception as e:
            return _handle_error("zoom_add_meeting_registrant", e)

    def list_meeting_registrants(self, inp: dict) -> str:
        permission_error, meeting_id = self._check(self.agent_id, self.PROVIDER_ID, "zoom_list_meeting_registrants", inp, "meeting_id")
        if permission_error: return permission_error
        try:
            params = {"page_size": inp.get("page_size", 30), "status": inp.get("status", "approved")}
            if inp.get("next_page_token"):
                params["next_page_token"] = inp["next_page_token"]
            resp = httpx.get(
                f"{_BASE}/meetings/{meeting_id}/registrants",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            registrants = [
                {
                    "id": r.get("id"),
                    "email": r.get("email"),
                    "first_name": r.get("first_name"),
                    "last_name": r.get("last_name"),
                    "status": r.get("status"),
                    "create_time": r.get("create_time"),
                    "join_url": r.get("join_url"),
                }
                for r in (data.get("registrants") or [])
            ]
            return json.dumps({
                "registrants": registrants,
                "count": len(registrants),
                "total_records": data.get("total_records"),
                "next_page_token": data.get("next_page_token"),
            })
        except Exception as e:
            return _handle_error("zoom_list_meeting_registrants", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "zoom_get_current_user",
                    "description": "Get the profile of the currently authenticated Zoom user.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_list_meetings",
                    "description": "List scheduled or upcoming meetings for a Zoom user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "Zoom user ID or email. Defaults to 'me' for the authenticated user."},
                            "type": {"type": "string", "description": "Meeting type: scheduled, live, upcoming, upcoming_meetings, previous_meetings (default scheduled)."},
                            "page_size": {"type": "integer", "description": "Max meetings to return (default 30, max 300)."},
                            "next_page_token": {"type": "string", "description": "Token for pagination."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_get_meeting",
                    "description": "Get details of a specific Zoom meeting by its ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_id": {"type": "string", "description": "Zoom meeting ID (numeric or UUID)."},
                        },
                        "required": ["meeting_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_list_webinars",
                    "description": "List webinars for a Zoom user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "Zoom user ID or email. Defaults to 'me'."},
                            "page_size": {"type": "integer", "description": "Max webinars to return (default 30, max 300)."},
                            "next_page_token": {"type": "string", "description": "Token for pagination."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_list_recordings",
                    "description": "List cloud recordings for a Zoom user, optionally filtered by date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "Zoom user ID or email. Defaults to 'me'."},
                            "from_date": {"type": "string", "description": "Start date filter (YYYY-MM-DD)."},
                            "to_date": {"type": "string", "description": "End date filter (YYYY-MM-DD)."},
                            "page_size": {"type": "integer", "description": "Max recording meetings to return (default 30)."},
                            "next_page_token": {"type": "string", "description": "Token for pagination."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_get_meeting_report",
                    "description": "Get a meeting activity report for a Zoom user within a date range (requires report:read:admin scope).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "Zoom user ID or email. Defaults to 'me'."},
                            "from_date": {"type": "string", "description": "Report start date (YYYY-MM-DD). Required."},
                            "to_date": {"type": "string", "description": "Report end date (YYYY-MM-DD). Required. Max 1 month range."},
                            "page_size": {"type": "integer", "description": "Max meetings per page (default 30)."},
                            "next_page_token": {"type": "string", "description": "Token for pagination."},
                        },
                        "required": ["from_date", "to_date"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_list_users",
                    "description": "List all users in the Zoom account (requires admin scope).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by user status: active, inactive, pending (default active)."},
                            "page_size": {"type": "integer", "description": "Max users to return (default 30, max 300)."},
                            "next_page_token": {"type": "string", "description": "Token for pagination."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_create_meeting",
                    "description": "Create a new Zoom meeting for the authenticated user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string", "description": "Meeting topic/title. Required."},
                            "start_time": {"type": "string", "description": "Meeting start time in ISO 8601 format (e.g. '2024-01-15T10:00:00Z'). Required for scheduled meetings."},
                            "duration": {"type": "integer", "description": "Meeting duration in minutes (default 60)."},
                            "timezone": {"type": "string", "description": "Timezone for the meeting (default 'UTC')."},
                            "agenda": {"type": "string", "description": "Meeting agenda or description."},
                            "type": {"type": "integer", "description": "Meeting type: 1=instant, 2=scheduled (default 2)."},
                            "password": {"type": "string", "description": "Meeting password."},
                        },
                        "required": ["topic"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_delete_meeting",
                    "description": "Delete a Zoom meeting by its ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_id": {"type": "string", "description": "Zoom meeting ID to delete."},
                        },
                        "required": ["meeting_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_update_meeting",
                    "description": "Update an existing Zoom meeting's details (topic, time, duration, or agenda).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_id": {"type": "string", "description": "Zoom meeting ID to update. Required."},
                            "topic": {"type": "string", "description": "New meeting topic/title."},
                            "start_time": {"type": "string", "description": "New start time in ISO 8601 format."},
                            "duration": {"type": "integer", "description": "New duration in minutes."},
                            "agenda": {"type": "string", "description": "New meeting agenda or description."},
                        },
                        "required": ["meeting_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_list_meeting_participants",
                    "description": "List participants of a past Zoom meeting from the reports API.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_id": {"type": "string", "description": "Zoom meeting ID. Required."},
                            "limit": {"type": "integer", "description": "Max participants to return (default 30)."},
                            "next_page_token": {"type": "string", "description": "Token for pagination."},
                        },
                        "required": ["meeting_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_get_recording_download_urls",
                    "description": "Get download URLs for all recording files of a Zoom meeting.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_id": {"type": "string", "description": "Zoom meeting ID. Required."},
                        },
                        "required": ["meeting_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_add_meeting_registrant",
                    "description": "Register an attendee for a Zoom meeting that requires registration.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_id": {"type": "string", "description": "Zoom meeting ID. Required."},
                            "email": {"type": "string", "description": "Registrant's email address. Required."},
                            "first_name": {"type": "string", "description": "Registrant's first name. Required."},
                            "last_name": {"type": "string", "description": "Registrant's last name (optional)."},
                        },
                        "required": ["meeting_id", "email", "first_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_list_meeting_registrants",
                    "description": "List registrants for a Zoom meeting.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_id": {"type": "string", "description": "Zoom meeting ID. Required."},
                            "status": {"type": "string", "description": "Filter by registrant status: pending, approved, or denied (default approved)."},
                            "page_size": {"type": "integer", "description": "Max registrants to return (default 30, max 300)."},
                            "next_page_token": {"type": "string", "description": "Token for pagination."},
                        },
                        "required": ["meeting_id"],
                    },
                },
            },
        ]
        callables = {
            "zoom_get_current_user": self.get_current_user,
            "zoom_list_meetings": self.list_meetings,
            "zoom_get_meeting": self.get_meeting,
            "zoom_list_webinars": self.list_webinars,
            "zoom_list_recordings": self.list_recordings,
            "zoom_get_meeting_report": self.get_meeting_report,
            "zoom_list_users": self.list_users,
            "zoom_create_meeting": self.create_meeting,
            "zoom_delete_meeting": self.delete_meeting,
            "zoom_update_meeting": self.update_meeting,
            "zoom_list_meeting_participants": self.list_meeting_participants,
            "zoom_get_recording_download_urls": self.get_recording_download_urls,
            "zoom_add_meeting_registrant": self.add_meeting_registrant,
            "zoom_list_meeting_registrants": self.list_meeting_registrants,
        }
        return tools, callables

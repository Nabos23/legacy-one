import json
import uuid
from datetime import datetime, timezone
import httpx

from ai.connectors.base import BaseConnector

_MEET_BASE = "https://meet.googleapis.com/v2"
_CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:500]}"
            )
        if e.response.status_code == 404:
            return f"Not found in {tool_name} (HTTP 404): {e.response.text[:300]}"
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class GoogleMeetConnector(BaseConnector):
    """Google Meet connector for spaces, video conference scheduling, conference records, participants, recordings, and transcripts."""

    PROVIDER_ID = "google-meet"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id=agent_id)
        token_val = access_token if access_token.startswith("Bearer ") else f"Bearer {access_token}"
        self._auth_headers = {"Authorization": token_val, "Content-Type": "application/json"}

    # ── Spaces ────────────────────────────────────────────────────────────────

    def create_space(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "google_meet_create_space", inp)
        if permission_error:
            return permission_error
        try:
            config: dict = {}
            if inp.get("access_type"):
                config["accessType"] = inp["access_type"].upper()
            if inp.get("entry_point_access"):
                config["entryPointAccess"] = inp["entry_point_access"].upper()
            payload: dict = {}
            if config:
                payload["config"] = config
            resp = httpx.post(f"{_MEET_BASE}/spaces", headers=self._auth_headers, json=payload, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_meet_create_space", e)

    def get_space(self, inp: dict) -> str:
        permission_error, space_id = self._check(self.agent_id, self.PROVIDER_ID, "google_meet_get_space", inp, "space_id")
        if permission_error:
            return permission_error
        try:
            name = space_id if space_id.startswith("spaces/") else f"spaces/{space_id}"
            resp = httpx.get(f"{_MEET_BASE}/{name}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_meet_get_space", e)

    def update_space(self, inp: dict) -> str:
        permission_error, space_id = self._check(self.agent_id, self.PROVIDER_ID, "google_meet_update_space", inp, "space_id")
        if permission_error:
            return permission_error
        try:
            name = space_id if space_id.startswith("spaces/") else f"spaces/{space_id}"
            config: dict = {}
            if inp.get("access_type"):
                config["accessType"] = inp["access_type"].upper()
            if inp.get("entry_point_access"):
                config["entryPointAccess"] = inp["entry_point_access"].upper()
            payload = {"config": config}
            params = {"updateMask": "config.accessType,config.entryPointAccess"}
            resp = httpx.patch(f"{_MEET_BASE}/{name}", headers=self._auth_headers, json=payload, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_meet_update_space", e)

    def end_active_conference(self, inp: dict) -> str:
        permission_error, space_id = self._check(self.agent_id, self.PROVIDER_ID, "google_meet_end_active_conference", inp, "space_id")
        if permission_error:
            return permission_error
        try:
            name = space_id if space_id.startswith("spaces/") else f"spaces/{space_id}"
            resp = httpx.post(f"{_MEET_BASE}/{name}:endActiveConference", headers=self._auth_headers, json={}, timeout=15)
            resp.raise_for_status()
            return json.dumps({"status": "success", "message": f"Active conference ended for {name}."})
        except Exception as e:
            return _handle_error("google_meet_end_active_conference", e)

    # ── Scheduling ────────────────────────────────────────────────────────────

    def schedule_meeting(self, inp: dict) -> str:
        permission_error, summary, start_time, end_time = self._check(
            self.agent_id, self.PROVIDER_ID, "google_meet_schedule_meeting", inp, "summary", "start_time", "end_time"
        )
        if permission_error:
            return permission_error
        try:
            event: dict = {
                "summary": summary,
                "start": {"dateTime": start_time},
                "end": {"dateTime": end_time},
                "conferenceData": {
                    "createRequest": {
                        "requestId": f"meet_{uuid.uuid4().hex}",
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                },
            }
            if inp.get("description"):
                event["description"] = inp["description"]
            if inp.get("attendees"):
                emails = inp["attendees"] if isinstance(inp["attendees"], list) else [inp["attendees"]]
                event["attendees"] = [{"email": email} for email in emails]
            url = f"{_CALENDAR_BASE}/calendars/primary/events?conferenceDataVersion=1"
            resp = httpx.post(url, headers=self._auth_headers, json=event, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "id": data.get("id"),
                "summary": data.get("summary"),
                "hangoutLink": data.get("hangoutLink"),
                "meetLink": data.get("hangoutLink"),
                "htmlLink": data.get("htmlLink"),
                "start": data.get("start"),
                "end": data.get("end"),
                "attendees": [a.get("email") for a in data.get("attendees", [])],
            })
        except Exception as e:
            return _handle_error("google_meet_schedule_meeting", e)

    def list_scheduled_meetings(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "google_meet_list_scheduled_meetings", inp)
        if permission_error:
            return permission_error
        try:
            params: dict = {
                "singleEvents": "true",
                "orderBy": "startTime",
            }
            if inp.get("time_min"):
                params["timeMin"] = inp["time_min"]
            else:
                params["timeMin"] = datetime.now(timezone.utc).isoformat()
            if inp.get("time_max"):
                params["timeMax"] = inp["time_max"]
            if inp.get("max_results"):
                params["maxResults"] = inp["max_results"]

            url = f"{_CALENDAR_BASE}/calendars/primary/events"
            resp = httpx.get(url, headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            events = []
            for item in data.get("items", []):
                meet_link = item.get("hangoutLink") or item.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri")
                if meet_link:
                    events.append({
                        "id": item.get("id"),
                        "summary": item.get("summary"),
                        "description": item.get("description"),
                        "start": item.get("start"),
                        "end": item.get("end"),
                        "meetLink": meet_link,
                        "htmlLink": item.get("htmlLink"),
                        "attendees": [a.get("email") for a in item.get("attendees", []) if a.get("email")],
                    })
            return json.dumps({"meetings": events, "count": len(events)})
        except Exception as e:
            return _handle_error("google_meet_list_scheduled_meetings", e)

    # ── Conference Records ────────────────────────────────────────────────────

    def list_conference_records(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "google_meet_list_conference_records", inp)
        if permission_error:
            return permission_error
        try:
            params: dict = {}
            if inp.get("page_size"):
                params["pageSize"] = inp["page_size"]
            if inp.get("page_token"):
                params["pageToken"] = inp["page_token"]
            if inp.get("filter"):
                params["filter"] = inp["filter"]
            resp = httpx.get(f"{_MEET_BASE}/conferenceRecords", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_meet_list_conference_records", e)

    def get_conference_record(self, inp: dict) -> str:
        permission_error, record_id = self._check(self.agent_id, self.PROVIDER_ID, "google_meet_get_conference_record", inp, "record_id")
        if permission_error:
            return permission_error
        try:
            name = record_id if record_id.startswith("conferenceRecords/") else f"conferenceRecords/{record_id}"
            resp = httpx.get(f"{_MEET_BASE}/{name}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_meet_get_conference_record", e)

    # ── Participants ──────────────────────────────────────────────────────────

    def list_participants(self, inp: dict) -> str:
        permission_error, record_id = self._check(self.agent_id, self.PROVIDER_ID, "google_meet_list_participants", inp, "record_id")
        if permission_error:
            return permission_error
        try:
            name = record_id if record_id.startswith("conferenceRecords/") else f"conferenceRecords/{record_id}"
            params: dict = {}
            if inp.get("page_size"):
                params["pageSize"] = inp["page_size"]
            if inp.get("page_token"):
                params["pageToken"] = inp["page_token"]
            resp = httpx.get(f"{_MEET_BASE}/{name}/participants", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_meet_list_participants", e)

    def get_participant(self, inp: dict) -> str:
        permission_error, record_id, participant_id = self._check(
            self.agent_id, self.PROVIDER_ID, "google_meet_get_participant", inp, "record_id", "participant_id"
        )
        if permission_error:
            return permission_error
        try:
            name = f"conferenceRecords/{record_id}/participants/{participant_id}" if not participant_id.startswith("conferenceRecords/") else participant_id
            resp = httpx.get(f"{_MEET_BASE}/{name}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_meet_get_participant", e)

    # ── Recordings & Transcripts ──────────────────────────────────────────────

    def list_recordings(self, inp: dict) -> str:
        permission_error, record_id = self._check(self.agent_id, self.PROVIDER_ID, "google_meet_list_recordings", inp, "record_id")
        if permission_error:
            return permission_error
        try:
            name = record_id if record_id.startswith("conferenceRecords/") else f"conferenceRecords/{record_id}"
            resp = httpx.get(f"{_MEET_BASE}/{name}/recordings", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_meet_list_recordings", e)

    def get_recording(self, inp: dict) -> str:
        permission_error, record_id, recording_id = self._check(
            self.agent_id, self.PROVIDER_ID, "google_meet_get_recording", inp, "record_id", "recording_id"
        )
        if permission_error:
            return permission_error
        try:
            name = f"conferenceRecords/{record_id}/recordings/{recording_id}" if not recording_id.startswith("conferenceRecords/") else recording_id
            resp = httpx.get(f"{_MEET_BASE}/{name}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_meet_get_recording", e)

    def list_transcripts(self, inp: dict) -> str:
        permission_error, record_id = self._check(self.agent_id, self.PROVIDER_ID, "google_meet_list_transcripts", inp, "record_id")
        if permission_error:
            return permission_error
        try:
            name = record_id if record_id.startswith("conferenceRecords/") else f"conferenceRecords/{record_id}"
            resp = httpx.get(f"{_MEET_BASE}/{name}/transcripts", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_meet_list_transcripts", e)

    def get_transcript(self, inp: dict) -> str:
        permission_error, record_id, transcript_id = self._check(
            self.agent_id, self.PROVIDER_ID, "google_meet_get_transcript", inp, "record_id", "transcript_id"
        )
        if permission_error:
            return permission_error
        try:
            name = f"conferenceRecords/{record_id}/transcripts/{transcript_id}" if not transcript_id.startswith("conferenceRecords/") else transcript_id
            resp = httpx.get(f"{_MEET_BASE}/{name}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("google_meet_get_transcript", e)

    # ── OpenAI Tools Definition ───────────────────────────────────────────────

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "google_meet_create_space",
                    "description": "Create a new Google Meet virtual space.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "access_type": {"type": "string", "description": "Access type: OPEN, TRUSTED, RESTRICTED."},
                            "entry_point_access": {"type": "string", "description": "Entry point access: ALL, CREATOR_APP_ONLY."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_meet_get_space",
                    "description": "Get detailed info and meeting URI for a Google Meet space.",
                    "parameters": {
                        "type": "object",
                        "properties": {"space_id": {"type": "string", "description": "Space ID or name (e.g. spaces/xyz or xyz)."}},
                        "required": ["space_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_meet_update_space",
                    "description": "Update configuration/access rules for a Google Meet space.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "space_id": {"type": "string", "description": "Space ID."},
                            "access_type": {"type": "string", "description": "New access type: OPEN, TRUSTED, RESTRICTED."},
                            "entry_point_access": {"type": "string", "description": "New entry point access: ALL, CREATOR_APP_ONLY."},
                        },
                        "required": ["space_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_meet_end_active_conference",
                    "description": "End the active call/conference within a Google Meet space.",
                    "parameters": {
                        "type": "object",
                        "properties": {"space_id": {"type": "string", "description": "Space ID."}},
                        "required": ["space_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_meet_schedule_meeting",
                    "description": "Schedule a meeting with an automated Google Meet video link.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string", "description": "Meeting title."},
                            "start_time": {"type": "string", "description": "Start time in ISO format (e.g. 2026-08-15T10:00:00Z)."},
                            "end_time": {"type": "string", "description": "End time in ISO format (e.g. 2026-08-15T10:30:00Z)."},
                            "description": {"type": "string", "description": "Optional meeting description/agenda."},
                            "attendees": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of attendee email addresses.",
                            },
                        },
                        "required": ["summary", "start_time", "end_time"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_meet_list_conference_records",
                    "description": "List past completed conference records in Google Meet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_size": {"type": "integer", "description": "Max items to return."},
                            "filter": {"type": "string", "description": "Filter string (e.g. space.name=\"spaces/xyz\")."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_meet_get_conference_record",
                    "description": "Get detailed info for a completed conference record.",
                    "parameters": {
                        "type": "object",
                        "properties": {"record_id": {"type": "string", "description": "Conference record ID."}},
                        "required": ["record_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_meet_list_participants",
                    "description": "List participants who attended a completed Google Meet conference.",
                    "parameters": {
                        "type": "object",
                        "properties": {"record_id": {"type": "string", "description": "Conference record ID."}},
                        "required": ["record_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_meet_get_participant",
                    "description": "Get participant details for a completed meeting.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "record_id": {"type": "string", "description": "Conference record ID."},
                            "participant_id": {"type": "string", "description": "Participant ID."},
                        },
                        "required": ["record_id", "participant_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_meet_list_recordings",
                    "description": "List video recordings associated with a completed meeting.",
                    "parameters": {
                        "type": "object",
                        "properties": {"record_id": {"type": "string", "description": "Conference record ID."}},
                        "required": ["record_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_meet_get_recording",
                    "description": "Get recording metadata and Drive link.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "record_id": {"type": "string", "description": "Conference record ID."},
                            "recording_id": {"type": "string", "description": "Recording ID."},
                        },
                        "required": ["record_id", "recording_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_meet_list_transcripts",
                    "description": "List meeting transcripts for a completed meeting.",
                    "parameters": {
                        "type": "object",
                        "properties": {"record_id": {"type": "string", "description": "Conference record ID."}},
                        "required": ["record_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_meet_list_scheduled_meetings",
                    "description": "List upcoming scheduled Google Meet meetings for the user.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "time_min": {"type": "string", "description": "ISO start time filter (default: now)."},
                            "time_max": {"type": "string", "description": "Optional ISO end time filter."},
                            "max_results": {"type": "integer", "description": "Max items to return (default: 250)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "google_meet_get_transcript",
                    "description": "Get transcript details and Drive file reference.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "record_id": {"type": "string", "description": "Conference record ID."},
                            "transcript_id": {"type": "string", "description": "Transcript ID."},
                        },
                        "required": ["record_id", "transcript_id"],
                    },
                },
            },
        ]
        callables = {
            "google_meet_create_space": self.create_space,
            "google_meet_get_space": self.get_space,
            "google_meet_update_space": self.update_space,
            "google_meet_end_active_conference": self.end_active_conference,
            "google_meet_schedule_meeting": self.schedule_meeting,
            "google_meet_list_scheduled_meetings": self.list_scheduled_meetings,
            "google_meet_list_conference_records": self.list_conference_records,
            "google_meet_get_conference_record": self.get_conference_record,
            "google_meet_list_participants": self.list_participants,
            "google_meet_get_participant": self.get_participant,
            "google_meet_list_recordings": self.list_recordings,
            "google_meet_get_recording": self.get_recording,
            "google_meet_list_transcripts": self.list_transcripts,
            "google_meet_get_transcript": self.get_transcript,
        }
        return tools, callables

import json
from base64 import b64encode

import httpx

from ai.connectors.base import BaseConnector


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the Twilio credentials are invalid "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their Twilio connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class TwilioConnector(BaseConnector):
    """
    Twilio connector.
    access_token format: "ACCOUNT_SID:AUTH_TOKEN"
    """

    PROVIDER_ID = "twilio"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id=agent_id)
        parts = access_token.split(":", 1)
        self._token = access_token
        self._account_sid = parts[0]
        self._auth_token = parts[1] if len(parts) > 1 else ""
        creds = b64encode(f"{self._account_sid}:{self._auth_token}".encode()).decode()
        self._headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded"}
        self._base = f"https://api.twilio.com/2010-04-01/Accounts/{self._account_sid}"

    @property
    def _auth_headers(self) -> dict:
        return self._headers

    @_auth_headers.setter
    def _auth_headers(self, value: dict) -> None:
        self._headers = value

    def send_sms(self, inp: dict) -> str:
        permission_error, to, from_, body = self._check(self.agent_id, self.PROVIDER_ID, "twilio_send_sms", inp, "to", "from_", "body")
        if permission_error: return permission_error
        try:
            data = {"To": to, "From": from_, "Body": body}
            resp = httpx.post(f"{self._base}/Messages.json", headers=self._auth_headers, data=data, timeout=15)
            resp.raise_for_status()
            msg = resp.json()
            return json.dumps({"sid": msg["sid"], "status": msg["status"], "to": msg["to"], "from": msg["from"]})
        except Exception as e:
            return _handle_error("twilio_send_sms", e)

    def list_messages(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "twilio_list_messages", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"PageSize": inp.get("limit", 20)}
            if inp.get("to"):
                params["To"] = inp["to"]
            if inp.get("from_"):
                params["From"] = inp["from_"]
            resp = httpx.get(f"{self._base}/Messages.json", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            messages = [
                {
                    "sid": m["sid"],
                    "from": m["from"],
                    "to": m["to"],
                    "body": m["body"],
                    "status": m["status"],
                    "direction": m["direction"],
                    "date_created": m.get("date_created"),
                }
                for m in data.get("messages", [])
            ]
            return json.dumps({"messages": messages, "count": len(messages)})
        except Exception as e:
            return _handle_error("twilio_list_messages", e)

    def get_message(self, inp: dict) -> str:
        permission_error, sid = self._check(self.agent_id, self.PROVIDER_ID, "twilio_get_message", inp, "sid")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/Messages/{sid}.json", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            m = resp.json()
            return json.dumps({
                "sid": m["sid"],
                "from": m["from"],
                "to": m["to"],
                "body": m["body"],
                "status": m["status"],
                "direction": m["direction"],
                "price": m.get("price"),
                "date_created": m.get("date_created"),
                "date_sent": m.get("date_sent"),
            })
        except Exception as e:
            return _handle_error("twilio_get_message", e)

    def list_phone_numbers(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "twilio_list_phone_numbers", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/IncomingPhoneNumbers.json", headers=self._auth_headers, params={"PageSize": inp.get("limit", 20)}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            numbers = [
                {"sid": n["sid"], "phone_number": n["phone_number"], "friendly_name": n.get("friendly_name"), "capabilities": n.get("capabilities")}
                for n in data.get("incoming_phone_numbers", [])
            ]
            return json.dumps({"phone_numbers": numbers, "count": len(numbers)})
        except Exception as e:
            return _handle_error("twilio_list_phone_numbers", e)

    def get_account_info(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "twilio_get_account_info", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"https://api.twilio.com/2010-04-01/Accounts/{self._account_sid}.json", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            a = resp.json()
            return json.dumps({
                "sid": a["sid"],
                "friendly_name": a.get("friendly_name"),
                "status": a.get("status"),
                "type": a.get("type"),
                "date_created": a.get("date_created"),
            })
        except Exception as e:
            return _handle_error("twilio_get_account_info", e)

    def make_call(self, inp: dict) -> str:
        permission_error, to, from_, twiml_url = self._check(self.agent_id, self.PROVIDER_ID, "twilio_make_call", inp, "to", "from_", "twiml_url")
        if permission_error: return permission_error
        try:
            data = {"To": to, "From": from_, "Url": twiml_url}
            resp = httpx.post(f"{self._base}/Calls.json", headers=self._auth_headers, data=data, timeout=15)
            resp.raise_for_status()
            call = resp.json()
            return json.dumps({"sid": call["sid"], "status": call["status"], "to": call["to"], "from": call["from"]})
        except Exception as e:
            return _handle_error("twilio_make_call", e)

    def list_calls(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "twilio_list_calls", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"PageSize": inp.get("limit", 20)}
            if inp.get("status"):
                params["Status"] = inp["status"]
            resp = httpx.get(f"{self._base}/Calls.json", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            calls = [
                {
                    "sid": c["sid"],
                    "from": c["from"],
                    "to": c["to"],
                    "status": c["status"],
                    "start_time": c.get("start_time"),
                    "end_time": c.get("end_time"),
                    "duration": c.get("duration"),
                    "direction": c.get("direction"),
                }
                for c in data.get("calls", [])
            ]
            return json.dumps({"calls": calls, "count": len(calls)})
        except Exception as e:
            return _handle_error("twilio_list_calls", e)

    def get_call(self, inp: dict) -> str:
        permission_error, call_sid = self._check(self.agent_id, self.PROVIDER_ID, "twilio_get_call", inp, "call_sid")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{self._base}/Calls/{call_sid}.json", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            c = resp.json()
            return json.dumps({
                "sid": c["sid"],
                "from": c["from"],
                "to": c["to"],
                "status": c["status"],
                "start_time": c.get("start_time"),
                "end_time": c.get("end_time"),
                "duration": c.get("duration"),
                "direction": c.get("direction"),
                "price": c.get("price"),
                "answered_by": c.get("answered_by"),
            })
        except Exception as e:
            return _handle_error("twilio_get_call", e)

    def send_mms(self, inp: dict) -> str:
        permission_error, to, from_, media_url = self._check(self.agent_id, self.PROVIDER_ID, "twilio_send_mms", inp, "to", "from_", "media_url")
        if permission_error: return permission_error
        try:
            data: dict = {"To": to, "From": from_, "MediaUrl": media_url}
            if inp.get("body"):
                data["Body"] = inp["body"]
            resp = httpx.post(f"{self._base}/Messages.json", headers=self._auth_headers, data=data, timeout=15)
            resp.raise_for_status()
            msg = resp.json()
            return json.dumps({"sid": msg["sid"], "status": msg["status"], "to": msg["to"], "from": msg["from"]})
        except Exception as e:
            return _handle_error("twilio_send_mms", e)

    def lookup_phone_number(self, inp: dict) -> str:
        permission_error, phone_number = self._check(self.agent_id, self.PROVIDER_ID, "twilio_lookup_phone_number", inp, "phone_number")
        if permission_error: return permission_error
        try:
            lookup_headers = {
                "Authorization": self._auth_headers["Authorization"],
                "Accept": "application/json",
            }
            resp = httpx.get(
                f"https://lookups.twilio.com/v2/PhoneNumbers/{phone_number}",
                headers=lookup_headers,
                params={"Fields": "line_type_intelligence"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            result: dict = {
                "phone_number": data.get("phone_number"),
                "country_code": data.get("country_code"),
            }
            lti = data.get("line_type_intelligence")
            if lti:
                result["line_type_intelligence"] = {"type": lti.get("type")}
            return json.dumps(result)
        except Exception as e:
            return _handle_error("twilio_lookup_phone_number", e)

    def cancel_message(self, inp: dict) -> str:
        permission_error, message_sid = self._check(self.agent_id, self.PROVIDER_ID, "twilio_cancel_message", inp, "message_sid")
        if permission_error: return permission_error
        try:
            data = {"Status": "canceled"}
            resp = httpx.post(f"{self._base}/Messages/{message_sid}.json", headers=self._auth_headers, data=data, timeout=15)
            resp.raise_for_status()
            msg = resp.json()
            return json.dumps({"sid": msg["sid"], "status": msg["status"]})
        except Exception as e:
            return _handle_error("twilio_cancel_message", e)

    def send_whatsapp_message(self, inp: dict) -> str:
        permission_error, to, from_, body = self._check(self.agent_id, self.PROVIDER_ID, "twilio_send_whatsapp_message", inp, "to", "from_", "body")
        if permission_error: return permission_error
        try:
            to_wa = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
            from_wa = from_ if from_.startswith("whatsapp:") else f"whatsapp:{from_}"
            data = {"To": to_wa, "From": from_wa, "Body": body}
            resp = httpx.post(f"{self._base}/Messages.json", headers=self._auth_headers, data=data, timeout=15)
            resp.raise_for_status()
            msg = resp.json()
            return json.dumps({"sid": msg["sid"], "status": msg["status"], "to": msg["to"], "from": msg["from"]})
        except Exception as e:
            return _handle_error("twilio_send_whatsapp_message", e)

    def end_call(self, inp: dict) -> str:
        permission_error, call_sid = self._check(self.agent_id, self.PROVIDER_ID, "twilio_end_call", inp, "call_sid")
        if permission_error: return permission_error
        try:
            data = {"Status": "completed"}
            resp = httpx.post(f"{self._base}/Calls/{call_sid}.json", headers=self._auth_headers, data=data, timeout=15)
            resp.raise_for_status()
            c = resp.json()
            return json.dumps({"sid": c["sid"], "status": c["status"]})
        except Exception as e:
            return _handle_error("twilio_end_call", e)

    def list_recordings(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "twilio_list_recordings", inp)
        if permission_error: return permission_error
        try:
            params: dict = {"PageSize": inp.get("limit", 20)}
            if inp.get("call_sid"):
                params["CallSid"] = inp["call_sid"]
            resp = httpx.get(f"{self._base}/Recordings.json", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            recordings = [
                {
                    "sid": r["sid"],
                    "call_sid": r.get("call_sid"),
                    "status": r.get("status"),
                    "duration": r.get("duration"),
                    "date_created": r.get("date_created"),
                    "media_url": f"https://api.twilio.com{r['uri'].replace('.json', '')}.mp3" if r.get("uri") else None,
                }
                for r in data.get("recordings", [])
            ]
            return json.dumps({"recordings": recordings, "count": len(recordings)})
        except Exception as e:
            return _handle_error("twilio_list_recordings", e)

    def get_usage_records(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "twilio_get_usage_records", inp)
        if permission_error: return permission_error
        try:
            params: dict = {}
            category = inp.get("category", "")
            if category:
                params["Category"] = category
            time_period = inp.get("time_period", "")
            if time_period:
                params["StartDate"] = time_period
            resp = httpx.get(
                f"{self._base}/Usage/Records.json",
                headers=self._auth_headers,
                params={**params, "PageSize": inp.get("limit", 20)},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            records = [
                {
                    "category": r.get("category"),
                    "description": r.get("description"),
                    "count": r.get("count"),
                    "usage": r.get("usage"),
                    "usage_unit": r.get("usage_unit"),
                    "price": r.get("price"),
                    "price_unit": r.get("price_unit"),
                    "start_date": r.get("start_date"),
                    "end_date": r.get("end_date"),
                }
                for r in data.get("usage_records", [])
            ]
            return json.dumps({"usage_records": records, "count": len(records)})
        except Exception as e:
            return _handle_error("twilio_get_usage_records", e)

    def verify_send_code(self, inp: dict) -> str:
        permission_error, verify_service_sid, to = self._check(self.agent_id, self.PROVIDER_ID, "twilio_verify_send_code", inp, "verify_service_sid", "to")
        if permission_error: return permission_error
        try:
            data = {"To": to, "Channel": inp.get("channel", "sms")}
            resp = httpx.post(
                f"https://verify.twilio.com/v2/Services/{verify_service_sid}/Verifications",
                headers=self._auth_headers,
                data=data,
                timeout=15,
            )
            resp.raise_for_status()
            v = resp.json()
            return json.dumps({"sid": v["sid"], "to": v.get("to"), "channel": v.get("channel"), "status": v.get("status")})
        except Exception as e:
            return _handle_error("twilio_verify_send_code", e)

    def verify_check_code(self, inp: dict) -> str:
        permission_error, verify_service_sid, to, code = self._check(self.agent_id, self.PROVIDER_ID, "twilio_verify_check_code", inp, "verify_service_sid", "to", "code")
        if permission_error: return permission_error
        try:
            data = {"To": to, "Code": code}
            resp = httpx.post(
                f"https://verify.twilio.com/v2/Services/{verify_service_sid}/VerificationCheck",
                headers=self._auth_headers,
                data=data,
                timeout=15,
            )
            resp.raise_for_status()
            v = resp.json()
            return json.dumps({"sid": v["sid"], "to": v.get("to"), "status": v.get("status"), "valid": v.get("valid")})
        except Exception as e:
            return _handle_error("twilio_verify_check_code", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "twilio_send_sms",
                    "description": "Send an SMS text message via Twilio.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient phone number in E.164 format (e.g. '+14155552671')."},
                            "from_": {"type": "string", "description": "Your Twilio phone number in E.164 format."},
                            "body": {"type": "string", "description": "SMS message body."},
                        },
                        "required": ["to", "from_", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_list_messages",
                    "description": "List recent SMS messages sent/received via Twilio.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Filter by recipient phone number."},
                            "from_": {"type": "string", "description": "Filter by sender phone number."},
                            "limit": {"type": "integer", "description": "Max messages to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_get_message",
                    "description": "Get details of a specific Twilio SMS message.",
                    "parameters": {
                        "type": "object",
                        "properties": {"sid": {"type": "string", "description": "Message SID (starts with 'SM')."}},
                        "required": ["sid"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_list_phone_numbers",
                    "description": "List Twilio phone numbers in the account.",
                    "parameters": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "description": "Max numbers to return (default 20)."}},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_get_account_info",
                    "description": "Get information about the Twilio account.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_make_call",
                    "description": "Initiate an outbound phone call via Twilio using a TwiML URL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient phone number in E.164 format."},
                            "from_": {"type": "string", "description": "Your Twilio phone number in E.164 format."},
                            "twiml_url": {"type": "string", "description": "URL that returns TwiML instructions for the call."},
                        },
                        "required": ["to", "from_", "twiml_url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_list_calls",
                    "description": "List recent phone calls in the Twilio account.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max calls to return (default 20)."},
                            "status": {"type": "string", "description": "Filter by call status: queued, ringing, in-progress, completed, failed, busy, no-answer."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_get_call",
                    "description": "Get details of a specific Twilio phone call.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "call_sid": {"type": "string", "description": "The SID of the call to retrieve (starts with 'CA')."},
                        },
                        "required": ["call_sid"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_send_mms",
                    "description": "Send an MMS (multimedia message) with a media attachment via Twilio.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient phone number in E.164 format (e.g. '+14155552671')."},
                            "from_": {"type": "string", "description": "Your Twilio phone number in E.164 format."},
                            "media_url": {"type": "string", "description": "Publicly accessible URL of the media to send (image, video, etc.)."},
                            "body": {"type": "string", "description": "Optional text body to accompany the media."},
                        },
                        "required": ["to", "from_", "media_url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_lookup_phone_number",
                    "description": "Look up information about a phone number, including whether it is mobile, landline, or VoIP.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "phone_number": {"type": "string", "description": "Phone number to look up in E.164 format (e.g. '+15551234567')."},
                        },
                        "required": ["phone_number"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_cancel_message",
                    "description": "Cancel a queued Twilio SMS/MMS message before it is sent.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message_sid": {"type": "string", "description": "The SID of the message to cancel (starts with 'SM')."},
                        },
                        "required": ["message_sid"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_send_whatsapp_message",
                    "description": "Send a WhatsApp message via Twilio (requires a WhatsApp-enabled Twilio sender number).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient phone number in E.164 format (e.g. '+14155552671'); 'whatsapp:' prefix optional, added automatically."},
                            "from_": {"type": "string", "description": "Your WhatsApp-enabled Twilio number in E.164 format; 'whatsapp:' prefix optional, added automatically."},
                            "body": {"type": "string", "description": "Message body text."},
                        },
                        "required": ["to", "from_", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_end_call",
                    "description": "Hang up / terminate an in-progress or ringing Twilio phone call.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "call_sid": {"type": "string", "description": "The SID of the call to end (starts with 'CA')."},
                        },
                        "required": ["call_sid"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_list_recordings",
                    "description": "List call recordings in the Twilio account, optionally filtered by call.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "call_sid": {"type": "string", "description": "Filter recordings by call SID."},
                            "limit": {"type": "integer", "description": "Max recordings to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_get_usage_records",
                    "description": "Get Twilio account usage/billing records (e.g. SMS, calls, cost) for reporting and cost monitoring.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "description": "Usage category to filter by (e.g. 'sms', 'calls', 'calls-inbound')."},
                            "time_period": {"type": "string", "description": "Start date filter in YYYY-MM-DD format."},
                            "limit": {"type": "integer", "description": "Max records to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_verify_send_code",
                    "description": "Send a one-time passcode (OTP) via SMS, call, or email using a Twilio Verify Service.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "verify_service_sid": {"type": "string", "description": "The Twilio Verify Service SID (starts with 'VA')."},
                            "to": {"type": "string", "description": "Phone number in E.164 format or email address to send the code to."},
                            "channel": {"type": "string", "description": "Delivery channel: 'sms', 'call', 'email', or 'whatsapp' (default 'sms')."},
                        },
                        "required": ["verify_service_sid", "to"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "twilio_verify_check_code",
                    "description": "Check/validate a one-time passcode (OTP) the user entered, using a Twilio Verify Service.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "verify_service_sid": {"type": "string", "description": "The Twilio Verify Service SID (starts with 'VA')."},
                            "to": {"type": "string", "description": "Phone number or email the code was sent to."},
                            "code": {"type": "string", "description": "The OTP code entered by the user."},
                        },
                        "required": ["verify_service_sid", "to", "code"],
                    },
                },
            },
        ]
        callables = {
            "twilio_send_sms": self.send_sms,
            "twilio_list_messages": self.list_messages,
            "twilio_get_message": self.get_message,
            "twilio_list_phone_numbers": self.list_phone_numbers,
            "twilio_get_account_info": self.get_account_info,
            "twilio_make_call": self.make_call,
            "twilio_list_calls": self.list_calls,
            "twilio_get_call": self.get_call,
            "twilio_send_mms": self.send_mms,
            "twilio_lookup_phone_number": self.lookup_phone_number,
            "twilio_cancel_message": self.cancel_message,
            "twilio_send_whatsapp_message": self.send_whatsapp_message,
            "twilio_end_call": self.end_call,
            "twilio_list_recordings": self.list_recordings,
            "twilio_get_usage_records": self.get_usage_records,
            "twilio_verify_send_code": self.verify_send_code,
            "twilio_verify_check_code": self.verify_check_code,
        }
        return tools, callables

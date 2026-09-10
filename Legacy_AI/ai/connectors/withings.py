import json
import hashlib
import hmac
import time
import uuid
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://wbsapi.withings.net"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector (HTTP {e.response.status_code})."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


def _check_status(tool_name: str, data: dict) -> str | None:
    status = data.get("status")
    if status != 0:
        return f"Withings API error in {tool_name}: status={status}, error={data.get('error', 'unknown')}"
    return None


class WithingsConnector(BaseConnector):
    """Withings health data connector for body measurements, activity, sleep, and devices."""

    PROVIDER_ID = "withings"

    def get_body_measurements(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "withings_get_body_measurements", inp)
        if permission_error: return permission_error
        meastype = inp.get("meastype")
        params = {
            "action": "getmeas",
            "access_token": self._token,
        }
        if meastype:
            params["meastype"] = meastype
        if inp.get("startdate"):
            params["startdate"] = inp["startdate"]
        if inp.get("enddate"):
            params["enddate"] = inp["enddate"]
        if inp.get("lastupdate"):
            params["lastupdate"] = inp["lastupdate"]
        try:
            resp = httpx.post(f"{_BASE}/measure", data=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            err = _check_status("withings_get_body_measurements", data)
            if err:
                return err
            body = data.get("body", {})
            groups = []
            for g in body.get("measuregrps", []):
                measures = []
                for m in g.get("measures", []):
                    value = m["value"] * (10 ** m["unit"])
                    mtype = m["type"]
                    type_labels = {
                        1: "weight_kg", 4: "height_m", 5: "lean_mass_kg", 6: "fat_ratio_pct",
                        8: "fat_mass_weight_kg", 9: "diastolic_bp_mmhg", 10: "systolic_bp_mmhg",
                        11: "pulse_bpm", 76: "muscle_mass_kg", 77: "hydration_kg", 88: "bone_mass_kg",
                        226: "spo2_pct",
                    }
                    measures.append({"type": type_labels.get(mtype, f"type_{mtype}"), "value": round(value, 4)})
                groups.append({"date": g.get("date"), "measures": measures})
            return json.dumps({"measuregrps": groups, "updatetime": body.get("updatetime")})
        except Exception as e:
            return _handle_error("withings_get_body_measurements", e)

    def get_daily_activity(self, inp: dict) -> str:
        permission_error, startdateymd, enddateymd = self._check(self.agent_id, self.PROVIDER_ID, "withings_get_daily_activity", inp, "startdateymd", "enddateymd")
        if permission_error: return permission_error
        params = {
            "action": "getactivity",
            "access_token": self._token,
            "startdateymd": startdateymd,
            "enddateymd": enddateymd,
        }
        try:
            resp = httpx.post(f"{_BASE}/v2/measure", data=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            err = _check_status("withings_get_daily_activity", data)
            if err:
                return err
            body = data.get("body", {})
            activities = [
                {
                    "date": a.get("date"),
                    "steps": a.get("steps"),
                    "distance_m": a.get("distance"),
                    "calories": a.get("calories"),
                    "active_calories": a.get("active"),
                    "elevation_m": a.get("elevation"),
                    "soft_activity_min": a.get("soft"),
                    "moderate_activity_min": a.get("moderate"),
                    "intense_activity_min": a.get("intense"),
                    "hr_average_bpm": a.get("hr_average"),
                    "hr_min_bpm": a.get("hr_min"),
                    "hr_max_bpm": a.get("hr_max"),
                }
                for a in body.get("activities", [])
            ]
            return json.dumps({"activities": activities, "more": body.get("more"), "offset": body.get("offset")})
        except Exception as e:
            return _handle_error("withings_get_daily_activity", e)

    def get_intraday_activity(self, inp: dict) -> str:
        permission_error, startdate, enddate = self._check(self.agent_id, self.PROVIDER_ID, "withings_get_intraday_activity", inp, "startdate", "enddate")
        if permission_error: return permission_error
        params = {
            "action": "getintradayactivity",
            "access_token": self._token,
            "startdate": startdate,
            "enddate": enddate,
        }
        if inp.get("data_fields"):
            params["data_fields"] = inp["data_fields"]
        try:
            resp = httpx.post(f"{_BASE}/v2/measure", data=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            err = _check_status("withings_get_intraday_activity", data)
            if err:
                return err
            body = data.get("body", {})
            series = body.get("series", {})
            result = []
            for ts, entry in series.items():
                row = {"timestamp": int(ts)}
                row.update(entry)
                result.append(row)
            result.sort(key=lambda x: x["timestamp"])
            return json.dumps({"series": result})
        except Exception as e:
            return _handle_error("withings_get_intraday_activity", e)

    def get_sleep_summary(self, inp: dict) -> str:
        permission_error, startdateymd, enddateymd = self._check(self.agent_id, self.PROVIDER_ID, "withings_get_sleep_summary", inp, "startdateymd", "enddateymd")
        if permission_error: return permission_error
        params = {
            "action": "getsummary",
            "access_token": self._token,
            "startdateymd": startdateymd,
            "enddateymd": enddateymd,
        }
        try:
            resp = httpx.post(f"{_BASE}/v2/sleep", data=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            err = _check_status("withings_get_sleep_summary", data)
            if err:
                return err
            body = data.get("body", {})
            series = [
                {
                    "date": s.get("date"),
                    "startdate": s.get("startdate"),
                    "enddate": s.get("enddate"),
                    "total_sleep_time_s": s.get("data", {}).get("total_sleep_time"),
                    "total_timeinbed_s": s.get("data", {}).get("total_timeinbed"),
                    "sleep_efficiency_pct": s.get("data", {}).get("sleep_efficiency"),
                    "sleep_latency_s": s.get("data", {}).get("sleep_latency"),
                    "wakeup_latency_s": s.get("data", {}).get("wakeup_latency"),
                    "waso_s": s.get("data", {}).get("waso"),
                    "nb_rem_episodes": s.get("data", {}).get("nb_rem_episodes"),
                    "light_sleep_s": s.get("data", {}).get("lightsleepduration"),
                    "deep_sleep_s": s.get("data", {}).get("deepsleepduration"),
                    "rem_sleep_s": s.get("data", {}).get("remsleepduration"),
                    "hr_average_bpm": s.get("data", {}).get("hr_average"),
                    "rr_average_brpm": s.get("data", {}).get("rr_average"),
                    "breathing_disturbances_intensity": s.get("data", {}).get("breathing_disturbances_intensity"),
                }
                for s in body.get("series", [])
            ]
            return json.dumps({"series": series, "more": body.get("more"), "offset": body.get("offset")})
        except Exception as e:
            return _handle_error("withings_get_sleep_summary", e)

    def get_sleep_data(self, inp: dict) -> str:
        permission_error, startdate, enddate = self._check(self.agent_id, self.PROVIDER_ID, "withings_get_sleep_data", inp, "startdate", "enddate")
        if permission_error: return permission_error
        params = {
            "action": "get",
            "access_token": self._token,
            "startdate": startdate,
            "enddate": enddate,
        }
        try:
            resp = httpx.post(f"{_BASE}/v2/sleep", data=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            err = _check_status("withings_get_sleep_data", data)
            if err:
                return err
            body = data.get("body", {})
            state_labels = {0: "awake", 1: "light", 2: "deep", 3: "rem"}
            series = [
                {
                    "startdate": s.get("startdate"),
                    "enddate": s.get("enddate"),
                    "state": state_labels.get(s.get("state"), f"state_{s.get('state')}"),
                }
                for s in body.get("series", [])
            ]
            return json.dumps({"model": body.get("model"), "series": series})
        except Exception as e:
            return _handle_error("withings_get_sleep_data", e)

    def get_workouts(self, inp: dict) -> str:
        permission_error, startdateymd, enddateymd = self._check(self.agent_id, self.PROVIDER_ID, "withings_get_workouts", inp, "startdateymd", "enddateymd")
        if permission_error: return permission_error
        params = {
            "action": "getworkouts",
            "access_token": self._token,
            "startdateymd": startdateymd,
            "enddateymd": enddateymd,
        }
        if inp.get("data_fields"):
            params["data_fields"] = inp["data_fields"]
        try:
            resp = httpx.post(f"{_BASE}/v2/measure", data=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            err = _check_status("withings_get_workouts", data)
            if err:
                return err
            body = data.get("body", {})
            series = [
                {
                    "id": w.get("id"),
                    "category": w.get("category"),
                    "startdate": w.get("startdate"),
                    "enddate": w.get("enddate"),
                    "data": w.get("data", {}),
                }
                for w in body.get("series", [])
            ]
            return json.dumps({"workouts": series, "more": body.get("more"), "offset": body.get("offset")})
        except Exception as e:
            return _handle_error("withings_get_workouts", e)

    def get_devices(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "withings_get_devices", inp)
        if permission_error: return permission_error
        params = {
            "action": "getdevice",
            "access_token": self._token,
        }
        try:
            resp = httpx.get(f"{_BASE}/v2/user", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            err = _check_status("withings_get_devices", data)
            if err:
                return err
            body = data.get("body", {})
            devices = [
                {
                    "type": d.get("type"),
                    "model": d.get("model"),
                    "model_id": d.get("model_id"),
                    "battery": d.get("battery"),
                    "deviceid": d.get("deviceid"),
                    "hash_deviceid": d.get("hash_deviceid"),
                    "timezone": d.get("timezone"),
                    "last_session_date": d.get("last_session_date"),
                }
                for d in body.get("devices", [])
            ]
            return json.dumps({"devices": devices})
        except Exception as e:
            return _handle_error("withings_get_devices", e)

    def get_user_info(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "withings_get_user_info", inp)
        if permission_error: return permission_error
        params = {
            "action": "getdevice",
            "access_token": self._token,
        }
        try:
            resp = httpx.get(f"{_BASE}/v2/user", params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            err = _check_status("withings_get_user_info", data)
            if err:
                return err
            body = data.get("body", {})
            return json.dumps({
                "userid": body.get("userid"),
                "devices_count": len(body.get("devices", [])),
                "devices": [
                    {"model": d.get("model"), "type": d.get("type"), "battery": d.get("battery")}
                    for d in body.get("devices", [])
                ],
            })
        except Exception as e:
            return _handle_error("withings_get_user_info", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "withings_get_body_measurements",
                    "description": "Get Withings body measurements such as weight, height, BMI, body fat, blood pressure, and pulse. Returns measurement groups with values.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meastype": {
                                "type": "integer",
                                "description": "Measurement type filter: 1=weight(kg), 4=height(m), 5=lean_mass, 6=fat_ratio(%), 8=fat_mass, 9=diastolic_bp, 10=systolic_bp, 11=pulse, 76=muscle_mass, 88=bone_mass, 226=spo2. Omit for all types.",
                            },
                            "startdate": {"type": "integer", "description": "Start date as Unix timestamp."},
                            "enddate": {"type": "integer", "description": "End date as Unix timestamp."},
                            "lastupdate": {"type": "integer", "description": "Return only measurements updated after this Unix timestamp."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "withings_get_daily_activity",
                    "description": "Get Withings daily activity summaries including steps, distance, calories, and heart rate for a date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "startdateymd": {"type": "string", "description": "Start date in YYYY-MM-DD format."},
                            "enddateymd": {"type": "string", "description": "End date in YYYY-MM-DD format."},
                        },
                        "required": ["startdateymd", "enddateymd"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "withings_get_intraday_activity",
                    "description": "Get Withings intraday heart rate and activity data at fine granularity (minute-level) for a time window.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "startdate": {"type": "integer", "description": "Start of window as Unix timestamp."},
                            "enddate": {"type": "integer", "description": "End of window as Unix timestamp (max 24h from startdate)."},
                            "data_fields": {"type": "string", "description": "Comma-separated fields to include, e.g. 'heart_rate,steps,calories'."},
                        },
                        "required": ["startdate", "enddate"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "withings_get_sleep_summary",
                    "description": "Get Withings sleep summaries including total sleep time, sleep efficiency, latency, light/deep/REM durations, and respiratory rate for a date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "startdateymd": {"type": "string", "description": "Start date in YYYY-MM-DD format."},
                            "enddateymd": {"type": "string", "description": "End date in YYYY-MM-DD format."},
                        },
                        "required": ["startdateymd", "enddateymd"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "withings_get_sleep_data",
                    "description": "Get raw Withings sleep state timeline (awake, light, deep, REM) for a specific time window.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "startdate": {"type": "integer", "description": "Start of sleep window as Unix timestamp."},
                            "enddate": {"type": "integer", "description": "End of sleep window as Unix timestamp."},
                        },
                        "required": ["startdate", "enddate"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "withings_get_devices",
                    "description": "Get a list of Withings devices linked to the user account, including model, battery level, and last session date.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "withings_get_user_info",
                    "description": "Get basic Withings user account info and a summary of linked device models.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "withings_get_workouts",
                    "description": "Get Withings workout summaries (calories, heart rate, steps, distance) for a date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "startdateymd": {"type": "string", "description": "Start date in YYYY-MM-DD format."},
                            "enddateymd": {"type": "string", "description": "End date in YYYY-MM-DD format."},
                            "data_fields": {"type": "string", "description": "Comma-separated fields to include, e.g. 'calories,steps,distance,hr_average'."},
                        },
                        "required": ["startdateymd", "enddateymd"],
                    },
                },
            },
        ]
        callables = {
            "withings_get_body_measurements": self.get_body_measurements,
            "withings_get_daily_activity": self.get_daily_activity,
            "withings_get_intraday_activity": self.get_intraday_activity,
            "withings_get_sleep_summary": self.get_sleep_summary,
            "withings_get_sleep_data": self.get_sleep_data,
            "withings_get_devices": self.get_devices,
            "withings_get_user_info": self.get_user_info,
            "withings_get_workouts": self.get_workouts,
        }
        return tools, callables

import json
import httpx
from datetime import date

from ai.connectors.base import BaseConnector

_BASE = "https://api.fitbit.com"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector (HTTP {e.response.status_code})."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class FitbitConnector(BaseConnector):
    """Fitbit connector using OAuth2 Bearer token."""

    PROVIDER_ID = "fitbit"

    def _today(self) -> str:
        return date.today().isoformat()

    def get_profile(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fitbit_get_profile", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/1/user/-/profile.json", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            user = resp.json().get("user", {})
            return json.dumps({
                "display_name": user.get("displayName"),
                "full_name": user.get("fullName"),
                "age": user.get("age"),
                "gender": user.get("gender"),
                "height": user.get("height"),
                "weight": user.get("weight"),
                "timezone": user.get("timezone"),
                "member_since": user.get("memberSince"),
                "avatar": user.get("avatar"),
            })
        except Exception as e:
            return _handle_error("fitbit_get_profile", e)

    def get_activities(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fitbit_get_activities", inp)
        if permission_error: return permission_error
        target_date = inp.get("date", self._today())
        try:
            resp = httpx.get(
                f"{_BASE}/1/user/-/activities/date/{target_date}.json",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            summary = data.get("summary", {})
            return json.dumps({
                "date": target_date,
                "steps": summary.get("steps"),
                "calories_out": summary.get("caloriesOut"),
                "active_minutes": {
                    "fairly_active": summary.get("fairlyActiveMinutes"),
                    "lightly_active": summary.get("lightlyActiveMinutes"),
                    "very_active": summary.get("veryActiveMinutes"),
                    "sedentary": summary.get("sedentaryMinutes"),
                },
                "distance_km": next(
                    (d["distance"] for d in summary.get("distances", []) if d.get("activity") == "total"), None
                ),
                "floors": summary.get("floors"),
                "activity_count": len(data.get("activities", [])),
            })
        except Exception as e:
            return _handle_error("fitbit_get_activities", e)

    def get_heart_rate(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fitbit_get_heart_rate", inp)
        if permission_error: return permission_error
        target_date = inp.get("date", self._today())
        period = inp.get("period", "1d")
        try:
            resp = httpx.get(
                f"{_BASE}/1/user/-/activities/heart/date/{target_date}/{period}.json",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            heart_data = data.get("activities-heart", [])
            result = []
            for entry in heart_data:
                value = entry.get("value", {})
                result.append({
                    "date": entry.get("dateTime"),
                    "resting_heart_rate": value.get("restingHeartRate"),
                    "heart_rate_zones": [
                        {
                            "name": z.get("name"),
                            "min": z.get("min"),
                            "max": z.get("max"),
                            "minutes": z.get("minutes"),
                            "calories_out": z.get("caloriesOut"),
                        }
                        for z in value.get("heartRateZones", [])
                    ],
                })
            return json.dumps({"heart_rate": result})
        except Exception as e:
            return _handle_error("fitbit_get_heart_rate", e)

    def get_sleep(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fitbit_get_sleep", inp)
        if permission_error: return permission_error
        target_date = inp.get("date", self._today())
        try:
            resp = httpx.get(
                f"{_BASE}/1.2/user/-/sleep/date/{target_date}.json",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            summary = data.get("summary", {})
            sleep_records = data.get("sleep", [])
            main_sleep = next((s for s in sleep_records if s.get("isMainSleep")), sleep_records[0] if sleep_records else {})
            return json.dumps({
                "date": target_date,
                "total_minutes_asleep": summary.get("totalMinutesAsleep"),
                "total_time_in_bed": summary.get("totalTimeInBed"),
                "total_sleep_records": summary.get("totalSleepRecords"),
                "stages": summary.get("stages"),
                "main_sleep": {
                    "start_time": main_sleep.get("startTime"),
                    "end_time": main_sleep.get("endTime"),
                    "duration_ms": main_sleep.get("duration"),
                    "efficiency": main_sleep.get("efficiency"),
                    "type": main_sleep.get("type"),
                } if main_sleep else None,
            })
        except Exception as e:
            return _handle_error("fitbit_get_sleep", e)

    def get_weight(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fitbit_get_weight", inp)
        if permission_error: return permission_error
        target_date = inp.get("date", self._today())
        try:
            resp = httpx.get(
                f"{_BASE}/1/user/-/body/log/weight/date/{target_date}.json",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            logs = data.get("weight", [])
            return json.dumps({
                "date": target_date,
                "entries": [
                    {
                        "date": w.get("date"),
                        "time": w.get("time"),
                        "weight": w.get("weight"),
                        "bmi": w.get("bmi"),
                        "fat": w.get("fat"),
                    }
                    for w in logs
                ],
            })
        except Exception as e:
            return _handle_error("fitbit_get_weight", e)

    def get_devices(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fitbit_get_devices", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/1/user/-/devices.json", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            devices = resp.json()
            return json.dumps({
                "devices": [
                    {
                        "id": d.get("id"),
                        "device_version": d.get("deviceVersion"),
                        "type": d.get("type"),
                        "battery": d.get("battery"),
                        "battery_level": d.get("batteryLevel"),
                        "last_sync_time": d.get("lastSyncTime"),
                        "mac": d.get("mac"),
                    }
                    for d in devices
                ]
            })
        except Exception as e:
            return _handle_error("fitbit_get_devices", e)

    def get_nutrition(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fitbit_get_nutrition", inp)
        if permission_error: return permission_error
        target_date = inp.get("date", self._today())
        try:
            resp = httpx.get(
                f"{_BASE}/1/user/-/foods/log/date/{target_date}.json",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            summary = data.get("summary", {})
            return json.dumps({
                "date": target_date,
                "calories": summary.get("calories"),
                "carbs": summary.get("carbs"),
                "fat": summary.get("fat"),
                "fiber": summary.get("fiber"),
                "protein": summary.get("protein"),
                "sodium": summary.get("sodium"),
                "water": summary.get("water"),
                "food_log_count": len(data.get("foods", [])),
            })
        except Exception as e:
            return _handle_error("fitbit_get_nutrition", e)

    def get_spo2(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fitbit_get_spo2", inp)
        if permission_error: return permission_error
        target_date = inp.get("date", self._today())
        try:
            resp = httpx.get(
                f"{_BASE}/1/user/-/spo2/date/{target_date}.json",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "date": target_date,
                "spo2": data.get("value", data),
            })
        except Exception as e:
            return _handle_error("fitbit_get_spo2", e)

    def log_activity(self, inp: dict) -> str:
        permission_error, duration_minutes = self._check(self.agent_id, self.PROVIDER_ID, "fitbit_log_activity", inp, "duration_minutes")
        if permission_error: return permission_error
        activity_id = inp.get("activity_id")
        activity_name = inp.get("activity_name")
        if not activity_id and not activity_name:
            return "Error: 'activity_id' or 'activity_name' is required."
        params = {
            "startTime": inp.get("start_time", "08:00"),
            "durationMillis": int(float(duration_minutes) * 60000),
            "date": inp.get("date", self._today()),
        }
        if activity_id:
            params["activityId"] = activity_id
        else:
            params["activityName"] = activity_name
            if not inp.get("manual_calories"):
                return "Error: 'manual_calories' is required when using 'activity_name' instead of 'activity_id'."
        if inp.get("manual_calories"):
            params["manualCalories"] = inp["manual_calories"]
        if inp.get("distance") is not None:
            params["distance"] = inp["distance"]
        try:
            resp = httpx.post(f"{_BASE}/1/user/-/activities.json", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            logged = data.get("activityLog", {})
            return json.dumps({
                "logged": True,
                "activity_log_id": logged.get("logId"),
                "activity_name": logged.get("activityName") or logged.get("name"),
                "calories": logged.get("calories"),
                "duration_ms": logged.get("duration"),
                "start_time": logged.get("startTime"),
            })
        except Exception as e:
            return _handle_error("fitbit_log_activity", e)

    def log_weight(self, inp: dict) -> str:
        permission_error, weight = self._check(self.agent_id, self.PROVIDER_ID, "fitbit_log_weight", inp, "weight")
        if permission_error: return permission_error
        weight = inp.get("weight")
        if weight is None:
            return "Error: 'weight' is required."
        params = {"weight": weight, "date": inp.get("date", self._today())}
        if inp.get("time"):
            params["time"] = inp["time"]
        try:
            resp = httpx.post(f"{_BASE}/1/user/-/body/log/weight.json", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            logged = resp.json().get("weightLog", {})
            return json.dumps({
                "logged": True,
                "log_id": logged.get("logId"),
                "date": logged.get("date"),
                "weight": logged.get("weight"),
                "bmi": logged.get("bmi"),
            })
        except Exception as e:
            return _handle_error("fitbit_log_weight", e)

    def log_food(self, inp: dict) -> str:
        permission_error, meal_type_id = self._check(self.agent_id, self.PROVIDER_ID, "fitbit_log_food", inp, "meal_type_id")
        if permission_error: return permission_error
        food_id = inp.get("food_id")
        food_name = inp.get("food_name")
        if not food_id and not food_name:
            return "Error: 'food_id' or 'food_name' is required."
        params = {
            "mealTypeId": meal_type_id,
            "date": inp.get("date", self._today()),
        }
        if food_id:
            params["foodId"] = food_id
            params["amount"] = inp.get("amount", 1)
            params["unitId"] = inp.get("unit_id", 147)
        else:
            params["foodName"] = food_name
            if not inp.get("calories"):
                return "Error: 'calories' is required when using 'food_name' instead of 'food_id'."
            params["calories"] = inp["calories"]
        try:
            resp = httpx.post(f"{_BASE}/1/user/-/foods/log.json", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            logged = (data.get("foodLog") or {})
            logged_food = logged.get("loggedFood", {})
            return json.dumps({
                "logged": True,
                "log_id": logged.get("logId"),
                "food_name": logged_food.get("name"),
                "amount": logged_food.get("amount"),
                "calories": logged.get("nutritionalValues", {}).get("calories"),
            })
        except Exception as e:
            return _handle_error("fitbit_log_food", e)

    def log_water(self, inp: dict) -> str:
        permission_error, amount = self._check(self.agent_id, self.PROVIDER_ID, "fitbit_log_water", inp, "amount")
        if permission_error: return permission_error
        params = {
            "amount": amount,
            "date": inp.get("date", self._today()),
            "unit": inp.get("unit", "ml"),
        }
        try:
            resp = httpx.post(f"{_BASE}/1/user/-/foods/log/water.json", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            logged = resp.json().get("waterLog", {})
            return json.dumps({
                "logged": True,
                "log_id": logged.get("logId"),
                "date": logged.get("date"),
                "amount": logged.get("amount"),
            })
        except Exception as e:
            return _handle_error("fitbit_log_water", e)

    def get_activity_goals(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fitbit_get_activity_goals", inp)
        if permission_error: return permission_error
        period = inp.get("period", "daily")
        if period not in ("daily", "weekly"):
            return "Error: 'period' must be 'daily' or 'weekly'."
        try:
            resp = httpx.get(f"{_BASE}/1/user/-/activities/goals/{period}.json", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            goals = resp.json().get("goals", {})
            return json.dumps({"period": period, "goals": goals})
        except Exception as e:
            return _handle_error("fitbit_get_activity_goals", e)

    def get_frequent_foods(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fitbit_get_frequent_foods", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/1/user/-/foods/log/frequent.json", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            foods = resp.json()
            return json.dumps({
                "frequent_foods": [
                    {
                        "food_id": f.get("foodId"),
                        "name": f.get("name"),
                        "amount": f.get("amount"),
                        "unit": (f.get("unit") or {}).get("name"),
                        "calories": f.get("calories"),
                        "meal_type_id": f.get("mealTypeId"),
                    }
                    for f in foods
                ],
            })
        except Exception as e:
            return _handle_error("fitbit_get_frequent_foods", e)

    def get_body_fat(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "fitbit_get_body_fat", inp)
        if permission_error: return permission_error
        target_date = inp.get("date", self._today())
        try:
            resp = httpx.get(
                f"{_BASE}/1/user/-/body/log/fat/date/{target_date}.json",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            logs = resp.json().get("fat", [])
            return json.dumps({
                "date": target_date,
                "entries": [
                    {"date": f.get("date"), "time": f.get("time"), "fat": f.get("fat"), "log_id": f.get("logId")}
                    for f in logs
                ],
            })
        except Exception as e:
            return _handle_error("fitbit_get_body_fat", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "fitbit_get_profile",
                    "description": "Get the authenticated Fitbit user's profile information.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fitbit_get_activities",
                    "description": "Get activity summary for a given date: steps, calories, active minutes, distance.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Date in YYYY-MM-DD format. Defaults to today."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fitbit_get_heart_rate",
                    "description": "Get heart rate data and zones for a given date and period.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Date in YYYY-MM-DD format. Defaults to today."},
                            "period": {"type": "string", "description": "Period: 1d, 7d, 30d, 1w, 1m. Defaults to 1d."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fitbit_get_sleep",
                    "description": "Get sleep log and summary (duration, stages, efficiency) for a given date.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Date in YYYY-MM-DD format. Defaults to today."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fitbit_get_weight",
                    "description": "Get body weight log entries for a given date.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Date in YYYY-MM-DD format. Defaults to today."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fitbit_get_devices",
                    "description": "List all Fitbit devices paired to the user's account with battery and sync info.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fitbit_get_nutrition",
                    "description": "Get nutrition log summary (calories, macros, water) for a given date.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Date in YYYY-MM-DD format. Defaults to today."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fitbit_get_spo2",
                    "description": "Get blood oxygen saturation (SpO2) data for a given date.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Date in YYYY-MM-DD format. Defaults to today."},
                        },
                        "required": [],
                    },
                },
            },
        ]
        callables = {
            "fitbit_get_profile": self.get_profile,
            "fitbit_get_activities": self.get_activities,
            "fitbit_get_heart_rate": self.get_heart_rate,
            "fitbit_get_sleep": self.get_sleep,
            "fitbit_get_weight": self.get_weight,
            "fitbit_get_devices": self.get_devices,
            "fitbit_get_nutrition": self.get_nutrition,
            "fitbit_get_spo2": self.get_spo2,
        }
        return tools, callables

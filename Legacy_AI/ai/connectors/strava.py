import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://www.strava.com/api/v3"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the Strava connector (HTTP {e.response.status_code})."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        if e.response.status_code == 429:
            return f"Rate limit exceeded in {tool_name}: Strava allows 200 requests/15 min and 2000/day. Try again later."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class StravaConnector(BaseConnector):
    """Strava connector providing access to athlete profile, activities, and stats."""

    PROVIDER_ID = "strava"

    def get_athlete(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "strava_get_athlete", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/athlete", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            a = resp.json()
            return json.dumps({
                "id": a.get("id"),
                "username": a.get("username"),
                "firstname": a.get("firstname"),
                "lastname": a.get("lastname"),
                "city": a.get("city"),
                "state": a.get("state"),
                "country": a.get("country"),
                "sex": a.get("sex"),
                "premium": a.get("premium"),
                "summit": a.get("summit"),
                "created_at": a.get("created_at"),
                "updated_at": a.get("updated_at"),
                "follower_count": a.get("follower_count"),
                "friend_count": a.get("friend_count"),
                "measurement_preference": a.get("measurement_preference"),
                "weight": a.get("weight"),
            })
        except Exception as e:
            return _handle_error("strava_get_athlete", e)

    def get_athlete_stats(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "strava_get_athlete_stats", inp)
        if permission_error: return permission_error
        try:
            me = httpx.get(f"{_BASE}/athlete", headers=self._auth_headers, timeout=15)
            me.raise_for_status()
            athlete_id = me.json().get("id")
            resp = httpx.get(f"{_BASE}/athletes/{athlete_id}/stats", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({
                "recent_run_totals": data.get("recent_run_totals"),
                "all_run_totals": data.get("all_run_totals"),
                "recent_ride_totals": data.get("recent_ride_totals"),
                "all_ride_totals": data.get("all_ride_totals"),
                "recent_swim_totals": data.get("recent_swim_totals"),
                "all_swim_totals": data.get("all_swim_totals"),
                "ytd_run_totals": data.get("ytd_run_totals"),
                "ytd_ride_totals": data.get("ytd_ride_totals"),
                "ytd_swim_totals": data.get("ytd_swim_totals"),
            })
        except Exception as e:
            return _handle_error("strava_get_athlete_stats", e)

    def list_activities(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "strava_list_activities", inp)
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("per_page", 30), "page": inp.get("page", 1)}
            if inp.get("before"):
                params["before"] = inp["before"]
            if inp.get("after"):
                params["after"] = inp["after"]
            resp = httpx.get(f"{_BASE}/athlete/activities", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            activities = [
                {
                    "id": a.get("id"),
                    "name": a.get("name"),
                    "type": a.get("type"),
                    "sport_type": a.get("sport_type"),
                    "start_date": a.get("start_date"),
                    "start_date_local": a.get("start_date_local"),
                    "distance": a.get("distance"),
                    "moving_time": a.get("moving_time"),
                    "elapsed_time": a.get("elapsed_time"),
                    "total_elevation_gain": a.get("total_elevation_gain"),
                    "average_speed": a.get("average_speed"),
                    "max_speed": a.get("max_speed"),
                    "average_heartrate": a.get("average_heartrate"),
                    "max_heartrate": a.get("max_heartrate"),
                    "kudos_count": a.get("kudos_count"),
                    "athlete_count": a.get("athlete_count"),
                    "trainer": a.get("trainer"),
                    "commute": a.get("commute"),
                }
                for a in resp.json()
            ]
            return json.dumps({"activities": activities, "count": len(activities)})
        except Exception as e:
            return _handle_error("strava_list_activities", e)

    def get_activity(self, inp: dict) -> str:
        permission_error, activity_id = self._check(self.agent_id, self.PROVIDER_ID, "strava_get_activity", inp, "activity_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/activities/{activity_id}",
                headers=self._auth_headers,
                params={"include_all_efforts": inp.get("include_all_efforts", False)},
                timeout=15,
            )
            resp.raise_for_status()
            a = resp.json()
            return json.dumps({
                "id": a.get("id"),
                "name": a.get("name"),
                "description": a.get("description"),
                "type": a.get("type"),
                "sport_type": a.get("sport_type"),
                "start_date": a.get("start_date"),
                "start_date_local": a.get("start_date_local"),
                "timezone": a.get("timezone"),
                "distance": a.get("distance"),
                "moving_time": a.get("moving_time"),
                "elapsed_time": a.get("elapsed_time"),
                "total_elevation_gain": a.get("total_elevation_gain"),
                "elev_high": a.get("elev_high"),
                "elev_low": a.get("elev_low"),
                "average_speed": a.get("average_speed"),
                "max_speed": a.get("max_speed"),
                "average_cadence": a.get("average_cadence"),
                "average_watts": a.get("average_watts"),
                "max_watts": a.get("max_watts"),
                "average_heartrate": a.get("average_heartrate"),
                "max_heartrate": a.get("max_heartrate"),
                "calories": a.get("calories"),
                "kudos_count": a.get("kudos_count"),
                "comment_count": a.get("comment_count"),
                "athlete_count": a.get("athlete_count"),
                "achievement_count": a.get("achievement_count"),
                "trainer": a.get("trainer"),
                "commute": a.get("commute"),
                "manual": a.get("manual"),
                "private": a.get("private"),
                "gear_id": a.get("gear_id"),
                "device_name": a.get("device_name"),
            })
        except Exception as e:
            return _handle_error("strava_get_activity", e)

    def get_activity_streams(self, inp: dict) -> str:
        permission_error, activity_id = self._check(self.agent_id, self.PROVIDER_ID, "strava_get_activity_streams", inp, "activity_id")
        if permission_error: return permission_error
        stream_types = inp.get("stream_types", "time,distance,heartrate,cadence,watts,velocity_smooth,altitude")
        try:
            resp = httpx.get(
                f"{_BASE}/activities/{activity_id}/streams",
                headers=self._auth_headers,
                params={"keys": stream_types, "key_by_type": True},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            result = {}
            if isinstance(data, list):
                for stream in data:
                    result[stream.get("type")] = {"data": stream.get("data"), "series_type": stream.get("series_type"), "resolution": stream.get("resolution")}
            elif isinstance(data, dict):
                result = data
            return json.dumps(result)
        except Exception as e:
            return _handle_error("strava_get_activity_streams", e)

    def get_athlete_zones(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "strava_get_athlete_zones", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/athlete/zones", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            return json.dumps(resp.json())
        except Exception as e:
            return _handle_error("strava_get_athlete_zones", e)

    def list_starred_segments(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "strava_list_starred_segments", inp)
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("per_page", 30), "page": inp.get("page", 1)}
            resp = httpx.get(f"{_BASE}/segments/starred", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            segments = [
                {
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "activity_type": s.get("activity_type"),
                    "distance": s.get("distance"),
                    "average_grade": s.get("average_grade"),
                    "maximum_grade": s.get("maximum_grade"),
                    "elevation_high": s.get("elevation_high"),
                    "elevation_low": s.get("elevation_low"),
                    "city": s.get("city"),
                    "state": s.get("state"),
                    "country": s.get("country"),
                    "climb_category": s.get("climb_category"),
                    "athlete_pr_effort": s.get("athlete_pr_effort"),
                }
                for s in resp.json()
            ]
            return json.dumps({"segments": segments, "count": len(segments)})
        except Exception as e:
            return _handle_error("strava_list_starred_segments", e)

    def get_activity_laps(self, inp: dict) -> str:
        permission_error, activity_id = self._check(self.agent_id, self.PROVIDER_ID, "strava_get_activity_laps", inp, "activity_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/activities/{activity_id}/laps", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            laps = [
                {
                    "id": lap.get("id"),
                    "name": lap.get("name"),
                    "lap_index": lap.get("lap_index"),
                    "split": lap.get("split"),
                    "distance": lap.get("distance"),
                    "moving_time": lap.get("moving_time"),
                    "elapsed_time": lap.get("elapsed_time"),
                    "average_speed": lap.get("average_speed"),
                    "max_speed": lap.get("max_speed"),
                    "average_heartrate": lap.get("average_heartrate"),
                    "max_heartrate": lap.get("max_heartrate"),
                    "average_cadence": lap.get("average_cadence"),
                    "average_watts": lap.get("average_watts"),
                    "total_elevation_gain": lap.get("total_elevation_gain"),
                    "start_date": lap.get("start_date"),
                    "start_date_local": lap.get("start_date_local"),
                }
                for lap in resp.json()
            ]
            return json.dumps({"laps": laps, "count": len(laps)})
        except Exception as e:
            return _handle_error("strava_get_activity_laps", e)

    def get_segment(self, inp: dict) -> str:
        permission_error, segment_id = self._check(self.agent_id, self.PROVIDER_ID, "strava_get_segment", inp, "segment_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/segments/{segment_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            s = resp.json()
            return json.dumps({
                "id": s.get("id"),
                "name": s.get("name"),
                "activity_type": s.get("activity_type"),
                "distance": s.get("distance"),
                "average_grade": s.get("average_grade"),
                "maximum_grade": s.get("maximum_grade"),
                "elevation_high": s.get("elevation_high"),
                "elevation_low": s.get("elevation_low"),
                "start_latlng": s.get("start_latlng"),
                "end_latlng": s.get("end_latlng"),
                "climb_category": s.get("climb_category"),
                "city": s.get("city"),
                "state": s.get("state"),
                "country": s.get("country"),
                "private": s.get("private"),
                "starred": s.get("starred"),
                "star_count": s.get("star_count"),
                "effort_count": s.get("effort_count"),
                "athlete_count": s.get("athlete_count"),
                "athlete_segment_stats": s.get("athlete_segment_stats"),
            })
        except Exception as e:
            return _handle_error("strava_get_segment", e)

    def explore_segments(self, inp: dict) -> str:
        permission_error, bounds = self._check(self.agent_id, self.PROVIDER_ID, "strava_explore_segments", inp, "bounds")
        if permission_error: return permission_error
        try:
            params = {"bounds": bounds}
            if inp.get("activity_type"):
                params["activity_type"] = inp["activity_type"]
            if inp.get("min_cat") is not None:
                params["min_cat"] = inp["min_cat"]
            if inp.get("max_cat") is not None:
                params["max_cat"] = inp["max_cat"]
            resp = httpx.get(f"{_BASE}/segments/explore", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            segments = [
                {
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "climb_category": s.get("climb_category"),
                    "climb_category_desc": s.get("climb_category_desc"),
                    "avg_grade": s.get("avg_grade"),
                    "elev_difference": s.get("elev_difference"),
                    "distance": s.get("distance"),
                    "starred": s.get("starred"),
                }
                for s in resp.json().get("segments", [])
            ]
            return json.dumps({"segments": segments, "count": len(segments)})
        except Exception as e:
            return _handle_error("strava_explore_segments", e)

    def list_segment_efforts(self, inp: dict) -> str:
        permission_error, segment_id = self._check(self.agent_id, self.PROVIDER_ID, "strava_list_segment_efforts", inp, "segment_id")
        if permission_error: return permission_error
        try:
            params = {"segment_id": segment_id, "per_page": inp.get("per_page", 30), "page": inp.get("page", 1)}
            if inp.get("start_date_local"):
                params["start_date_local"] = inp["start_date_local"]
            if inp.get("end_date_local"):
                params["end_date_local"] = inp["end_date_local"]
            resp = httpx.get(f"{_BASE}/segment_efforts", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            efforts = [
                {
                    "id": e.get("id"),
                    "name": e.get("name"),
                    "activity_id": (e.get("activity") or {}).get("id"),
                    "elapsed_time": e.get("elapsed_time"),
                    "moving_time": e.get("moving_time"),
                    "start_date": e.get("start_date"),
                    "start_date_local": e.get("start_date_local"),
                    "distance": e.get("distance"),
                    "average_watts": e.get("average_watts"),
                    "average_heartrate": e.get("average_heartrate"),
                    "max_heartrate": e.get("max_heartrate"),
                    "kom_rank": e.get("kom_rank"),
                    "pr_rank": e.get("pr_rank"),
                }
                for e in resp.json()
            ]
            return json.dumps({"efforts": efforts, "count": len(efforts)})
        except Exception as e:
            return _handle_error("strava_list_segment_efforts", e)

    def update_activity(self, inp: dict) -> str:
        permission_error, activity_id = self._check(self.agent_id, self.PROVIDER_ID, "strava_update_activity", inp, "activity_id")
        if permission_error: return permission_error
        try:
            headers = {**self._auth_headers, "Content-Type": "application/json"}
            updates: dict = {}
            if inp.get("name"):
                updates["name"] = inp["name"]
            if inp.get("description") is not None:
                updates["description"] = inp["description"]
            if inp.get("sport_type"):
                updates["sport_type"] = inp["sport_type"]
            if inp.get("gear_id") is not None:
                updates["gear_id"] = inp["gear_id"]
            if inp.get("trainer") is not None:
                updates["trainer"] = inp["trainer"]
            if inp.get("commute") is not None:
                updates["commute"] = inp["commute"]
            if not updates:
                return "Error: at least one of 'name', 'description', 'sport_type', 'gear_id', 'trainer', 'commute' is required."
            resp = httpx.put(f"{_BASE}/activities/{activity_id}", headers=headers, json=updates, timeout=15)
            resp.raise_for_status()
            a = resp.json()
            return json.dumps({
                "id": a.get("id"),
                "name": a.get("name"),
                "description": a.get("description"),
                "sport_type": a.get("sport_type"),
                "gear_id": a.get("gear_id"),
                "trainer": a.get("trainer"),
                "commute": a.get("commute"),
                "status": "updated",
            })
        except Exception as e:
            return _handle_error("strava_update_activity", e)

    def list_athlete_clubs(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "strava_list_athlete_clubs", inp)
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("per_page", 30), "page": inp.get("page", 1)}
            resp = httpx.get(f"{_BASE}/athlete/clubs", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            clubs = [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "sport_type": c.get("sport_type"),
                    "city": c.get("city"),
                    "state": c.get("state"),
                    "country": c.get("country"),
                    "private": c.get("private"),
                    "member_count": c.get("member_count"),
                    "url": c.get("url"),
                }
                for c in resp.json()
            ]
            return json.dumps({"clubs": clubs, "count": len(clubs)})
        except Exception as e:
            return _handle_error("strava_list_athlete_clubs", e)

    def list_club_activities(self, inp: dict) -> str:
        permission_error, club_id = self._check(self.agent_id, self.PROVIDER_ID, "strava_list_club_activities", inp, "club_id")
        if permission_error: return permission_error
        try:
            params = {"per_page": inp.get("per_page", 30), "page": inp.get("page", 1)}
            resp = httpx.get(f"{_BASE}/clubs/{club_id}/activities", headers=self._auth_headers, params=params, timeout=15)
            resp.raise_for_status()
            activities = [
                {
                    "athlete_name": f"{(a.get('athlete') or {}).get('firstname', '')} {(a.get('athlete') or {}).get('lastname', '')}".strip(),
                    "name": a.get("name"),
                    "type": a.get("type"),
                    "distance": a.get("distance"),
                    "moving_time": a.get("moving_time"),
                    "elapsed_time": a.get("elapsed_time"),
                    "total_elevation_gain": a.get("total_elevation_gain"),
                    "workout_type": a.get("workout_type"),
                }
                for a in resp.json()
            ]
            return json.dumps({"activities": activities, "count": len(activities)})
        except Exception as e:
            return _handle_error("strava_list_club_activities", e)

    def get_gear(self, inp: dict) -> str:
        permission_error, gear_id = self._check(self.agent_id, self.PROVIDER_ID, "strava_get_gear", inp, "gear_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(f"{_BASE}/gear/{gear_id}", headers=self._auth_headers, timeout=15)
            resp.raise_for_status()
            g = resp.json()
            return json.dumps({
                "id": g.get("id"),
                "primary": g.get("primary"),
                "name": g.get("name"),
                "distance": g.get("distance"),
                "brand_name": g.get("brand_name"),
                "model_name": g.get("model_name"),
                "frame_type": g.get("frame_type"),
                "description": g.get("description"),
            })
        except Exception as e:
            return _handle_error("strava_get_gear", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "strava_get_athlete",
                    "description": "Get the authenticated Strava athlete's profile information.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "strava_get_athlete_stats",
                    "description": "Get totals and stats for the authenticated Strava athlete across runs, rides, and swims (recent, YTD, and all-time).",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "strava_list_activities",
                    "description": "List the authenticated athlete's activities on Strava, optionally filtered by date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "per_page": {"type": "integer", "description": "Number of activities per page (default 30, max 200)."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                            "before": {"type": "integer", "description": "Unix epoch timestamp — return activities before this time."},
                            "after": {"type": "integer", "description": "Unix epoch timestamp — return activities after this time."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "strava_get_activity",
                    "description": "Get detailed information about a specific Strava activity by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "activity_id": {"type": "string", "description": "The Strava activity ID."},
                            "include_all_efforts": {"type": "boolean", "description": "Whether to include all segment efforts (default false)."},
                        },
                        "required": ["activity_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "strava_get_activity_streams",
                    "description": "Get time-series data streams for a Strava activity (e.g. heartrate, cadence, altitude, power, velocity).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "activity_id": {"type": "string", "description": "The Strava activity ID."},
                            "stream_types": {
                                "type": "string",
                                "description": "Comma-separated stream types to fetch. Options: time, distance, latlng, altitude, velocity_smooth, heartrate, cadence, watts, temp, moving, grade_smooth. Default: time,distance,heartrate,cadence,watts,velocity_smooth,altitude.",
                            },
                        },
                        "required": ["activity_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "strava_get_athlete_zones",
                    "description": "Get the authenticated athlete's heart rate and power zones configured in Strava.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "strava_list_starred_segments",
                    "description": "List the authenticated athlete's starred segments on Strava.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "per_page": {"type": "integer", "description": "Number of segments per page (default 30)."},
                            "page": {"type": "integer", "description": "Page number (default 1)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "strava_get_activity_laps",
                    "description": "Get the laps for a specific Strava activity.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "activity_id": {"type": "string", "description": "The Strava activity ID."},
                        },
                        "required": ["activity_id"],
                    },
                },
            },
        ]
        callables = {
            "strava_get_athlete": self.get_athlete,
            "strava_get_athlete_stats": self.get_athlete_stats,
            "strava_list_activities": self.list_activities,
            "strava_get_activity": self.get_activity,
            "strava_get_activity_streams": self.get_activity_streams,
            "strava_get_athlete_zones": self.get_athlete_zones,
            "strava_list_starred_segments": self.list_starred_segments,
            "strava_get_activity_laps": self.get_activity_laps,
        }
        return tools, callables

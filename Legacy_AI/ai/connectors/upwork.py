import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.upwork.com/api"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Upwork account lacks permission "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their Upwork connector."
            )
        if e.response.status_code == 404:
            return f"Not found in {tool_name}: the requested resource does not exist."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class UpworkConnector(BaseConnector):
    """Upwork API v2/v3 connector using OAuth2."""

    PROVIDER_ID = "upwork"

    def get_profile(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "upwork_get_profile", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/profiles/v2/users/me.json",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            u = resp.json().get("user", {})
            return json.dumps({
                "id": u.get("id"),
                "name": f"{u.get('first_name', '')} {u.get('last_name', '')}".strip(),
                "email": u.get("email"),
                "profile_url": u.get("profile_url"),
                "account_type": u.get("account_type"),
                "timezone": u.get("timezone"),
                "company": u.get("company_name"),
            })
        except Exception as e:
            return _handle_error("upwork_get_profile", e)

    def list_contracts(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "upwork_list_contracts", inp)
        if permission_error: return permission_error
        try:
            params: dict = {
                "status": inp.get("status", "active"),
                "buyer_team__reference": inp.get("team_ref", ""),
            }
            resp = httpx.get(
                f"{_BASE}/hr/v2/contracts.json",
                headers=self._auth_headers,
                params={k: v for k, v in params.items() if v},
                timeout=15,
            )
            resp.raise_for_status()
            contracts = resp.json().get("contracts", [])
            if isinstance(contracts, dict):
                contracts = [contracts]
            result = [
                {
                    "id": c.get("reference"),
                    "title": c.get("job__title"),
                    "status": c.get("status"),
                    "contractor_name": c.get("contractor__name"),
                    "client_name": c.get("buyer__name"),
                    "rate": c.get("hourly_pay_rate") or c.get("fixed_pay_amount_agreed"),
                    "start_date": c.get("start_date"),
                    "end_date": c.get("end_date"),
                }
                for c in contracts
            ]
            return json.dumps({"contracts": result, "count": len(result)})
        except Exception as e:
            return _handle_error("upwork_list_contracts", e)

    def get_contract(self, inp: dict) -> str:
        permission_error, contract_id = self._check(self.agent_id, self.PROVIDER_ID, "upwork_get_contract", inp, "contract_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/hr/v2/contracts/{contract_id}.json",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            c = resp.json().get("contract", {})
            return json.dumps({
                "id": c.get("reference"),
                "title": c.get("job__title"),
                "description": c.get("job__description", "")[:500],
                "status": c.get("status"),
                "contractor_name": c.get("contractor__name"),
                "contractor_id": c.get("contractor__reference"),
                "client_name": c.get("buyer__name"),
                "hourly_rate": c.get("hourly_pay_rate"),
                "fixed_amount": c.get("fixed_pay_amount_agreed"),
                "start_date": c.get("start_date"),
                "end_date": c.get("end_date"),
                "total_hours": c.get("total_hours"),
                "total_charges": c.get("total_charges"),
            })
        except Exception as e:
            return _handle_error("upwork_get_contract", e)

    def search_jobs(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "upwork_search_jobs", inp, "query")
        if permission_error: return permission_error
        try:
            params: dict = {
                "q": query,
                "paging": f"0;{inp.get('limit', 10)}",
                "sort": inp.get("sort", "recency"),
            }
            if inp.get("job_type"):
                params["job_type"] = inp["job_type"]
            if inp.get("budget_from"):
                params["budget"] = f"{inp['budget_from']};{inp.get('budget_to', '')}"
            resp = httpx.get(
                f"{_BASE}/jobs/v2/search/jobs.json",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("jobs", {}).get("job", [])
            if isinstance(jobs, dict):
                jobs = [jobs]
            result = [
                {
                    "id": j.get("id"),
                    "title": j.get("title"),
                    "snippet": j.get("snippet", "")[:300],
                    "job_type": j.get("job_type"),
                    "budget": j.get("budget"),
                    "skills": j.get("skills", {}).get("skill", []) if isinstance(j.get("skills"), dict) else [],
                    "date_created": j.get("date_created"),
                    "client_country": j.get("client", {}).get("country"),
                    "url": f"https://www.upwork.com/jobs/{j.get('id', '')}",
                }
                for j in jobs
            ]
            return json.dumps({
                "jobs": result,
                "count": len(result),
                "total": data.get("jobs", {}).get("@count", len(result)),
            })
        except Exception as e:
            return _handle_error("upwork_search_jobs", e)

    def search_talent(self, inp: dict) -> str:
        permission_error, query = self._check(self.agent_id, self.PROVIDER_ID, "upwork_search_talent", inp, "query")
        if permission_error: return permission_error
        try:
            params: dict = {
                "q": query,
                "paging": f"0;{inp.get('limit', 10)}",
            }
            if inp.get("hourly_rate_min"):
                params["rate"] = f"{inp['hourly_rate_min']};{inp.get('hourly_rate_max', '')}"
            resp = httpx.get(
                f"{_BASE}/profiles/v1/search/providers.json",
                headers=self._auth_headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            providers = data.get("providers", {}).get("provider", [])
            if isinstance(providers, dict):
                providers = [providers]
            result = [
                {
                    "id": p.get("ciphertext"),
                    "name": p.get("dev_full_name"),
                    "title": p.get("dev_blurb"),
                    "hourly_rate": p.get("dev_pay_rate"),
                    "country": p.get("dev_country"),
                    "score": p.get("dev_score"),
                    "total_hours": p.get("dev_tot_hours"),
                    "url": p.get("dev_profile_title"),
                    "skills": p.get("dev_skilltest", []),
                }
                for p in providers
            ]
            return json.dumps({"talent": result, "count": len(result)})
        except Exception as e:
            return _handle_error("upwork_search_talent", e)

    def list_rooms(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "upwork_list_rooms", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/messages/v3/rooms.json",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            rooms = data.get("rooms", [])
            result = [
                {
                    "id": r.get("id"),
                    "topic": r.get("topic"),
                    "last_message": r.get("last_message", {}).get("message", {}).get("body", "")[:200],
                    "unread": r.get("unread_count", 0),
                    "updated_at": r.get("updated_at"),
                }
                for r in rooms[:inp.get("limit", 20)]
            ]
            return json.dumps({"rooms": result, "count": len(result)})
        except Exception as e:
            return _handle_error("upwork_list_rooms", e)

    def get_messages(self, inp: dict) -> str:
        permission_error, room_id = self._check(self.agent_id, self.PROVIDER_ID, "upwork_get_messages", inp, "room_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/messages/v3/rooms/{room_id}/stories.json",
                headers=self._auth_headers,
                params={"limit": inp.get("limit", 20)},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            stories = data.get("stories", [])
            messages = [
                {
                    "id": s.get("id"),
                    "author": s.get("author_name"),
                    "body": s.get("message", {}).get("body", "")[:500],
                    "created_at": s.get("created_at"),
                }
                for s in stories
                if s.get("message")
            ]
            return json.dumps({"messages": messages, "count": len(messages), "room_id": room_id})
        except Exception as e:
            return _handle_error("upwork_get_messages", e)

    def list_teams(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "upwork_list_teams", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/hr/v2/teams.json",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            teams = data.get("teams", [])
            if isinstance(teams, dict):
                teams = [teams]
            result = [
                {"id": t.get("id"), "name": t.get("name"), "company_id": t.get("company_id")}
                for t in teams
            ]
            return json.dumps({"teams": result, "count": len(result)})
        except Exception as e:
            return _handle_error("upwork_list_teams", e)

    def get_time_report(self, inp: dict) -> str:
        permission_error, contract_id = self._check(self.agent_id, self.PROVIDER_ID, "upwork_get_time_report", inp, "contract_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{_BASE}/hr/v2/contracts/{contract_id}/time_reports.json",
                headers=self._auth_headers,
                params={"limit": inp.get("limit", 20)},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            entries = data.get("time_reports", [])
            if isinstance(entries, dict):
                entries = [entries]
            return json.dumps({"time_reports": entries, "count": len(entries), "contract_id": contract_id})
        except Exception as e:
            return _handle_error("upwork_get_time_report", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "upwork_get_profile",
                    "description": "Get the authenticated Upwork user's profile info.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "upwork_list_contracts",
                    "description": "List Upwork contracts (as client or freelancer).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by status: active (default), closed, paused."},
                            "team_ref": {"type": "string", "description": "Optional team reference to filter contracts."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "upwork_get_contract",
                    "description": "Get full details of a specific Upwork contract.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "contract_id": {"type": "string", "description": "Contract reference/ID from upwork_list_contracts."},
                        },
                        "required": ["contract_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "upwork_search_jobs",
                    "description": "Search for Upwork job postings by keyword.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search terms (e.g. 'React developer', 'data science')."},
                            "job_type": {"type": "string", "description": "Filter by type: hourly or fixed-price."},
                            "budget_from": {"type": "number", "description": "Minimum budget in USD."},
                            "budget_to": {"type": "number", "description": "Maximum budget in USD."},
                            "sort": {"type": "string", "description": "Sort order: recency (default) or relevance."},
                            "limit": {"type": "integer", "description": "Max results (default 10)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "upwork_search_talent",
                    "description": "Search for freelancers/talent on Upwork by skill or keyword.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search terms (e.g. 'Python developer', 'graphic designer')."},
                            "hourly_rate_min": {"type": "number", "description": "Minimum hourly rate in USD."},
                            "hourly_rate_max": {"type": "number", "description": "Maximum hourly rate in USD."},
                            "limit": {"type": "integer", "description": "Max results (default 10)."},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "upwork_list_rooms",
                    "description": "List Upwork message rooms (conversations with clients or freelancers).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max rooms to return (default 20)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "upwork_get_messages",
                    "description": "Get messages in a specific Upwork conversation room.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "room_id": {"type": "string", "description": "Room ID from upwork_list_rooms."},
                            "limit": {"type": "integer", "description": "Max messages to return (default 20)."},
                        },
                        "required": ["room_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "upwork_list_teams",
                    "description": "List Upwork teams the authenticated user manages or belongs to.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "upwork_get_time_report",
                    "description": "Get logged work hours (time report entries) for a specific Upwork contract.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "contract_id": {"type": "string", "description": "Contract reference/ID from upwork_list_contracts."},
                            "limit": {"type": "integer", "description": "Max entries to return (default 20)."},
                        },
                        "required": ["contract_id"],
                    },
                },
            },
        ]
        callables = {
            "upwork_get_profile": self.get_profile,
            "upwork_list_contracts": self.list_contracts,
            "upwork_get_contract": self.get_contract,
            "upwork_search_jobs": self.search_jobs,
            "upwork_search_talent": self.search_talent,
            "upwork_list_rooms": self.list_rooms,
            "upwork_get_messages": self.get_messages,
            "upwork_list_teams": self.list_teams,
            "upwork_get_time_report": self.get_time_report,
        }
        return tools, callables

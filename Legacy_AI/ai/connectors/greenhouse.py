import json
import httpx
from ai.connectors.base import BaseConnector

_BASE = "https://harvest.greenhouse.io/v1"

def _handle_error(tool_name, e):
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        if e.response.status_code == 429:
            return f"Rate limit exceeded in {tool_name}: please retry after a moment."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class GreenhouseConnector(BaseConnector):
    """Greenhouse Recruiting connector for candidates, jobs, applications, and org structure."""

    PROVIDER_ID = "greenhouse"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id=agent_id)
        self._token = access_token
        self._api_key = access_token

    @property
    def _auth_headers(self):
        return {"Accept": "application/json"}

    @_auth_headers.setter
    def _auth_headers(self, value: dict) -> None:
        pass

    def _auth(self):
        return (self._api_key, "")

    def greenhouse_list_candidates(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "greenhouse_list_candidates", inp)
        if permission_error: return permission_error
        params = {}
        if inp.get("per_page"):
            params["per_page"] = inp["per_page"]
        if inp.get("page"):
            params["page"] = inp["page"]
        if inp.get("email"):
            params["email"] = inp["email"]
        if inp.get("job_id"):
            params["job_id"] = inp["job_id"]
        try:
            r = httpx.get(f"{_BASE}/candidates", params=params, headers=self._auth_headers, auth=self._auth())
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("greenhouse_list_candidates", e)

    def greenhouse_get_candidate(self, inp: dict) -> str:
        permission_error, candidate_id = self._check(self.agent_id, self.PROVIDER_ID, "greenhouse_get_candidate", inp, "candidate_id")
        if permission_error: return permission_error
        try:
            r = httpx.get(f"{_BASE}/candidates/{candidate_id}", headers=self._auth_headers, auth=self._auth())
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("greenhouse_get_candidate", e)

    def greenhouse_list_applications(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "greenhouse_list_applications", inp)
        if permission_error: return permission_error
        params = {}
        if inp.get("per_page"):
            params["per_page"] = inp["per_page"]
        if inp.get("page"):
            params["page"] = inp["page"]
        if inp.get("job_id"):
            params["job_id"] = inp["job_id"]
        if inp.get("status"):
            params["status"] = inp["status"]
        try:
            r = httpx.get(f"{_BASE}/applications", params=params, headers=self._auth_headers, auth=self._auth())
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("greenhouse_list_applications", e)

    def greenhouse_list_jobs(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "greenhouse_list_jobs", inp)
        if permission_error: return permission_error
        params = {}
        if inp.get("per_page"):
            params["per_page"] = inp["per_page"]
        if inp.get("page"):
            params["page"] = inp["page"]
        if inp.get("status"):
            params["status"] = inp["status"]
        if inp.get("department_id"):
            params["department_id"] = inp["department_id"]
        try:
            r = httpx.get(f"{_BASE}/jobs", params=params, headers=self._auth_headers, auth=self._auth())
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("greenhouse_list_jobs", e)

    def greenhouse_list_users(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "greenhouse_list_users", inp)
        if permission_error: return permission_error
        params = {}
        if inp.get("per_page"):
            params["per_page"] = inp["per_page"]
        if inp.get("page"):
            params["page"] = inp["page"]
        if inp.get("email"):
            params["email"] = inp["email"]
        try:
            r = httpx.get(f"{_BASE}/users", params=params, headers=self._auth_headers, auth=self._auth())
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("greenhouse_list_users", e)

    def greenhouse_list_departments(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "greenhouse_list_departments", inp)
        if permission_error: return permission_error
        try:
            r = httpx.get(f"{_BASE}/departments", headers=self._auth_headers, auth=self._auth())
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("greenhouse_list_departments", e)

    def greenhouse_list_offices(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "greenhouse_list_offices", inp)
        if permission_error: return permission_error
        try:
            r = httpx.get(f"{_BASE}/offices", headers=self._auth_headers, auth=self._auth())
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("greenhouse_list_offices", e)

    def greenhouse_list_job_stages(self, inp: dict) -> str:
        permission_error, job_id = self._check(self.agent_id, self.PROVIDER_ID, "greenhouse_list_job_stages", inp, "job_id")
        if permission_error: return permission_error
        try:
            r = httpx.get(f"{_BASE}/job_stages", params={"job_id": job_id}, headers=self._auth_headers, auth=self._auth())
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("greenhouse_list_job_stages", e)

    def greenhouse_create_candidate(self, inp: dict) -> str:
        permission_error, first_name, last_name = self._check(self.agent_id, self.PROVIDER_ID, "greenhouse_create_candidate", inp, "first_name", "last_name")
        if permission_error: return permission_error
        email = inp.get("email")
        phone = inp.get("phone")
        company = inp.get("company")
        title = inp.get("title")
        user_id = inp.get("user_id", "1")
        body: dict = {
            "first_name": first_name,
            "last_name": last_name,
        }
        if email:
            body["email_addresses"] = [{"value": email, "type": "personal"}]
        if phone:
            body["phone_numbers"] = [{"value": phone, "type": "mobile"}]
        if company:
            body["company"] = company
        if title:
            body["title"] = title
        headers = {**self._auth_headers, "Content-Type": "application/json", "On-Behalf-Of": str(user_id)}
        try:
            r = httpx.post(f"{_BASE}/candidates", headers=headers, auth=self._auth(), json=body)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("greenhouse_create_candidate", e)

    def greenhouse_add_application(self, inp: dict) -> str:
        permission_error, candidate_id, job_id = self._check(self.agent_id, self.PROVIDER_ID, "greenhouse_add_application", inp, "candidate_id", "job_id")
        if permission_error: return permission_error
        user_id = inp.get("user_id", "1")
        body = {"job_id": job_id}
        headers = {**self._auth_headers, "Content-Type": "application/json", "On-Behalf-Of": str(user_id)}
        try:
            r = httpx.post(f"{_BASE}/candidates/{candidate_id}/applications", headers=headers, auth=self._auth(), json=body)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("greenhouse_add_application", e)

    def greenhouse_advance_application(self, inp: dict) -> str:
        permission_error, application_id, from_stage_id = self._check(self.agent_id, self.PROVIDER_ID, "greenhouse_advance_application", inp, "application_id", "from_stage_id")
        if permission_error: return permission_error
        user_id = inp.get("user_id", "1")
        body = {"from_stage_id": from_stage_id}
        headers = {**self._auth_headers, "Content-Type": "application/json", "On-Behalf-Of": str(user_id)}
        try:
            r = httpx.post(f"{_BASE}/applications/{application_id}/advance", headers=headers, auth=self._auth(), json=body)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("greenhouse_advance_application", e)

    def greenhouse_list_interviews(self, inp: dict) -> str:
        permission_error, application_id = self._check(self.agent_id, self.PROVIDER_ID, "greenhouse_list_interviews", inp, "application_id")
        if permission_error: return permission_error
        try:
            r = httpx.get(
                f"{_BASE}/scheduled_interviews",
                params={"application_id": application_id},
                headers=self._auth_headers,
                auth=self._auth(),
            )
            r.raise_for_status()
            interviews = r.json()
            result = [
                {
                    "id": iv.get("id"),
                    "start": iv.get("start", {}).get("date_time"),
                    "end": iv.get("end", {}).get("date_time"),
                    "status": iv.get("status"),
                    "interviewers": [{"name": i.get("name")} for i in iv.get("interviewers", [])],
                }
                for iv in (interviews if isinstance(interviews, list) else [])
            ]
            return json.dumps(result)
        except Exception as e:
            return _handle_error("greenhouse_list_interviews", e)

    def greenhouse_reject_application(self, inp: dict) -> str:
        permission_error, application_id = self._check(self.agent_id, self.PROVIDER_ID, "greenhouse_reject_application", inp, "application_id")
        if permission_error: return permission_error
        body: dict = {}
        if inp.get("rejection_reason_id"):
            body["rejection_reason_id"] = inp["rejection_reason_id"]
        if inp.get("rejection_notes"):
            body["rejection_notes"] = inp["rejection_notes"]
        user_id = inp.get("user_id", "1")
        headers = {**self._auth_headers, "Content-Type": "application/json", "On-Behalf-Of": str(user_id)}
        try:
            r = httpx.post(f"{_BASE}/applications/{application_id}/reject", headers=headers, auth=self._auth(), json=body)
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("greenhouse_reject_application", e)

    def greenhouse_list_scorecards(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "greenhouse_list_scorecards", inp)
        if permission_error: return permission_error
        params = {}
        if inp.get("application_id"):
            params["application_id"] = inp["application_id"]
        if inp.get("interview_id"):
            params["interview_id"] = inp["interview_id"]
        try:
            r = httpx.get(f"{_BASE}/scorecards", params=params, headers=self._auth_headers, auth=self._auth())
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("greenhouse_list_scorecards", e)

    def greenhouse_list_offers(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "greenhouse_list_offers", inp)
        if permission_error: return permission_error
        params = {}
        if inp.get("application_id"):
            params["application_id"] = inp["application_id"]
        if inp.get("status"):
            params["status"] = inp["status"]
        try:
            r = httpx.get(f"{_BASE}/offers", params=params, headers=self._auth_headers, auth=self._auth())
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("greenhouse_list_offers", e)

    def as_tools(self):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "greenhouse_list_candidates",
                    "description": "List candidates in Greenhouse. Optionally filter by email or job_id.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "per_page": {"type": "integer", "description": "Number of results per page (max 500)."},
                            "page": {"type": "integer", "description": "Page number for pagination."},
                            "email": {"type": "string", "description": "Filter candidates by email address."},
                            "job_id": {"type": "integer", "description": "Filter candidates by job ID."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "greenhouse_get_candidate",
                    "description": "Get details for a specific candidate by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "candidate_id": {"type": "integer", "description": "The ID of the candidate."},
                        },
                        "required": ["candidate_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "greenhouse_list_applications",
                    "description": "List job applications in Greenhouse. Filter by job_id or status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "per_page": {"type": "integer", "description": "Number of results per page (max 500)."},
                            "page": {"type": "integer", "description": "Page number for pagination."},
                            "job_id": {"type": "integer", "description": "Filter applications by job ID."},
                            "status": {"type": "string", "description": "Filter by status: active, rejected, hired."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "greenhouse_list_jobs",
                    "description": "List jobs in Greenhouse. Filter by status or department.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "per_page": {"type": "integer", "description": "Number of results per page (max 500)."},
                            "page": {"type": "integer", "description": "Page number for pagination."},
                            "status": {"type": "string", "description": "Filter by job status: open, closed, draft."},
                            "department_id": {"type": "integer", "description": "Filter jobs by department ID."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "greenhouse_list_users",
                    "description": "List users in the Greenhouse organization. Optionally filter by email.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "per_page": {"type": "integer", "description": "Number of results per page (max 500)."},
                            "page": {"type": "integer", "description": "Page number for pagination."},
                            "email": {"type": "string", "description": "Filter users by email address."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "greenhouse_list_departments",
                    "description": "List all departments in the Greenhouse organization.",
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
                    "name": "greenhouse_list_offices",
                    "description": "List all offices in the Greenhouse organization.",
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
                    "name": "greenhouse_list_job_stages",
                    "description": "List the interview stages for a specific job in Greenhouse.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "job_id": {"type": "integer", "description": "The ID of the job to retrieve stages for."},
                        },
                        "required": ["job_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "greenhouse_create_candidate",
                    "description": "Create a new candidate in Greenhouse.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "first_name": {"type": "string", "description": "Candidate's first name."},
                            "last_name": {"type": "string", "description": "Candidate's last name."},
                            "email": {"type": "string", "description": "Candidate's email address (optional)."},
                            "phone": {"type": "string", "description": "Candidate's phone number (optional)."},
                            "company": {"type": "string", "description": "Candidate's current company (optional)."},
                            "title": {"type": "string", "description": "Candidate's current job title (optional)."},
                            "user_id": {"type": "string", "description": "Greenhouse user ID to act on behalf of (optional, defaults to '1')."},
                        },
                        "required": ["first_name", "last_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "greenhouse_add_application",
                    "description": "Add a job application for an existing candidate in Greenhouse.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "candidate_id": {"type": "integer", "description": "The ID of the candidate."},
                            "job_id": {"type": "integer", "description": "The ID of the job to apply to."},
                            "user_id": {"type": "string", "description": "Greenhouse user ID to act on behalf of (optional, defaults to '1')."},
                        },
                        "required": ["candidate_id", "job_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "greenhouse_advance_application",
                    "description": "Advance an application to the next stage in Greenhouse.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "application_id": {"type": "integer", "description": "The ID of the application to advance."},
                            "from_stage_id": {"type": "integer", "description": "The current stage ID the application is being advanced from."},
                            "user_id": {"type": "string", "description": "Greenhouse user ID to act on behalf of (optional, defaults to '1')."},
                        },
                        "required": ["application_id", "from_stage_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "greenhouse_list_interviews",
                    "description": "List scheduled interviews for a specific application in Greenhouse.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "application_id": {"type": "integer", "description": "The ID of the application to list interviews for."},
                        },
                        "required": ["application_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "greenhouse_reject_application",
                    "description": "Reject a candidate's application in Greenhouse.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "application_id": {"type": "integer", "description": "The ID of the application to reject."},
                            "rejection_reason_id": {"type": "integer", "description": "ID of the rejection reason (optional)."},
                            "rejection_notes": {"type": "string", "description": "Notes about the rejection (optional)."},
                            "user_id": {"type": "string", "description": "Greenhouse user ID to act on behalf of (optional, defaults to '1')."},
                        },
                        "required": ["application_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "greenhouse_list_scorecards",
                    "description": "List interview scorecards in Greenhouse, optionally filtered by application or interview.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "application_id": {"type": "integer", "description": "Filter scorecards by application ID."},
                            "interview_id": {"type": "integer", "description": "Filter scorecards by interview ID."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "greenhouse_list_offers",
                    "description": "List job offers in Greenhouse, optionally filtered by application or status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "application_id": {"type": "integer", "description": "Filter offers by application ID."},
                            "status": {"type": "string", "description": "Filter by offer status: sent, accepted, rejected, or deprecated."},
                        },
                        "required": [],
                    },
                },
            },
        ]
        callables = {
            "greenhouse_list_candidates": self.greenhouse_list_candidates,
            "greenhouse_get_candidate": self.greenhouse_get_candidate,
            "greenhouse_list_applications": self.greenhouse_list_applications,
            "greenhouse_list_jobs": self.greenhouse_list_jobs,
            "greenhouse_list_users": self.greenhouse_list_users,
            "greenhouse_list_departments": self.greenhouse_list_departments,
            "greenhouse_list_offices": self.greenhouse_list_offices,
            "greenhouse_list_job_stages": self.greenhouse_list_job_stages,
            "greenhouse_create_candidate": self.greenhouse_create_candidate,
            "greenhouse_add_application": self.greenhouse_add_application,
            "greenhouse_advance_application": self.greenhouse_advance_application,
            "greenhouse_list_interviews": self.greenhouse_list_interviews,
            "greenhouse_reject_application": self.greenhouse_reject_application,
            "greenhouse_list_scorecards": self.greenhouse_list_scorecards,
            "greenhouse_list_offers": self.greenhouse_list_offers,
        }
        return tools, callables

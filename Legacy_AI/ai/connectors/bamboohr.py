import json
import httpx
from datetime import date, timedelta
from ai.connectors.base import BaseConnector


def _handle_error(tool_name, e):
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return f"Authorization error in {tool_name}: reconnect the connector."
        if e.response.status_code == 404:
            return f"Not found in {tool_name}."
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class BamboohrConnector(BaseConnector):
    """BambooHR connector for employee directory, time-off, job info, and reports."""

    PROVIDER_ID = "bamboohr"

    def __init__(self, access_token: str, agent_id: str = None) -> None:
        super().__init__(access_token, agent_id=agent_id)
        parts = access_token.split(":", 1)
        self._api_key = parts[0]
        self._subdomain = parts[1] if len(parts) > 1 else ""
        self._base = f"https://{self._subdomain}.bamboohr.com/api/gateway.php/{self._subdomain}/v1"

    @property
    def _auth_headers(self):
        return {"Accept": "application/json"}

    @_auth_headers.setter
    def _auth_headers(self, value: dict) -> None:
        pass

    def _auth(self):
        return (self._api_key, "x")

    def bamboohr_get_employee_directory(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "bamboohr_get_employee_directory", inp)
        if permission_error: return permission_error
        try:
            r = httpx.get(
                f"{self._base}/employees/directory",
                auth=self._auth(),
                headers=self._auth_headers,
                timeout=30,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("bamboohr_get_employee_directory", e)

    def bamboohr_get_employee(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "bamboohr_get_employee", inp)
        if permission_error: return permission_error
        employee_id = inp.get("employee_id", "")
        fields = inp.get("fields", "firstName,lastName,jobTitle,department,workEmail,mobilePhone,hireDate")
        try:
            r = httpx.get(
                f"{self._base}/employees/{employee_id}",
                params={"fields": fields},
                auth=self._auth(),
                headers=self._auth_headers,
                timeout=30,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("bamboohr_get_employee", e)

    def bamboohr_get_time_off_requests(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "bamboohr_get_time_off_requests", inp)
        if permission_error: return permission_error
        employee_id = inp.get("employee_id", "")
        start = inp.get("start", "")
        end = inp.get("end", "")
        params = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        try:
            r = httpx.get(
                f"{self._base}/employees/{employee_id}/timeOff/requests",
                params=params,
                auth=self._auth(),
                headers=self._auth_headers,
                timeout=30,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("bamboohr_get_time_off_requests", e)

    def bamboohr_get_time_off_types(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "bamboohr_get_time_off_types", inp)
        if permission_error: return permission_error
        try:
            r = httpx.get(
                f"{self._base}/time_off/types",
                auth=self._auth(),
                headers=self._auth_headers,
                timeout=30,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("bamboohr_get_time_off_types", e)

    def bamboohr_get_employee_job_info(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "bamboohr_get_employee_job_info", inp)
        if permission_error: return permission_error
        employee_id = inp.get("employee_id", "")
        try:
            r = httpx.get(
                f"{self._base}/employees/{employee_id}/jobInfo",
                auth=self._auth(),
                headers=self._auth_headers,
                timeout=30,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("bamboohr_get_employee_job_info", e)

    def bamboohr_get_employment_status(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "bamboohr_get_employment_status", inp)
        if permission_error: return permission_error
        employee_id = inp.get("employee_id", "")
        try:
            r = httpx.get(
                f"{self._base}/employees/{employee_id}/employmentStatus",
                auth=self._auth(),
                headers=self._auth_headers,
                timeout=30,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("bamboohr_get_employment_status", e)

    def bamboohr_run_custom_report(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "bamboohr_run_custom_report", inp)
        if permission_error: return permission_error
        fields = inp.get("fields", ["firstName", "lastName", "jobTitle", "department", "hireDate"])
        title = inp.get("title", "Custom Report")
        filters = inp.get("filters", {})
        payload = {"title": title, "fields": fields}
        if filters:
            payload["filters"] = filters
        try:
            r = httpx.post(
                f"{self._base}/reports/custom",
                params={"format": "json"},
                auth=self._auth(),
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("bamboohr_run_custom_report", e)

    def bamboohr_update_employee(self, inp: dict) -> str:
        permission_error, employee_id = self._check(self.agent_id, self.PROVIDER_ID, "bamboohr_update_employee", inp, "employee_id")
        if permission_error: return permission_error
        allowed_fields = {"firstName", "lastName", "workEmail", "department", "jobTitle", "location"}
        body = {k: v for k, v in inp.items() if k in allowed_fields}
        if not body:
            return "Error: at least one field to update is required (firstName, lastName, workEmail, department, jobTitle, location)."
        try:
            r = httpx.post(
                f"{self._base}/employees/{employee_id}/",
                auth=self._auth(),
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=30,
            )
            r.raise_for_status()
            return json.dumps({"updated": True, "id": employee_id})
        except Exception as e:
            return _handle_error("bamboohr_update_employee", e)

    def bamboohr_request_time_off(self, inp: dict) -> str:
        permission_error, employee_id, start_date, end_date, time_off_type_id = self._check(self.agent_id, self.PROVIDER_ID, "bamboohr_request_time_off", inp, "employee_id", "start_date", "end_date", "time_off_type_id")
        if permission_error: return permission_error
        note = inp.get("note", "")
        body = {
            "status": "requested",
            "start": start_date,
            "end": end_date,
            "timeOffTypeId": time_off_type_id,
            "notes": {"employee": {"note": note}},
        }
        try:
            r = httpx.put(
                f"{self._base}/time_off/requests/",
                auth=self._auth(),
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=30,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("bamboohr_request_time_off", e)

    def bamboohr_list_who_is_out(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "bamboohr_list_who_is_out", inp)
        if permission_error: return permission_error
        today = date.today().isoformat()
        start_date = inp.get("start_date", today)
        end_date = inp.get("end_date", (date.today() + timedelta(days=30)).isoformat())
        try:
            r = httpx.get(
                f"{self._base}/time_off/whos_out/",
                params={"start": start_date, "end": end_date},
                auth=self._auth(),
                headers=self._auth_headers,
                timeout=30,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("bamboohr_list_who_is_out", e)

    def bamboohr_get_employee_files(self, inp: dict) -> str:
        permission_error, employee_id = self._check(self.agent_id, self.PROVIDER_ID, "bamboohr_get_employee_files", inp, "employee_id")
        if permission_error: return permission_error
        try:
            r = httpx.get(
                f"{self._base}/employees/{employee_id}/files/view/",
                auth=self._auth(),
                headers=self._auth_headers,
                timeout=30,
            )
            r.raise_for_status()
            return json.dumps(r.json())
        except Exception as e:
            return _handle_error("bamboohr_get_employee_files", e)

    def bamboohr_add_employee(self, inp: dict) -> str:
        permission_error, first_name, last_name = self._check(self.agent_id, self.PROVIDER_ID, "bamboohr_add_employee", inp, "first_name", "last_name")
        if permission_error: return permission_error
        body: dict = {"firstName": first_name, "lastName": last_name}
        if inp.get("hire_date"):
            body["hireDate"] = inp["hire_date"]
        if inp.get("work_email"):
            body["workEmail"] = inp["work_email"]
        if inp.get("job_title"):
            body["jobTitle"] = inp["job_title"]
        if inp.get("department"):
            body["department"] = inp["department"]
        try:
            r = httpx.post(
                f"{self._base}/employees/",
                auth=self._auth(),
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=30,
            )
            r.raise_for_status()
            location = r.headers.get("Location", "")
            employee_id = location.rstrip("/").split("/")[-1] if location else None
            return json.dumps({"employee_id": employee_id, "status": "created"})
        except Exception as e:
            return _handle_error("bamboohr_add_employee", e)

    def as_tools(self):
        tool_defs = [
            {
                "type": "function",
                "function": {
                    "name": "bamboohr_get_employee_directory",
                    "description": "Retrieve the full employee directory from BambooHR.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "bamboohr_get_employee",
                    "description": "Get details for a specific employee by ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {"type": "string", "description": "The BambooHR employee ID."},
                            "fields": {"type": "string", "description": "Comma-separated list of fields to return. Defaults to common fields."},
                        },
                        "required": ["employee_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "bamboohr_get_time_off_requests",
                    "description": "Get time-off requests for a specific employee, optionally filtered by date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {"type": "string", "description": "The BambooHR employee ID."},
                            "start": {"type": "string", "description": "Start date in YYYY-MM-DD format."},
                            "end": {"type": "string", "description": "End date in YYYY-MM-DD format."},
                        },
                        "required": ["employee_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "bamboohr_get_time_off_types",
                    "description": "List all available time-off types configured in BambooHR.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "bamboohr_get_employee_job_info",
                    "description": "Get job information history for a specific employee.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {"type": "string", "description": "The BambooHR employee ID."},
                        },
                        "required": ["employee_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "bamboohr_get_employment_status",
                    "description": "Get employment status history for a specific employee.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {"type": "string", "description": "The BambooHR employee ID."},
                        },
                        "required": ["employee_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "bamboohr_run_custom_report",
                    "description": "Run a custom report in BambooHR with specified fields and optional filters.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fields": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of field names to include in the report.",
                            },
                            "title": {"type": "string", "description": "Title for the custom report."},
                            "filters": {"type": "object", "description": "Optional filter criteria for the report."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "bamboohr_update_employee",
                    "description": "Update an employee's profile fields in BambooHR.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {"type": "string", "description": "The BambooHR employee ID to update."},
                            "firstName": {"type": "string", "description": "Updated first name (optional)."},
                            "lastName": {"type": "string", "description": "Updated last name (optional)."},
                            "workEmail": {"type": "string", "description": "Updated work email address (optional)."},
                            "department": {"type": "string", "description": "Updated department name (optional)."},
                            "jobTitle": {"type": "string", "description": "Updated job title (optional)."},
                            "location": {"type": "string", "description": "Updated work location (optional)."},
                        },
                        "required": ["employee_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "bamboohr_request_time_off",
                    "description": "Submit a time-off request for an employee in BambooHR.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {"type": "string", "description": "The BambooHR employee ID."},
                            "start_date": {"type": "string", "description": "Start date of time off in YYYY-MM-DD format."},
                            "end_date": {"type": "string", "description": "End date of time off in YYYY-MM-DD format."},
                            "time_off_type_id": {"type": "integer", "description": "The ID of the time-off type (use bamboohr_get_time_off_types to look up IDs)."},
                            "note": {"type": "string", "description": "Optional note from the employee for the request."},
                        },
                        "required": ["employee_id", "start_date", "end_date", "time_off_type_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "bamboohr_list_who_is_out",
                    "description": "List employees who are out of office within a date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format (defaults to today)."},
                            "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format (defaults to today + 30 days)."},
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "bamboohr_get_employee_files",
                    "description": "Get the list of file categories and files for a specific employee in BambooHR.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {"type": "string", "description": "The BambooHR employee ID."},
                        },
                        "required": ["employee_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "bamboohr_add_employee",
                    "description": "Create a new employee (new hire) in BambooHR.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "first_name": {"type": "string", "description": "Employee's legal first name."},
                            "last_name": {"type": "string", "description": "Employee's legal last name."},
                            "hire_date": {"type": "string", "description": "Hire date in YYYY-MM-DD format (optional)."},
                            "work_email": {"type": "string", "description": "Work email address (optional)."},
                            "job_title": {"type": "string", "description": "Job title (optional)."},
                            "department": {"type": "string", "description": "Department name (optional)."},
                        },
                        "required": ["first_name", "last_name"],
                    },
                },
            },
        ]
        callables = {
            "bamboohr_get_employee_directory": self.bamboohr_get_employee_directory,
            "bamboohr_get_employee": self.bamboohr_get_employee,
            "bamboohr_get_time_off_requests": self.bamboohr_get_time_off_requests,
            "bamboohr_get_time_off_types": self.bamboohr_get_time_off_types,
            "bamboohr_get_employee_job_info": self.bamboohr_get_employee_job_info,
            "bamboohr_get_employment_status": self.bamboohr_get_employment_status,
            "bamboohr_run_custom_report": self.bamboohr_run_custom_report,
            "bamboohr_update_employee": self.bamboohr_update_employee,
            "bamboohr_request_time_off": self.bamboohr_request_time_off,
            "bamboohr_list_who_is_out": self.bamboohr_list_who_is_out,
            "bamboohr_get_employee_files": self.bamboohr_get_employee_files,
            "bamboohr_add_employee": self.bamboohr_add_employee,
        }
        return tool_defs, callables

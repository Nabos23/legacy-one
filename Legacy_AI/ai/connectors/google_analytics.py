import json
import httpx

from ai.connectors.base import BaseConnector


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Google Analytics account lacks permission "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their Google Analytics connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


class GoogleAnalyticsConnector(BaseConnector):
    """Google Analytics Data API v1 (GA4) connector."""

    PROVIDER_ID = "google-analytics"
    _BASE = "https://analyticsdata.googleapis.com/v1beta"
    _ADMIN_BASE = "https://analyticsadmin.googleapis.com/v1beta"

    def list_properties(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "ga_list_properties", inp)
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{self._ADMIN_BASE}/accountSummaries",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            summaries = resp.json().get("accountSummaries", [])
            properties = []
            for account in summaries:
                for prop in account.get("propertySummaries", []):
                    properties.append({
                        "property_id": prop.get("property", "").replace("properties/", ""),
                        "display_name": prop.get("displayName"),
                        "account": account.get("displayName"),
                    })
            return json.dumps({"properties": properties, "count": len(properties)})
        except Exception as e:
            return _handle_error("ga_list_properties", e)

    def get_report(self, inp: dict) -> str:
        permission_error, property_id = self._check(self.agent_id, self.PROVIDER_ID, "ga_get_report", inp, "property_id")
        if permission_error: return permission_error
        try:
            start_date = inp.get("start_date", "30daysAgo")
            end_date = inp.get("end_date", "today")
            dimensions = inp.get("dimensions", ["date"])
            metrics = inp.get("metrics", ["sessions", "activeUsers", "newUsers"])

            body = {
                "dateRanges": [{"startDate": start_date, "endDate": end_date}],
                "dimensions": [{"name": d} for d in dimensions],
                "metrics": [{"name": m} for m in metrics],
                "limit": inp.get("limit", 20),
            }
            resp = httpx.post(
                f"{self._BASE}/properties/{property_id}:runReport",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            rows = []
            dim_headers = [h["name"] for h in data.get("dimensionHeaders", [])]
            met_headers = [h["name"] for h in data.get("metricHeaders", [])]
            for row in data.get("rows", []):
                row_data = {}
                for i, val in enumerate(row.get("dimensionValues", [])):
                    row_data[dim_headers[i]] = val.get("value")
                for i, val in enumerate(row.get("metricValues", [])):
                    row_data[met_headers[i]] = val.get("value")
                rows.append(row_data)
            return json.dumps({"rows": rows, "count": len(rows), "date_range": f"{start_date} to {end_date}"})
        except Exception as e:
            return _handle_error("ga_get_report", e)

    def get_realtime(self, inp: dict) -> str:
        permission_error, property_id = self._check(self.agent_id, self.PROVIDER_ID, "ga_get_realtime", inp, "property_id")
        if permission_error: return permission_error
        try:
            body = {
                "dimensions": [{"name": d} for d in inp.get("dimensions", ["country"])],
                "metrics": [{"name": m} for m in inp.get("metrics", ["activeUsers"])],
                "limit": inp.get("limit", 10),
            }
            resp = httpx.post(
                f"{self._BASE}/properties/{property_id}:runRealtimeReport",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            rows = []
            dim_headers = [h["name"] for h in data.get("dimensionHeaders", [])]
            met_headers = [h["name"] for h in data.get("metricHeaders", [])]
            for row in data.get("rows", []):
                row_data = {}
                for i, val in enumerate(row.get("dimensionValues", [])):
                    row_data[dim_headers[i]] = val.get("value")
                for i, val in enumerate(row.get("metricValues", [])):
                    row_data[met_headers[i]] = val.get("value")
                rows.append(row_data)
            return json.dumps({"realtime_rows": rows, "count": len(rows)})
        except Exception as e:
            return _handle_error("ga_get_realtime", e)

    def get_top_pages(self, inp: dict) -> str:
        permission_error, property_id = self._check(self.agent_id, self.PROVIDER_ID, "ga_get_top_pages", inp, "property_id")
        if permission_error: return permission_error
        try:
            body = {
                "dateRanges": [{"startDate": inp.get("start_date", "30daysAgo"), "endDate": inp.get("end_date", "today")}],
                "dimensions": [{"name": "pagePath"}, {"name": "pageTitle"}],
                "metrics": [{"name": "screenPageViews"}, {"name": "activeUsers"}, {"name": "averageSessionDuration"}],
                "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}],
                "limit": inp.get("limit", 10),
            }
            resp = httpx.post(
                f"{self._BASE}/properties/{property_id}:runReport",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            pages = []
            for row in data.get("rows", []):
                dims = row.get("dimensionValues", [])
                mets = row.get("metricValues", [])
                pages.append({
                    "path": dims[0].get("value") if len(dims) > 0 else "",
                    "title": dims[1].get("value") if len(dims) > 1 else "",
                    "pageviews": mets[0].get("value") if len(mets) > 0 else "0",
                    "active_users": mets[1].get("value") if len(mets) > 1 else "0",
                    "avg_session_duration": mets[2].get("value") if len(mets) > 2 else "0",
                })
            return json.dumps({"top_pages": pages, "count": len(pages)})
        except Exception as e:
            return _handle_error("ga_get_top_pages", e)

    def get_metadata(self, inp: dict) -> str:
        permission_error, property_id = self._check(self.agent_id, self.PROVIDER_ID, "ga_get_metadata", inp, "property_id")
        if permission_error: return permission_error
        try:
            resp = httpx.get(
                f"{self._BASE}/properties/{property_id}/metadata",
                headers=self._auth_headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            dimensions = [d.get("apiName") for d in data.get("dimensions", [])]
            metrics = [m.get("apiName") for m in data.get("metrics", [])]
            return json.dumps({"dimensions": dimensions, "metrics": metrics})
        except Exception as e:
            return _handle_error("ga_get_metadata", e)

    def batch_run_reports(self, inp: dict) -> str:
        permission_error, property_id, requests = self._check(self.agent_id, self.PROVIDER_ID, "ga_batch_run_reports", inp, "property_id", "requests")
        if permission_error: return permission_error
        if len(requests) > 5:
            return "Error: a maximum of 5 report requests can be batched per call."
        try:
            report_requests = []
            for r in requests:
                report_requests.append({
                    "dateRanges": [{"startDate": r.get("start_date", "30daysAgo"), "endDate": r.get("end_date", "today")}],
                    "dimensions": [{"name": d} for d in r.get("dimensions", ["date"])],
                    "metrics": [{"name": m} for m in r.get("metrics", ["sessions"])],
                    "limit": r.get("limit", 20),
                })
            body = {"requests": report_requests}
            resp = httpx.post(
                f"{self._BASE}/properties/{property_id}:batchRunReports",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            reports = []
            for report in data.get("reports", []):
                dim_headers = [h["name"] for h in report.get("dimensionHeaders", [])]
                met_headers = [h["name"] for h in report.get("metricHeaders", [])]
                rows = []
                for row in report.get("rows", []):
                    row_data = {}
                    for i, val in enumerate(row.get("dimensionValues", [])):
                        row_data[dim_headers[i]] = val.get("value")
                    for i, val in enumerate(row.get("metricValues", [])):
                        row_data[met_headers[i]] = val.get("value")
                    rows.append(row_data)
                reports.append({"rows": rows})
            return json.dumps({"reports": reports, "count": len(reports)})
        except Exception as e:
            return _handle_error("ga_batch_run_reports", e)

    def check_compatibility(self, inp: dict) -> str:
        permission_error, property_id = self._check(self.agent_id, self.PROVIDER_ID, "ga_check_compatibility", inp, "property_id")
        if permission_error: return permission_error
        dimensions = inp.get("dimensions", [])
        metrics = inp.get("metrics", [])
        if not dimensions and not metrics:
            return "Error: at least one of 'dimensions' or 'metrics' is required."
        try:
            body = {
                "dimensions": [{"name": d} for d in dimensions],
                "metrics": [{"name": m} for m in metrics],
            }
            resp = httpx.post(
                f"{self._BASE}/properties/{property_id}:checkCompatibility",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            dim_compat = [{"name": d.get("apiName"), "compatibility": d.get("compatibility")} for d in data.get("dimensionCompatibilities", [])]
            met_compat = [{"name": m.get("apiName"), "compatibility": m.get("compatibility")} for m in data.get("metricCompatibilities", [])]
            return json.dumps({"dimensions": dim_compat, "metrics": met_compat})
        except Exception as e:
            return _handle_error("ga_check_compatibility", e)

    def get_traffic_sources(self, inp: dict) -> str:
        permission_error, property_id = self._check(self.agent_id, self.PROVIDER_ID, "ga_get_traffic_sources", inp, "property_id")
        if permission_error: return permission_error
        try:
            body = {
                "dateRanges": [{"startDate": inp.get("start_date", "30daysAgo"), "endDate": inp.get("end_date", "today")}],
                "dimensions": [{"name": "sessionSource"}, {"name": "sessionMedium"}],
                "metrics": [{"name": "sessions"}, {"name": "activeUsers"}, {"name": "conversions"}],
                "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
                "limit": inp.get("limit", 10),
            }
            resp = httpx.post(
                f"{self._BASE}/properties/{property_id}:runReport",
                headers={**self._auth_headers, "Content-Type": "application/json"},
                json=body,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            sources = []
            for row in data.get("rows", []):
                dims = row.get("dimensionValues", [])
                mets = row.get("metricValues", [])
                sources.append({
                    "source": dims[0].get("value") if len(dims) > 0 else "",
                    "medium": dims[1].get("value") if len(dims) > 1 else "",
                    "sessions": mets[0].get("value") if len(mets) > 0 else "0",
                    "active_users": mets[1].get("value") if len(mets) > 1 else "0",
                    "conversions": mets[2].get("value") if len(mets) > 2 else "0",
                })
            return json.dumps({"traffic_sources": sources, "count": len(sources)})
        except Exception as e:
            return _handle_error("ga_get_traffic_sources", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "ga_list_properties",
                    "description": "List all Google Analytics 4 properties the user has access to.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ga_get_report",
                    "description": "Run a custom Google Analytics report with specified dimensions and metrics.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_id": {"type": "string", "description": "GA4 property ID (numeric, e.g. '123456789')."},
                            "start_date": {"type": "string", "description": "Start date (e.g. '30daysAgo', '2024-01-01'). Default '30daysAgo'."},
                            "end_date": {"type": "string", "description": "End date (e.g. 'today', '2024-01-31'). Default 'today'."},
                            "dimensions": {"type": "array", "items": {"type": "string"}, "description": "Dimensions (e.g. ['date', 'country', 'deviceCategory'])."},
                            "metrics": {"type": "array", "items": {"type": "string"}, "description": "Metrics (e.g. ['sessions', 'activeUsers', 'newUsers', 'bounceRate'])."},
                            "limit": {"type": "integer", "description": "Max rows to return (default 20)."},
                        },
                        "required": ["property_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ga_get_realtime",
                    "description": "Get real-time active users and activity on the site right now.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_id": {"type": "string", "description": "GA4 property ID."},
                            "dimensions": {"type": "array", "items": {"type": "string"}, "description": "Dimensions (e.g. ['country', 'city', 'pagePath'])."},
                            "metrics": {"type": "array", "items": {"type": "string"}, "description": "Metrics (default ['activeUsers'])."},
                            "limit": {"type": "integer", "description": "Max rows (default 10)."},
                        },
                        "required": ["property_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ga_get_top_pages",
                    "description": "Get the top pages by page views for a GA4 property.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_id": {"type": "string", "description": "GA4 property ID."},
                            "start_date": {"type": "string", "description": "Start date (default '30daysAgo')."},
                            "end_date": {"type": "string", "description": "End date (default 'today')."},
                            "limit": {"type": "integer", "description": "Max pages to return (default 10)."},
                        },
                        "required": ["property_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ga_get_metadata",
                    "description": "Get the list of all dimension and metric API names available for reporting on a GA4 property (including custom dimensions/metrics).",
                    "parameters": {
                        "type": "object",
                        "properties": {"property_id": {"type": "string", "description": "GA4 property ID."}},
                        "required": ["property_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ga_batch_run_reports",
                    "description": "Run up to 5 GA4 reports in a single batch request, each with its own dimensions, metrics, and date range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_id": {"type": "string", "description": "GA4 property ID."},
                            "requests": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "dimensions": {"type": "array", "items": {"type": "string"}},
                                        "metrics": {"type": "array", "items": {"type": "string"}},
                                        "start_date": {"type": "string"},
                                        "end_date": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                                "description": "Array of report specs (max 5), each like {dimensions, metrics, start_date, end_date, limit}.",
                            },
                        },
                        "required": ["property_id", "requests"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ga_check_compatibility",
                    "description": "Check which dimensions and metrics can be combined together in a single GA4 report request before running it.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_id": {"type": "string", "description": "GA4 property ID."},
                            "dimensions": {"type": "array", "items": {"type": "string"}, "description": "Dimension names to check."},
                            "metrics": {"type": "array", "items": {"type": "string"}, "description": "Metric names to check."},
                        },
                        "required": ["property_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ga_get_traffic_sources",
                    "description": "Get sessions, active users, and conversions broken down by traffic source and medium (e.g. google/organic, direct/none).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "property_id": {"type": "string", "description": "GA4 property ID."},
                            "start_date": {"type": "string", "description": "Start date (default '30daysAgo')."},
                            "end_date": {"type": "string", "description": "End date (default 'today')."},
                            "limit": {"type": "integer", "description": "Max rows to return (default 10)."},
                        },
                        "required": ["property_id"],
                    },
                },
            },
        ]
        callables = {
            "ga_list_properties": self.list_properties,
            "ga_get_report": self.get_report,
            "ga_get_realtime": self.get_realtime,
            "ga_get_top_pages": self.get_top_pages,
            "ga_get_metadata": self.get_metadata,
            "ga_batch_run_reports": self.batch_run_reports,
            "ga_check_compatibility": self.check_compatibility,
            "ga_get_traffic_sources": self.get_traffic_sources,
        }
        return tools, callables

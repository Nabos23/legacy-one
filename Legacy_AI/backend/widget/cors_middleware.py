"""Dynamic, per-widget CORS for the public /widget/* surface.

Deliberately separate from the app-wide `CORSMiddleware` in backend/main.py,
which stays a small static allowlist for the authenticated dashboard origin.
/widget/* requests come from arbitrary third-party sites an org has
allowlisted for a specific widget, which a static list can't express.

Note this is a UX layer, not the security boundary -- CORS only controls
whether a browser lets its own JS read the response; it doesn't stop the
request from reaching the server. The real access control is
`get_widget_context` (backend/widget/dependencies.py), which every /widget/*
route depends on independently of what happens here.
"""

from starlette.datastructures import MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.widget.origins import is_origin_allowed

_WIDGET_PREFIX = "/widget/"
_ALLOWED_METHODS = "GET, POST, OPTIONS"
_ALLOWED_HEADERS = "Content-Type, X-Widget-Api-Key"


class DynamicWidgetCORSMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith(_WIDGET_PREFIX):
            await self.app(scope, receive, send)
            return

        headers = MutableHeaders(scope=scope)
        origin = headers.get("origin", "")
        allowed = await is_origin_allowed(origin) if origin else False

        if scope["method"] == "OPTIONS":
            response = Response(status_code=204)
            if allowed:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Methods"] = _ALLOWED_METHODS
                response.headers["Access-Control-Allow-Headers"] = _ALLOWED_HEADERS
                response.headers["Access-Control-Max-Age"] = "600"
            await response(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start" and allowed:
                response_headers = MutableHeaders(scope=message)
                response_headers["Access-Control-Allow-Origin"] = origin
                response_headers["Vary"] = "Origin"
            await send(message)

        await self.app(scope, receive, send_wrapper)

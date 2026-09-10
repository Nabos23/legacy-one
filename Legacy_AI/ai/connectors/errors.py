"""Shared detection for connector auth failures.

Every connector's `_handle_error` (duplicated per-file across ai/connectors/*.py)
returns the same consistent phrase on a 401/403 instead of raising an exception
— this detects that phrase centrally so callers can tell "this tool result is
actually an auth failure" without needing to touch any of the ~58 connector
files individually.
"""

_AUTH_PHRASE = "ask the user to reconnect"


def is_connector_auth_error(tool_result) -> bool:
    if not isinstance(tool_result, str):
        return False
    return _AUTH_PHRASE in tool_result.lower()

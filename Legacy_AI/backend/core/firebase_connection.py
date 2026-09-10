"""Helpers for Firebase database connection strings.

The API stores database targets as a single encrypted string. Firebase needs a
service account JSON object, so we encode that JSON into a URL-safe payload:

firebase://firestore?credentials=<base64url-json>&database_id=(default)
"""

from __future__ import annotations

import base64
import json
from urllib.parse import parse_qs, urlencode, urlparse


FIREBASE_SCHEME = "firebase"
FIRESTORE_TARGET = "firestore"
DEFAULT_FIRESTORE_DATABASE = "(default)"


class FirebaseConnectionError(ValueError):
    """Raised when a Firebase connection string is malformed."""


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def is_firebase_connection(connection_string: str) -> bool:
    return urlparse(connection_string).scheme.lower() == FIREBASE_SCHEME


def build_firestore_connection_string(
    service_account: dict,
    database_id: str = DEFAULT_FIRESTORE_DATABASE,
) -> str:
    """Build the encrypted-at-rest connection string used by the API."""
    payload = _b64url_encode(
        json.dumps(service_account, separators=(",", ":")).encode("utf-8")
    )
    query = urlencode({"credentials": payload, "database_id": database_id or DEFAULT_FIRESTORE_DATABASE})
    return f"{FIREBASE_SCHEME}://{FIRESTORE_TARGET}?{query}"


def parse_firestore_connection_string(connection_string: str) -> tuple[dict, str, str]:
    """Return (service_account_info, project_id, database_id)."""
    parsed = urlparse(connection_string)
    if parsed.scheme.lower() != FIREBASE_SCHEME:
        raise FirebaseConnectionError("Firebase connection strings must start with firebase://")
    if parsed.netloc.lower() != FIRESTORE_TARGET:
        raise FirebaseConnectionError("Only firebase://firestore connections are supported.")

    params = parse_qs(parsed.query, keep_blank_values=True)
    encoded_credentials = (params.get("credentials") or [""])[0]
    if not encoded_credentials:
        raise FirebaseConnectionError("Missing Firebase service account credentials.")

    try:
        service_account = json.loads(_b64url_decode(encoded_credentials).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise FirebaseConnectionError("Firebase credentials must be base64url-encoded JSON.") from exc

    required = ("project_id", "client_email", "private_key")
    missing = [name for name in required if not service_account.get(name)]
    if missing:
        raise FirebaseConnectionError(
            "Firebase service account JSON is missing: " + ", ".join(missing)
        )

    project_id = (params.get("project_id") or [service_account["project_id"]])[0]
    database_id = (params.get("database_id") or [DEFAULT_FIRESTORE_DATABASE])[0]
    return service_account, project_id, database_id or DEFAULT_FIRESTORE_DATABASE

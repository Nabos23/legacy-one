"""Check connectivity to the configured MongoDB (local or Atlas).

Usage (from project root):
    uv run python -m backend.scripts.test_connection
"""

import asyncio

from backend.db.database import DATABASE_NAME, MONGO_URL, client, db


def _redact(uri: str) -> str:
    """Hide the password when printing the connection string."""
    if "@" in uri and "//" in uri:
        scheme, rest = uri.split("//", 1)
        creds, host = rest.split("@", 1)
        user = creds.split(":", 1)[0]
        return f"{scheme}//{user}:****@{host}"
    return uri


async def main() -> None:
    print("MONGO_URL :", _redact(MONGO_URL))
    print("DATABASE  :", DATABASE_NAME)
    try:
        info = await client.server_info()
        names = await db.list_collection_names()
        print(f"Connected. MongoDB server version {info.get('version')}")
        print(f"Collections ({len(names)}):", sorted(names) or "(none yet)")
    except Exception as e:
        print("Connection FAILED:", type(e).__name__, e)


if __name__ == "__main__":
    asyncio.run(main())

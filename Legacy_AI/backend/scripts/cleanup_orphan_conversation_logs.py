"""
One-time cleanup: delete orphan conversation_log documents that were created
by the old stateless behaviour (session_id regenerated per message → one doc
per message instead of one doc per session).

A document is considered an orphan when its session_id does NOT exist in the
chat_sessions collection — meaning it was created with a throwaway uuid that
was never persisted as a real session.

Run from the project root:
    python -m backend.scripts.cleanup_orphan_conversation_logs
"""

import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "aiddb")


def main() -> None:
    client = MongoClient(MONGO_URL)
    db = client[DATABASE_NAME]

    conv_col = db["conversation_logs"]
    sess_col = db["chat_sessions"]

    # Collect all real session ids from chat_sessions.
    real_session_ids = set(
        doc["thread_id"] for doc in sess_col.find({}, {"thread_id": 1})
    )
    print(f"Found {len(real_session_ids)} real session(s) in chat_sessions.")

    # Count orphan docs before deletion.
    total = conv_col.count_documents({})
    orphan_count = conv_col.count_documents(
        {"session_id": {"$nin": list(real_session_ids)}}
    )
    print(f"conversation_logs total: {total} | orphans (no matching session): {orphan_count}")

    if orphan_count == 0:
        print("Nothing to delete.")
        return

    confirm = input(f"Delete {orphan_count} orphan document(s)? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    result = conv_col.delete_many(
        {"session_id": {"$nin": list(real_session_ids)}}
    )
    print(f"Deleted {result.deleted_count} orphan document(s).")
    client.close()


if __name__ == "__main__":
    main()

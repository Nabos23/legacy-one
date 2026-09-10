"""Smoke-test live HTTP APIs for agent-scoped conversation memory.

Usage (server must be running, e.g. uvicorn on :8765):
    uv run python -m backend.scripts.live_memory_api_test
"""

import asyncio
import uuid

import httpx
from dotenv import load_dotenv

from backend.db.database import agents_collection, conversation_logs_collection

load_dotenv()

BASE = "http://127.0.0.1:8765"


async def main() -> None:
    tag = uuid.uuid4().hex[:8]
    org_id = f"live-mem-org-{tag}"
    email = f"live-mem+{tag}@test.example.com"

    async with httpx.AsyncClient(base_url=BASE, timeout=120.0) as client:
        # Health
        r = await client.get("/")
        assert r.status_code == 200, r.text
        print("GET / -> ok")

        r = await client.get("/mongo-check")
        assert r.status_code == 200, r.text
        mongo_status = r.json().get("status", "")
        print("GET /mongo-check ->", "connected" if "Connected" in mongo_status else mongo_status)

        # Auth
        r = await client.post(
            "/auth/signup",
            json={
                "organization_id": org_id,
                "name": "Live Mem Tester",
                "email": email,
                "password": "Password123",
                "role": "admin",
            },
        )
        assert r.status_code == 201, r.text
        token = r.json()["access_token"]
        user_id = r.json()["user"]["id"]
        headers = {"Authorization": f"Bearer {token}"}
        print("POST /auth/signup -> user_id", user_id)

        # Agent for direct chat
        r = await client.post(
            "/agents",
            headers=headers,
            json={
                "name": "Live Support Agent",
                "prompt": "You are a concise support assistant.",
                "guardrails": "",
            },
        )
        assert r.status_code == 201, r.text
        agent_id = r.json()["id"]
        print("POST /agents -> agent_id", agent_id)

        # Direct chat — turn 1
        r = await client.post(
            "/chat",
            headers=headers,
            json={"agent_id": agent_id, "message": "Hello, what can you help with?"},
        )
        assert r.status_code == 200, r.text
        direct_body = r.json()
        session_id = direct_body["session_id"]
        print("POST /chat (direct) turn 1 -> session_id", session_id)
        print("  reply:", (direct_body.get("reply") or "")[:120])

        # Direct chat — turn 2 (resume session)
        r = await client.post(
            "/chat",
            headers=headers,
            json={
                "agent_id": agent_id,
                "message": "Can you remember I asked about help?",
                "session_id": session_id,
            },
        )
        assert r.status_code == 200, r.text
        print("POST /chat (direct) turn 2 -> ok")

        # Multi-agent session
        r = await client.post("/chat/session", headers=headers)
        assert r.status_code == 201, r.text
        thread_id = r.json()["thread_id"]
        print("POST /chat/session -> thread_id", thread_id)

        r = await client.post(
            "/chat/message",
            headers=headers,
            json={"thread_id": thread_id, "message": "Hi team, I need onboarding help."},
        )
        assert r.status_code == 200, r.text
        print("POST /chat/message -> response:", (r.json().get("response") or "")[:120])

    # Mongo verification
    direct_doc = await conversation_logs_collection.find_one(
        {"session_id": session_id, "user_id": user_id, "agent_id": agent_id}
    )
    assert direct_doc is not None, "direct chat conversation_logs doc missing"
    turns = [c for c in direct_doc.get("conversations", []) if c.get("type") == "turn"]
    assert len(turns) == 2, f"expected 2 turns, got {len(turns)}"
    assert direct_doc.get("total_messages") == 2
    assert "agent_name" not in direct_doc
    print(
        f"Mongo direct doc: total_messages={direct_doc['total_messages']}, "
        f"turns={len(turns)}, summaries={direct_doc.get('total_summaries', 0)}"
    )

    multi_docs = await conversation_logs_collection.find(
        {"session_id": thread_id, "user_id": user_id}
    ).to_list(length=10)
    assert len(multi_docs) >= 1, "multi-agent conversation_logs missing"
    for doc in multi_docs:
        assert "agent_name" not in doc
    print(f"Mongo multi-agent docs for session: {len(multi_docs)}")

    print("\nLive API memory smoke test PASSED")


if __name__ == "__main__":
    asyncio.run(main())

"""Live 55-turn memory test — direct chat + LangGraph multi-agent.

Sends questions one-by-one (like terminal_chat), then prints MongoDB state.
Compressions fire when total_messages >= 20 and total_messages % 10 == 0
(turns 20, 30, 40, 50, ...). Keeps last 10 turns each time.

Usage (server must run UPDATED code):
    uvicorn backend.main:app --reload --port 8001
    uv run python -m backend.scripts.live_22_turn_test --url http://127.0.0.1:8001
    uv run python -m backend.scripts.live_22_turn_test --direct-only
    uv run python -m backend.scripts.live_22_turn_test --multi-only
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import textwrap
import uuid
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

from backend.db.database import chat_sessions_collection, conversation_logs_collection
from backend.memory.sub_agent_memory import (
    COMPRESS_INTERVAL,
    KEEP_AFTER_COMPRESS,
    TURNS_BEFORE_COMPRESS,
)

load_dotenv()

# 55 support-style questions (answers come from live LLM)
QUESTIONS = [
    "Hi, I need help setting up my account.",
    "Yes, I confirmed my email but I can't log in.",
    "I did that and got a reset link. It says the link expired.",
    "Got it, I reset my password and I'm in now. How do I add team members?",
    "What roles are available?",
    "I want to give my colleague Admin access. Is that safe?",
    "Understood. How do I connect our Slack workspace?",
    "The Slack connection worked. Now how do I set up notifications?",
    "Can I limit notifications to business hours only?",
    "Great. How do I export our data for a monthly report?",
    "The export is taking a long time - is that normal?",
    "Got the export email. Now I want to set up an API integration.",
    "What's the rate limit on the API?",
    "We're on a Business plan. Can we increase it?",
    "How do we handle webhooks for real-time events?",
    "What events can we subscribe to?",
    "Is there retry logic if our webhook endpoint is down?",
    "Perfect. How do I see failed webhook deliveries?",
    "Can I test webhooks without real events?",
    "How do I rotate our API key without downtime?",
    "What's the best way to monitor API usage?",
    "Thanks, how do we upgrade to Enterprise?",
    "What billing cycles do you support for Enterprise?",
    "Can we get a dedicated account manager on Enterprise?",
    "How long does Enterprise onboarding usually take?",
    "Do you offer SSO with SAML or OIDC?",
    "Can we restrict API access by IP allowlist?",
    "Is there an audit log for admin actions?",
    "How do we export audit logs to our SIEM?",
    "Can we run the platform in our own VPC?",
    "What SLA do you offer for uptime?",
    "Can we get custom data retention policies?",
    # turns 33-55 — second compression block + beyond
    "How do I set up SCIM provisioning for users?",
    "Can we enforce MFA for all team members?",
    "What compliance certifications do you hold?",
    "Do you support HIPAA BAA agreements?",
    "How do I configure custom email domains?",
    "Can we white-label the customer portal?",
    "What analytics dashboards are available?",
    "How do I create custom report templates?",
    "Can I schedule reports to run automatically?",
    "How do I set up role-based data access?",
    "What backup and disaster recovery options exist?",
    "How often are backups taken?",
    "Can we restore data to a specific point in time?",
    "How do I contact support for a P1 incident?",
    "What is your average P1 response time?",
    "Can we get a sandbox environment for testing?",
    "How do I migrate data from our old system?",
    "Do you offer professional services for migration?",
    "What training resources do you provide for new admins?",
    "Can you walk me through the admin console basics?",
    "How do I set up department-level cost allocation?",
    "Can we get quarterly business review support from your team?",
    "Please give me a final recap of everything we covered today.",
]

MAX_QUESTIONS = len(QUESTIONS)


def _compression_turns(n_turns: int) -> list[int]:
    return list(range(TURNS_BEFORE_COMPRESS, n_turns + 1, COMPRESS_INTERVAL))


def _expected_final(n_turns: int) -> dict:
    """Compute expected Mongo state after n_turns messages."""
    compress_at = _compression_turns(n_turns)
    compressions = len(compress_at)
    last_compress = compress_at[-1] if compress_at else None
    if last_compress is None:
        return {
            "total_messages": n_turns,
            "total_summaries": 0,
            "turns_in_doc": n_turns,
            "since_compress": n_turns,
            "epoch": 1,
        }
    since = n_turns - last_compress
    return {
        "total_messages": n_turns,
        "total_summaries": compressions,
        "turns_in_doc": KEEP_AFTER_COMPRESS + since,
        "since_compress": since,
        "epoch": 1 + compressions,
    }


def _checkpoints(n_turns: int) -> set[int]:
    base = {19, 20, 21, 25, 29, 30, 39, 40, 41, 45, 50, n_turns}
    return {t for t in base if t <= n_turns}


def _print(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode(), flush=True)


def _wrap(label: str, text: str, width: int = 72) -> None:
    _print(f"\n{label}")
    for line in textwrap.wrap((text or "(empty)")[:500], width=width):
        _print(f"  {line}")


def _turn_count(doc: dict | None) -> int:
    if not doc:
        return 0
    return sum(1 for c in doc.get("conversations", []) if c.get("type") == "turn")


def _summary_text(doc: dict | None) -> str | None:
    if not doc:
        return None
    for entry in doc.get("conversations", []):
        if entry.get("type") == "summary":
            return entry.get("content")
    return None


async def _mongo_doc(session_id: str, user_id: str, agent_id: str) -> dict | None:
    return await conversation_logs_collection.find_one(
        {"session_id": session_id, "user_id": user_id, "agent_id": agent_id}
    )


async def _print_checkpoint(
    label: str,
    session_id: str,
    user_id: str,
    agent_id: str,
    turn_num: int,
    n_turns: int,
) -> None:
    doc = await _mongo_doc(session_id, user_id, agent_id)
    sess = await chat_sessions_collection.find_one({"thread_id": session_id})
    _print(f"\n--- {label} | turn {turn_num}/{n_turns} ---")
    if doc:
        _print(
            f"  total_messages={doc.get('total_messages')}  "
            f"turns_in_doc={_turn_count(doc)}  "
            f"summaries={doc.get('total_summaries')}  "
            f"since_compress={doc.get('new_messages_since_compression')}"
        )
        summary = _summary_text(doc)
        if summary:
            _wrap("  summary", summary[:300])
    else:
        _print("  (no conversation_logs doc yet)")
    if sess:
        _print(
            f"  session epoch={sess.get('epoch', 1)}  "
            f"lg_thread_id={sess.get('lg_thread_id', session_id)}"
        )


async def _post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict,
    json: dict,
    retries: int = 3,
) -> httpx.Response:
    last: httpx.Response | None = None
    for attempt in range(1, retries + 1):
        r = await client.post(url, headers=headers, json=json)
        if r.status_code < 500:
            return r
        last = r
        wait = 2 * attempt
        _print(f"  retry {attempt}/{retries} after {r.status_code}, waiting {wait}s...")
        await asyncio.sleep(wait)
    assert last is not None
    return last


async def _signup_and_agent(client: httpx.AsyncClient, tag: str) -> tuple[str, str, str]:
    org_id = f"live-{tag}"
    email = f"live+{tag}@test.example.com"
    r = await client.post(
        "/auth/signup",
        json={
            "organization_id": org_id,
            "name": "Live Memory Tester",
            "email": email,
            "password": "Password123",
            "role": "admin",
        },
    )
    if r.status_code != 201:
        raise RuntimeError(f"signup failed: {r.status_code} {r.text}")
    body = r.json()
    token = body["access_token"]
    user_id = body["user"]["id"]

    headers = {"Authorization": f"Bearer {token}"}
    r = await client.post(
        "/agents",
        headers=headers,
        json={
            "name": "Support Agent",
            "prompt": (
                "You are a knowledgeable SaaS support agent. "
                "Answer customer questions clearly and concisely in 2-4 sentences."
            ),
            "guardrails": "",
        },
    )
    if r.status_code != 201:
        raise RuntimeError(f"create agent failed: {r.status_code} {r.text}")
    agent_id = r.json()["id"]
    return user_id, agent_id, token


def _check_final(
    doc: dict, *, epoch: int | None = None, n_turns: int = MAX_QUESTIONS
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    exp = _expected_final(n_turns)

    if doc.get("total_messages", 0) != exp["total_messages"]:
        errors.append(
            f"expected total_messages={exp['total_messages']}, got {doc.get('total_messages')}"
        )
    if doc.get("total_summaries", 0) != exp["total_summaries"]:
        errors.append(
            f"expected total_summaries={exp['total_summaries']}, "
            f"got {doc.get('total_summaries')}"
        )
    turns = _turn_count(doc)
    if turns != exp["turns_in_doc"]:
        errors.append(
            f"expected turns_in_doc={exp['turns_in_doc']}, got {turns}"
        )
    since = doc.get("new_messages_since_compression", 0)
    if since != exp["since_compress"]:
        errors.append(
            f"expected since_compress={exp['since_compress']}, got {since}"
        )
    if not _summary_text(doc):
        errors.append("expected summary entry in conversations[]")

    if epoch is not None and epoch < exp["epoch"]:
        errors.append(f"expected epoch >= {exp['epoch']}, got {epoch}")

    return len(errors) == 0, errors


async def test_direct(
    client: httpx.AsyncClient, tag: str, delay: float, n_turns: int
) -> bool:
    questions = QUESTIONS[:n_turns]
    checkpoints = _checkpoints(n_turns)
    _print("\n" + "=" * 60)
    _print(f"DIRECT CHAT — POST /chat  ({n_turns} turns)")
    _print("=" * 60)

    user_id, agent_id, token = await _signup_and_agent(client, f"direct-{tag}")
    headers = {"Authorization": f"Bearer {token}"}
    session_id: str | None = None
    ok = True

    for turn_num, question in enumerate(questions, start=1):
        payload: dict = {"agent_id": agent_id, "message": question}
        if session_id:
            payload["session_id"] = session_id

        _print(f"\n[direct turn {turn_num}/{n_turns}] you> {question[:70]}...")
        r = await _post_with_retry(client, "/chat", headers=headers, json=payload)
        if r.status_code != 200:
            _print(f"  FAIL ({r.status_code}): {r.text[:200]}")
            ok = False
            break

        body = r.json()
        session_id = body["session_id"]
        _wrap(f"  bot (session {session_id[:8]}...)", body.get("reply", ""))

        if turn_num in checkpoints:
            await _print_checkpoint("direct", session_id, user_id, agent_id, turn_num, n_turns)

        if delay > 0 and turn_num < n_turns:
            await asyncio.sleep(delay)

    if not session_id:
        return False

    doc = await _mongo_doc(session_id, user_id, agent_id)
    if not doc:
        _print("\nDIRECT FAIL: no conversation_logs document")
        return False

    passed, errors = _check_final(doc, n_turns=n_turns)
    _print(
        f"\nDIRECT FINAL: total_messages={doc.get('total_messages')} "
        f"turns_in_doc={_turn_count(doc)} summaries={doc.get('total_summaries')} "
        f"since_compress={doc.get('new_messages_since_compression')}"
    )
    for err in errors:
        _print(f"  FAIL: {err}")
        ok = False
    if passed and ok:
        _print("  DIRECT PASS")
    return passed and ok


async def test_multi(
    client: httpx.AsyncClient, tag: str, delay: float, n_turns: int
) -> bool:
    questions = QUESTIONS[:n_turns]
    checkpoints = _checkpoints(n_turns)
    _print("\n" + "=" * 60)
    _print(
        f"LANGGRAPH MULTI-AGENT — POST /chat/session + /chat/message  ({n_turns} turns)"
    )
    _print("=" * 60)

    user_id, agent_id, token = await _signup_and_agent(client, f"multi-{tag}")
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post("/chat/session", headers=headers)
    if r.status_code != 201:
        _print(f"session create failed: {r.status_code} {r.text}")
        return False
    thread_id = r.json()["thread_id"]
    _print(f"session thread_id: {thread_id}")

    ok = True
    recorded_agent_id = agent_id

    for turn_num, question in enumerate(questions, start=1):
        _print(f"\n[multi turn {turn_num}/{n_turns}] you> {question[:70]}...")
        r = await _post_with_retry(
            client,
            "/chat/message",
            headers=headers,
            json={"thread_id": thread_id, "message": question},
        )
        if r.status_code != 200:
            _print(f"  FAIL ({r.status_code}): {r.text[:200]}")
            ok = False
            break

        body = r.json()
        _wrap("  bot", body.get("response", ""))

        if turn_num == 1:
            docs = await conversation_logs_collection.find(
                {"session_id": thread_id, "user_id": user_id}
            ).to_list(5)
            if docs:
                recorded_agent_id = docs[0]["agent_id"]
                _print(f"  recording agent_id: {recorded_agent_id}")

        if turn_num in checkpoints:
            await _print_checkpoint(
                "multi", thread_id, user_id, recorded_agent_id, turn_num, n_turns
            )

        if delay > 0 and turn_num < n_turns:
            await asyncio.sleep(delay)

    doc = await _mongo_doc(thread_id, user_id, recorded_agent_id)
    if not doc:
        docs = await conversation_logs_collection.find(
            {"session_id": thread_id, "user_id": user_id}
        ).to_list(5)
        doc = docs[0] if docs else None
        if doc:
            recorded_agent_id = doc["agent_id"]

    if not doc:
        _print("\nMULTI FAIL: no conversation_logs document")
        return False

    sess = await chat_sessions_collection.find_one({"thread_id": thread_id})
    epoch = sess.get("epoch", 1) if sess else 1

    passed, errors = _check_final(doc, epoch=epoch, n_turns=n_turns)
    _print(
        f"\nMULTI FINAL: total_messages={doc.get('total_messages')} "
        f"turns_in_doc={_turn_count(doc)} summaries={doc.get('total_summaries')} "
        f"since_compress={doc.get('new_messages_since_compression')} "
        f"epoch={epoch} agent_id={recorded_agent_id}"
    )
    for err in errors:
        _print(f"  FAIL: {err}")
        ok = False
    if passed and ok:
        _print("  MULTI PASS")
    return passed and ok


async def main() -> int:
    parser = argparse.ArgumentParser(description="Live memory compression test")
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--direct-only", action="store_true")
    parser.add_argument("--multi-only", action="store_true")
    parser.add_argument(
        "--max-turns",
        type=int,
        default=MAX_QUESTIONS,
        help=f"Number of turns to run (max {MAX_QUESTIONS})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Seconds between turns (default 1.5)",
    )
    args = parser.parse_args()
    n_turns = min(max(1, args.max_turns), MAX_QUESTIONS)

    tag = uuid.uuid4().hex[:8]
    exp = _expected_final(n_turns)
    _print(f"Live {n_turns}-turn test @ {args.url}")
    _print(
        f"Compress when total_messages >= {TURNS_BEFORE_COMPRESS} "
        f"and % {COMPRESS_INTERVAL} == 0, keep {KEEP_AFTER_COMPRESS}"
    )
    _print(
        f"After {n_turns} turns expect: "
        f"total_messages={exp['total_messages']}, turns_in_doc={exp['turns_in_doc']}, "
        f"since_compress={exp['since_compress']}, summaries={exp['total_summaries']}, "
        f"epoch={exp['epoch']}"
    )
    _print(f"Delay between turns: {args.delay}s")
    _print(f"Started: {datetime.now(timezone.utc).isoformat()}")

    async with httpx.AsyncClient(base_url=args.url, timeout=180.0) as client:
        r = await client.get("/mongo-check")
        if r.status_code != 200:
            _print("API not reachable")
            return 1

        results = []
        if not args.multi_only:
            results.append(await test_direct(client, tag, args.delay, n_turns))
        if not args.direct_only:
            results.append(await test_multi(client, tag, args.delay, n_turns))

    _print("\n" + "=" * 60)
    if all(results):
        _print("ALL TESTS PASSED")
        return 0
    _print("SOME TESTS FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

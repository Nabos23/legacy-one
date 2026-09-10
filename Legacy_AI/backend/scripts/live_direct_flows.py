"""Live direct-chat flow tests for test@gmail.com.

Flow 1 — Single agent, one session, 50+ turns.
Flow 2 — Multiple agents, one session, 100+ turns total (switch agent mid-session).

Usage:
    uvicorn backend.main:app --reload --port 8002
    uv run python -m backend.scripts.live_direct_flows --url http://127.0.0.1:8002
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

from backend.db.database import conversation_logs_collection

load_dotenv()

EMAIL = "test@gmail.com"
PASSWORD = "StrongPass123"

NEW_AGENTS = [
    {
        "name": "HR Agent",
        "prompt": "You are an HR specialist. Answer about leave, benefits, and policies in 2-4 sentences.",
        "guardrails": "",
    },
    {
        "name": "Sales Agent",
        "prompt": "You are a sales specialist. Answer pricing, demos, and plans in 2-4 sentences.",
        "guardrails": "",
    },
    {
        "name": "Technical Agent",
        "prompt": "You are a technical support engineer. Answer API, integrations, and dev questions in 2-4 sentences.",
        "guardrails": "",
    },
]

# 52 questions for single-agent flow
SINGLE_AGENT_QUESTIONS = [
    "Hi, I need help setting up my account.",
    "I can't log in after confirming my email.",
    "How do I reset my password?",
    "How do I invite team members?",
    "What roles are available?",
    "How do I connect Slack?",
    "How do I set up notifications?",
    "Can I limit notifications to business hours?",
    "How do I export monthly reports?",
    "Exports are slow — is that normal?",
    "How do I set up API integration?",
    "What is the API rate limit?",
    "Can Business plan increase rate limits?",
    "How do webhooks work?",
    "What webhook events exist?",
    "Is there webhook retry logic?",
    "How do I see failed webhook deliveries?",
    "Can I test webhooks without real events?",
    "How do I rotate API keys safely?",
    "How do I monitor API usage?",
    "How do we upgrade to Enterprise?",
    "What Enterprise billing cycles exist?",
    "Do we get a dedicated account manager?",
    "How long is Enterprise onboarding?",
    "Do you support SSO?",
    "Can we use IP allowlists for API?",
    "Is there an admin audit log?",
    "How do we export audit logs to SIEM?",
    "Can we run in our own VPC?",
    "What uptime SLA do you offer?",
    "Can we set custom data retention?",
    "How do I set up SCIM provisioning?",
    "Can we enforce MFA for all users?",
    "What compliance certs do you hold?",
    "Do you support HIPAA BAA?",
    "How do I configure custom email domains?",
    "Can we white-label the portal?",
    "What analytics dashboards exist?",
    "How do I create custom report templates?",
    "Can I schedule automatic reports?",
    "How do I set role-based data access?",
    "What backup options exist?",
    "How often are backups taken?",
    "Can we restore to a point in time?",
    "How do I contact support for P1?",
    "What is average P1 response time?",
    "Can we get a sandbox environment?",
    "How do I migrate from our old system?",
    "Do you offer migration professional services?",
    "What admin training is available?",
    "Walk me through the admin console basics.",
    "Give me a recap of everything we discussed.",
]

# Per-agent question pools for multi-agent flow (26 each × 4 = 104)
HR_QUESTIONS = [
    "What is our PTO policy?",
    "How many sick days do employees get?",
    "How do I request parental leave?",
    "When do benefits enrollment open?",
    "How do I add a dependent to health insurance?",
    "What is the 401k match?",
    "How do I submit an expense report?",
    "What is the remote work policy?",
    "How do I update my tax withholding?",
    "What holidays are observed?",
    "How do I report a workplace concern?",
    "What training is mandatory for new hires?",
    "How do performance reviews work?",
    "Can I work from another country temporarily?",
    "How do I change my direct deposit?",
    "What is the dress code policy?",
    "How do I refer a candidate?",
    "What is the referral bonus?",
    "How do I access the employee handbook?",
    "Who is my HR business partner?",
    "How do I request an employment verification letter?",
    "What is the bereavement leave policy?",
    "How do I enroll in the wellness program?",
    "What mental health resources are available?",
    "How do I file a grievance?",
    "Summarize my HR questions from this session.",
]

SALES_QUESTIONS = [
    "What plans do you offer for startups?",
    "How much does the Business plan cost?",
    "What is included in Enterprise?",
    "Can I get a custom quote?",
    "Do you offer annual discounts?",
    "How does the free trial work?",
    "What payment methods do you accept?",
    "Can we pay by invoice?",
    "What is your refund policy?",
    "How do I book a product demo?",
    "Who should attend the demo call?",
    "Do you have case studies for fintech?",
    "What ROI do customers typically see?",
    "How long is a typical sales cycle?",
    "Can we do a proof of concept?",
    "What does onboarding cost?",
    "Are professional services included?",
    "Do you offer partner discounts?",
    "What is the minimum contract term?",
    "Can we start month-to-month?",
    "How do seat licenses work?",
    "What happens if we exceed our seat count?",
    "Do you have a startup program?",
    "Can we get a security questionnaire filled?",
    "Who is our account executive?",
    "Summarize my sales questions from this session.",
]

TECH_QUESTIONS = [
    "How do I authenticate API requests?",
    "What SDKs do you provide?",
    "Is there a Postman collection?",
    "How do I handle pagination?",
    "What error codes should I expect?",
    "How do I set up OAuth for our app?",
    "Can I use webhooks for user events?",
    "What is the webhook signature format?",
    "How do I debug failed API calls?",
    "Is there a staging API environment?",
    "What are the IP ranges for webhooks?",
    "How do I increase API timeout limits?",
    "Can I batch API requests?",
    "How do I version my API integration?",
    "What breaking changes policy do you follow?",
    "How do I monitor API latency?",
    "Is there GraphQL support?",
    "How do I connect via MCP?",
    "What rate limit headers are returned?",
    "How do I request a rate limit increase?",
    "Can I whitelist our egress IPs?",
    "How do I rotate client secrets?",
    "What logs are available for API debugging?",
    "How do I report an API bug?",
    "What is your API deprecation timeline?",
    "Summarize my technical questions from this session.",
]

SUPPORT_QUESTIONS = [
    "I need help with my dashboard layout.",
    "Notifications are not arriving — what should I check?",
    "How do I reset a team member's MFA?",
    "Can I bulk import users via CSV?",
    "How do I customize email templates?",
    "Why is my export stuck at 90%?",
    "How do I delete a workspace?",
    "Can I recover a deleted project?",
    "How do I change our company logo?",
    "What browsers do you support?",
    "How do I enable dark mode for all users?",
    "Can I set default user permissions?",
    "How do I contact support on weekends?",
    "What info should I include in a support ticket?",
    "How do I check system status page?",
    "Is there a maintenance window this week?",
    "How do I enable two-factor for admins only?",
    "Can I restrict login by domain?",
    "How do I audit user login history?",
    "What mobile app features are available?",
    "How do I sync calendar integrations?",
    "Can I embed widgets in our intranet?",
    "How do I set up SSO just for admins?",
    "What data residency options exist?",
    "How do I request a feature?",
    "Summarize my support questions from this session.",
]


def _print(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode(), flush=True)


def _wrap(label: str, text: str) -> None:
    _print(f"\n{label}")
    for line in textwrap.wrap((text or "(empty)")[:400], width=72):
        _print(f"  {line}")


async def _login(client: httpx.AsyncClient) -> tuple[str, str, dict]:
    r = await client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"Login failed ({r.status_code}): {r.text}")
    body = r.json()
    token = body["access_token"]
    user = body["user"]
    return token, user["id"], {"Authorization": f"Bearer {token}"}


async def _ensure_agents(client: httpx.AsyncClient, headers: dict) -> list[dict]:
    r = await client.get("/agents", headers=headers, params={"limit": 50})
    if r.status_code != 200:
        raise RuntimeError(f"List agents failed: {r.text}")
    existing = {a["name"]: a for a in r.json().get("items", [])}

    for spec in NEW_AGENTS:
        if spec["name"] not in existing:
            cr = await client.post("/agents", headers=headers, json=spec)
            if cr.status_code != 201:
                raise RuntimeError(f"Create {spec['name']} failed: {cr.text}")
            existing[spec["name"]] = cr.json()
            _print(f"Created agent: {spec['name']} ({cr.json()['id']})")
        else:
            _print(f"Agent exists: {spec['name']} ({existing[spec['name']]['id']})")

    # Prefer Support Agent if present, else first agent
    support = existing.get("Support Agent")
    agents = []
    for name in ["Support Agent", "HR Agent", "Sales Agent", "Technical Agent"]:
        if name in existing:
            agents.append(existing[name])
    if not agents:
        agents = list(existing.values())
    if support and support not in agents:
        agents.insert(0, support)
    elif support:
        agents = [support] + [a for a in agents if a["name"] != "Support Agent"]

    return agents[:4]


async def _chat(
    client: httpx.AsyncClient,
    headers: dict,
    agent_id: str,
    message: str,
    session_id: str | None,
    retries: int = 3,
) -> tuple[str, str]:
    payload: dict = {"agent_id": agent_id, "message": message}
    if session_id:
        payload["session_id"] = session_id
    last = None
    for attempt in range(1, retries + 1):
        r = await client.post("/chat", headers=headers, json=payload)
        if r.status_code < 500:
            if r.status_code != 200:
                raise RuntimeError(f"Chat failed ({r.status_code}): {r.text[:300]}")
            body = r.json()
            return body["reply"], body["session_id"]
        last = r
        await asyncio.sleep(2 * attempt)
    raise RuntimeError(f"Chat failed after retries: {last.text if last else 'unknown'}")


async def _mongo_summary(session_id: str, user_id: str) -> None:
    docs = await conversation_logs_collection.find(
        {"session_id": session_id, "user_id": user_id}
    ).to_list(20)
    _print(f"\n  conversation_logs docs: {len(docs)}")
    for doc in docs:
        turns = sum(1 for c in doc.get("conversations", []) if c.get("type") == "turn")
        _print(
            f"    agent={doc.get('agent_id')} total_messages={doc.get('total_messages')} "
            f"turns_in_doc={turns} summaries={doc.get('total_summaries')} "
            f"since_compress={doc.get('new_messages_since_compression')}"
        )


async def flow_single_agent(
    client: httpx.AsyncClient,
    headers: dict,
    user_id: str,
    agent: dict,
    delay: float,
    min_turns: int,
) -> bool:
    _print("\n" + "=" * 60)
    _print(f"FLOW 1: Single agent ({agent['name']}) — {min_turns}+ turns, one session")
    _print("=" * 60)

    questions = SINGLE_AGENT_QUESTIONS[:min_turns]
    session_id = None
    for i, q in enumerate(questions, 1):
        _print(f"\n[flow1 {i}/{len(questions)}] you> {q[:65]}...")
        reply, session_id = await _chat(client, headers, agent["id"], q, session_id)
        _wrap("  bot", reply)
        if i in {19, 20, 21, 30, 40, 50, len(questions)}:
            await _mongo_summary(session_id, user_id)
        if delay and i < len(questions):
            await asyncio.sleep(delay)

    await _mongo_summary(session_id, user_id)
    doc = await conversation_logs_collection.find_one(
        {"session_id": session_id, "user_id": user_id, "agent_id": agent["id"]}
    )
    ok = doc and doc.get("total_messages", 0) >= min_turns
    _print(
        f"\nFLOW 1 RESULT: total_messages={doc.get('total_messages') if doc else 0} "
        f"(need >={min_turns}) -> {'PASS' if ok else 'FAIL'}"
    )
    return bool(ok)


async def flow_multi_agent(
    client: httpx.AsyncClient,
    headers: dict,
    user_id: str,
    agents: list[dict],
    delay: float,
    min_total_turns: int,
) -> bool:
    _print("\n" + "=" * 60)
    _print(
        f"FLOW 2: Multi-agent session — {min_total_turns}+ turns across "
        f"{len(agents)} agents (same session_id)"
    )
    _print("=" * 60)

    pools = {
        "HR Agent": HR_QUESTIONS,
        "Sales Agent": SALES_QUESTIONS,
        "Technical Agent": TECH_QUESTIONS,
        "Support Agent": SUPPORT_QUESTIONS,
    }
    # 26 turns per agent × 4 = 104
    turns_per_agent = max(26, min_total_turns // max(len(agents), 1))

    session_id = None
    total_sent = 0
    for agent in agents:
        name = agent["name"]
        qs = pools.get(name, SUPPORT_QUESTIONS)[:turns_per_agent]
        _print(f"\n--- Switching to {name} ({turns_per_agent} turns) ---")
        for i, q in enumerate(qs, 1):
            total_sent += 1
            _print(f"\n[flow2 {total_sent}] [{name}] you> {q[:60]}...")
            reply, session_id = await _chat(
                client, headers, agent["id"], q, session_id
            )
            _wrap("  bot", reply)
            if total_sent in {20, 30, 50, 75, 100, total_sent}:
                await _mongo_summary(session_id, user_id)
            if delay:
                await asyncio.sleep(delay)

    await _mongo_summary(session_id, user_id)
    sess_docs = await conversation_logs_collection.find(
        {"session_id": session_id, "user_id": user_id}
    ).to_list(20)
    grand_total = sum(d.get("total_messages", 0) for d in sess_docs)
    ok = grand_total >= min_total_turns and len(sess_docs) >= 2
    _print(
        f"\nFLOW 2 RESULT: agents_with_logs={len(sess_docs)} "
        f"grand_total_messages={grand_total} (need >={min_total_turns}) "
        f"-> {'PASS' if ok else 'FAIL'}"
    )
    return bool(ok)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8002")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--flow1-turns", type=int, default=52)
    parser.add_argument("--flow2-turns", type=int, default=104)
    parser.add_argument("--flow1-only", action="store_true")
    parser.add_argument("--flow2-only", action="store_true")
    args = parser.parse_args()

    _print(f"Direct-chat flow test @ {args.url}")
    _print(f"User: {EMAIL}")
    _print(f"Started: {datetime.now(timezone.utc).isoformat()}")

    async with httpx.AsyncClient(base_url=args.url, timeout=180.0) as client:
        r = await client.get("/mongo-check")
        if r.status_code != 200:
            _print("API not reachable")
            return 1

        _, user_id, headers = await _login(client)
        agents = await _ensure_agents(client, headers)
        if len(agents) < 2:
            _print("Need at least 2 agents for flow 2")
            return 1

        primary = agents[0]
        results = []
        if not args.flow2_only:
            results.append(
                await flow_single_agent(
                    client, headers, user_id, primary, args.delay, args.flow1_turns
                )
            )
        if not args.flow1_only:
            results.append(
                await flow_multi_agent(
                    client, headers, user_id, agents, args.delay, args.flow2_turns
                )
            )

    _print("\n" + "=" * 60)
    if all(results):
        _print("ALL DIRECT-CHAT FLOWS PASSED")
        return 0
    _print("SOME FLOWS FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

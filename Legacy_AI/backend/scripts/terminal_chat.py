"""Interactive terminal chat against the live API.

Talk to a single agent (direct) or the multi-agent supervisor from your terminal.
Session memory is stored in MongoDB conversation_logs automatically.

Prerequisites:
  1. API server running, e.g.:
       uvicorn backend.main:app --reload --port 8000
  2. A user account (login) or allow signup on first run

Usage (from project root):
    uv run python -m backend.scripts.terminal_chat
    uv run python -m backend.scripts.terminal_chat --url http://127.0.0.1:8000
    uv run python -m backend.scripts.terminal_chat --email admin@example.com --password "YourPass"
    uv run python -m backend.scripts.terminal_chat --mode multi
    uv run python -m backend.scripts.terminal_chat --agent-id 64f1a2b3c4d5e6f7a8b9c0d1

Environment (optional):
    CHAT_API_URL   Base URL (default http://127.0.0.1:8000)
    CHAT_EMAIL     Login email
    CHAT_PASSWORD  Login password

In-chat commands:
    /help              Show commands
    /quit, /exit       Leave
    /agents            List agents in your org
    /agent <id>        Switch direct-chat agent (direct mode)
    /mode direct|multi Switch chat mode (starts a new session)
    /session           Show current session / thread id
    /new               Start a fresh session
    /memory            Print conversation_logs from Mongo for this session
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import textwrap
import uuid
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_URL = os.getenv("CHAT_API_URL", "http://127.0.0.1:8000")
TIMEOUT = 120.0

HELP = """
Commands:
  /help                 Show this help
  /quit, /exit          Exit
  /agents               List available agents
  /agent <id>           Pick agent for direct mode
  /mode direct|multi    Switch mode (new session)
  /session              Show current session id
  /new                  Start a new session
  /memory               Show MongoDB conversation_logs for this session
"""


def _print(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode())


def _wrap(label: str, text: str, width: int = 78) -> None:
    _print(f"\n{label}")
    _print("-" * len(label))
    for line in textwrap.wrap(text or "(empty)", width=width):
        _print(f"  {line}")
    _print()


class TerminalChat:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=TIMEOUT)
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.org_id: Optional[str] = None
        self.mode = "direct"  # direct | multi
        self.agent_id: Optional[str] = None
        self.session_id: Optional[str] = None  # direct: session_id, multi: thread_id

    def _headers(self) -> dict:
        if not self.token:
            raise RuntimeError("Not authenticated")
        return {"Authorization": f"Bearer {self.token}"}

    def _api_ok(self) -> bool:
        try:
            r = self.client.get("/mongo-check")
            return r.status_code == 200 and "Connected" in r.json().get("status", "")
        except httpx.HTTPError as e:
            _print(f"Cannot reach API at {self.base_url}: {e}")
            return False

    def login(self, email: str, password: str) -> bool:
        r = self.client.post("/auth/login", json={"email": email, "password": password})
        if r.status_code != 200:
            _print(f"Login failed ({r.status_code}): {r.text}")
            return False
        body = r.json()
        self.token = body["access_token"]
        user = body["user"]
        self.user_id = user["id"]
        self.org_id = user["organization_id"]
        _print(f"Logged in as {user['email']} (org: {self.org_id})")
        return True

    def signup(self, email: str, password: str, name: str = "Terminal User") -> bool:
        org_id = f"term-org-{uuid.uuid4().hex[:8]}"
        r = self.client.post(
            "/auth/signup",
            json={
                "organization_id": org_id,
                "name": name,
                "email": email,
                "password": password,
                "role": "admin",
            },
        )
        if r.status_code != 201:
            _print(f"Signup failed ({r.status_code}): {r.text}")
            return False
        body = r.json()
        self.token = body["access_token"]
        user = body["user"]
        self.user_id = user["id"]
        self.org_id = user["organization_id"]
        _print(f"Signed up as {user['email']} (org: {self.org_id})")
        return True

    def list_agents(self) -> list[dict]:
        r = self.client.get("/agents", headers=self._headers(), params={"limit": 50})
        if r.status_code != 200:
            _print(f"Failed to list agents ({r.status_code}): {r.text}")
            return []
        return r.json().get("items", [])

    def pick_agent_interactive(self) -> None:
        agents = self.list_agents()
        if not agents:
            _print("No agents found. Create one via POST /agents or the admin UI.")
            create = input("Create a default Support Agent now? [y/N] ").strip().lower()
            if create == "y":
                r = self.client.post(
                    "/agents",
                    headers=self._headers(),
                    json={
                        "name": "Support Agent",
                        "prompt": "You are a helpful support assistant.",
                        "guardrails": "",
                    },
                )
                if r.status_code == 201:
                    self.agent_id = r.json()["id"]
                    _print(f"Created agent: {self.agent_id}")
                else:
                    _print(f"Create failed ({r.status_code}): {r.text}")
            return

        _print("\nAgents:")
        for i, a in enumerate(agents, 1):
            _print(f"  {i}. {a['name']}  ({a['id']})")
        choice = input("Pick agent number (or paste id): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(agents):
            self.agent_id = agents[int(choice) - 1]["id"]
        else:
            self.agent_id = choice
        _print(f"Using agent: {self.agent_id}")

    def start_multi_session(self) -> bool:
        r = self.client.post("/chat/session", headers=self._headers())
        if r.status_code != 201:
            _print(f"Session create failed ({r.status_code}): {r.text}")
            return False
        body = r.json()
        self.session_id = body["thread_id"]
        names = [a["name"] for a in body.get("available_agents", [])]
        _print(f"Multi-agent session: {self.session_id}")
        if names:
            _print(f"Available agents: {', '.join(names)}")
        return True

    def send_direct(self, message: str) -> Optional[str]:
        if not self.agent_id:
            _print("No agent selected. Use /agents or /agent <id>.")
            return None
        payload: dict = {"agent_id": self.agent_id, "message": message}
        if self.session_id:
            payload["session_id"] = self.session_id
        r = self.client.post("/chat", headers=self._headers(), json=payload)
        if r.status_code != 200:
            _print(f"Chat failed ({r.status_code}): {r.text}")
            return None
        body = r.json()
        self.session_id = body["session_id"]
        return body.get("reply", "")

    def send_multi(self, message: str) -> Optional[str]:
        if not self.session_id and not self.start_multi_session():
            return None
        r = self.client.post(
            "/chat/message",
            headers=self._headers(),
            json={"thread_id": self.session_id, "message": message},
        )
        if r.status_code != 200:
            _print(f"Message failed ({r.status_code}): {r.text}")
            return None
        return r.json().get("response", "")

    def send(self, message: str) -> Optional[str]:
        if self.mode == "multi":
            return self.send_multi(message)
        return self.send_direct(message)

    async def show_memory(self) -> None:
        if not self.session_id or not self.user_id:
            _print("No active session yet.")
            return
        from backend.db.database import conversation_logs_collection

        cursor = conversation_logs_collection.find(
            {"session_id": self.session_id, "user_id": self.user_id}
        )
        docs = await cursor.to_list(length=20)
        if not docs:
            _print("No conversation_logs documents for this session yet.")
            return
        for doc in docs:
            _print(f"\nagent_id: {doc.get('agent_id')}")
            _print(
                f"  total_messages={doc.get('total_messages')}  "
                f"total_summaries={doc.get('total_summaries')}  "
                f"since_compress={doc.get('new_messages_since_compression')}"
            )
            for entry in doc.get("conversations", []):
                if entry.get("type") == "summary":
                    _wrap("  [summary]", entry.get("content", ""))
                elif entry.get("type") == "turn":
                    _print(f"  [turn] you: {entry.get('human_message', '')[:80]}")
                    _print(f"         bot: {(entry.get('agent_message') or '')[:80]}")

    def handle_command(self, line: str) -> bool:
        """Return False to exit the REPL."""
        parts = line.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/quit", "/exit"):
            return False
        if cmd == "/help":
            _print(HELP)
        elif cmd == "/agents":
            for a in self.list_agents():
                _print(f"  {a['name']:20} {a['id']}")
        elif cmd == "/agent":
            if not arg:
                _print("Usage: /agent <agent_id>")
            else:
                self.agent_id = arg
                _print(f"Agent set to {self.agent_id}")
        elif cmd == "/mode":
            if arg not in ("direct", "multi"):
                _print("Usage: /mode direct|multi")
            else:
                self.mode = arg
                self.session_id = None
                _print(f"Mode: {self.mode} (session cleared)")
                if self.mode == "multi":
                    self.start_multi_session()
                elif not self.agent_id:
                    self.pick_agent_interactive()
        elif cmd == "/session":
            _print(f"mode={self.mode}  session_id={self.session_id or '(none)'}")
            if self.mode == "direct":
                _print(f"agent_id={self.agent_id or '(none)'}")
        elif cmd == "/new":
            self.session_id = None
            _print("New session — next message will start fresh.")
            if self.mode == "multi":
                self.start_multi_session()
        elif cmd == "/memory":
            asyncio.run(self.show_memory())
        else:
            _print(f"Unknown command: {cmd}. Type /help")
        return True

    def run_repl(self) -> None:
        _print(f"\nTerminal chat — {self.base_url}  mode={self.mode}")
        _print("Type a message to chat, or /help for commands.")
        _print("Tip: restart the API after code changes (uvicorn --reload).\n")

        if self.mode == "multi":
            self.start_multi_session()
        elif not self.agent_id:
            self.pick_agent_interactive()

        while True:
            try:
                line = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                _print("\nBye.")
                break
            if not line:
                continue
            if line.startswith("/"):
                if not self.handle_command(line):
                    break
                continue

            _print("... thinking")
            reply = self.send(line)
            if reply is not None:
                _wrap("bot", reply)
                if self.session_id:
                    _print(f"(session: {self.session_id} — /memory to inspect MongoDB)\n")

    def close(self) -> None:
        self.client.close()


def _prompt_credentials(
    email: Optional[str], password: Optional[str]
) -> tuple[str, str]:
    if not email:
        email = input("Email: ").strip()
    if not password:
        import getpass

        password = getpass.getpass("Password: ")
    return email, password


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive terminal chat")
    parser.add_argument("--url", default=DEFAULT_URL, help="API base URL")
    parser.add_argument("--email", default=os.getenv("CHAT_EMAIL"))
    parser.add_argument("--password", default=os.getenv("CHAT_PASSWORD"))
    parser.add_argument("--mode", choices=("direct", "multi"), default="direct")
    parser.add_argument("--agent-id", default=None, help="Agent id for direct mode")
    parser.add_argument("--signup", action="store_true", help="Register a new user")
    args = parser.parse_args()

    chat = TerminalChat(args.url)
    try:
        if not chat._api_ok():
            _print("Start the server first:")
            _print("  uvicorn backend.main:app --reload --port 8000")
            sys.exit(1)

        email, password = _prompt_credentials(args.email, args.password)
        if args.signup:
            ok = chat.signup(email, password)
        else:
            ok = chat.login(email, password)
            if not ok:
                _print("Try again with --signup to create a new account.")
                sys.exit(1)

        chat.mode = args.mode
        chat.agent_id = args.agent_id
        chat.run_repl()
    finally:
        chat.close()


if __name__ == "__main__":
    main()

"""Seed the `tool_registry` collection with the built-in function tools.

Adds the first-party tools an agent can be given:

* ``query_db``        — run a query against the org's connected data source.
* ``search_internet`` — search the web for info not in the org database.
* ``ask_human``       — pause the workflow and ask the user (human-in-the-loop).

These are catalog entries only. Most are attached to an agent on demand via
POST /tools. Entries flagged ``auto_assign: True`` (e.g. ``ask_human``) are
attached automatically to every agent at creation time (see
backend.agent.services._auto_assign_default_tools).

A registry entry may carry a ``prompt`` block; when the tool is assigned, that
block is composed into the agent's stored ``tool_prompt`` (see
regenerate_tool_prompt), so all tool guidance lives in the agent's system prompt
rather than being injected at runtime.

Usage (from project root):
    uv run python -m backend.scripts.seed_function_tools

Re-running is safe: each entry is upserted by `name`.
"""

from datetime import datetime, timezone

from pymongo import MongoClient

from backend.db import constants as c
from backend.db.database import DATABASE_NAME, MONGO_URL

FUNCTION_TOOLS = [
    {
        "name": "query_db",
        # Must be "db_query" (not "function"): chat.services._has_db_query_tool
        # keys off this to pre-fetch and inject the DB schema per message. With
        # any other type the agent runs query_db blind, guessing table/col names.
        "type": "db_query",
        "description": (
            "Execute a database query against the organization's connected data "
            "source. Use this tool when information is expected to exist in the "
            "organization's database."
        ),
        "tool_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The database query or natural language request to retrieve data.",
                },
                "reason": {
                    "type": "string",
                    "description": "Explanation of why this database query is required and what information is being sought.",
                },
            },
            "required": ["query", "reason"],
            "additionalProperties": False,
        },
        "is_active": True,
    },
    {
        "name": "search_internet",
        "type": "function",
        "handler": "search_internet",
        "description": (
            "Search the internet for information that is not available in the "
            "organization's database or requires external knowledge."
        ),
        "tool_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to execute on the internet.",
                },
                "reason": {
                    "type": "string",
                    "description": "Explanation of why an internet search is needed and what information is expected.",
                },
            },
            "required": ["query", "reason"],
            "additionalProperties": False,
        },
        "is_active": True,
    },
    {
        "name": "ask_human",
        # Special type: the handler raises HumanInterruptException, which the
        # orchestration runtime catches to pause the run (waiting_for_human).
        "type": "human_in_loop",
        "handler": "ask_human",
        # Attached to EVERY agent automatically at creation (unlike query_db /
        # search_internet, which are opt-in).
        "auto_assign": True,
        "description": (
            "Pause the workflow and ask the user one specific clarifying question. "
            "Use when you are missing information required to complete your task."
        ),
        "tool_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The single, specific question to ask the user.",
                },
            },
            "required": ["question"],
            "additionalProperties": False,
        },
        # Composed into agent.tool_prompt at assignment time.
        "prompt": (
            "## Human-in-the-loop (ask_human) — REQUIRED behavior\n"
            "You have the `ask_human` tool. It is the ONLY way to reach the user: a "
            "plain-text question in your reply does NOT reach them and does NOT "
            "pause the workflow. Only calling `ask_human` pauses the run.\n"
            "\n"
            "STOP and call `ask_human` (instead of writing a normal reply) whenever "
            "ANY of these is true:\n"
            "- The request does not clearly and specifically instruct YOU to perform "
            "your role's action (e.g. you are the email step but no email was "
            "requested, or it is unclear whether/what to send/create/update).\n"
            "- You are missing any detail needed to act (recipient, subject, body, "
            "target sheet, ticket project, values, IDs, dates, etc.).\n"
            "- You are unsure how to proceed for any reason.\n"
            "\n"
            "Hard rules:\n"
            "- NEVER guess, invent, or use placeholder values — ask instead.\n"
            "- NEVER substitute a text summary for your action, and NEVER just "
            "repeat or re-summarize what previous agents already produced. If you "
            "have nothing concrete to act on, call `ask_human` to confirm what the "
            "user wants you to do — do not answer as a general chatbot.\n"
            "- Only perform your action (by calling your real tool) when the request "
            "clearly requires it AND you have every required detail. Never claim an "
            "action is done unless its tool call actually returned success."
        ),
        "is_active": True,
    },
    {
        "name": "generate_pdf",
        "type": "function",
        "description": (
            "Convert an written Markdown report into a polished PDF file and return a download link. Do not add any prefix or additional text to the download link. only ouput the report link."
            "You must generate the full report yourself first, in "
            "Markdown (headings, bullet lists, tables, etc. are all supported), "
            "then pass that finished Markdown text to this tool."
        ),
        "tool_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The finished report content, written in Markdown.",
                },
                "reason": {
                    "type": "string",
                    "description": "Explanation of why this report is being generated.",
                },
            },
            "required": ["content", "reason"],
            "additionalProperties": False,
        },
        "is_active": True,
    },
]


def main() -> None:
    registry = MongoClient(MONGO_URL)[DATABASE_NAME][c.TOOL_REGISTRY_COLLECTION]
    now = datetime.now(timezone.utc)

    for tool in FUNCTION_TOOLS:
        set_fields = {k: v for k, v in tool.items() if k != "name"}
        set_fields["is_deleted"] = False
        registry.update_one(
            {"name": tool["name"]},
            {
                "$set": set_fields,
                "$setOnInsert": {"name": tool["name"], "created_at": now},
            },
            upsert=True,
        )
        print(f"Seeded tool_registry entry '{tool['name']}' (type={tool['type']}).")


if __name__ == "__main__":
    main()
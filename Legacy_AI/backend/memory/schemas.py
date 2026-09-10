from datetime import datetime
from typing import Dict, List, Literal, Optional, Tuple, Union

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field


class SummaryEntry(BaseModel):
    type: Literal["summary"] = "summary"
    content: str
    timestamp: datetime


class TurnEntry(BaseModel):
    type: Literal["turn"] = "turn"
    human_message: str
    agent_message: str
    timestamp: datetime
    tool_called: bool = False
    tool_name: Optional[str] = None
    # Connector tool calls that failed on auth this turn — each entry:
    # {"fn_name", "connector_id", "provider_id", "display_name"}. Lets the
    # frontend show a "Reconnect" action even after the conversation reloads.
    auth_errors: List[Dict[str, Optional[str]]] = Field(default_factory=list)


ConversationEntry = Union[SummaryEntry, TurnEntry]


class ConversationDocument(BaseModel):
    session_id: str
    user_id: str
    organization_id: str
    agent_id: str
    conversations: list[ConversationEntry] = Field(default_factory=list)
    total_messages: int = 0
    total_summaries: int = 0
    new_messages_since_compression: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def _parse_entry(raw: dict) -> ConversationEntry:
    if raw.get("type") == "summary":
        return SummaryEntry(**raw)
    return TurnEntry(**raw)


def split_entries(
    conversations: list[ConversationEntry],
) -> Tuple[Optional[SummaryEntry], list[TurnEntry]]:
    summary: Optional[SummaryEntry] = None
    turns: list[TurnEntry] = []
    for entry in conversations:
        if isinstance(entry, SummaryEntry) or entry.type == "summary":
            summary = entry if isinstance(entry, SummaryEntry) else SummaryEntry(**entry.model_dump())
        else:
            turns.append(entry if isinstance(entry, TurnEntry) else TurnEntry(**entry.model_dump()))
    return summary, turns


def turns_to_langchain(turns: list[TurnEntry]) -> list:
    messages: list = []
    for turn in turns:
        messages.append(HumanMessage(content=turn.human_message))
        messages.append(AIMessage(content=turn.agent_message))
    return messages


def doc_from_mongo(doc: dict) -> ConversationDocument:
    conversations = [_parse_entry(e) for e in doc.get("conversations", [])]
    return ConversationDocument(
        session_id=doc["session_id"],
        user_id=doc["user_id"],
        organization_id=doc["organization_id"],
        agent_id=doc["agent_id"],
        conversations=conversations,
        total_messages=doc.get("total_messages", 0),
        total_summaries=doc.get("total_summaries", 0),
        new_messages_since_compression=doc.get("new_messages_since_compression", 0),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


def entries_to_mongo(conversations: list[ConversationEntry]) -> list[dict]:
    return [e.model_dump() for e in conversations]

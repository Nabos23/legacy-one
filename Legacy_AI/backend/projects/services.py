import asyncio
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import HTTPException, UploadFile, status
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from ai.tracing.tracer import AgentTracer
from backend.agent.services import (
    _fetch_connectors_summary,
    _validate_allowed_user_ids,
    _validate_org_exists,
    _validate_team_id,
    bind_runtime_db_tools,
    build_agent_visibility_clauses,
    sync_connector_permissions,
)
from backend.chat.auth_error_sink import get_auth_errors, reset_auth_errors
from backend.chat.event_sink import set_event_sink
from backend.chat.graph import AgentRuntime, get_or_build_single_agent_graph
from backend.chat.services import (
    _set_chat_name_if_unset,
    load_agent_connectors,
)
from backend.chat.tracing_ctx import set_tracer
from backend.core.config import settings
from backend.core.softdelete import NOT_DELETED, soft_delete_update
from backend.core.uploads import delete_stored_upload, save_image_upload
from backend.db.database import (
    agent_permissions_collection,
    chat_sessions_collection,
    connector_registry_collection,
    db,
    db_connections_collection,
    project_chats_collection,
    projects_collection,
    tool_registry_collection,
    tools_permissions_registry_collection,
)
from backend.memory.conversation_store import ConversationStore
from backend.memory.sub_agent_memory import SubAgentMemory
from backend.projects.models import ProjectFile
from backend.projects.schemas import (
    ProjectChatMessagePublic,
    ProjectChatResponse,
    ProjectCreate,
    ProjectFilePublic,
    ProjectPublic,
    ProjectUpdate,
)
from backend.projects.validators import validate_object_id

logger = logging.getLogger("projects.services")

PROJECT_SORTABLE_FIELDS = {"name", "created_at"}

_conversation_store = ConversationStore(db=db)
_sub_agent_memory = SubAgentMemory(store=_conversation_store, model=settings.DEFAULT_MODEL)


def _to_file_public(f: dict | ProjectFile) -> ProjectFilePublic:
    """Map a stored file dict/model to ProjectFilePublic."""
    if isinstance(f, dict):
        return ProjectFilePublic(
            id=str(f.get("id")),
            filename=f.get("filename", "unknown"),
            original_filename=f.get("original_filename", f.get("filename", "unknown")),
            file_type=f.get("file_type", "other"),
            file_size=f.get("file_size", 0),
            content=f.get("content"),
            content_summary=f.get("content_summary"),
            uploaded_by=f.get("uploaded_by", ""),
            uploaded_at=f.get("uploaded_at") or datetime.now(timezone.utc),
        )
    return ProjectFilePublic(
        id=f.id,
        filename=f.filename,
        original_filename=f.original_filename,
        file_type=f.file_type,
        file_size=f.file_size,
        content=f.content,
        content_summary=f.content_summary,
        uploaded_by=f.uploaded_by,
        uploaded_at=f.uploaded_at,
    )




def _to_public(
    doc: dict,
    connectors_map: dict | None = None,
    connector_permissions: dict | None = None,
) -> ProjectPublic:
    """Map a MongoDB project document to the public schema."""
    conn_list = []
    if connectors_map:
        for cid in doc.get("connector_ids", []):
            if cid in connectors_map:
                conn_list.append(connectors_map[cid])

    files_list = [_to_file_public(f) for f in doc.get("files", [])]

    return ProjectPublic(
        id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        name=doc["name"],
        description=doc.get("description"),
        system_prompt=doc.get("system_prompt") or "",
        guardrails=doc.get("guardrails") or "",
        tool_ids=doc.get("tool_ids", []),
        connector_ids=doc.get("connector_ids", []),
        connectors=conn_list,
        connector_permissions=connector_permissions,
        knowledge_base_ids=doc.get("knowledge_base_ids", []),
        files=files_list,
        created_by=doc["created_by"],
        created_at=doc["created_at"],
        updated_at=doc.get("updated_at"),
        owner_scope=doc.get("owner_scope", "organization"),
        allowed_user_ids=doc.get("allowed_user_ids", []),
        team_id=doc.get("team_id"),
    )


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

async def create_project(
    payload: ProjectCreate,
    created_by: str,
    owner_scope: str = "organization",
    allowed_user_ids: Optional[List[str]] = None,
    team_id: Optional[str] = None,
) -> ProjectPublic:
    """Create a new project."""
    await _validate_org_exists(payload.organization_id)
    cleaned_allowed_user_ids: List[str] = []
    if owner_scope == "selected_users":
        cleaned_allowed_user_ids = await _validate_allowed_user_ids(
            payload.organization_id, allowed_user_ids or []
        )
    cleaned_team_id: Optional[str] = None
    if owner_scope == "team":
        cleaned_team_id = await _validate_team_id(payload.organization_id, team_id)

    now = datetime.now(timezone.utc)
    doc = {
        "organization_id": payload.organization_id,
        "name": payload.name,
        "description": payload.description,
        "system_prompt": payload.system_prompt or "",
        "guardrails": payload.guardrails or "",
        "tool_ids": payload.tool_ids or [],
        "connector_ids": payload.connector_ids or [],
        "knowledge_base_ids": payload.knowledge_base_ids or [],
        "files": [],
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
        "owner_scope": owner_scope,
        "allowed_user_ids": cleaned_allowed_user_ids,
        "team_id": cleaned_team_id,
    }

    result = await projects_collection.insert_one(doc)
    doc["_id"] = result.inserted_id

    # Sync connector permissions if connectors were provided
    perms = await sync_connector_permissions(
        str(result.inserted_id),
        payload.organization_id,
        payload.connector_ids or [],
        payload.connector_permissions,
        is_project=True,
    )

    conn_map = await _fetch_connectors_summary(doc.get("connector_ids", []))
    return _to_public(doc, conn_map, perms)


async def get_project(
    project_id: str,
    org_id: str = "",
    user_id: str = "",
) -> ProjectPublic:
    """Fetch a single project by id, enforcing org and visibility scoping."""
    oid = validate_object_id(project_id)
    query: dict = {"_id": oid, **NOT_DELETED}
    if org_id:
        query["organization_id"] = org_id
    if user_id:
        query["$or"] = await build_agent_visibility_clauses(user_id)

    doc = await projects_collection.find_one(query)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    perm_doc = await agent_permissions_collection.find_one({"project_id": str(oid)})
    connector_perms = perm_doc.get("permissions", {}).get("connectors") if perm_doc else None

    conn_map = await _fetch_connectors_summary(doc.get("connector_ids", []))
    return _to_public(doc, conn_map, connector_perms)


async def _build_project_query(
    *,
    organization_id: Optional[str] = None,
    requesting_user_id: Optional[str] = None,
    search: Optional[str] = None,
    has_tools: Optional[bool] = None,
    has_connectors: Optional[bool] = None,
) -> dict:
    """Shared filter-building for project listings."""
    query: dict = {**NOT_DELETED}
    if organization_id:
        query["organization_id"] = organization_id
    if requesting_user_id is not None:
        query["$or"] = await build_agent_visibility_clauses(requesting_user_id)
    if search:
        query["name"] = {"$regex": re.escape(search), "$options": "i"}
    if has_tools is not None:
        query["tool_ids.0"] = {"$exists": has_tools}
    if has_connectors is not None:
        query["connector_ids.0"] = {"$exists": has_connectors}
    return query


def _resolve_project_sort(sort_by: Optional[str], sort_order: str) -> list[tuple[str, int]]:
    field = sort_by if sort_by in PROJECT_SORTABLE_FIELDS else "created_at"
    direction = 1 if sort_order == "asc" else -1
    return [(field, direction)]


async def list_projects(
    skip: int = 0,
    limit: int = 20,
    requesting_user_id: Optional[str] = None,
    search: Optional[str] = None,
    has_tools: Optional[bool] = None,
    has_connectors: Optional[bool] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
) -> tuple[List[ProjectPublic], int]:
    """List all projects across the platform (super-admin only)."""
    query = await _build_project_query(
        requesting_user_id=requesting_user_id,
        search=search,
        has_tools=has_tools,
        has_connectors=has_connectors,
    )
    total = await projects_collection.count_documents(query)
    cursor = (
        projects_collection.find(query)
        .sort(_resolve_project_sort(sort_by, sort_order))
        .skip(skip)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    project_ids = [str(doc["_id"]) for doc in docs]
    perm_docs = await agent_permissions_collection.find({"project_id": {"$in": project_ids}}).to_list(length=limit)
    perms_by_pid = {p["project_id"]: p.get("permissions", {}).get("connectors") for p in perm_docs}

    all_connector_ids = [cid for doc in docs for cid in doc.get("connector_ids", [])]
    conn_map = await _fetch_connectors_summary(all_connector_ids)
    return [_to_public(doc, conn_map, perms_by_pid.get(str(doc["_id"]))) for doc in docs], total


async def list_projects_by_org(
    org_id: str,
    skip: int = 0,
    limit: int = 20,
    requesting_user_id: Optional[str] = None,
    search: Optional[str] = None,
    has_tools: Optional[bool] = None,
    has_connectors: Optional[bool] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
) -> tuple[List[ProjectPublic], int]:
    """List projects that belong to a specific organization (paginated)."""
    query = await _build_project_query(
        organization_id=org_id,
        requesting_user_id=requesting_user_id,
        search=search,
        has_tools=has_tools,
        has_connectors=has_connectors,
    )
    total = await projects_collection.count_documents(query)
    cursor = (
        projects_collection.find(query)
        .sort(_resolve_project_sort(sort_by, sort_order))
        .skip(skip)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    project_ids = [str(doc["_id"]) for doc in docs]
    perm_docs = await agent_permissions_collection.find({"project_id": {"$in": project_ids}}).to_list(length=limit)
    perms_by_pid = {p["project_id"]: p.get("permissions", {}).get("connectors") for p in perm_docs}

    all_connector_ids = [cid for doc in docs for cid in doc.get("connector_ids", [])]
    conn_map = await _fetch_connectors_summary(all_connector_ids)
    return [_to_public(doc, conn_map, perms_by_pid.get(str(doc["_id"]))) for doc in docs], total


async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    org_id: str = "",
) -> ProjectPublic:
    """Update an existing project."""
    oid = validate_object_id(project_id)
    query: dict = {"_id": oid, **NOT_DELETED}
    if org_id:
        query["organization_id"] = org_id

    existing = await projects_collection.find_one(query)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    update_fields: dict = {"updated_at": datetime.now(timezone.utc)}
    if payload.name is not None:
        update_fields["name"] = payload.name
    if payload.description is not None:
        update_fields["description"] = payload.description
    if payload.system_prompt is not None:
        update_fields["system_prompt"] = payload.system_prompt
    if payload.guardrails is not None:
        update_fields["guardrails"] = payload.guardrails
    if payload.tool_ids is not None:
        update_fields["tool_ids"] = payload.tool_ids
    if payload.connector_ids is not None:
        update_fields["connector_ids"] = payload.connector_ids
    if payload.knowledge_base_ids is not None:
        update_fields["knowledge_base_ids"] = payload.knowledge_base_ids
    if payload.owner_scope is not None:
        update_fields["owner_scope"] = payload.owner_scope
        if payload.owner_scope == "selected_users":
            update_fields["allowed_user_ids"] = await _validate_allowed_user_ids(
                existing["organization_id"], payload.allowed_user_ids or []
            )
        elif payload.owner_scope == "team":
            update_fields["team_id"] = await _validate_team_id(
                existing["organization_id"], payload.team_id
            )
        else:
            update_fields["allowed_user_ids"] = []
            update_fields["team_id"] = None

    await projects_collection.update_one({"_id": oid}, {"$set": update_fields})
    updated = await projects_collection.find_one({"_id": oid})

    # Sync connector permissions if passed or if connector_ids were changed
    perms: Optional[Dict[str, Dict[str, bool]]] = None
    if payload.connector_permissions is not None or payload.connector_ids is not None:
        perms = await sync_connector_permissions(
            str(oid),
            updated["organization_id"],
            updated.get("connector_ids", []),
            payload.connector_permissions,
            is_project=True,
        )
    else:
        perm_doc = await agent_permissions_collection.find_one({"project_id": str(oid)})
        perms = perm_doc.get("permissions", {}).get("connectors") if perm_doc else None

    conn_map = await _fetch_connectors_summary(updated.get("connector_ids", []))
    return _to_public(updated, conn_map, perms)


async def delete_project(project_id: str, org_id: str = "") -> None:
    """Soft delete a project."""
    oid = validate_object_id(project_id)
    query: dict = {"_id": oid, **NOT_DELETED}
    if org_id:
        query["organization_id"] = org_id

    result = await projects_collection.update_one(query, soft_delete_update())
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")


# ---------------------------------------------------------------------------
# Skills & Files Management (Direct MongoDB Storage)
# ---------------------------------------------------------------------------

_FILE_EXT_MAP = {
    ".md": "markdown", ".markdown": "markdown",
    ".py": "code", ".js": "code", ".ts": "code", ".tsx": "code", ".jsx": "code",
    ".json": "code", ".yaml": "code", ".yml": "code", ".sql": "code", ".sh": "code", ".toml": "code",
    ".txt": "text", ".csv": "text", ".tsv": "text", ".log": "text",
    ".pdf": "document", ".docx": "document", ".xlsx": "document", ".pptx": "document",
}

_BINARY_MAGIC = {
    b"%PDF": "document",
    b"PK\x03\x04": "document",
    b"\xd0\xcf\x11\xe0": "document",
    b"\x89PNG": "image",
    b"\xff\xd8\xff": "image",
    b"GIF8": "image",
}


def _infer_file_type(filename: str, raw_bytes: Optional[bytes] = None) -> str:
    """Infer file category using magic byte headers with extension fallback."""
    lower = filename.lower()
    if lower.startswith("skill") or "skills." in lower:
        return "skill"

    if raw_bytes:
        for magic, ftype in _BINARY_MAGIC.items():
            if raw_bytes.startswith(magic):
                return ftype

    ext = os.path.splitext(lower)[1]
    return _FILE_EXT_MAP.get(ext, "other")


async def upload_project_file(
    project_id: str,
    file: UploadFile,
    uploaded_by: str,
    org_id: str = "",
) -> ProjectFilePublic:
    """Read uploaded file, decode text/markdown/skill content, and save directly in MongoDB."""
    oid = validate_object_id(project_id)
    query: dict = {"_id": oid, **NOT_DELETED}
    if org_id:
        query["organization_id"] = org_id

    project = await projects_collection.find_one(query)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    original_filename = file.filename or "uploaded_file"
    file_type = _infer_file_type(original_filename, raw_bytes=raw_bytes)
    file_size = len(raw_bytes)

    # Extract clean text content for PDF/Word/Excel/PowerPoint documents, or plain text for code/markdown/skills
    content: Optional[str] = None
    if file_type == "document" or raw_bytes.startswith(b"%PDF"):
        try:
            from fastapi.concurrency import run_in_threadpool
            from backend.core.attachments import _extract_pdf, _extract_docx, _extract_xlsx, _extract_pptx
            lname = original_filename.lower()
            if raw_bytes.startswith(b"%PDF") or lname.endswith(".pdf"):
                content = await run_in_threadpool(_extract_pdf, raw_bytes)
            elif lname.endswith(".docx"):
                content = await run_in_threadpool(_extract_docx, raw_bytes)
            elif lname.endswith(".xlsx"):
                content = await run_in_threadpool(_extract_xlsx, raw_bytes)
        except Exception as exc:
            logger.warning("[PROJECT:FILES] document text extraction failed for '%s': %s", original_filename, exc)
            content = None
    else:
        try:
            content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = None

    content_summary = (content[:200] + "...") if content and len(content) > 200 else content

    file_doc = {
        "id": uuid.uuid4().hex,
        "filename": original_filename,
        "original_filename": original_filename,
        "file_type": file_type,
        "file_size": file_size,
        "content": content,
        "content_summary": content_summary,
        "uploaded_by": uploaded_by,
        "uploaded_at": datetime.now(timezone.utc),
    }

    await projects_collection.update_one(
        {"_id": oid},
        {
            "$push": {"files": file_doc},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )

    logger.info(
        "[PROJECT:FILES] uploaded file '%s' (type=%s, size=%d bytes) to project=%s",
        original_filename, file_type, file_size, project_id,
    )
    return _to_file_public(file_doc)


async def list_project_files(project_id: str, org_id: str = "") -> List[ProjectFilePublic]:
    """List all files and skills saved in a project."""
    oid = validate_object_id(project_id)
    query: dict = {"_id": oid, **NOT_DELETED}
    if org_id:
        query["organization_id"] = org_id

    doc = await projects_collection.find_one(query, {"files": 1})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    return [_to_file_public(f) for f in doc.get("files", [])]


async def get_project_file(project_id: str, file_id: str, org_id: str = "") -> ProjectFilePublic:
    """Retrieve details and content of a specific file inside a project."""
    oid = validate_object_id(project_id)
    query: dict = {"_id": oid, **NOT_DELETED}
    if org_id:
        query["organization_id"] = org_id

    doc = await projects_collection.find_one(query, {"files": 1})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    for f in doc.get("files", []):
        if f.get("id") == file_id:
            return _to_file_public(f)

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in project.")


async def delete_project_file(project_id: str, file_id: str, org_id: str = "") -> None:
    """Delete a file/skill from a project."""
    oid = validate_object_id(project_id)
    query: dict = {"_id": oid, **NOT_DELETED}
    if org_id:
        query["organization_id"] = org_id

    result = await projects_collection.update_one(
        query,
        {
            "$pull": {"files": {"id": file_id}},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")


# ---------------------------------------------------------------------------
# Project Chat & Runtime Execution
# ---------------------------------------------------------------------------

def _build_skills_context(files: List[dict]) -> str:
    """Format uploaded skills, markdown files, and instructions into a context block."""
    if not files:
        return ""

    skill_blocks: list[str] = []
    for f in files:
        fname = f.get("filename") or f.get("original_filename") or "skill"
        content = f.get("content")
        if not content:
            continue
        skill_blocks.append(f"### Skill / Document: {fname}\n{content.strip()}")

    if not skill_blocks:
        return ""

    return (
        "## Project Skills & Attached Files\n"
        "You have access to the following project skills and reference instructions:\n\n"
        + "\n\n".join(skill_blocks)
    )


async def _load_project_runtime(
    org_id: str,
    project_id: str,
    user_id: str = "",
) -> AgentRuntime:
    """Load a project and adapt it into an AgentRuntime for LangGraph execution."""
    oid = validate_object_id(project_id)
    query: dict = {
        "_id": oid,
        "organization_id": org_id,
        **NOT_DELETED,
        "$or": await build_agent_visibility_clauses(user_id),
    }
    project_doc = await projects_collection.find_one(query)
    if not project_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    project_name = project_doc.get("name", project_id)
    tool_ids = project_doc.get("tool_ids", [])
    logger.info("[PROJECT:TOOLS] project=%s (id=%s) tool_ids=%s", project_name, project_id, tool_ids)

    # 1. Resolve registered tools directly from tool_registry_collection
    tools: list = []
    for tid in tool_ids:
        if ObjectId.is_valid(tid):
            reg_doc = await tool_registry_collection.find_one({"_id": ObjectId(tid), "is_deleted": {"$ne": True}})
            if reg_doc:
                tool_doc = {
                    "_id": reg_doc["_id"],
                    "tool_id": str(reg_doc["_id"]),
                    "name": reg_doc.get("name") or "Tool",
                    "user_description": reg_doc.get("description", ""),
                    "description": reg_doc.get("description", ""),
                    "handler": reg_doc.get("handler") or reg_doc.get("name"),
                    "input_schema": reg_doc.get("tool_schema", {}),
                    "tool_schema": reg_doc.get("tool_schema", {}),
                    "type": reg_doc.get("type", "function"),
                    "organization_id": org_id,
                }
                tools.append(tool_doc)

    # Ensure ask_human tool is always included and cannot be omitted
    has_ask_human = any(t.get("handler") == "ask_human" or t.get("name") == "ask_human" for t in tools)
    if not has_ask_human:
        ask_human_reg = await tool_registry_collection.find_one({
            "$or": [{"name": "ask_human"}, {"auto_assign": True}],
            "is_deleted": {"$ne": True},
        })
        if ask_human_reg:
            tools.append({
                "_id": ask_human_reg["_id"],
                "tool_id": str(ask_human_reg["_id"]),
                "name": ask_human_reg.get("name") or "ask_human",
                "user_description": ask_human_reg.get("description", ""),
                "description": ask_human_reg.get("description", ""),
                "handler": "ask_human",
                "input_schema": ask_human_reg.get("tool_schema", {}),
                "tool_schema": ask_human_reg.get("tool_schema", {}),
                "type": ask_human_reg.get("type", "function"),
                "organization_id": org_id,
            })

    logger.info(
        "[PROJECT:TOOLS] project=%s (id=%s) resolved %d tool(s) (including ask_human): %s",
        project_name, project_id, len(tools),
        [t.get("name") or t.get("user_description", "?")[:40] for t in tools],
    )

    # 2. Database connections if database tools are attached
    db_conn_ids = await bind_runtime_db_tools(tools, org_id)

    # 3. Load Connectors
    connector_tools, connector_callables, connector_tool_owner, connector_load_errors = (
        await load_agent_connectors(project_doc, user_id)
    )

    # 4. Construct composite prompt: Base System Prompt + Skills Context
    base_prompt = (
        project_doc.get("system_prompt")
        or f"You are the {project_name} project assistant. Be helpful, concise, and follow project instructions."
    )
    skills_context = _build_skills_context(project_doc.get("files", []))
    if skills_context:
        full_prompt = f"{base_prompt.rstrip()}\n\n{skills_context}"
    else:
        full_prompt = base_prompt

    # Create adapter doc for AgentRuntime
    runtime_doc = dict(project_doc)
    runtime_doc["prompt"] = full_prompt

    runtime = AgentRuntime(runtime_doc, tools, db_conn_ids=db_conn_ids)
    runtime.connector_tools = connector_tools
    runtime.connector_callables = connector_callables
    runtime.connector_tool_owner = connector_tool_owner
    runtime.connector_load_errors = connector_load_errors
    return runtime


@dataclass
class _ProjectChatCtx:
    runtime: AgentRuntime
    project_id: str
    thread_id: str
    message: str
    org_id: str
    user_id: str
    existing_name: Optional[str]
    title_task: Optional[asyncio.Task]
    graph: Any
    config: dict
    tracer: AgentTracer
    is_interrupted: bool
    graph_input: Any


# ---------------------------------------------------------------------------
# Project-Based Chat History (Stored in project_chats collection)
# ---------------------------------------------------------------------------

async def list_project_messages(
    project_id: str,
    org_id: str = "",
    limit: int = 100,
) -> List[ProjectChatMessagePublic]:
    """Retrieve continuous chat history for a project from project_chats collection."""
    oid = validate_object_id(project_id)
    query: dict = {"_id": oid, **NOT_DELETED}
    if org_id:
        query["organization_id"] = org_id
    proj = await projects_collection.find_one(query)
    if not proj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    cursor = (
        project_chats_collection.find({"project_id": str(oid), **NOT_DELETED})
        .sort("created_at", 1)
        .limit(limit)
    )
    messages = []
    async for doc in cursor:
        messages.append(
            ProjectChatMessagePublic(
                id=str(doc["_id"]),
                project_id=doc["project_id"],
                organization_id=doc.get("organization_id", org_id),
                role=doc["role"],
                content=doc["content"],
                auth_errors=doc.get("auth_errors", []),
                user_id=doc.get("user_id"),
                created_at=doc["created_at"],
            )
        )
    return messages


async def clear_project_messages(
    project_id: str,
    org_id: str = "",
) -> None:
    """Clear chat history for a project."""
    oid = validate_object_id(project_id)
    query: dict = {"_id": oid, **NOT_DELETED}
    if org_id:
        query["organization_id"] = org_id
    proj = await projects_collection.find_one(query)
    if not proj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    await project_chats_collection.update_many(
        {"project_id": str(oid), **NOT_DELETED},
        soft_delete_update(),
    )


async def _prepare_project_chat(
    project_id: str,
    message: str,
    org_id: str,
    user_id: str,
    session_id: Optional[str] = None,
) -> _ProjectChatCtx:
    """Prepare context and LangGraph state for project chat using project_chats collection."""
    runtime = await _load_project_runtime(org_id, project_id, user_id=user_id)

    # Use persistent project thread
    thread_id = f"proj_{project_id}"

    # 1. Fetch recent project chat history from project_chats collection
    past_docs = await project_chats_collection.find(
        {"project_id": project_id, **NOT_DELETED}
    ).sort("created_at", 1).to_list(length=100)

    history_messages: List[Any] = []
    for doc in past_docs:
        role = doc.get("role")
        content = doc.get("content", "")
        if role == "user":
            history_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            history_messages.append(AIMessage(content=content))

    # 2. Record the incoming user message in project_chats collection
    now = datetime.now(timezone.utc)
    user_msg_doc = {
        "project_id": project_id,
        "organization_id": org_id,
        "user_id": user_id,
        "role": "user",
        "content": message,
        "auth_errors": [],
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
    }
    await project_chats_collection.insert_one(user_msg_doc)

    messages_for_graph = history_messages + [HumanMessage(content=message)]
    graph = get_or_build_single_agent_graph(org_id, runtime, settings.DEFAULT_MODEL)
    config = {"configurable": {"thread_id": thread_id}}
    tracer = AgentTracer(org_id=org_id, user_id=user_id, session_id=thread_id)

    snapshot = await graph.aget_state(config)
    is_interrupted = bool(snapshot.next) and any(
        t.interrupts for t in snapshot.tasks
    )

    if is_interrupted:
        graph_input: Any = Command(resume=message)
    else:
        graph_input = {
            "messages": messages_for_graph,
            "next": "",
            "unattended": False,
        }

    return _ProjectChatCtx(
        runtime=runtime,
        project_id=project_id,
        thread_id=thread_id,
        message=message,
        org_id=org_id,
        user_id=user_id,
        existing_name=runtime.name,
        title_task=None,
        graph=graph,
        config=config,
        tracer=tracer,
        is_interrupted=is_interrupted,
        graph_input=graph_input,
    )


async def _finalize_project_chat(ctx: _ProjectChatCtx, result: dict) -> ProjectChatResponse:
    reply = ""
    for m in reversed(result.get("messages", [])):
        if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None):
            reply = str(m.content)
            break

    final_reply = reply or "Request processed."

    ctx.tracer.end_trace(output={"response": final_reply[:500], "project": ctx.runtime.name})
    set_tracer(None)

    auth_errors = get_auth_errors()

    # Save assistant message to project_chats collection
    now = datetime.now(timezone.utc)
    assistant_msg_doc = {
        "project_id": ctx.project_id,
        "organization_id": ctx.org_id,
        "user_id": ctx.user_id,
        "role": "assistant",
        "content": final_reply,
        "auth_errors": auth_errors,
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
    }
    await project_chats_collection.insert_one(assistant_msg_doc)

    return ProjectChatResponse(
        reply=final_reply,
        session_id=ctx.thread_id,
        name=ctx.runtime.name,
        auth_errors=auth_errors,
    )


async def project_chat(
    project_id: str,
    message: str,
    org_id: str,
    user_id: str,
    session_id: Optional[str] = None,
) -> ProjectChatResponse:
    """Send a message directly to a project (blocking)."""
    ctx = await _prepare_project_chat(project_id, message, org_id, user_id, session_id)

    set_tracer(ctx.tracer)
    reset_auth_errors()
    ctx.tracer.start_trace("project_chat.turn", input={"query": message[:500]})
    ctx.tracer.tag_agent(ctx.runtime.agent_id, ctx.runtime.name)
    try:
        result = await ctx.graph.ainvoke(ctx.graph_input, config=ctx.config)
    except Exception:
        ctx.tracer.end_trace(output={"error": "project chat turn failed"})
        set_tracer(None)
        raise

    return await _finalize_project_chat(ctx, result)


async def prepare_project_chat_stream(
    project_id: str,
    message: str,
    org_id: str,
    user_id: str,
    session_id: Optional[str] = None,
) -> _ProjectChatCtx:
    """Pre-validate and load context before streaming response starts."""
    return await _prepare_project_chat(project_id, message, org_id, user_id, session_id)


async def project_chat_stream(ctx: _ProjectChatCtx):
    """Async generator streaming live tool-call events and final answer for project chat."""
    queue: asyncio.Queue = asyncio.Queue()

    async def sink(event_type: str, payload: dict) -> None:
        await queue.put((event_type, payload))

    set_tracer(ctx.tracer)
    set_event_sink(sink)
    reset_auth_errors()
    ctx.tracer.start_trace("project_chat.turn", input={"query": ctx.message[:500]})
    ctx.tracer.tag_agent(ctx.runtime.agent_id, ctx.runtime.name)

    graph_task = asyncio.create_task(
        ctx.graph.ainvoke(ctx.graph_input, config=ctx.config)
    )

    try:
        pending_get: Optional[asyncio.Task] = None
        while not graph_task.done():
            if pending_get is None:
                pending_get = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait(
                {graph_task, pending_get}, return_when=asyncio.FIRST_COMPLETED
            )
            if pending_get in done:
                event_type, payload = pending_get.result()
                yield f"data: {json.dumps({'type': event_type, 'payload': payload})}\n\n"
                pending_get = None
        if pending_get is not None:
            pending_get.cancel()
        while not queue.empty():
            event_type, payload = queue.get_nowait()
            yield f"data: {json.dumps({'type': event_type, 'payload': payload})}\n\n"
    except asyncio.CancelledError:
        graph_task.cancel()
        raise
    finally:
        set_event_sink(None)

    try:
        result = graph_task.result()
    except Exception:
        ctx.tracer.end_trace(output={"error": "project chat turn failed"})
        set_tracer(None)
        yield f"data: {json.dumps({'type': 'error', 'payload': {'message': 'Something went wrong processing your message.'}})}\n\n"
        return

    response = await _finalize_project_chat(ctx, result)
    yield f"data: {json.dumps({'type': 'done', 'payload': response.model_dump(mode='json')})}\n\n"

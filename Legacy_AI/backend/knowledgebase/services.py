import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from backend.core.attachments import process_attachment
from backend.core.softdelete import NOT_DELETED, soft_delete_update
from backend.db.database import db, kb_documents_collection, rag_sources_collection
from backend.knowledgebase.schemas import (
    KBDocumentPublic,
    KnowledgeBaseCreate,
    KnowledgeBasePublic,
    KnowledgeBaseUpdate,
)

logger = logging.getLogger(__name__)

KB_GRIDFS_BUCKET = "kb_document_files"

# Fire-and-forget background tasks must be held somewhere, or they can in
# principle be garbage-collected before completion — this set is the fix for
# that exact pitfall found in backend/dbconnection/services.py during review.
_background_tasks: set[asyncio.Task] = set()


def _track(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def _bucket() -> AsyncIOMotorGridFSBucket:
    return AsyncIOMotorGridFSBucket(db, bucket_name=KB_GRIDFS_BUCKET)


def _validate_object_id(value: str, label: str = "Resource") -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found.")
    return ObjectId(value)


async def build_kb_visibility_clauses(requesting_user_id: str) -> list[dict]:
    """Same visibility model as build_agent_visibility_clauses, applied to
    Knowledge Bases. Phase 1 only ever sets owner_scope="organization", but
    the clause shape is ready for user/selected_users/team KBs without
    changes here."""
    from backend.team import services as team_services

    team_ids = await team_services.get_team_ids_for_user(requesting_user_id)
    clauses = [
        {"owner_scope": {"$nin": ["user", "selected_users", "team"]}},
        {"owner_scope": "user", "created_by": requesting_user_id},
        {"owner_scope": "selected_users", "created_by": requesting_user_id},
        {"owner_scope": "selected_users", "allowed_user_ids": requesting_user_id},
        {"owner_scope": "team", "created_by": requesting_user_id},
    ]
    if team_ids:
        clauses.append({"owner_scope": "team", "team_id": {"$in": team_ids}})
    return clauses


def build_kb_visibility_clauses_sync(sync_db, requesting_user_id: str) -> list[dict]:
    """Sync (pymongo) counterpart of build_kb_visibility_clauses, for the
    ai/multi_orchestration engine, which loads its graph from a worker thread
    with no running event loop — same reasoning as the sync/async client
    pairs already used throughout ai/rag/."""
    team_ids = [
        str(d["_id"])
        for d in sync_db.teams.find({"member_ids": requesting_user_id, "is_deleted": {"$ne": True}}, {"_id": 1})
    ]
    clauses = [
        {"owner_scope": {"$nin": ["user", "selected_users", "team"]}},
        {"owner_scope": "user", "created_by": requesting_user_id},
        {"owner_scope": "selected_users", "created_by": requesting_user_id},
        {"owner_scope": "selected_users", "allowed_user_ids": requesting_user_id},
        {"owner_scope": "team", "created_by": requesting_user_id},
    ]
    if team_ids:
        clauses.append({"owner_scope": "team", "team_id": {"$in": team_ids}})
    return clauses


def filter_visible_kb_ids_sync(sync_db, org_id: str, kb_ids: List[str], user_id: str) -> List[str]:
    """Sync counterpart of filter_visible_kb_ids for the ai/multi_orchestration
    engine's GraphLoader, which resolves agent tools from a worker thread."""
    if not kb_ids:
        return []
    valid_oids = [ObjectId(kid) for kid in kb_ids if ObjectId.is_valid(kid)]
    if not valid_oids:
        return []
    query = {
        "_id": {"$in": valid_oids},
        "organization_id": org_id,
        "is_deleted": {"$ne": True},
        "$or": build_kb_visibility_clauses_sync(sync_db, user_id),
    }
    docs = list(sync_db.rag_sources.find(query, {"_id": 1}))
    return [str(d["_id"]) for d in docs]


async def filter_visible_kb_ids(org_id: str, kb_ids: List[str], user_id: str) -> List[str]:
    """Re-check KB visibility for a specific user against a candidate kb_id list.

    Used when resolving an agent's rag_ids into the search_knowledge_base tool
    (AgentRuntime construction, where user_id is already in scope) — so a
    personal/team/selected-users KB an agent references is never searchable
    by a user who shouldn't see it, even though it's baked into the agent's
    rag_ids. The management/listing endpoints already enforce this via
    build_kb_visibility_clauses; this is the same check applied at the point
    an agent's KBs are resolved for actual retrieval.
    """
    if not kb_ids:
        return []
    valid_oids = [ObjectId(kid) for kid in kb_ids if ObjectId.is_valid(kid)]
    if not valid_oids:
        return []
    query = {
        "_id": {"$in": valid_oids},
        "organization_id": org_id,
        **NOT_DELETED,
        "$or": await build_kb_visibility_clauses(user_id),
    }
    docs = await rag_sources_collection.find(query, {"_id": 1}).to_list(length=len(valid_oids))
    return [str(d["_id"]) for d in docs]


async def _document_count(kb_id: str) -> int:
    return await kb_documents_collection.count_documents({"kb_id": kb_id, "status": "indexed", **NOT_DELETED})


def _to_public(doc: dict, document_count: int = 0) -> KnowledgeBasePublic:
    return KnowledgeBasePublic(
        id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        name=doc["name"],
        description=doc.get("description"),
        created_by=doc["created_by"],
        owner_scope=doc.get("owner_scope", "organization"),
        allowed_user_ids=doc.get("allowed_user_ids", []),
        team_id=doc.get("team_id"),
        graph_expand_enabled=doc.get("graph_expand_enabled", True),
        auto_created=doc.get("auto_created", False),
        document_count=document_count,
        created_at=doc["created_at"],
    )


def _doc_to_public(doc: dict) -> KBDocumentPublic:
    return KBDocumentPublic(
        id=str(doc["_id"]),
        kb_id=doc["kb_id"],
        organization_id=doc["organization_id"],
        filename=doc["filename"],
        doc_type=doc.get("doc_type", ""),
        description=doc.get("description"),
        status=doc.get("status", "processing"),
        chunk_count=doc.get("chunk_count", 0),
        error=doc.get("error"),
        auto_classified=doc.get("auto_classified", False),
        created_by=doc["created_by"],
        created_at=doc["created_at"],
    )


async def create_knowledge_base(
    payload: KnowledgeBaseCreate, created_by: str, auto_created: bool = False
) -> KnowledgeBasePublic:
    from backend.agent.services import _validate_allowed_user_ids, _validate_team_id

    cleaned_allowed_user_ids: List[str] = []
    if payload.owner_scope == "selected_users":
        cleaned_allowed_user_ids = await _validate_allowed_user_ids(
            payload.organization_id, payload.allowed_user_ids
        )
    cleaned_team_id: Optional[str] = None
    if payload.owner_scope == "team":
        cleaned_team_id = await _validate_team_id(payload.organization_id, payload.team_id)

    doc = {
        "organization_id": payload.organization_id,
        "name": payload.name.strip(),
        "description": (payload.description or "").strip() or None,
        "created_by": created_by,
        "owner_scope": payload.owner_scope,
        "allowed_user_ids": cleaned_allowed_user_ids,
        "team_id": cleaned_team_id,
        "graph_expand_enabled": payload.graph_expand_enabled,
        "auto_created": auto_created,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc),
    }
    result = await rag_sources_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _to_public(doc)


async def get_knowledge_base(kb_id: str) -> KnowledgeBasePublic:
    oid = _validate_object_id(kb_id, "Knowledge base")
    doc = await rag_sources_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return _to_public(doc, await _document_count(kb_id))


async def list_knowledge_bases(org_id: str, requesting_user_id: str) -> List[KnowledgeBasePublic]:
    query = {
        "organization_id": org_id,
        **NOT_DELETED,
        "$or": await build_kb_visibility_clauses(requesting_user_id),
    }
    cursor = rag_sources_collection.find(query)
    docs = await cursor.to_list(length=500)
    return [_to_public(d, await _document_count(str(d["_id"]))) for d in docs]


async def update_knowledge_base(kb_id: str, payload: KnowledgeBaseUpdate) -> KnowledgeBasePublic:
    from backend.agent.services import _validate_allowed_user_ids, _validate_team_id

    oid = _validate_object_id(kb_id, "Knowledge base")
    existing = await rag_sources_collection.find_one({"_id": oid, **NOT_DELETED})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update.")

    effective_scope = updates.get("owner_scope", existing.get("owner_scope"))
    if "allowed_user_ids" in updates or effective_scope == "selected_users":
        updates["allowed_user_ids"] = await _validate_allowed_user_ids(
            existing["organization_id"], updates.get("allowed_user_ids", existing.get("allowed_user_ids", []))
        )
    if "team_id" in updates or effective_scope == "team":
        updates["team_id"] = await _validate_team_id(
            existing["organization_id"], updates.get("team_id", existing.get("team_id"))
        )

    doc = await rag_sources_collection.find_one_and_update(
        {"_id": oid, **NOT_DELETED}, {"$set": updates}, return_document=True
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return _to_public(doc, await _document_count(kb_id))


async def delete_knowledge_base(kb_id: str) -> None:
    oid = _validate_object_id(kb_id, "Knowledge base")
    doc = await rag_sources_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    await rag_sources_collection.update_one({"_id": oid, **NOT_DELETED}, soft_delete_update())

    doc_cursor = kb_documents_collection.find({"kb_id": kb_id, **NOT_DELETED})
    docs = await doc_cursor.to_list(length=10_000)
    for d in docs:
        await kb_documents_collection.update_one({"_id": d["_id"]}, soft_delete_update())
        if d.get("gridfs_id"):
            await _delete_gridfs_file(d["gridfs_id"])

    _track(_delete_kb_index_background(org_id=doc["organization_id"], kb_id=kb_id))


async def _delete_gridfs_file(gridfs_id) -> None:
    try:
        await _bucket().delete(ObjectId(str(gridfs_id)))
    except Exception:
        logger.warning("[kb] best-effort GridFS cleanup failed for file=%s", gridfs_id, exc_info=True)


async def _delete_kb_index_background(org_id: str, kb_id: str) -> None:
    try:
        from ai.rag.kb_indexer import delete_kb_index

        await delete_kb_index(org_id=org_id, kb_id=kb_id)
        logger.info("[kb] removed vectors for deleted kb=%s", kb_id)
    except Exception:
        logger.exception("[kb] failed to remove vectors for kb=%s", kb_id)


async def list_documents(kb_id: str) -> List[KBDocumentPublic]:
    cursor = kb_documents_collection.find({"kb_id": kb_id, **NOT_DELETED}).sort("created_at", -1)
    docs = await cursor.to_list(length=1000)
    return [_doc_to_public(d) for d in docs]


async def list_documents_for_review(org_id: str) -> List[KBDocumentPublic]:
    """Admin review listing: every auto-classified document across the org's
    KBs, most recent first, so a corrected assignment doesn't require
    re-uploading."""
    cursor = kb_documents_collection.find(
        {"organization_id": org_id, "auto_classified": True, **NOT_DELETED}
    ).sort("created_at", -1)
    docs = await cursor.to_list(length=500)
    return [_doc_to_public(d) for d in docs]


async def get_document(doc_id: str) -> KBDocumentPublic:
    oid = _validate_object_id(doc_id, "Document")
    doc = await kb_documents_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return _doc_to_public(doc)


async def reassign_document(doc_id: str, new_kb_id: str) -> KBDocumentPublic:
    """Admin correction: move a document to a different KB and re-index its
    chunks under the new kb_id (Qdrant filters/scoping are per-kb_id, so the
    old vectors must move too, not just the Mongo record)."""
    oid = _validate_object_id(doc_id, "Document")
    kb_oid = _validate_object_id(new_kb_id, "Knowledge base")
    doc = await kb_documents_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    kb_doc = await rag_sources_collection.find_one({"_id": kb_oid, **NOT_DELETED})
    if not kb_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")

    old_kb_id = doc["kb_id"]
    await kb_documents_collection.update_one(
        {"_id": oid}, {"$set": {"kb_id": new_kb_id, "auto_classified": False}}
    )
    updated = await kb_documents_collection.find_one({"_id": oid})

    if old_kb_id != new_kb_id and doc.get("gridfs_id"):
        _track(
            _reindex_moved_document_background(
                org_id=doc["organization_id"],
                old_kb_id=old_kb_id,
                new_kb_id=new_kb_id,
                doc_id=str(oid),
                gridfs_id=doc["gridfs_id"],
                filename=doc.get("filename", ""),
                doc_type=doc.get("doc_type", ""),
                description=doc.get("description") or "",
            )
        )
    return _doc_to_public(updated)


async def _reindex_moved_document_background(
    org_id: str, old_kb_id: str, new_kb_id: str, doc_id: str, gridfs_id: str,
    filename: str, doc_type: str, description: str,
) -> None:
    try:
        from ai.rag.kb_indexer import delete_document_index, index_document
        from backend.core.attachments import extract_document_text

        stream = await _bucket().open_download_stream(ObjectId(str(gridfs_id)))
        raw = await stream.read()
        text = await extract_document_text(raw, filename)
        await index_document(
            org_id=org_id, kb_id=new_kb_id, doc_id=doc_id, text=text, doc_type=doc_type, description=description
        )
        await delete_document_index(org_id=org_id, kb_id=old_kb_id, doc_id=doc_id)
        logger.info("[kb] re-indexed doc=%s from kb=%s to kb=%s", doc_id, old_kb_id, new_kb_id)
    except Exception:
        logger.exception("[kb] failed to re-index moved doc=%s", doc_id)


async def delete_document(doc_id: str) -> None:
    oid = _validate_object_id(doc_id, "Document")
    doc = await kb_documents_collection.find_one({"_id": oid, **NOT_DELETED})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    await kb_documents_collection.update_one({"_id": oid}, soft_delete_update())
    if doc.get("gridfs_id"):
        await _delete_gridfs_file(doc["gridfs_id"])
    _track(_delete_document_index_background(doc["organization_id"], doc["kb_id"], str(oid)))


async def _delete_document_index_background(org_id: str, kb_id: str, doc_id: str) -> None:
    try:
        from ai.rag.kb_indexer import delete_document_index

        await delete_document_index(org_id=org_id, kb_id=kb_id, doc_id=doc_id)
    except Exception:
        logger.exception("[kb] failed to remove vectors for deleted doc=%s", doc_id)


async def upload_document(
    org_id: str,
    file: UploadFile,
    created_by: str,
    kb_id: Optional[str] = None,
) -> KBDocumentPublic:
    """Upload one document. If kb_id is given, file it there directly (no
    classification). If omitted, the document is filed with status
    "processing" and classified in the background — auto-matched to an
    existing KB or auto-creating a new one."""
    if kb_id is not None:
        _validate_object_id(kb_id, "Knowledge base")
        kb_doc = await rag_sources_collection.find_one({"_id": ObjectId(kb_id), **NOT_DELETED})
        if not kb_doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")

    # Keep the original bytes for GridFS (audit trail + so extraction can be
    # redone later with an improved pipeline) — process_attachment consumes
    # the UploadFile's stream, so read it once here and rewind before handing
    # it off, rather than re-deriving "raw bytes" from the extracted text.
    raw_bytes = await file.read()
    await file.seek(0)

    extracted = await process_attachment(file)
    if extracted["kind"] != "document":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Knowledge base documents must be text-extractable files (PDF, Word, Excel, text/markdown).",
        )
    text = extracted["text"]
    filename = extracted["filename"]

    gridfs_id = await _bucket().upload_from_stream(filename, raw_bytes)

    doc = {
        "kb_id": kb_id or "",
        "organization_id": org_id,
        "filename": filename,
        "doc_type": filename.rsplit(".", 1)[-1].lower() if "." in filename else "",
        "description": None,
        "status": "processing",
        "chunk_count": 0,
        "error": None,
        "gridfs_id": str(gridfs_id),
        "created_by": created_by,
        "auto_classified": kb_id is None,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc),
    }
    result = await kb_documents_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    doc_id = str(result.inserted_id)

    _track(
        _identify_and_index_background(
            org_id=org_id, doc_id=doc_id, text=text, filename=filename, kb_id=kb_id, created_by=created_by
        )
    )

    return _doc_to_public(doc)


async def bulk_upload_documents(
    org_id: str, files: List[UploadFile], created_by: str, kb_id: Optional[str] = None
) -> List[KBDocumentPublic]:
    """Bulk upload — each file is processed independently; one failure never
    blocks the rest of the batch."""
    results: List[KBDocumentPublic] = []
    for f in files:
        try:
            results.append(await upload_document(org_id=org_id, file=f, created_by=created_by, kb_id=kb_id))
        except HTTPException as exc:
            logger.warning("[kb] upload failed for file=%s: %s", f.filename, exc.detail)
    return results


async def _identify_and_index_background(
    org_id: str, doc_id: str, text: str, filename: str, kb_id: Optional[str], created_by: str
) -> None:
    """Background pipeline stage: identify the document (description +
    KB match/auto-create), then chunk + embed + index it. Every step is
    wrapped so a failure here always surfaces as status="failed" on the
    document rather than leaving it stuck at "processing" forever."""
    try:
        resolved_kb_id = kb_id
        description = None
        auto_classified = kb_id is None

        if resolved_kb_id is None:
            from ai.rag.kb_identifier import identify_document

            existing = await rag_sources_collection.find(
                {"organization_id": org_id, **NOT_DELETED}
            ).to_list(length=200)
            existing_kbs = [
                {"id": str(k["_id"]), "name": k["name"], "description": k.get("description") or ""}
                for k in existing
            ]
            result = await identify_document(text, existing_kbs)
            description = result["document_description"]

            if result["matched_kb_id"] and any(k["id"] == result["matched_kb_id"] for k in existing_kbs):
                resolved_kb_id = result["matched_kb_id"]
            else:
                new_kb = await create_knowledge_base(
                    KnowledgeBaseCreate(
                        organization_id=org_id,
                        name=result["new_kb_name"] or "Uncategorized",
                        description=result["new_kb_description"],
                    ),
                    created_by=created_by,
                    auto_created=True,
                )
                resolved_kb_id = new_kb.id
        else:
            from ai.rag.kb_identifier import identify_document

            result = await identify_document(text, [])
            description = result["document_description"]

        chunk_count = await _index_document_chunks(
            org_id=org_id, kb_id=resolved_kb_id, doc_id=doc_id, text=text, filename=filename, description=description
        )

        await kb_documents_collection.update_one(
            {"_id": ObjectId(doc_id)},
            {
                "$set": {
                    "kb_id": resolved_kb_id,
                    "description": description,
                    "status": "indexed",
                    "chunk_count": chunk_count,
                    "auto_classified": auto_classified,
                }
            },
        )
        logger.info("[kb] indexed doc=%s into kb=%s (%d chunks)", doc_id, resolved_kb_id, chunk_count)
    except Exception as e:
        logger.exception("[kb] background indexing failed for doc=%s", doc_id)
        await kb_documents_collection.update_one(
            {"_id": ObjectId(doc_id)}, {"$set": {"status": "failed", "error": str(e)[:500]}}
        )


async def _index_document_chunks(
    org_id: str, kb_id: str, doc_id: str, text: str, filename: str, description: str
) -> int:
    from ai.rag.kb_indexer import index_document

    doc_type = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return await index_document(
        org_id=org_id, kb_id=kb_id, doc_id=doc_id, text=text, doc_type=doc_type, description=description
    )

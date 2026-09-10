import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, UploadFile, status

from backend.auth.permissions import assert_org_access
from backend.auth.schemas import UserPublic
from backend.dependencies import get_current_user, require_permission
from backend.knowledgebase import services
from backend.knowledgebase.schemas import (
    KBDocumentPublic,
    KnowledgeBaseCreate,
    KnowledgeBasePublic,
    KnowledgeBaseUpdate,
    ReassignDocumentRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/knowledge-bases",
    tags=["knowledge-bases"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=KnowledgeBasePublic, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    current_user: UserPublic = Depends(require_permission("create_knowledge_base")),
) -> KnowledgeBasePublic:
    assert_org_access(current_user, payload.organization_id)
    return await services.create_knowledge_base(payload, created_by=current_user.id)


@router.get("", response_model=List[KnowledgeBasePublic])
async def list_knowledge_bases(
    organization_id: str,
    current_user: UserPublic = Depends(require_permission("view_knowledge_base")),
) -> List[KnowledgeBasePublic]:
    assert_org_access(current_user, organization_id)
    return await services.list_knowledge_bases(organization_id, current_user.id)


@router.get("/review", response_model=List[KBDocumentPublic])
async def list_documents_for_review(
    organization_id: str,
    current_user: UserPublic = Depends(require_permission("edit_knowledge_base")),
) -> List[KBDocumentPublic]:
    """Every auto-classified document in the org, for the admin review
    screen — lets a bulk-uploaded batch be double-checked/reassigned without
    re-uploading anything."""
    assert_org_access(current_user, organization_id)
    return await services.list_documents_for_review(organization_id)


@router.get("/{kb_id}", response_model=KnowledgeBasePublic)
async def get_knowledge_base(
    kb_id: str,
    current_user: UserPublic = Depends(require_permission("view_knowledge_base")),
) -> KnowledgeBasePublic:
    kb = await services.get_knowledge_base(kb_id)
    assert_org_access(current_user, kb.organization_id)
    return kb


@router.put("/{kb_id}", response_model=KnowledgeBasePublic)
async def update_knowledge_base(
    kb_id: str,
    payload: KnowledgeBaseUpdate,
    current_user: UserPublic = Depends(require_permission("edit_knowledge_base")),
) -> KnowledgeBasePublic:
    kb = await services.get_knowledge_base(kb_id)
    assert_org_access(current_user, kb.organization_id)
    return await services.update_knowledge_base(kb_id, payload)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: str,
    current_user: UserPublic = Depends(require_permission("delete_knowledge_base")),
) -> None:
    kb = await services.get_knowledge_base(kb_id)
    assert_org_access(current_user, kb.organization_id)
    await services.delete_knowledge_base(kb_id)


@router.get("/{kb_id}/documents", response_model=List[KBDocumentPublic])
async def list_documents(
    kb_id: str,
    current_user: UserPublic = Depends(require_permission("view_knowledge_base")),
) -> List[KBDocumentPublic]:
    kb = await services.get_knowledge_base(kb_id)
    assert_org_access(current_user, kb.organization_id)
    return await services.list_documents(kb_id)


@router.post("/{kb_id}/documents", response_model=KBDocumentPublic, status_code=status.HTTP_201_CREATED)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    current_user: UserPublic = Depends(require_permission("create_knowledge_base")),
) -> KBDocumentPublic:
    """Upload a single document directly into this KB (no auto-classification)."""
    kb = await services.get_knowledge_base(kb_id)
    assert_org_access(current_user, kb.organization_id)
    return await services.upload_document(
        org_id=kb.organization_id, file=file, created_by=current_user.id, kb_id=kb_id
    )


@router.post("/documents/bulk-upload", response_model=List[KBDocumentPublic], status_code=status.HTTP_201_CREATED)
async def bulk_upload_documents(
    organization_id: str,
    files: List[UploadFile] = File(...),
    current_user: UserPublic = Depends(require_permission("create_knowledge_base")),
) -> List[KBDocumentPublic]:
    """Bulk upload without picking a KB per file — each document is
    classified and routed automatically (matched to an existing KB, or a new
    KB is auto-created). See GET /knowledge-bases/review to check/correct
    the assignments afterward."""
    assert_org_access(current_user, organization_id)
    return await services.bulk_upload_documents(
        org_id=organization_id, files=files, created_by=current_user.id, kb_id=None
    )


@router.get("/documents/{doc_id}", response_model=KBDocumentPublic)
async def get_document(
    doc_id: str,
    current_user: UserPublic = Depends(require_permission("view_knowledge_base")),
) -> KBDocumentPublic:
    doc = await services.get_document(doc_id)
    assert_org_access(current_user, doc.organization_id)
    return doc


@router.put("/documents/{doc_id}/reassign", response_model=KBDocumentPublic)
async def reassign_document(
    doc_id: str,
    payload: ReassignDocumentRequest,
    current_user: UserPublic = Depends(require_permission("edit_knowledge_base")),
) -> KBDocumentPublic:
    doc = await services.get_document(doc_id)
    assert_org_access(current_user, doc.organization_id)
    return await services.reassign_document(doc_id, payload.kb_id)


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: str,
    current_user: UserPublic = Depends(require_permission("delete_knowledge_base")),
) -> None:
    doc = await services.get_document(doc_id)
    assert_org_access(current_user, doc.organization_id)
    await services.delete_document(doc_id)

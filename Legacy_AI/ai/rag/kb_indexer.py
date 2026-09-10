"""Chunk, embed (dense + sparse), and index a Knowledge Base document into Qdrant.

One shared `kb_chunks` collection for every org/KB/document — differentiated
by payload (org_id tenant index, kb_id + doc_id keyword indexes), the same
multi-tenant pattern already proven by ai/rag/schema_indexer.py.

Unlike schema_indexer.py's delete-then-upsert (which leaves a document with
zero indexed chunks if the process crashes between the two steps), this
indexer upserts the new "generation" first and only deletes the previous
generation's points afterwards — so a crash mid-index leaves the OLD chunks
still searchable rather than a silent gap.
"""

import hashlib
import logging
import re
import uuid
from typing import Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    HasIdCondition,
    HnswConfigDiff,
    KeywordIndexParams,
    KeywordIndexType,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from ai.rag.kb_llm import embed_texts
from backend.core.config import settings

logger = logging.getLogger(__name__)

COLLECTION = "kb_chunks"
VECTOR_DIM = 1536  # text-embedding-3-small output size
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"

MAX_CHUNK_CHARS = 1200
CHUNK_OVERLAP_CHARS = 150

_qdrant: Optional[AsyncQdrantClient] = None
_sparse_model = None  # lazy-loaded fastembed model, shared with kb_retriever


def _get_client() -> AsyncQdrantClient:
    global _qdrant
    if _qdrant is None:
        logger.info("[kb-index] connecting to Qdrant at %s", settings.QDRANT_URL)
        _qdrant = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
            check_compatibility=False,
        )
    return _qdrant


def set_client(client: AsyncQdrantClient) -> None:
    """Override the singleton client — used in tests to inject in-memory Qdrant."""
    global _qdrant
    _qdrant = client


def get_sparse_model():
    """Lazily load the shared BM25 sparse-embedding model (fastembed)."""
    global _sparse_model
    if _sparse_model is None:
        from fastembed import SparseTextEmbedding

        logger.info("[kb-index] loading sparse embedding model (Qdrant/bm25)")
        _sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    return _sparse_model


def embed_sparse(texts: list[str]) -> list[SparseVector]:
    model = get_sparse_model()
    return [
        SparseVector(indices=e.indices.tolist(), values=e.values.tolist())
        for e in model.embed(texts)
    ]


async def _ensure_collection() -> None:
    client = _get_client()
    existing = {c.name for c in (await client.get_collections()).collections}
    if COLLECTION not in existing:
        await client.create_collection(
            collection_name=COLLECTION,
            vectors_config={
                DENSE_VECTOR_NAME: VectorParams(
                    size=VECTOR_DIM,
                    distance=Distance.COSINE,
                    hnsw_config=HnswConfigDiff(m=0, payload_m=16),
                )
            },
            sparse_vectors_config={SPARSE_VECTOR_NAME: SparseVectorParams()},
        )
        await client.create_payload_index(
            collection_name=COLLECTION,
            field_name="org_id",
            field_schema=KeywordIndexParams(
                type=KeywordIndexType.KEYWORD, is_tenant=True, on_disk=True
            ),
        )
        await client.create_payload_index(
            collection_name=COLLECTION,
            field_name="kb_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        await client.create_payload_index(
            collection_name=COLLECTION,
            field_name="doc_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )


def _stable_id(kb_id: str, doc_id: str, chunk_index: int) -> str:
    """Deterministic UUID so re-indexing the same chunk position upserts rather
    than duplicates."""
    raw = f"{kb_id}:{doc_id}:{chunk_index}".encode()
    return str(uuid.UUID(hashlib.md5(raw).hexdigest()))


def _split_into_sections(text: str) -> list[str]:
    """Structural split: break on markdown-style headings or blank-line
    paragraph breaks, whichever the document actually has."""
    heading_split = re.split(r"\n(?=#{1,6}\s|\d+\.\s[A-Z]|[A-Z][A-Z \t]{4,}\n)", text)
    sections = [s for s in heading_split if s.strip()]
    if len(sections) > 1:
        return sections
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def _split_semantic(section: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """Semantic split within a section: sentence-boundary aware windowing so a
    chunk never cuts mid-sentence when avoidable."""
    if len(section) <= max_chars:
        return [section.strip()]

    sentences = re.split(r"(?<=[.!?])\s+", section)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 > max_chars and current:
            chunks.append(current.strip())
            # carry a small overlap from the tail of the previous chunk
            current = current[-overlap:] + " " + sentence
        else:
            current = f"{current} {sentence}".strip()
    if current.strip():
        chunks.append(current.strip())
    return chunks


def chunk_document(text: str) -> list[str]:
    """Structural split by section, then semantic split within each section."""
    chunks: list[str] = []
    for section in _split_into_sections(text):
        chunks.extend(_split_semantic(section))
    return [c for c in chunks if c.strip()]


def _build_chunk_links(n: int) -> list[list[int]]:
    """Sequential links only for phase 1 (prev/next chunk index) — the doc's
    own "how many hops" and scoring questions for hierarchical links are left
    unresolved deliberately; sequential links are the well-defined subset."""
    return [
        [i for i in (idx - 1, idx + 1) if 0 <= i < n]
        for idx in range(n)
    ]


async def index_document(
    org_id: str,
    kb_id: str,
    doc_id: str,
    text: str,
    doc_type: str = "",
    description: str = "",
) -> int:
    """Chunk, embed, and upsert a document's chunks into Qdrant.

    Upserts the new generation of points first, then deletes any points for
    this {org_id, kb_id, doc_id} that weren't part of this upsert (i.e. from
    a previous version with more chunks) — so a crash mid-index never leaves
    the document with zero searchable chunks.
    """
    if not settings.QDRANT_URL:
        logger.warning("[kb-index] QDRANT_URL is not set — skipping indexing for doc %s", doc_id)
        return 0

    await _ensure_collection()
    client = _get_client()

    chunks = chunk_document(text)
    if not chunks:
        logger.warning("[kb-index] no chunks extracted for doc=%s", doc_id)
        return 0

    links = _build_chunk_links(len(chunks))
    point_ids = [_stable_id(kb_id, doc_id, i) for i in range(len(chunks))]

    dense_vectors = []
    EMBED_BATCH = 50
    for i in range(0, len(chunks), EMBED_BATCH):
        dense_vectors.extend(await embed_texts(chunks[i : i + EMBED_BATCH]))
    sparse_vectors = embed_sparse(chunks)

    points = [
        PointStruct(
            id=point_ids[i],
            vector={DENSE_VECTOR_NAME: dense_vectors[i], SPARSE_VECTOR_NAME: sparse_vectors[i]},
            payload={
                "org_id": org_id,
                "kb_id": kb_id,
                "doc_id": doc_id,
                "doc_type": doc_type,
                "description": description,
                "chunk_index": i,
                "text": chunks[i],
                "linked_chunk_ids": [point_ids[j] for j in links[i]],
            },
        )
        for i in range(len(chunks))
    ]

    UPSERT_BATCH = 100
    for i in range(0, len(points), UPSERT_BATCH):
        await client.upsert(collection_name=COLLECTION, points=points[i : i + UPSERT_BATCH])

    # Drop any leftover points from a previous, larger version of this document.
    await client.delete(
        collection_name=COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(key="org_id", match=MatchValue(value=org_id)),
                FieldCondition(key="kb_id", match=MatchValue(value=kb_id)),
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
            ],
            must_not=[HasIdCondition(has_id=point_ids)],
        ),
    )

    logger.info("[kb-index] indexed %d chunk(s) for doc=%s kb=%s", len(points), doc_id, kb_id)
    return len(points)


async def delete_document_index(org_id: str, kb_id: str, doc_id: str) -> None:
    if not settings.QDRANT_URL:
        return
    await _ensure_collection()
    client = _get_client()
    await client.delete(
        collection_name=COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(key="org_id", match=MatchValue(value=org_id)),
                FieldCondition(key="kb_id", match=MatchValue(value=kb_id)),
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
            ]
        ),
    )


async def delete_kb_index(org_id: str, kb_id: str) -> None:
    """Remove every chunk belonging to a whole Knowledge Base (called on KB delete)."""
    if not settings.QDRANT_URL:
        return
    await _ensure_collection()
    client = _get_client()
    await client.delete(
        collection_name=COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(key="org_id", match=MatchValue(value=org_id)),
                FieldCondition(key="kb_id", match=MatchValue(value=kb_id)),
            ]
        ),
    )

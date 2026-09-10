"""Retrieve relevant chunks from a Knowledge Base given a natural-language query.

Pipeline: rephrase (using recent chat history) -> hybrid dense+sparse search,
scoped to org_id + kb_id(s) -> one-hop graph expand on linked chunks -> format.

Mirrors ai/rag/schema_retriever.py's shape (one sync implementation + a thin
async wrapper via run_in_threadpool) so both the FastAPI/graph engine and the
worker-thread ai/multi_orchestration engine share one code path.
"""

import logging

from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    FusionQuery,
    Fusion,
    MatchAny,
    MatchValue,
    Prefetch,
)

from ai.rag.kb_indexer import COLLECTION, DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME, embed_sparse
from ai.rag.kb_llm import embed_texts_sync
from backend.core.config import settings

logger = logging.getLogger(__name__)

TOP_K = 12
GRAPH_EXPAND_MAX_EXTRA = 6
# Fixed, deliberately conservative placeholder score for a chunk pulled in only
# via graph expand (it was never ranked by the search itself) — the doc's own
# "graph expand in detail" section leaves this scoring question unresolved;
# this is our chosen answer, tunable later.
GRAPH_EXPAND_SCORE = 0.0

_qdrant_sync: QdrantClient | None = None


def _get_sync_client() -> QdrantClient:
    global _qdrant_sync
    if _qdrant_sync is None:
        logger.info("[kb-retriever] connecting to Qdrant (sync) at %s", settings.QDRANT_URL)
        _qdrant_sync = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
            check_compatibility=False,
        )
    return _qdrant_sync


def set_sync_client(client: QdrantClient) -> None:
    global _qdrant_sync
    _qdrant_sync = client


def _build_kb_filter(org_id: str, kb_ids: list[str]) -> Filter:
    must = [FieldCondition(key="org_id", match=MatchValue(value=org_id))]
    if kb_ids:
        must.append(FieldCondition(key="kb_id", match=MatchAny(any=kb_ids)))
    return Filter(must=must)


def rephrase_query_sync(query: str, history: list[dict] | None = None) -> str:
    """Resolve pronouns/follow-ups ("it", "that") against the last 3 turns.

    Same last-3-turns window as MainAgent._route, same "fall back to the
    original query on any failure" convention as schema_retriever.py.
    """
    if not history:
        return query
    try:
        import litellm

        recent = (history or [])[-3:]
        convo = "\n".join(f"{h.get('role', 'user')}: {h.get('content', '')}" for h in recent)
        resp = litellm.completion(
            model=settings.DEFAULT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Rewrite the user's latest message into a fully self-contained "
                        "search query, resolving pronouns and references using the "
                        "conversation so far. Return ONLY the rewritten query, no "
                        "explanation."
                    ),
                },
                {"role": "user", "content": f"Conversation so far:\n{convo}\n\nLatest message: {query}"},
            ],
            temperature=0,
            max_tokens=100,
            timeout=10,
            num_retries=1,
        )
        rewritten = resp.choices[0].message.content.strip()
        return rewritten or query
    except Exception as e:
        logger.warning("[kb-retriever] rephrase failed — %s: %s, using original query", type(e).__name__, e)
        return query


def _format_hits(hits: list[dict], query: str) -> str:
    if not hits:
        logger.info("[kb-retriever] no relevant chunks found for query=%.100s", query)
        return "No relevant knowledge base content found for this query."

    lines = ["Relevant knowledge base content for your query:\n"]
    for hit in hits:
        p = hit["payload"]
        lines.append(f"Source document: {p.get('description') or p.get('doc_id')}")
        lines.append(p.get("text", ""))
        lines.append("")
    return "\n".join(lines)


def search_knowledge_base_sync(
    query: str,
    org_id: str,
    kb_ids: list[str],
    history: list[dict] | None = None,
    top_k: int = TOP_K,
    graph_expand: bool = True,
) -> str:
    if not settings.QDRANT_URL or not kb_ids:
        logger.warning("[kb-retriever] skipping — QDRANT_URL not set or no kb_ids")
        return "Knowledge base search is not available."

    rephrased = rephrase_query_sync(query, history)
    client = _get_sync_client()
    query_filter = _build_kb_filter(org_id, kb_ids)

    try:
        dense_vec = embed_texts_sync([rephrased])[0]
        sparse_vec = embed_sparse([rephrased])[0]

        result = client.query_points(
            collection_name=COLLECTION,
            prefetch=[
                Prefetch(query=dense_vec, using=DENSE_VECTOR_NAME, filter=query_filter, limit=top_k * 2),
                Prefetch(query=sparse_vec, using=SPARSE_VECTOR_NAME, filter=query_filter, limit=top_k * 2),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        hits = [{"payload": pt.payload, "score": pt.score} for pt in result.points]
    except Exception as e:
        logger.warning("[kb-retriever] search failed — %s: %s, skipping KB injection", type(e).__name__, e)
        return "Knowledge base search is temporarily unavailable."

    if graph_expand and hits:
        try:
            hits = _expand_with_links(client, hits)
        except Exception as e:
            # Expansion is an enhancement, not the core result — never let it
            # fail the whole search.
            logger.warning("[kb-retriever] graph expand failed — %s: %s, using unexpanded hits", type(e).__name__, e)

    return _format_hits(hits, query)


def _expand_with_links(client: QdrantClient, hits: list[dict]) -> list[dict]:
    seen_ids = set()
    linked_ids: list[str] = []
    for hit in hits:
        for lid in hit["payload"].get("linked_chunk_ids", []):
            if lid not in linked_ids:
                linked_ids.append(lid)
    linked_ids = linked_ids[:GRAPH_EXPAND_MAX_EXTRA]
    if not linked_ids:
        return hits

    fetched = client.retrieve(collection_name=COLLECTION, ids=linked_ids, with_payload=True)
    existing_texts = {h["payload"].get("text") for h in hits}
    for pt in fetched:
        if pt.payload.get("text") in existing_texts:
            continue
        hits.append({"payload": pt.payload, "score": GRAPH_EXPAND_SCORE})
    return hits


async def search_knowledge_base(
    query: str,
    org_id: str,
    kb_ids: list[str],
    history: list[dict] | None = None,
    top_k: int = TOP_K,
    graph_expand: bool = True,
) -> str:
    """Thin async wrapper — see schema_retriever.get_relevant_schema for why
    this is a run_in_threadpool wrapper rather than a second implementation."""
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(
        search_knowledge_base_sync, query, org_id, kb_ids, history, top_k, graph_expand
    )

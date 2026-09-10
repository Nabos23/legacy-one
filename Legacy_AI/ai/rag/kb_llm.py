"""Shared LLM-call wrapper for the Knowledge Base pipeline.

Every KB module (indexer, identifier, retriever) calls through this instead
of invoking litellm directly, so retry/timeout policy is defined once instead
of being reinvented per-file (the DB-schema RAG pipeline has four different,
inconsistent policies across schema_indexer.py / schema_retriever.py /
dbconnection/services.py — this file exists specifically to avoid repeating
that in the KB pipeline).
"""

import logging

import litellm

from backend.core.config import settings

logger = logging.getLogger(__name__)

EMBED_TIMEOUT_SECONDS = 15
EMBED_RETRIES = 2
COMPLETION_TIMEOUT_SECONDS = 30
COMPLETION_RETRIES = 2


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Dense-embed a batch of texts using the shared embedding model."""
    resp = await litellm.aembedding(
        model=settings.EMBEDDING_MODEL,
        input=texts,
        timeout=EMBED_TIMEOUT_SECONDS,
        num_retries=EMBED_RETRIES,
    )
    return [item["embedding"] if isinstance(item, dict) else item.embedding for item in resp.data]


def embed_texts_sync(texts: list[str]) -> list[list[float]]:
    """Sync counterpart for callers with no running event loop."""
    resp = litellm.embedding(
        model=settings.EMBEDDING_MODEL,
        input=texts,
        timeout=EMBED_TIMEOUT_SECONDS,
        num_retries=EMBED_RETRIES,
    )
    return [item["embedding"] if isinstance(item, dict) else item.embedding for item in resp.data]


async def complete(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 500,
    response_format: dict | None = None,
) -> str:
    """One completion call with the shared retry/timeout policy.

    Returns the raw message content. Raises on failure — callers decide their
    own fallback (e.g. "use the original query unchanged"), this function
    does not swallow errors itself.
    """
    kwargs = dict(
        model=model or settings.DEFAULT_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=COMPLETION_TIMEOUT_SECONDS,
        num_retries=COMPLETION_RETRIES,
    )
    if response_format:
        kwargs["response_format"] = response_format
    resp = await litellm.acompletion(**kwargs)
    return resp.choices[0].message.content.strip()

"""Document identification: generate a short description for an uploaded
document and classify it into the right Knowledge Base (or signal that a new
KB should be created).

Runs once per document at ingest time, as its own explicit pipeline stage —
not a side-effect of chunking/embedding. Same "one litellm call, fall back
safely on failure" convention as query rephrasing.
"""

import json
import logging

from ai.rag.kb_llm import complete

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a document classifier for an organization's knowledge base system. "
    "Given a document's text and a list of existing Knowledge Bases (each with a "
    "name and description), decide which KB this document belongs in.\n\n"
    "If it clearly matches an existing KB, return that KB's id. If none fit well, "
    "propose a new KB name and description (e.g. \"Time Tracking Policy\" — "
    "\"Rules for logging work hours and time-off requests\").\n\n"
    "Also write a short (1 sentence) description of THIS document specifically.\n\n"
    "Return ONLY valid JSON: "
    '{"document_description": "...", "matched_kb_id": "<id or null>", '
    '"new_kb_name": "<string or null>", "new_kb_description": "<string or null>"}'
)


async def identify_document(text: str, existing_kbs: list[dict]) -> dict:
    """Classify a document against existing KBs and generate its description.

    existing_kbs: list of {"id": str, "name": str, "description": str}

    Returns a dict with document_description, matched_kb_id (or None),
    new_kb_name, new_kb_description. On any failure, falls back to a
    generic description and no KB match (caller decides what "no match"
    means — for phase 1, that's auto-create a new KB from the filename).
    """
    kb_listing = "\n".join(
        f"- id={kb['id']}: {kb['name']} — {kb.get('description', '')}" for kb in existing_kbs
    ) or "(no existing knowledge bases yet)"

    excerpt = text[:6000]

    try:
        raw = await complete(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Existing Knowledge Bases:\n{kb_listing}\n\nDocument text:\n{excerpt}",
                },
            ],
            temperature=0.2,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(raw)
        return {
            "document_description": parsed.get("document_description") or "Untitled document",
            "matched_kb_id": parsed.get("matched_kb_id") or None,
            "new_kb_name": parsed.get("new_kb_name") or None,
            "new_kb_description": parsed.get("new_kb_description") or None,
        }
    except Exception as e:
        logger.warning("[kb-identify] classification failed — %s: %s, falling back to new KB", type(e).__name__, e)
        return {
            "document_description": "Untitled document",
            "matched_kb_id": None,
            "new_kb_name": "Uncategorized",
            "new_kb_description": "Documents that could not be automatically classified.",
        }

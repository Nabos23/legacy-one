"""
End-to-end test for the schema RAG pipeline.

Uses:
  - db_schema.json   (already fetched from the MSSQL org DB)
  - In-memory Qdrant (no server needed)
  - Real OpenAI embeddings via the .env OPENAI_API_KEY
  - org_id = '12'  (mohsin@gmail.com)
  - db_conn_id = 'test-conn-001' (synthetic, for test only)

Run:
  python backend/scripts/test_rag_pipeline.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
load_dotenv("backend/.env")
load_dotenv(".env")

ORG_ID = "12"
DB_CONN_ID = "test-conn-001"
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "db_schema.json")

TEST_QUERIES = [
    "show me employee payroll information",
    "which tables store leave requests and holidays",
    "I need data about assets assigned to employees",
    "find tables related to invoices and expenses",
    "where is performance evaluation stored",
]


async def main():
    # ── 1. Load schema ────────────────────────────────────────────────────
    print("Loading schema from db_schema.json ...")
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    print(f"  {len(schema)} tables loaded\n")

    # ── 2. Inject in-memory Qdrant ────────────────────────────────────────
    from qdrant_client import AsyncQdrantClient
    from ai.rag.schema_indexer import set_client
    from ai.rag.schema_retriever import get_relevant_schema

    mem_client = AsyncQdrantClient(location=":memory:")
    set_client(mem_client)
    print("In-memory Qdrant client injected\n")

    # ── 3. Index the schema ───────────────────────────────────────────────
    from ai.rag.schema_indexer import index_schema

    print("Indexing schema (LLM descriptions + embeddings) ...")
    print("  This may take 1-2 minutes for 108 tables ...\n")
    count = await index_schema(org_id=ORG_ID, db_conn_id=DB_CONN_ID, schema=schema)
    print(f"  Indexed {count} tables into Qdrant\n")

    # ── 4. Run test queries ───────────────────────────────────────────────
    print("=" * 60)
    print("RETRIEVAL TESTS")
    print("=" * 60)

    for query in TEST_QUERIES:
        print(f"\nQuery: \"{query}\"")
        print("-" * 40)
        result = await get_relevant_schema(query=query, db_conn_ids=[DB_CONN_ID], org_id=ORG_ID)
        print(result)

    print("\nPipeline test complete.")


if __name__ == "__main__":
    asyncio.run(main())

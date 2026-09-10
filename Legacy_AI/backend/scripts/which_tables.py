import asyncio, sys
from ai.rag.schema_retriever import get_relevant_schema

CONN_IDS = ['6a292c6fd1e608fe3e6dbfd8','6a29307ee06052d81fb1210a','6a29352c6a1e639c367ff1c7','6a29413bfcf5233d2827c118']
ORG_ID = ''  # set the org id these connections belong to before running

async def main(q):
    txt = await get_relevant_schema(q, CONN_IDS, ORG_ID)
    for line in txt.splitlines():
        if line.startswith("Table:"):
            print(line)

asyncio.run(main(sys.argv[1]))

class HumanInterruptException(Exception):
    """Raised by the ask_human tool to pause and surface a clarifying question."""
    def __init__(self, question: str):
        super().__init__(question)
        self.question = question

import base64
import binascii
import os
import tempfile
import uuid
import asyncio
import re
import shutil
import sys
import time
import logging
import httpx
from bson import ObjectId
from datetime import datetime, timezone
from ddgs import DDGS
from backend.core.encryption import decrypt, decrypt_or_none
import json
import litellm
from ai.agents.loop import _image_generation_with_retry
from backend.core.config import settings
from backend.db.database import sync_db
from starlette.concurrency import run_in_threadpool
from backend.core.query_runner import QueryExecutionError, run_query, run_mongo_query, run_sql_query

logger = logging.getLogger(__name__)


async def _assert_read_only_llm(query_input: str | dict) -> None:
    """Use a cheap LiteLLM completion to verify if the query is strictly read-only."""
    query_str = json.dumps(query_input) if isinstance(query_input, dict) else str(query_input or "").strip()
    if not query_str:
        return
    prompt = (
        "Determine if the following database query is a read-only query (for SQL, MONGO, MARIA etc), "
        "Also check if the query is valid or not. Output 'ok' if it is read-only, or 'bad' if it contains "
        "modifications/writes (like INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, REPLACE, etc.). Respond with only 'ok' or 'bad'."
    )
    resp = await litellm.acompletion(
        model=settings.TITLE_MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": query_str[:1000]},
        ],
        max_tokens=10,
        temperature=0.0,
    )
    decision = resp.choices[0].message.content.strip().lower()
    if "ok" not in decision:
        raise ValueError("Write query detected in read operation.")


def get_db_connection_doc(tool_doc: dict, sync_db) -> dict | None:
    """Fetch the database connection document for a given tool doc."""
    org_id = tool_doc.get("_org_id", "")
    db_conn_id = tool_doc.get("db_conn_id")
    if db_conn_id and ObjectId.is_valid(str(db_conn_id)):
        return sync_db.db_connections.find_one(
            {"_id": ObjectId(str(db_conn_id)), "organization_id": org_id, "is_deleted": {"$ne": True}}
        )
    return sync_db.db_connections.find_one(
        {"organization_id": org_id, "is_deleted": {"$ne": True}}
    )


def validate_query_and_connection(tool_doc: dict, args: dict, sync_db=sync_db, is_mongo: bool = False) -> str | None:
    """Validate that query parameters and database connection doc exist before execution."""
    query = (args.get("query") or "").strip()
    if is_mongo:
        if not query and not args.get("collection"):
            return "Provide a query to execute."
    elif not query:
        return "Provide a query to execute."

    conn_doc = get_db_connection_doc(tool_doc, sync_db)
    if not conn_doc:
        return "No database connection configured for this organization."

    return None


def build_fetch_schema_tool(org_id: str, db_conn_ids: list[str]) -> dict:
    """
    Synthetic tool doc for fetching DB schema, shaped exactly like the per-agent
    tool docs that come out of `tools_collection` so AgentRuntime / _make_tool_spec
    / _execute_tool handle it with no special-casing.

    Injected automatically into any agent that has the query_db tool, so the agent
    can look up real table/column names before it tries to query.  Reuses the
    existing RAG execution path via the `_is_search_schema` flag.
    """
    return {
        "name": "fetch_schema",
        "description": (
            "Fetch the connected database schema (tables and columns) relevant to a "
            "request. ALWAYS call this FIRST before using the query_db tool, so you "
            "use the exact table and column names that actually exist."
        ),
        "db_conn_id": None,
        "_is_search_schema": True,
        "_org_id": org_id,
        "_db_conn_ids": db_conn_ids,
    }


class Tools:

    @staticmethod
    def query_mongo_sync(tool_doc: dict, args: dict, sync_db) -> str:
        """Synchronous query runner explicitly for MongoDB databases."""
        query = (args.get("query") or "").strip()
        org_id = tool_doc.get("_org_id", "")
        agent_id = tool_doc.get("_agent_id", "")
        conn_doc = get_db_connection_doc(tool_doc, sync_db)

        logger.info("[Tools.query_mongo_sync] executing MongoDB query for org=%s agent=%s", org_id, agent_id)
        start = time.monotonic()
        error: str | None = None
        rows = 0
        try:
            conn_str = decrypt(conn_doc["connection_string"])
            query_param = query or args
            result = run_mongo_query(conn_str, query_param)
            rows = result.count("\n")
            return result
        except QueryExecutionError as e:
            error = str(e)
            return f"Query failed: {e}"
        except Exception as e:  # noqa: BLE001
            error = f"{type(e).__name__}: {e}"
            return f"Unexpected error: {error}"
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            try:
                sync_db.query_audit_logs.insert_one({
                    "org_id": org_id,
                    "agent_id": agent_id,
                    "tool_name": tool_doc.get("name", "query_mongo"),
                    "db_conn_id": str(conn_doc["_id"]) if conn_doc else "",
                    "query": str(query),
                    "rows_returned": rows,
                    "duration_ms": duration_ms,
                    "error": error,
                    "executed_at": datetime.now(timezone.utc),
                })
            except Exception:  # noqa: BLE001
                logging.getLogger(__name__).exception(
                    "[query-audit-mongo] failed to write audit log for org=%s", org_id,
                )

    @staticmethod
    def query_sql_sync(tool_doc: dict, args: dict, sync_db) -> str:
        """Synchronous query runner explicitly for SQL databases."""
        query = (args.get("query") or "").strip()
        org_id = tool_doc.get("_org_id", "")
        agent_id = tool_doc.get("_agent_id", "")
        conn_doc = get_db_connection_doc(tool_doc, sync_db)

        logger.info("[Tools.query_sql_sync] executing SQL query for org=%s agent=%s", org_id, agent_id)
        start = time.monotonic()
        error: str | None = None
        rows = 0
        try:
            conn_str = decrypt(conn_doc["connection_string"])
            result = run_sql_query(conn_str, query)
            rows = result.count("\n")
            return result
        except QueryExecutionError as e:
            error = str(e)
            return f"Query failed: {e}"
        except Exception as e:  # noqa: BLE001
            error = f"{type(e).__name__}: {e}"
            return f"Unexpected error: {error}"
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            try:
                sync_db.query_audit_logs.insert_one({
                    "org_id": org_id,
                    "agent_id": agent_id,
                    "tool_name": tool_doc.get("name", "query_sql"),
                    "db_conn_id": str(conn_doc["_id"]) if conn_doc else "",
                    "query": query,
                    "rows_returned": rows,
                    "duration_ms": duration_ms,
                    "error": error,
                    "executed_at": datetime.now(timezone.utc),
                })
            except Exception:  # noqa: BLE001
                logging.getLogger(__name__).exception(
                    "[query-audit-sql] failed to write audit log for org=%s", org_id,
                )

    @staticmethod
    async def query_mongo_read(tool_doc: dict, args: dict) -> str:
        """Execute a MongoDB read query via threadpool after read-only LLM check."""
        err = validate_query_and_connection(tool_doc, args, is_mongo=True)
        if err:
            return err
        query_input = args.get("query") or args
        await _assert_read_only_llm(query_input)
        try:
            return await asyncio.wait_for(
                run_in_threadpool(Tools.query_mongo_sync, tool_doc, args, sync_db), timeout=30
            )
        except asyncio.TimeoutError:
            return "Query timed out after 30 seconds. Try a more selective query."

    @staticmethod
    async def query_mongo_write(tool_doc: dict, args: dict) -> str:
        """Execute a MongoDB write query via threadpool."""
        err = validate_query_and_connection(tool_doc, args, is_mongo=True)
        if err:
            return err
        try:
            return await asyncio.wait_for(
                run_in_threadpool(Tools.query_mongo_sync, tool_doc, args, sync_db), timeout=30
            )
        except asyncio.TimeoutError:
            return "Query timed out after 30 seconds. Try a more selective query."

    @staticmethod
    async def query_sql_read(tool_doc: dict, args: dict) -> str:
        """Execute a SQL read query via threadpool after read-only LLM check."""
        err = validate_query_and_connection(tool_doc, args, is_mongo=False)
        if err:
            return err
        query = (args.get("query") or "").strip()
        if query:
            await _assert_read_only_llm(query)
        try:
            return await asyncio.wait_for(
                run_in_threadpool(Tools.query_sql_sync, tool_doc, args, sync_db), timeout=30
            )
        except asyncio.TimeoutError:
            return "Query timed out after 30 seconds. Try a more selective query."

    @staticmethod
    async def query_sql_write(tool_doc: dict, args: dict) -> str:
        """Execute a SQL write query via threadpool."""
        err = validate_query_and_connection(tool_doc, args, is_mongo=False)
        if err:
            return err
        try:
            return await asyncio.wait_for(
                run_in_threadpool(Tools.query_sql_sync, tool_doc, args, sync_db), timeout=30
            )
        except asyncio.TimeoutError:
            return "Query timed out after 30 seconds. Try a more selective query."

    @staticmethod
    def search_internet(input: dict) -> str:
        """
        Search the internet using DuckDuckGo.
        Expects input = {"query": "<question>"}
        Returns a formatted string with the top search results including
        titles, URLs, and snippets.
        """


        query = input.get("query", "").strip()
        max_results: int = input.get("max_results", 5)

        if not query:
            return "No query provided. Please supply a 'query' key."

        try:
            with DDGS() as ddgs:
                hits = list(ddgs.text(query, max_results=max_results))

            if not hits:
                return f"No results found for query: '{query}'"

            results = []
            for i, hit in enumerate(hits, start=1):
                title = hit.get("title", "No title")
                url = hit.get("href", "")
                snippet = hit.get("body", "No description available.")
                results.append(
                    f"[{i}] {title}\n"
                    f"    URL: {url}\n"
                    f"    {snippet}"
                )

            return (
                f"Search results for '{query}':\n\n"
                + "\n\n".join(results)
            )

        except Exception as e:  # noqa: BLE001
            return f"Search failed for query '{query}': {type(e).__name__}: {e}"

    @staticmethod
    def ask_human(input: dict, **_config) -> str:
        """
        Pause and ask the user a clarifying question (human-in-the-loop).

        Always raises HumanInterruptException; the caller (e.g. SubAgent._run)
        catches it and surfaces the question as the agent's output.
        """

        raise HumanInterruptException(
            input.get("question") or input.get("query") or "The agent needs clarification."
        )


    @staticmethod
    async def generate_document(input: dict) -> str:
        """
        Execute AI-supplied Python code inside an isolated subprocess to produce
        a document of any type (pdf, docx, xlsx, pptx, csv, html, md, txt, svg, ...).
 
        Example
        Input: {
            "code": "from docx import Document\\ndoc = Document()\\ndoc.add_heading('Report')\\ndoc.save(OUTPUT_PATH)",
            "file_name": "sales_report",
            "extension": "docx"
        }
        Output: "Report generated successfully.\\nDownload it at:\\n/chat/reports/sales_report_a1b2c3d4.docx"
        """
 

        if "code" not in input:
            return (
                "Missing required 'code' argument. This tool expects "
                "{'code': '<python>', 'file_name': '<name>', 'extension': '<ext>', 'reason': '<why>'} "
                "-- got keys: " + ", ".join(sorted(input.keys())) + ". "
                "If you're seeing this, the tool schema the agent was given does not match "
                "the tool's actual implementation -- check the registered tool spec."
            )
 
        code = (input.get("code") or "").strip()
        file_name = (input.get("file_name") or "document").strip()
        extension = (input.get("extension") or "").strip().lstrip(".")
        dependencies = input.get("dependencies") or []
 
        if not code:
            return "'code' was provided but is empty. Supply Python code that saves the document to OUTPUT_PATH."
        if not extension:
            return "No 'extension' provided (e.g. 'pdf', 'docx', 'xlsx')."
        if not isinstance(dependencies, list) or not all(isinstance(d, str) for d in dependencies):
            return "'dependencies', if provided, must be a list of package name strings."
 
        # Only allow simple pip package specifiers (name, optional ==version) --
        # blocks flags, URLs, VCS refs, and shell metacharacters.
        _PKG_RE = re.compile(r"^[A-Za-z0-9_.\-]+(==[A-Za-z0-9_.\-]+)?$")
        bad = [d for d in dependencies if not _PKG_RE.fullmatch(d)]
        if bad:
            return f"Invalid dependency name(s): {bad}. Only plain 'package' or 'package==version' is allowed."
 
        file_name = "".join(c for c in file_name.replace(" ", "_") if c.isalnum() or c in "_-") or "document"
        short_id = uuid.uuid4().hex[:8]
        filename = f"{file_name}_{short_id}.{extension}"
 
        workdir = tempfile.mkdtemp(prefix="docgen_")
        try:
            output_path = os.path.join(workdir, filename)
 
            # Wrap the agent's code so OUTPUT_PATH is defined before it runs,
            # without letting the agent choose or override that path itself.
            script_path = os.path.join(workdir, "script.py")
            wrapped = (
                f"OUTPUT_PATH = {output_path!r}\n\n"
                + code
            )
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(wrapped)
 
            python_bin = sys.executable
 
            if dependencies:
                venv_dir = os.path.join(workdir, "venv")
                create_proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "venv", "--system-site-packages", venv_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, create_err = await asyncio.wait_for(create_proc.communicate(), timeout=30)
                if create_proc.returncode != 0:
                    return f"Document generation failed: could not create sandbox environment: {create_err.decode(errors='replace').strip()}"
 
                venv_python = (
                    os.path.join(venv_dir, "Scripts", "python.exe")
                    if sys.platform == "win32"
                    else os.path.join(venv_dir, "bin", "python")
                )
                install_proc = await asyncio.create_subprocess_exec(
                    venv_python, "-m", "pip", "install", "--quiet", "--no-input", *dependencies,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    _, install_err = await asyncio.wait_for(install_proc.communicate(), timeout=120)
                except asyncio.TimeoutError:
                    install_proc.kill()
                    await install_proc.wait()
                    return f"Document generation failed: installing dependencies {dependencies} timed out."
 
                if install_proc.returncode != 0:
                    error_output = install_err.decode("utf-8", errors="replace").strip()
                    return f"Document generation failed: could not install dependencies {dependencies}: {error_output}"
 
                python_bin = venv_python
 
            # Run in a separate process, isolated from the main FastAPI process.
            # Swappable later for a container/Docker-based executor without
            # touching the rest of this tool.
            proc = await asyncio.create_subprocess_exec(
                python_bin, script_path,
                cwd=workdir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return "Document generation failed: execution timed out after 60 seconds."
 
            if proc.returncode != 0:
                error_output = stderr.decode("utf-8", errors="replace").strip()
                return f"Document generation failed: {error_output or 'Unknown error (no traceback captured).'}"
 
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                created_files = [
                    os.path.join(workdir, f) for f in os.listdir(workdir)
                    if f not in ("script.py", "venv") and os.path.isfile(os.path.join(workdir, f))
                ]
                if created_files:
                    output_path = created_files[0]
                else:
                    return "Document generation failed: Output file was not created. Ensure your Python code saves the document to OUTPUT_PATH."
 
            reports_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "backend", "storage", "reports"
            )
            reports_dir = os.path.normpath(reports_dir)
            os.makedirs(reports_dir, exist_ok=True)
 
            dest_path = os.path.join(reports_dir, filename)
            shutil.move(output_path, dest_path)
 
            return f"Report generated successfully.\nDownload it at:\n/chat/reports/{filename}"
 
        except Exception as e:  # noqa: BLE001
            return f"Document generation failed: {type(e).__name__}: {e}"
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    @staticmethod
    async def generate_image(tool_doc: dict, input: dict) -> str:
        """
        Generate an image from a text prompt using an AI image model and return
        a download link.
 
        Example
        Input: {"prompt": "A minimalist logo of a fox, flat vector style, orange and white",
                "file_name": "fox_logo", "size": "1024x1024", "reason": "User asked for a logo concept."}
        Output: "Image generated successfully.\\nDownload it at:\\n/chat/reports/fox_logo_a1b2c3d4.png"
        """

        prompt = (input.get("prompt") or input.get("query") or  "").strip()
        file_name = (input.get("file_name") or "image").strip()
        size = (input.get("size") or "1024x1024").strip()
 
        if not prompt:
            return "'prompt' is required: describe the image to generate."
 
        file_name = "".join(c for c in file_name.replace(" ", "_") if c.isalnum() or c in "_-") or "image"
        
        # trusted, server-side — never came from the LLM
        encrypted_api_key = tool_doc.get("encrypted_api_key")
        custom_base_url = tool_doc.get("custom_base_url")
        custom_model = tool_doc.get("custom_model")

        api_key = None
        if encrypted_api_key:
            api_key = decrypt_or_none(encrypted_api_key)
            if api_key is None:
                return (
                    "This tool's custom API key could not be read (it may need to "
                    "be reconfigured)."
                )

        if custom_model:
            model = custom_model
            base_url = custom_base_url
        else:
            model = getattr(settings, "IMAGE_MODEL", "gpt-image-1")
            api_key = None
            base_url = None
 
        try:
            resp = await asyncio.to_thread(
                _image_generation_with_retry,
                model=model, prompt=prompt, n=1, size=size,
                api_key=api_key, api_base=base_url,
            )

        except Exception as e:  # noqa: BLE001
            return f"Image generation failed: {type(e).__name__}: {e}"
 
        try:
            item = resp.data[0]
            image_b64 = getattr(item, "b64_json", None) or item.get("b64_json")
            image_url = getattr(item, "url", None) or (item.get("url") if isinstance(item, dict) else None)
        except (AttributeError, IndexError, KeyError, TypeError) as e:
            return f"Image generation failed: could not read model response ({type(e).__name__}: {e})."
 
        if not image_b64 and not image_url:
            return "Image generation failed: model returned no image data."
 
        short_id = uuid.uuid4().hex[:8]
        filename = f"{file_name}_{short_id}.png"
 
        reports_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "backend", "storage", "reports")
        )
        os.makedirs(reports_dir, exist_ok=True)
        dest_path = os.path.join(reports_dir, filename)
 
        try:
            if image_b64:
                with open(dest_path, "wb") as f:
                    f.write(base64.b64decode(image_b64))
            else:
                async with httpx.AsyncClient(timeout=60) as client:
                    r = await client.get(image_url)
                    r.raise_for_status()
                    with open(dest_path, "wb") as f:
                        f.write(r.content)
        except (OSError, binascii.Error) as e:
            return f"Image generation failed: could not save image: {type(e).__name__}: {e}"
        except Exception as e:  # noqa: BLE001 - covers httpx errors without a hard dependency on the type
            return f"Image generation failed: could not fetch/save image: {type(e).__name__}: {e}"
 
        return f"Image generated successfully.\nDownload it at:\n/chat/reports/{filename}"
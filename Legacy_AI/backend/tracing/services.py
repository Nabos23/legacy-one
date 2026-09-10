import asyncio
import hashlib
import json
import logging
import time
from typing import Optional

import httpx
from bson import ObjectId
from fastapi import HTTPException, status

from backend.auth.permissions import is_org_manager_or_above, is_super_admin
from backend.auth.schemas import UserPublic
from backend.core.config import settings
from backend.db.database import agents_collection, users_collection

from ai.tracing.tags import agent_tag, org_tag

logger = logging.getLogger(__name__)


def effective_org_id(current_user: UserPublic, organization_id: Optional[str]) -> str:
    """Super admins may scope requests to any org; all others are locked to their own."""
    if is_super_admin(current_user.role) and organization_id:
        return organization_id
    return current_user.organization_id


def effective_user_id(current_user: UserPublic, requested_user_id: Optional[str]) -> Optional[str]:
    """org_admin/org_manager/super_admin may scope a query to any user (or pass
    None to aggregate across the whole org); a plain 'user' is always locked
    to their own id, regardless of what was requested."""
    if is_org_manager_or_above(current_user.role):
        return requested_user_id
    return current_user.id


_CACHE_TTL_SECONDS = 60
_cache: dict[str, tuple[float, dict]] = {}
_MAX_CACHE_ENTRIES = 200
_LF_MAX_RETRIES = 3
_lf_failures: dict[str, tuple[float, int, str]] = {}
_lf_inflight: dict[str, "asyncio.Future[dict]"] = {}
_lf_refresh_tasks: set["asyncio.Task[None]"] = set()

_lf_client: httpx.AsyncClient | None = None
_lf_client_lock = asyncio.Lock()


async def _get_lf_client() -> httpx.AsyncClient:
    global _lf_client
    if _lf_client is not None and not _lf_client.is_closed:
        return _lf_client
    async with _lf_client_lock:
        if _lf_client is None or _lf_client.is_closed:
            _lf_client = httpx.AsyncClient(
                base_url=settings.LANGFUSE_HOST,
                auth=(settings.LANGFUSE_PUBLIC_KEY, settings.LANGFUSE_SECRET_KEY),
                timeout=httpx.Timeout(
                    connect=settings.LANGFUSE_CONNECT_TIMEOUT,
                    read=settings.LANGFUSE_READ_TIMEOUT,
                    write=settings.LANGFUSE_READ_TIMEOUT,
                    pool=settings.LANGFUSE_CONNECT_TIMEOUT,
                ),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
    return _lf_client


async def close_langfuse_client() -> None:
    global _lf_client
    if _lf_client is not None and not _lf_client.is_closed:
        await _lf_client.aclose()
    _lf_client = None


def _cache_key(path: str, params: dict | None) -> str:
    raw = path + "|" + json.dumps(sorted((params or {}).items()), default=str)
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_get(key: str) -> dict | None:
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry[0]) < settings.LANGFUSE_CACHE_TTL_SECONDS:
        return entry[1]
    return None


def _cache_get_stale(key: str) -> dict | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    if time.monotonic() - entry[0] < settings.LANGFUSE_STALE_TTL_SECONDS:
        return entry[1]
    _cache.pop(key, None)
    return None


def _cache_put(key: str, value: dict) -> None:
    if len(_cache) >= _MAX_CACHE_ENTRIES:
        now = time.monotonic()
        stale = [k for k, (ts, _) in _cache.items() if now - ts >= _CACHE_TTL_SECONDS]
        for k in stale:
            _cache.pop(k, None)
        if len(_cache) >= _MAX_CACHE_ENTRIES:
            oldest = min(_cache, key=lambda k: _cache[k][0])
            _cache.pop(oldest, None)
    _cache[key] = (time.monotonic(), value)


def _is_configured() -> bool:
    return bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)


async def _lf_get(path: str, params: dict | None = None) -> dict:
    if not _is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Langfuse is not configured. Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY.",
        )

    key = _cache_key(path, params)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    stale = _cache_get_stale(key)
    if stale is not None:
        _schedule_refresh(key, path, params)
        return stale

    failure = _lf_failures.get(key)
    if failure is not None:
        failed_at, code, detail = failure
        if time.monotonic() - failed_at < settings.LANGFUSE_FAILURE_CACHE_SECONDS:
            raise HTTPException(status_code=code, detail=detail)
        _lf_failures.pop(key, None)

    return await _lf_get_uncached(key, path, params)


def _schedule_refresh(key: str, path: str, params: dict | None) -> None:
    if key in _lf_inflight:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _refresh() -> None:
        try:
            await _lf_get_uncached(key, path, params)
        except Exception:
            pass

    task = loop.create_task(_refresh())
    _lf_refresh_tasks.add(task)
    task.add_done_callback(_lf_refresh_tasks.discard)


async def _lf_get_uncached(key: str, path: str, params: dict | None) -> dict:
    existing = _lf_inflight.get(key)
    if existing is not None:
        return await asyncio.shield(existing)

    loop = asyncio.get_running_loop()
    future: "asyncio.Future[dict]" = loop.create_future()
    _lf_inflight[key] = future
    try:
        data = await _lf_fetch(key, path, params)
    except BaseException as exc:
        _lf_inflight.pop(key, None)
        if not future.done():
            future.set_exception(exc)
        future.exception()
        raise
    else:
        _lf_inflight.pop(key, None)
        if not future.done():
            future.set_result(data)
        return data


async def _lf_fetch(key: str, path: str, params: dict | None) -> dict:
    deadline = time.monotonic() + settings.LANGFUSE_TOTAL_BUDGET_SECONDS
    attempts = max(1, settings.LANGFUSE_MAX_ATTEMPTS)
    last_exc: HTTPException | None = None

    for attempt in range(attempts):
        if time.monotonic() >= deadline:
            break
        try:
            client = await _get_lf_client()
            resp = await client.get(path, params=params or {})
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.warning(
                "Langfuse %s on %s — attempt %d/%d",
                type(exc).__name__, path, attempt + 1, attempts,
            )
            last_exc = HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Langfuse request timed out ({type(exc).__name__}).",
            )
            if attempt + 1 < attempts and time.monotonic() + 1 < deadline:
                await asyncio.sleep(1)
            continue

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("retry-after", 2 * (attempt + 1)))
            remaining = deadline - time.monotonic()
            delay = min(retry_after, 15, max(0.0, remaining))
            logger.warning(
                "Langfuse 429 on %s — attempt %d/%d, waiting %.1fs",
                path, attempt + 1, attempts, delay,
            )
            last_exc = HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Langfuse rate-limited (429).",
            )
            if delay <= 0 or attempt + 1 >= attempts:
                break
            await asyncio.sleep(delay)
            continue

        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Resource not found in Langfuse.")

        if not resp.is_success:
            logger.error("Langfuse API error %d: %s", resp.status_code, resp.text[:300])
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Langfuse returned {resp.status_code}.",
            )

        data = resp.json()
        _cache_put(key, data)
        _lf_failures.pop(key, None)
        return data

    exc = last_exc or HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Langfuse request failed.",
    )
    _lf_failures[key] = (time.monotonic(), exc.status_code, str(exc.detail))
    logger.error(
        "Langfuse gave up on %s after %d attempt(s); failing fast for %.0fs",
        path, attempts, settings.LANGFUSE_FAILURE_CACHE_SECONDS,
    )
    raise exc


# ---------------------------------------------------------------------------
# Normalizers — Langfuse uses camelCase; our schemas use snake_case
# ---------------------------------------------------------------------------

def _norm_trace(t: dict) -> dict:
    meta = t.get("metadata") or {}
    return {
        "id":         t["id"],
        "timestamp":  t.get("timestamp"),
        "name":       t.get("name", ""),
        "input":      t.get("input"),
        "output":     t.get("output"),
        "session_id": t.get("sessionId"),
        "user_id":    t.get("userId"),
        "metadata":   meta,
        "tags":       t.get("tags", []),
        "latency":    t.get("latency"),
        "total_cost": t.get("totalCost"),
        "agent_name": meta.get("agent_name"),
    }


def _norm_observation(o: dict) -> dict:
    return {
        "id":                    o["id"],
        "trace_id":              o.get("traceId"),
        "type":                  o.get("type", "SPAN"),
        "name":                  o.get("name", ""),
        "start_time":            o.get("startTime"),
        "end_time":              o.get("endTime"),
        "input":                 o.get("input"),
        "output":                o.get("output"),
        "metadata":              o.get("metadata"),
        "parent_observation_id": o.get("parentObservationId"),
        "model":                 o.get("model"),
        "usage":                 o.get("usage"),
        "calculated_total_cost": o.get("calculatedTotalCost"),
        "latency":               o.get("latency"),
    }


def _norm_session(s: dict) -> dict:
    traces = s.get("traces") or []
    return {
        "id":          s["id"],
        "created_at":  s.get("createdAt"),
        "user_id":     traces[0].get("userId") if traces else None,
        "trace_count": len(traces),
        "bookmarked":  s.get("bookmarked", False),
    }


def _usage_from_dict(usage: dict) -> tuple[int, int]:
    """Extract input/output token counts from a Langfuse usage object."""
    if not usage:
        return 0, 0
    inp = int(usage.get("input") or usage.get("promptTokens") or 0)
    out = int(usage.get("output") or usage.get("completionTokens") or 0)
    return inp, out


def _generation_usage(observations: list) -> tuple[int, int]:
    """Sum token usage from GENERATION observations on a trace."""
    total_in = total_out = 0
    for o in observations:
        if (o.get("type") or "").upper() != "GENERATION":
            continue
        inp, out = _usage_from_dict(o.get("usage") or {})
        total_in += inp
        total_out += out
    return total_in, total_out


async def _batch_generation_usage(trace_ids: list[str]) -> dict[str, tuple[int, int]]:
    """Return a map of trace_id -> (input_tokens, output_tokens) by fetching
    all GENERATION observations in a single API call.

    This avoids the N+1 pattern of fetching trace detail for each trace, which
    exhausts Langfuse's per-minute rate limit on the trace-detail endpoint.
    The observations endpoint is project-scoped so no tag filter is needed.
    """
    if not trace_ids:
        return {}

    trace_id_set = set(trace_ids)
    usage_map: dict[str, tuple[int, int]] = {}

    try:
        pages = await asyncio.gather(
            *(
                _lf_get("/api/public/observations", {"type": "GENERATION", "limit": 100, "page": n})
                for n in (1, 2)
            ),
            return_exceptions=True,
        )
        observations: list = []
        for page in pages:
            if isinstance(page, BaseException):
                continue
            page_data = page.get("data", [])
            observations.extend(page_data)
            if len(page_data) < 100:
                break
        data = {"data": observations}
    except Exception as e:
        logger.warning("Failed to batch-fetch generation observations: %s", e)
        return {}

    for obs in data.get("data", []):
        tid = obs.get("traceId")
        if tid not in trace_id_set:
            continue
        inp, out = _usage_from_dict(obs.get("usage") or {})
        prev_in, prev_out = usage_map.get(tid, (0, 0))
        usage_map[tid] = (prev_in + inp, prev_out + out)

    return usage_map


# ---------------------------------------------------------------------------
# Tag helpers
# ---------------------------------------------------------------------------

async def _agent_tag(agent_id: str) -> Optional[str]:
    """Resolve an agent's Langfuse tag from its MongoDB id. Returns None if not found."""
    if not ObjectId.is_valid(agent_id):
        return None
    try:
        doc = await agents_collection.find_one({"_id": ObjectId(agent_id)}, {"name": 1})
    except Exception:
        return None
    return agent_tag(doc["name"]) if doc and doc.get("name") else None


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

async def list_traces(
    org_id: str,
    page: int = 1,
    limit: int = 20,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    tags = [org_tag(org_id)]
    if agent_id:
        tag = await _agent_tag(agent_id)
        if tag:
            tags.append(tag)

    params: dict = {"page": page, "limit": limit, "tags": tags}
    if session_id:
        params["sessionId"] = session_id
    if user_id:
        params["userId"] = user_id

    data = await _lf_get("/api/public/traces", params)
    meta = data.get("meta", {})
    items = [_norm_trace(t) for t in data.get("data", [])]
    return {
        "items":       items,
        "total":       meta.get("totalItems", len(items)),
        "page":        meta.get("page", page),
        "page_size":   meta.get("limit", limit),
        "total_pages": meta.get("totalPages", 1),
    }


async def get_trace_detail(trace_id: str, org_id: str, user_id: Optional[str] = None) -> dict:
    data = await _lf_get(f"/api/public/traces/{trace_id}")

    # Security: reject traces that don't belong to this org
    if org_tag(org_id) not in (data.get("tags") or []):
        raise HTTPException(status_code=404, detail="Trace not found.")
    if user_id and data.get("userId") != user_id:
        raise HTTPException(status_code=404, detail="Trace not found.")

    trace = _norm_trace(data)
    trace["observations"] = [
        _norm_observation(o) for o in (data.get("observations") or [])
    ]
    return trace


async def _resolve_user_labels(
    user_ids: set[str],
) -> dict[str, tuple[Optional[str], Optional[str]]]:
    """Map Mongo user id -> (name, email) for the given ids. Best-effort: ids
    that aren't valid ObjectIds or aren't found are simply omitted."""
    if not user_ids:
        return {}
    valid_oids = [ObjectId(uid) for uid in user_ids if ObjectId.is_valid(uid)]
    if not valid_oids:
        return {}
    try:
        cursor = users_collection.find({"_id": {"$in": valid_oids}}, {"name": 1, "email": 1})
        return {
            str(doc["_id"]): (doc.get("name"), doc.get("email"))
            async for doc in cursor
        }
    except Exception:
        return {}


async def get_trace_stats(
    org_id: str,
    agent_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    tags = [org_tag(org_id)]
    if agent_id:
        tag = await _agent_tag(agent_id)
        if tag:
            tags.append(tag)

    lf_params: dict = {"tags": tags, "limit": 100, "page": 1}
    if user_id:
        lf_params["userId"] = user_id
    traces_data = await _lf_get("/api/public/traces", lf_params)
    traces = traces_data.get("data", [])
    total = traces_data.get("meta", {}).get("totalItems", len(traces))

    gen_usage = await _batch_generation_usage([t["id"] for t in traces])

    total_cost = 0.0
    total_input = 0
    total_output = 0
    agent_map: dict = {}
    user_map: dict = {}

    for t in traces:
        # Prefer list-level usage (rarely populated); fall back to aggregated gen usage
        list_inp, list_out = _usage_from_dict(t.get("usage") or {})
        if list_inp or list_out:
            inp, out = list_inp, list_out
        else:
            inp, out = gen_usage.get(t["id"], (0, 0))

        cost = t.get("totalCost") or 0.0
        total_cost += cost
        total_input += inp
        total_output += out

        a_name = (t.get("metadata") or {}).get("agent_name") or "direct"
        if a_name not in agent_map:
            agent_map[a_name] = {"trace_count": 0, "total_cost": 0.0, "total_tokens": 0}
        agent_map[a_name]["trace_count"] += 1
        agent_map[a_name]["total_cost"] += cost
        agent_map[a_name]["total_tokens"] += inp + out

        t_user_id = t.get("userId") or "unknown"
        if t_user_id not in user_map:
            user_map[t_user_id] = {"trace_count": 0, "total_cost": 0.0, "total_tokens": 0}
        user_map[t_user_id]["trace_count"] += 1
        user_map[t_user_id]["total_cost"] += cost
        user_map[t_user_id]["total_tokens"] += inp + out

    breakdown = [
        {"agent_name": k, **v}
        for k, v in sorted(agent_map.items(), key=lambda x: -x[1]["trace_count"])
    ]

    user_labels = await _resolve_user_labels(set(user_map) - {"unknown"})
    user_breakdown = [
        {
            "user_id": uid,
            "user_name": user_labels.get(uid, (None, None))[0],
            "user_email": user_labels.get(uid, (None, None))[1],
            **v,
        }
        for uid, v in sorted(user_map.items(), key=lambda x: -x[1]["trace_count"])
    ]

    return {
        "total_traces":        total,
        "total_cost":          round(total_cost, 6),
        "total_input_tokens":  total_input,
        "total_output_tokens": total_output,
        "agent_breakdown":     breakdown,
        "user_breakdown":      user_breakdown,
    }


async def list_sessions(page: int = 1, limit: int = 20) -> dict:
    data = await _lf_get("/api/public/sessions", {"page": page, "limit": limit})
    meta  = data.get("meta", {})
    items = [_norm_session(s) for s in data.get("data", [])]
    return {
        "items":       items,
        "total":       meta.get("totalItems", len(items)),
        "page":        meta.get("page", page),
        "page_size":   meta.get("limit", limit),
        "total_pages": meta.get("totalPages", 1),
    }

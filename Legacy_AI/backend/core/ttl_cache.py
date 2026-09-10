import asyncio
import time
from typing import Awaitable, Callable, Generic, Hashable, Optional, TypeVar

T = TypeVar("T")


class AsyncTTLCache(Generic[T]):
    def __init__(self, ttl_seconds: float, max_entries: int = 2048, name: str = "cache"):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.name = name
        self._values: dict[Hashable, tuple[float, T]] = {}
        self._inflight: dict[Hashable, asyncio.Future[T]] = {}
        self.hits = 0
        self.misses = 0

    def _get_fresh(self, key: Hashable) -> Optional[tuple[T]]:
        entry = self._values.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if self.ttl_seconds <= 0 or time.monotonic() - stored_at >= self.ttl_seconds:
            self._values.pop(key, None)
            return None
        return (value,)

    def _store(self, key: Hashable, value: T) -> None:
        if self.ttl_seconds <= 0:
            return
        if len(self._values) >= self.max_entries:
            victims = sorted(self._values.items(), key=lambda kv: kv[1][0])
            for k, _ in victims[: max(1, self.max_entries // 10)]:
                self._values.pop(k, None)
        self._values[key] = (time.monotonic(), value)

    async def get_or_load(self, key: Hashable, loader: Callable[[], Awaitable[T]]) -> T:
        fresh = self._get_fresh(key)
        if fresh is not None:
            self.hits += 1
            return fresh[0]

        existing = self._inflight.get(key)
        if existing is not None:
            self.hits += 1
            return await asyncio.shield(existing)

        self.misses += 1
        loop = asyncio.get_running_loop()
        future: asyncio.Future[T] = loop.create_future()
        self._inflight[key] = future
        try:
            value = await loader()
        except BaseException as exc:
            self._inflight.pop(key, None)
            if not future.done():
                future.set_exception(exc)
            future.exception()
            raise
        else:
            self._store(key, value)
            self._inflight.pop(key, None)
            if not future.done():
                future.set_result(value)
            return value

    def invalidate(self, key: Hashable) -> None:
        self._values.pop(key, None)

    def clear(self) -> None:
        self._values.clear()

    def stats(self) -> dict[str, int | float]:
        total = self.hits + self.misses
        return {
            "name": self.name,
            "entries": len(self._values),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 3) if total else 0.0,
            "ttl_seconds": self.ttl_seconds,
        }

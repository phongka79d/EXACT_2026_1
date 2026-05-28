from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List


def build_local_premise_cache_key(record_id: int) -> str:
    return f"record:{record_id}"


def build_api_premise_cache_key(
    premises: List[str],
    *,
    model: str,
    prompt_version: str,
    compiler_version: str,
) -> str:
    payload = {
        "premises": [p.strip() for p in premises],
        "model": model,
        "prompt_version": prompt_version,
        "compiler_version": compiler_version,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return f"premises_hash:{digest}"


@dataclass
class PremiseFrameCache:
    _values: Dict[str, Any]
    _locks: Dict[str, asyncio.Lock]
    _guard: asyncio.Lock

    def __init__(self) -> None:
        self._values = {}
        self._locks = {}
        self._guard = asyncio.Lock()

    async def get_or_create(self, key: str, factory: Callable[[], Awaitable[Any]]) -> Any:
        if key in self._values:
            return self._values[key]
        lock = await self._get_lock(key)
        async with lock:
            if key in self._values:
                return self._values[key]
            value = await factory()
            self._values[key] = value
            return value

    async def _get_lock(self, key: str) -> asyncio.Lock:
        async with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

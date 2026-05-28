from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import ConfigError, load_llm_config
from app.llm_client import LLMError, LLMPermanentError, LLMTimeoutError, LLMTransientError, OpenAICompatibleClient
from app.redaction import redact_obj, redact_text


async def run_async_smoke(dotenv: str, requests_count: int, prompt: str) -> Dict[str, Any]:
    config = load_llm_config(dotenv)
    client = OpenAICompatibleClient(config)
    sem = asyncio.Semaphore(config.max_concurrency)
    results: List[Dict[str, Any]] = [None] * requests_count  # type: ignore[assignment]

    async def worker(i: int) -> None:
        async with sem:
            resp = await client.acomplete(prompt)
            results[i] = {"index": i, "preview": resp.text[:80]}

    tasks = [asyncio.create_task(worker(i)) for i in range(requests_count)]
    await asyncio.gather(*tasks)
    return {
        "status": "ok",
        "config": config.sanitized(),
        "count": requests_count,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Live async LLM smoke test using .env configuration.")
    parser.add_argument("--dotenv", default=".env", help="Path to .env file")
    parser.add_argument("--count", default=3, type=int, help="Number of concurrent requests")
    parser.add_argument("--prompt", default="Reply with exactly: OK", help="Tiny runtime-safe prompt")
    args = parser.parse_args()
    try:
        payload = asyncio.run(run_async_smoke(args.dotenv, args.count, args.prompt))
        print(json.dumps(redact_obj(payload), ensure_ascii=True))
        return 0
    except ConfigError as exc:
        print(json.dumps({"status": "blocked", "reason": redact_text(str(exc))}, ensure_ascii=True))
        return 2
    except (LLMTimeoutError, LLMTransientError, LLMPermanentError, LLMError) as exc:
        print(json.dumps({"status": "blocked", "reason": redact_text(str(exc))}, ensure_ascii=True))
        return 3


if __name__ == "__main__":
    sys.exit(main())

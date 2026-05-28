from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import ConfigError, load_llm_config
from app.llm_client import LLMError, LLMPermanentError, LLMTimeoutError, LLMTransientError, OpenAICompatibleClient
from app.redaction import redact_obj, redact_text


def main() -> int:
    parser = argparse.ArgumentParser(description="Live sync LLM smoke test using .env configuration.")
    parser.add_argument("--dotenv", default=".env", help="Path to .env file")
    parser.add_argument("--prompt", default="Reply with exactly: OK", help="Tiny runtime-safe prompt")
    args = parser.parse_args()
    try:
        config = load_llm_config(args.dotenv)
        client = OpenAICompatibleClient(config)
        response = client.complete(args.prompt)
        payload = {
            "status": "ok",
            "config": config.sanitized(),
            "response_preview": response.text[:120],
        }
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

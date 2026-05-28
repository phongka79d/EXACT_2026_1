from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import ConfigError, load_llm_config
from app.frame_artifacts import write_frame_events_jsonl
from app.llm_client import OpenAICompatibleClient
from app.parse_frame_extractor import extract_premise_frame
from app.redaction import redact_obj


def main() -> int:
    parser = argparse.ArgumentParser(description="Live smoke test for strict compact parse-frame extraction.")
    parser.add_argument("--dotenv", default=".env")
    parser.add_argument("--artifacts", default="artifacts/frame_events.jsonl")
    parser.add_argument(
        "--premise-text",
        default="If a student has GPA at least 7.0 then the student can change majors.",
        help="Runtime-safe premise text to parse.",
    )
    parser.add_argument("--premise-id", type=int, default=1)
    args = parser.parse_args()

    try:
        cfg = load_llm_config(args.dotenv)
    except ConfigError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2

    client = OpenAICompatibleClient(cfg)
    try:
        result = extract_premise_frame(
            client=client,
            premise_text=args.premise_text,
            premise_id=args.premise_id,
            repair_attempts=2,
        )
    except Exception as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        return 1

    write_frame_events_jsonl(args.artifacts, result["events"])
    print(
        json.dumps(
            redact_obj(
                {
                    "status": "ok",
                    "frame_kind": result["frame"].get("kind"),
                    "source_id": result["frame"].get("source_id"),
                }
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

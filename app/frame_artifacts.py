from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from app.redaction import redact_obj

EVENT_TYPES = {"raw_response", "normalized_frame", "validated_frame", "compiled_ast", "rejected"}


class ArtifactContractError(ValueError):
    pass


def build_frame_event(event_type: str, source_id: str, payload: Dict[str, Any], reason: str | None = None) -> Dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise ArtifactContractError("invalid frame event type")
    if not isinstance(source_id, str) or not source_id:
        raise ArtifactContractError("source_id is required")
    if not isinstance(payload, dict):
        raise ArtifactContractError("payload must be an object")
    event = {"event_type": event_type, "source_id": source_id, "payload": payload}
    if event_type == "rejected":
        if not isinstance(reason, str) or not reason:
            raise ArtifactContractError("rejected event requires reason")
        event["reason"] = reason
    return event


def serialize_frame_events_jsonl(events: Iterable[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for event in events:
        lines.append(json.dumps(redact_obj(event), ensure_ascii=False))
    return "\n".join(lines) + ("\n" if lines else "")


def write_frame_events_jsonl(path: str, events: Iterable[Dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = serialize_frame_events_jsonl(events)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(payload)

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SECRET_QUERY_KEYS = {"api_key", "apikey", "key", "token", "access_token", "auth"}
SECRET_JSON_KEYS = {"api_key", "authorization", "auth", "token", "access_token"}


def _redact_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except Exception:
        return value
    if not parts.scheme or not parts.netloc:
        return value
    query = parse_qsl(parts.query, keep_blank_values=True)
    new_query = []
    for key, val in query:
        if key.lower() in SECRET_QUERY_KEYS:
            new_query.append((key, "***REDACTED***"))
        else:
            new_query.append((key, val))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(new_query), parts.fragment))


def redact_text(value: str) -> str:
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer ***REDACTED***", value)
    redacted = re.sub(r"(?i)(api[_-]?key\s*[=:]\s*)([^\s,;]+)", r"\1***REDACTED***", redacted)
    if "http://" in redacted or "https://" in redacted:
        tokens = redacted.split()
        redacted = " ".join(_redact_url(token) for token in tokens)
    return redacted


def redact_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        clean = {}
        for key, value in obj.items():
            if str(key).lower() in SECRET_JSON_KEYS:
                clean[key] = "***REDACTED***"
            else:
                clean[key] = redact_obj(value)
        return clean
    if isinstance(obj, list):
        return [redact_obj(item) for item in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj


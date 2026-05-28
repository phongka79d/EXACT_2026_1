from __future__ import annotations

from app.redaction import redact_obj, redact_text


def test_redact_bearer() -> None:
    value = "Authorization: Bearer abc.def.ghi"
    assert "abc.def.ghi" not in redact_text(value)


def test_redact_query_token() -> None:
    value = "https://example.com/path?token=abc123&x=1"
    redacted = redact_text(value)
    assert "abc123" not in redacted
    assert "REDACTED" in redacted


def test_redact_nested_payload() -> None:
    payload = {
        "error": {"authorization": "Bearer secret", "msg": "bad"},
        "api_key": "xyz",
    }
    out = redact_obj(payload)
    assert out["api_key"] == "***REDACTED***"
    assert out["error"]["authorization"] == "***REDACTED***"

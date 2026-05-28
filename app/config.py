from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from app.redaction import redact_text


class ConfigError(ValueError):
    pass


def load_dotenv(dotenv_path: str = ".env") -> None:
    path = Path(dotenv_path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Missing required env key: {name}")
    return value


def _parse_int(name: str, min_value: int = 1) -> int:
    raw = _require(name)
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if value < min_value:
        raise ConfigError(f"{name} must be >= {min_value}")
    return value


def _parse_float(name: str, min_value: float = 0.0) -> float:
    raw = _require(name)
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc
    if value < min_value:
        raise ConfigError(f"{name} must be >= {min_value}")
    return value


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    temperature: float
    max_tokens: int
    timeout_seconds: float
    max_retries: int
    retry_base_delay_seconds: float
    retry_max_delay_seconds: float
    max_concurrency: int

    def sanitized(self) -> Dict[str, object]:
        return {
            "base_url": redact_text(self.base_url),
            "api_key": "***REDACTED***",
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "retry_base_delay_seconds": self.retry_base_delay_seconds,
            "retry_max_delay_seconds": self.retry_max_delay_seconds,
            "max_concurrency": self.max_concurrency,
        }


def load_llm_config(dotenv_path: str = ".env") -> LLMConfig:
    load_dotenv(dotenv_path)
    base_url = _require("SHOPAIKEY_BASE_URL")
    api_key = _require("SHOPAIKEY_API_KEY")
    model = _require("SHOPAIKEY_MODEL")
    temperature = _parse_float("LLM_TEMPERATURE", min_value=0.0)
    if temperature > 2.0:
        raise ConfigError("LLM_TEMPERATURE must be <= 2.0")
    max_tokens = _parse_int("LLM_MAX_TOKENS")
    timeout_seconds = _parse_float("LLM_TIMEOUT_SECONDS", min_value=0.1)
    max_retries = _parse_int("LLM_MAX_RETRIES", min_value=0)
    retry_base_delay_seconds = _parse_float("LLM_RETRY_BASE_DELAY_SECONDS", min_value=0.0)
    retry_max_delay_seconds = _parse_float("LLM_RETRY_MAX_DELAY_SECONDS", min_value=0.0)
    max_concurrency = _parse_int("LLM_MAX_CONCURRENCY")
    if retry_max_delay_seconds < retry_base_delay_seconds:
        raise ConfigError("LLM_RETRY_MAX_DELAY_SECONDS must be >= LLM_RETRY_BASE_DELAY_SECONDS")
    return LLMConfig(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        retry_base_delay_seconds=retry_base_delay_seconds,
        retry_max_delay_seconds=retry_max_delay_seconds,
        max_concurrency=max_concurrency,
    )


from __future__ import annotations

import os

import pytest

from app.config import ConfigError, load_llm_config


def _set_valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHOPAIKEY_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("SHOPAIKEY_API_KEY", "secret")
    monkeypatch.setenv("SHOPAIKEY_MODEL", "qwen2.5-7b-instruct")
    monkeypatch.setenv("LLM_TEMPERATURE", "0")
    monkeypatch.setenv("LLM_MAX_TOKENS", "128")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("LLM_RETRY_BASE_DELAY_SECONDS", "0.2")
    monkeypatch.setenv("LLM_RETRY_MAX_DELAY_SECONDS", "1.0")
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "4")


def test_load_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_valid_env(monkeypatch)
    cfg = load_llm_config("__none__.env")
    assert cfg.model == "qwen2.5-7b-instruct"
    assert cfg.max_retries == 2


def test_missing_required(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_valid_env(monkeypatch)
    monkeypatch.delenv("SHOPAIKEY_MODEL", raising=False)
    with pytest.raises(ConfigError):
        load_llm_config("__none__.env")


def test_invalid_numeric(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("LLM_MAX_TOKENS", "abc")
    with pytest.raises(ConfigError):
        load_llm_config("__none__.env")


def test_retry_range(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("LLM_RETRY_BASE_DELAY_SECONDS", "2")
    monkeypatch.setenv("LLM_RETRY_MAX_DELAY_SECONDS", "1")
    with pytest.raises(ConfigError):
        load_llm_config("__none__.env")

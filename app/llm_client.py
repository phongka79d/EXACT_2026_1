from __future__ import annotations

import asyncio
import json
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from urllib import error, request

from app.config import LLMConfig


class LLMError(RuntimeError):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMTransientError(LLMError):
    pass


class LLMPermanentError(LLMError):
    pass


@dataclass
class LLMResponse:
    text: str
    raw: Dict[str, Any]


def _default_sleep(seconds: float) -> None:
    time.sleep(seconds)


class OpenAICompatibleClient:
    def __init__(
        self,
        config: LLMConfig,
        transport: Optional[Callable[[str, Dict[str, Any], Dict[str, str], float], Dict[str, Any]]] = None,
        sleeper: Callable[[float], None] = _default_sleep,
    ) -> None:
        self.config = config
        self._transport = transport or self._http_transport
        self._sleep = sleeper

    def _http_transport(self, url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float) -> Dict[str, Any]:
        req = request.Request(url=url, method="POST", headers=headers, data=json.dumps(payload).encode("utf-8"))
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                content = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            code = getattr(exc, "code", 500)
            body = exc.read().decode("utf-8", errors="ignore")
            if code in (408, 409, 425, 429, 500, 502, 503, 504):
                raise LLMTransientError(f"Transient HTTP error {code}: {body[:200]}") from exc
            raise LLMPermanentError(f"Permanent HTTP error {code}: {body[:200]}") from exc
        except TimeoutError as exc:
            raise LLMTimeoutError("Request timed out") from exc
        except Exception as exc:  # network errors
            raise LLMTransientError(str(exc)) from exc
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError("Malformed JSON response") from exc

    def _completion_url(self) -> str:
        return f"{self.config.base_url.rstrip('/')}/chat/completions"

    def _payload(self, prompt: str) -> Dict[str, Any]:
        return {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

    def _parse_response(self, data: Dict[str, Any]) -> LLMResponse:
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise LLMError("Malformed response shape: missing choices[0].message.content") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError("Malformed response shape: empty content")
        return LLMResponse(text=content.strip(), raw=data)

    def complete(self, prompt: str) -> LLMResponse:
        last_error: Optional[Exception] = None
        for attempt in range(self.config.max_retries + 1):
            try:
                data = self._transport(self._completion_url(), self._payload(prompt), self._headers(), self.config.timeout_seconds)
                return self._parse_response(data)
            except LLMPermanentError:
                raise
            except LLMTimeoutError as exc:
                last_error = exc
            except LLMTransientError as exc:
                last_error = exc
            except LLMError:
                raise
            if attempt < self.config.max_retries:
                span = min(
                    self.config.retry_max_delay_seconds,
                    self.config.retry_base_delay_seconds * (2 ** attempt),
                )
                delay = 0.0 if span <= 0 else random.uniform(0.0, span)
                self._sleep(delay)
        if isinstance(last_error, LLMTimeoutError):
            raise LLMTimeoutError("Request timed out after retries") from last_error
        raise LLMTransientError("Transient error after retries") from last_error

    async def acomplete(self, prompt: str) -> LLMResponse:
        return await asyncio.to_thread(self.complete, prompt)


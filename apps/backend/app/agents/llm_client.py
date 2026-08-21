"""Provider-neutral LLM client boundary.

The diagnosis graph only depends on this module.  A callable can be injected
in tests or by an application integration; otherwise an OpenAI-compatible
HTTP endpoint can be used without adding a provider SDK dependency.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from typing import Any

import httpx


class LLMClient:
    """Small synchronous client with a stable completion interface."""

    def __init__(
        self,
        complete_fn: Callable[..., str] | None = None,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._complete_fn = complete_fn
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "")).rstrip("/")
        self.model = model or os.getenv("LLM_MODEL", "")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.timeout = timeout

    def complete(self, prompt: str, **kwargs: Any) -> str:
        """Return plain text from the configured provider."""
        if self._complete_fn is not None:
            return str(self._complete_fn(prompt, **kwargs))
        if not self.base_url or not self.model:
            raise RuntimeError("No LLM provider configured; inject complete_fn or set LLM_BASE_URL and LLM_MODEL")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            **kwargs,
        }
        response = httpx.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        body = response.json()
        return str(body["choices"][0]["message"]["content"])

    def structured_complete(
        self,
        prompt: str,
        schema: type[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Complete and parse JSON, optionally validating it with a Pydantic model."""
        text = self.complete(
            f"{prompt}\nReturn only valid JSON."
            if "json" not in prompt.lower()
            else prompt,
            **kwargs,
        )
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM returned invalid JSON") from exc
        if schema is not None:
            if hasattr(schema, "model_validate"):
                return schema.model_validate(value)
            if isinstance(value, Mapping):
                return schema(**value)
        return value


def get_llm_client() -> LLMClient:
    """Build the configured client at the integration boundary."""
    return LLMClient()

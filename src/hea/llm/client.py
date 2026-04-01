"""OpenRouter HTTP client for LLM calls."""

from __future__ import annotations

import json
import logging

import httpx
from pydantic import ValidationError

from hea.llm.exceptions import LLMAPIError, LLMParseError, LLMTimeoutError
from hea.models.llm import LLMResponse
from hea.settings import Settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.AsyncClient(
            base_url=settings.openrouter_base_url,
            timeout=httpx.Timeout(
                float(settings.llm_timeout_seconds),
                connect=5.0,
            ),
        )

    async def __aenter__(self) -> LLMClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMResponse:
        """Send a chat completion request and parse the structured response."""
        response_schema = LLMResponse.model_json_schema()

        payload = {
            "model": self._settings.openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "llm_response",
                    "strict": True,
                    "schema": response_schema,
                },
            },
        }

        try:
            resp = await self._http.post(
                "/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("LLM request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMAPIError(
                f"LLM API error: {exc.response.status_code}"
            ) from exc

        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return LLMResponse.model_validate(parsed)
        except (KeyError, IndexError, json.JSONDecodeError, ValidationError) as exc:
            raise LLMParseError("Failed to parse LLM response") from exc

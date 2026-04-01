"""Tests for LLM client error handling and context manager."""

import json

import httpx
import pytest

from hea.llm.client import LLMClient
from hea.llm.exceptions import LLMAPIError, LLMParseError, LLMTimeoutError
from hea.settings import Settings


def _make_settings(**overrides: object) -> Settings:
    defaults = {
        "telegram_bot_token": "fake-token",
        "openrouter_api_key": "fake-key",
        "openrouter_base_url": "https://fake.api",
    }
    return Settings(**(defaults | overrides))


class TestLLMClientContextManager:
    async def test_aenter_returns_self(self):
        settings = _make_settings()
        client = LLMClient(settings)
        async with client as c:
            assert c is client

    async def test_aexit_closes_http_client(self):
        settings = _make_settings()
        async with LLMClient(settings) as client:
            assert not client._http.is_closed
        assert client._http.is_closed


class TestLLMClientErrorHandling:
    async def test_timeout_raises_llm_timeout_error(self):
        settings = _make_settings()
        client = LLMClient(settings)

        transport = httpx.MockTransport(
            lambda req: (_ for _ in ()).throw(httpx.TimeoutException("timed out"))
        )
        client._http = httpx.AsyncClient(transport=transport, base_url="https://fake.api")

        with pytest.raises(LLMTimeoutError):
            await client.complete("system", "user")
        await client.close()

    async def test_http_error_raises_llm_api_error(self):
        settings = _make_settings()
        client = LLMClient(settings)

        transport = httpx.MockTransport(
            lambda req: httpx.Response(500, text="Internal Server Error")
        )
        client._http = httpx.AsyncClient(transport=transport, base_url="https://fake.api")

        with pytest.raises(LLMAPIError):
            await client.complete("system", "user")
        await client.close()

    async def test_invalid_json_raises_llm_parse_error(self):
        settings = _make_settings()
        client = LLMClient(settings)

        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "not valid json {"}}]
                },
            )
        )
        client._http = httpx.AsyncClient(transport=transport, base_url="https://fake.api")

        with pytest.raises(LLMParseError):
            await client.complete("system", "user")
        await client.close()

    async def test_missing_choices_raises_llm_parse_error(self):
        settings = _make_settings()
        client = LLMClient(settings)

        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json={"unexpected": "shape"})
        )
        client._http = httpx.AsyncClient(transport=transport, base_url="https://fake.api")

        with pytest.raises(LLMParseError):
            await client.complete("system", "user")
        await client.close()

    async def test_successful_response(self):
        settings = _make_settings()
        client = LLMClient(settings)

        llm_content = json.dumps({
            "reasoning": "test",
            "matched_category": "young",
            "score_updates": {},
            "next_node_id": "end",
            "user_message": "Hello!",
            "needs_clarification": False,
        })
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json={"choices": [{"message": {"content": llm_content}}]},
            )
        )
        client._http = httpx.AsyncClient(transport=transport, base_url="https://fake.api")

        resp = await client.complete("system", "user")
        assert resp.matched_category == "young"
        await client.close()

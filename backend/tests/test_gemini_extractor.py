import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from google import genai
from pydantic import SecretStr

from questline.config import Settings
from questline.providers.errors import ProviderUnavailable
from questline.providers.extractor import FakeExtractor
from questline.providers.gemini_extractor import GeminiExtractor
from questline.providers.selection import extractor_for_settings
from questline.schemas import MessageRead

MESSAGE = MessageRead(
    id=uuid4(),
    external_id="message-1",
    author_id="Alice",
    sent_at="2026-10-10T14:30:00Z",
    text="Let's visit Coastal Bakery, Big Sur.",
)
MENTION = {
    "mention_text": "Coastal Bakery",
    "search_query": "Coastal Bakery, Big Sur",
    "message_ids": [str(MESSAGE.id)],
    "category_guess": "eat",
}


class StubClient:
    def __init__(self, text=None, error=None):
        self.aio = self
        self.models = SimpleNamespace(
            generate_content=AsyncMock(return_value=SimpleNamespace(text=text), side_effect=error)
        )
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True


def extractor(text=None, error=None):
    client = StubClient(text, error)
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)
        return client

    return GeminiExtractor("secret-key", "configured-model", client_factory=factory), client, calls


async def test_grounded_structured_output_and_configuration():
    provider, client, calls = extractor(json.dumps({"mentions": [MENTION, MENTION]}))
    result = await provider.extract([MESSAGE])
    assert len(result) == 1
    assert result[0].message_ids == [MESSAGE.id]
    assert client.closed
    assert calls[0]["http_options"].retry_options.attempts == 1
    assert calls[0]["http_options"].timeout == 25_000
    config = client.models.generate_content.call_args.kwargs
    assert config["model"] == "configured-model"
    assert json.loads(config["contents"])["messages"] == [
        {"id": str(MESSAGE.id), "text": MESSAGE.text}
    ]
    assert config["config"].response_mime_type == "application/json"
    assert config["config"].response_json_schema["$defs"]["Mention"]["properties"]["message_ids"][
        "items"
    ]["enum"] == [str(MESSAGE.id)]
    assert "untrusted" in config["config"].system_instruction
    assert "secret-key" not in config["contents"]


async def test_empty_input_does_not_call_sdk():
    provider, _, calls = extractor()
    assert await provider.extract([]) == []
    assert calls == []


@pytest.mark.parametrize(
    "text",
    [
        None,
        "not JSON",
        "{}",
        '{"mentions": null}',
        json.dumps({"mentions": [{**MENTION, "message_ids": []}]}),
        json.dumps({"mentions": [{**MENTION, "message_ids": [str(uuid4())]}]}),
        json.dumps({"mentions": [{**MENTION, "mention_text": "Invented Place"}]}),
        json.dumps({"mentions": [{**MENTION, "search_query": " "}]}),
        json.dumps({"mentions": [{**MENTION, "votes": {"Alice": "in"}}]}),
        json.dumps({"mentions": [{**MENTION, "category_guess": "invented"}]}),
    ],
)
async def test_invalid_ungrounded_or_vote_output_fails_safely(text):
    provider, _, _ = extractor(text)
    with pytest.raises(ProviderUnavailable) as error:
        await provider.extract([MESSAGE])
    assert "secret-key" not in str(error.value)
    assert MESSAGE.text not in str(error.value)


@pytest.mark.parametrize("error", [RuntimeError("secret-key"), TimeoutError("secret-key")])
async def test_sdk_failure_is_sanitized(error):
    provider, client, _ = extractor(error=error)
    with pytest.raises(ProviderUnavailable, match="Import again") as caught:
        await provider.extract([MESSAGE])
    assert "secret-key" not in str(caught.value)
    assert client.closed


async def test_shutdown_cancellation_propagates():
    provider, _, _ = extractor(error=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await provider.extract([MESSAGE])


async def test_real_sdk_request_uses_mock_transport():
    calls = []

    def handler(request):
        calls.append(request)
        body = json.loads(request.content)
        assert ":generateContent" in str(request.url)
        assert request.headers["x-goog-api-key"] == "offline-key"
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert body["generationConfig"]["responseJsonSchema"]["type"] == "object"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": json.dumps({"mentions": [MENTION]})}],
                        },
                        "finishReason": "STOP",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:

        def factory(**kwargs):
            options = kwargs["http_options"].model_copy(update={"httpx_async_client": http_client})
            return genai.Client(api_key=kwargs["api_key"], http_options=options)

        provider = GeminiExtractor("offline-key", "configured-model", client_factory=factory)
        assert len(await provider.extract([MESSAGE])) == 1
    assert len(calls) == 1


def test_selection_and_required_configuration():
    assert isinstance(extractor_for_settings(Settings(_env_file=None)), FakeExtractor)
    for key, model in [(None, None), ("key", None), (None, "model"), ("", "model")]:
        settings = Settings(
            _env_file=None,
            planner_provider="gemini",
            gemini_model=model,
            gemini_api_key=SecretStr(key) if key is not None else None,
        )
        with pytest.raises(ProviderUnavailable, match="GEMINI_API_KEY and GEMINI_MODEL"):
            extractor_for_settings(settings)
    settings = Settings(
        _env_file=None,
        planner_provider="gemini",
        gemini_model="configured-model",
        gemini_api_key=SecretStr("key"),
    )
    assert isinstance(extractor_for_settings(settings), GeminiExtractor)

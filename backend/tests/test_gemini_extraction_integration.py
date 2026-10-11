import json
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select
from test_gemini_extractor import StubClient
from test_google_maps import PLACE
from test_integration import TRIP, drain, request_generation

from questline.models import Import, Message
from questline.providers import selection
from questline.providers.extractor import Mention
from questline.providers.gemini_extractor import GeminiExtractor
from questline.providers.google_maps import GoogleMaps
from questline.services.extraction import extract_places

pytestmark = pytest.mark.integration


async def test_real_extraction_pipeline_preserves_evidence_and_skips_bad_matches(api, monkeypatch):
    client, app = api
    trip_id = (await client.post("/api/v1/trips", json=TRIP)).json()["trip"]["id"]
    settings = app.state.settings
    settings.planner_provider = "gemini"
    settings.maps_provider = "google"
    settings.gemini_api_key = SecretStr("offline-gemini-key")
    settings.google_maps_api_key = SecretStr("offline-google-key")
    settings.gemini_model = "configured-model"
    sdk = StubClient()

    async def generate(**kwargs):
        messages = json.loads(kwargs["contents"])["messages"]
        mentions = [
            {
                "mention_text": name,
                "search_query": name,
                "message_ids": [message["id"]],
            }
            for message in messages
            for name in ["Coastal Bakery", "Far Cafe", "Mystery Cafe"]
            if name in message["text"]
        ]
        return SimpleNamespace(text=json.dumps({"mentions": mentions}))

    sdk.models.generate_content = AsyncMock(side_effect=generate)
    monkeypatch.setattr(
        selection, "GeminiExtractor", partial(GeminiExtractor, client_factory=lambda **kwargs: sdk)
    )

    def google(request):
        query = json.loads(request.content)["textQuery"]
        assert "locationBias" in json.loads(request.content)
        name = "Different Place" if query == "Mystery Cafe" else query
        location = (
            {"latitude": 40.7, "longitude": -74} if query == "Far Cafe" else PLACE["location"]
        )
        return httpx.Response(
            200,
            json={
                "places": [
                    {
                        **PLACE,
                        "id": query,
                        "displayName": {"text": name},
                        "location": location,
                    }
                ]
            },
        )

    monkeypatch.setattr(
        selection, "GoogleMaps", partial(GoogleMaps, transport=httpx.MockTransport(google))
    )
    text = "Alice: Coastal Bakery sounds good.\nBob: Far Cafe maybe?\nCarol: Mystery Cafe?"
    for _ in range(2):
        response = await client.post(f"/api/v1/trips/{trip_id}/import", json={"text": text})
        assert response.status_code == 202, response.text
        await drain(app)
    state = (await client.get(f"/api/v1/trips/{trip_id}")).json()
    assert all(imported["status"] == "succeeded" for imported in state["imports"])
    assert len(state["places"]) == 1
    assert state["places"][0]["name"] == "Coastal Bakery"
    assert len(state["places"][0]["source_message_ids"]) == 1
    assert len(state["trip"]["unresolved_mentions"]) == 2
    assert len(state["messages"]) == 3
    assert state["votes"] == []
    # Planning is still deliberately unavailable, not a fake Gemini success.
    assert (await request_generation(client, trip_id)).status_code == 503


async def test_missing_configuration_rejects_before_import_persistence(api):
    client, app = api
    trip_id = (await client.post("/api/v1/trips", json=TRIP)).json()["trip"]["id"]
    app.state.settings.planner_provider = "gemini"
    app.state.settings.gemini_api_key = None
    app.state.settings.gemini_model = None
    response = await client.post(f"/api/v1/trips/{trip_id}/import", json={"text": "Alice: Bakery"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"
    state = (await client.get(f"/api/v1/trips/{trip_id}")).json()
    assert state["imports"] == [] and state["messages"] == []


async def test_bad_evidence_fails_before_any_maps_calls(api):
    client, app = api
    trip_id = (await client.post("/api/v1/trips", json=TRIP)).json()["trip"]["id"]
    response = await client.post(f"/api/v1/trips/{trip_id}/import", json={"text": "Alice: Bakery"})
    import_id = response.json()["import_id"]
    async with app.state.sessions() as session:
        imported = await session.scalar(select(Import).where(Import.id == import_id))
        assert imported is not None
        saved_id = imported.id

    class BadExtractor:
        async def extract(self, messages):
            return [Mention(mention_text="Bakery", search_query="Bakery", message_ids=[uuid4()])]

    class NoMaps:
        async def resolve_place(self, *args, **kwargs):
            pytest.fail("Unknown message IDs must be rejected before paid calls")

    await extract_places(saved_id, app.state.sessions, extractor=BadExtractor(), maps=NoMaps())
    state = (await client.get(f"/api/v1/trips/{trip_id}")).json()
    assert state["imports"][0]["status"] == "failed"
    assert state["places"] == []
    assert state["imports"][0]["error"] == "Extraction failed. Import again to retry."
    # The original input remains available; no transcript content was leaked into the error.
    async with app.state.sessions() as session:
        assert (await session.scalars(select(Message))).all()

from functools import partial

import httpx
import pytest
from pydantic import SecretStr
from test_google_maps import PLACE
from test_integration import TRIP

from questline.providers import selection
from questline.providers.google_maps import GoogleMaps

pytestmark = pytest.mark.integration


async def test_google_create_add_and_failure_contracts(api, monkeypatch):
    client, app = api
    app.state.settings.maps_provider = "google"
    app.state.settings.google_maps_api_key = SecretStr("private-test-key")
    calls = []

    def handler(request):
        import json

        query = json.loads(request.content)["textQuery"]
        calls.append(query)
        if query == "Unknown":
            return httpx.Response(200, json={})
        if query == "Failure":
            return httpx.Response(403, text="private-test-key")
        place = {**PLACE, "id": query, "displayName": {"text": query}}
        return httpx.Response(200, json={"places": [place]})

    monkeypatch.setattr(
        selection, "GoogleMaps", partial(GoogleMaps, transport=httpx.MockTransport(handler))
    )
    response = await client.post("/api/v1/trips", json=TRIP)
    assert response.status_code == 201, response.text
    trip = response.json()["trip"]
    assert trip["origin"]["google_place_id"] == TRIP["origin"]
    assert trip["destination"]["google_place_id"] == TRIP["destination"]
    url = f"/api/v1/trips/{trip['id']}/places"
    added = await client.post(url, json={"query": "Bakery"})
    assert added.status_code == 201, added.text
    place = added.json()["place"]
    assert place["google_place_id"] == "Bakery"
    assert place["category"] == "eat"
    assert place["source"] == "added"
    repeated = await client.post(url, json={"query": "Bakery"})
    assert repeated.json()["place"]["id"] == place["id"]
    missing = await client.post(url, json={"query": "Unknown"})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "place_not_found"
    failure = await client.post(url, json={"query": "Failure"})
    assert failure.status_code == 503
    assert failure.json()["error"]["code"] == "provider_unavailable"
    assert "private-test-key" not in failure.text
    state = (await client.get(f"/api/v1/trips/{trip['id']}")).json()
    assert len(state["places"]) == 1
    assert state["revision"] == 3
    assert calls == [TRIP["origin"], TRIP["destination"], "Bakery", "Bakery", "Unknown", "Failure"]


async def test_google_unresolved_endpoint_does_not_create_trip(api, monkeypatch):
    client, app = api
    app.state.settings.maps_provider = "google"
    app.state.settings.google_maps_api_key = SecretStr("key")
    monkeypatch.setattr(
        selection,
        "GoogleMaps",
        partial(GoogleMaps, transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))),
    )
    response = await client.post("/api/v1/trips", json=TRIP)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"

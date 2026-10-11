import json

import httpx
import pytest
from pydantic import SecretStr

from questline.config import Settings
from questline.main import create_app
from questline.providers.google_maps import FIELD_MASK, GoogleMaps, MapsUnavailable
from questline.providers.maps import FakeMaps
from questline.providers.selection import maps_for_settings

PLACE = {
    "id": "google-place-1",
    "displayName": {"text": "Coastal Bakery"},
    "formattedAddress": "1 Coast Road, Big Sur, CA",
    "location": {"latitude": 36.27, "longitude": -121.80},
    "googleMapsUri": "https://maps.google.com/?cid=1",
    "types": ["bakery", "food", "establishment"],
    "priceLevel": "PRICE_LEVEL_MODERATE",
}


async def test_google_places_request_and_resolved_fields():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "POST"
        assert str(request.url) == "https://places.googleapis.com/v1/places:searchText"
        assert request.headers["X-Goog-Api-Key"] == "test-secret"
        assert request.headers["X-Goog-FieldMask"] == FIELD_MASK
        assert json.loads(request.content) == {
            "textQuery": "Coastal Bakery, Big Sur",
            "pageSize": 1,
            "languageCode": "en",
        }
        return httpx.Response(200, json={"places": [PLACE]})

    provider = GoogleMaps("test-secret", transport=httpx.MockTransport(handler))
    query = "Coastal Bakery, Big Sur"
    endpoint = await provider.resolve_endpoint(query)
    assert endpoint is not None
    assert endpoint.label == "Coastal Bakery"
    assert endpoint.google_place_id == PLACE["id"]
    place = await provider.resolve_place(query)
    assert place is not None
    assert place.category == "eat"
    assert (place.lat, place.lng) == (36.27, -121.80)
    assert place.google_maps_uri == PLACE["googleMapsUri"]
    assert place.price_level is None  # Not requested; no invented price estimates.
    assert place.est_cost_low is None and place.est_cost_high is None
    assert "test-secret" not in place.model_dump_json()
    assert len(requests) == 2


@pytest.mark.parametrize("payload", [{}, {"places": []}])
async def test_no_matches(payload):
    provider = GoogleMaps(
        "key", transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    )
    assert await provider.resolve_place("Unknown place") is None
    assert await provider.resolve_endpoint("Unknown city") is None


async def test_blank_query_does_not_make_request():
    def forbidden(request):
        pytest.fail("Blank queries must not call Google")

    assert (
        await GoogleMaps("key", transport=httpx.MockTransport(forbidden)).resolve_place(" ") is None
    )


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 503, 302])
async def test_upstream_failure_is_sanitized_and_not_retried(status):
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(status, text="private upstream error with key-secret")

    with pytest.raises(MapsUnavailable) as error:
        await GoogleMaps("key-secret", transport=httpx.MockTransport(handler)).resolve_place("Cafe")
    assert "key-secret" not in str(error.value)
    assert "private upstream" not in str(error.value)
    assert calls == 1


@pytest.mark.parametrize("exception", [httpx.ReadTimeout, httpx.ConnectError])
async def test_transport_errors_hide_credentials(exception):
    def handler(request):
        assert request.extensions["timeout"]["read"] == 10.0
        raise exception("private key-secret", request=request)

    with pytest.raises(MapsUnavailable, match="unavailable") as error:
        await GoogleMaps("key-secret", transport=httpx.MockTransport(handler)).resolve_place("Cafe")
    assert "key-secret" not in str(error.value)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"places": None},
        {"places": [{}]},
        {"places": [{**PLACE, "id": ""}]},
        {"places": [{**PLACE, "location": {"latitude": 91, "longitude": 0}}]},
        {"places": [{**PLACE, "location": {"latitude": 0, "longitude": 181}}]},
    ],
)
async def test_malformed_results_are_provider_errors(payload):
    provider = GoogleMaps(
        "key", transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    )
    with pytest.raises(MapsUnavailable):
        await provider.resolve_place("Cafe")


async def test_malformed_json_is_provider_error():
    provider = GoogleMaps(
        "key", transport=httpx.MockTransport(lambda _: httpx.Response(200, text="not JSON"))
    )
    with pytest.raises(MapsUnavailable):
        await provider.resolve_endpoint("City")


@pytest.mark.parametrize(
    ("types", "expected"),
    [(["campground"], "stay"), (["museum"], "do"), (["unknown"], "along_the_way")],
)
async def test_category_mapping(types, expected):
    provider = GoogleMaps(
        "key",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"places": [{**PLACE, "types": types}]})
        ),
    )
    place = await provider.resolve_place("Place")
    assert place is not None and place.category == expected


def test_provider_selection():
    assert isinstance(maps_for_settings(Settings(_env_file=None)), FakeMaps)
    with pytest.raises(MapsUnavailable, match="GOOGLE_MAPS_API_KEY"):
        maps_for_settings(Settings(_env_file=None, maps_provider="google"))
    assert isinstance(
        maps_for_settings(
            Settings(_env_file=None, maps_provider="google", google_maps_api_key=SecretStr("key"))
        ),
        GoogleMaps,
    )


async def test_missing_google_key_returns_structured_503():
    app = create_app(Settings(_env_file=None, app_env="test", maps_provider="google"))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/trips",
                json={
                    "name": "Trip",
                    "origin": "City A",
                    "destination": "City B",
                    "start_date": "2026-10-17",
                    "end_date": "2026-10-18",
                    "timezone": "America/Los_Angeles",
                    "organizer_name": "Alice",
                },
            )
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "provider_unavailable"

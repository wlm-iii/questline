import json

import httpx
import pytest
from test_google_maps import PLACE

from questline.providers.google_maps import GoogleMaps
from questline.providers.maps import SearchBounds
from questline.schemas import Endpoint


def endpoint(lat, lng):
    return Endpoint(label="Point", google_place_id="point", lat=lat, lng=lng)


def test_trip_box_and_antimeridian():
    bounds = SearchBounds.for_trip(endpoint(37, -122), endpoint(36, -121))
    assert bounds.contains(36.5, -121.5)
    assert not bounds.contains(40, -75)
    wrap = SearchBounds.for_trip(endpoint(10, 179), endpoint(11, -179))
    assert wrap.contains(10, 179.5)
    assert wrap.contains(10, -179.5)
    assert not wrap.contains(10, 0)


@pytest.mark.parametrize(
    ("name", "lat", "lng", "resolved"),
    [
        ("Coastal Bakery", 36.27, -121.8, True),
        ("Coastal Bakery", 40.7, -74, False),
        ("Different Restaurant", 36.27, -121.8, False),
    ],
)
async def test_location_bias_is_not_trusted_without_validation(name, lat, lng, resolved):
    bounds = SearchBounds.for_trip(endpoint(37.338, -121.886), endpoint(36.270, -121.808))

    def handler(request):
        assert json.loads(request.content)["locationBias"] == bounds.google_bias()
        return httpx.Response(
            200,
            json={
                "places": [
                    {
                        **PLACE,
                        "displayName": {"text": name},
                        "location": {"latitude": lat, "longitude": lng},
                    }
                ]
            },
        )

    provider = GoogleMaps("key", transport=httpx.MockTransport(handler))
    place = await provider.resolve_place(
        "Coastal Bakery, Big Sur", bounds=bounds, mention_text="Coastal Bakery"
    )
    assert (place is not None) == resolved


async def test_legacy_trip_cannot_resolve_imports_without_region():
    def forbidden(request):
        pytest.fail("An ungrounded legacy import should not call Google")

    provider = GoogleMaps("key", transport=httpx.MockTransport(forbidden))
    assert await provider.resolve_place("Bakery", mention_text="Bakery") is None

"""Place-resolution boundary. Only explicit fixture places are supported in fake mode."""

from typing import Protocol

from questline.schemas import Endpoint


class MapsProvider(Protocol):
    async def resolve_endpoint(self, query: str) -> Endpoint | None: ...


class FakeMaps:
    async def resolve_endpoint(self, query: str) -> Endpoint | None:
        fixtures = {
            "san jose, ca": Endpoint(
                label="San Jose, CA (fixture)",
                google_place_id="fake-san-jose",
                lat=37.3382,
                lng=-121.8863,
            ),
            "big sur, ca": Endpoint(
                label="Big Sur, CA (fixture)",
                google_place_id="fake-big-sur",
                lat=36.2704,
                lng=-121.8081,
            ),
        }
        return fixtures.get(query.strip().lower())

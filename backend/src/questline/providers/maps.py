"""Place-resolution boundary. Only explicit fixture places are supported in fake mode."""

from typing import Protocol

from questline.schemas import Endpoint, Schema


class ResolvedPlace(Schema):
    google_place_id: str
    name: str
    category: str
    address: str
    lat: float
    lng: float
    google_maps_uri: str | None = None
    price_level: int | None = None
    est_cost_low: float | None = None
    est_cost_high: float | None = None
    cost_basis: str | None = None


class MapsProvider(Protocol):
    async def resolve_endpoint(self, query: str) -> Endpoint | None: ...
    async def resolve_place(self, query: str) -> ResolvedPlace | None: ...


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

    async def resolve_place(self, query: str) -> ResolvedPlace | None:
        fixtures = {
            "mcway falls": ResolvedPlace(
                google_place_id="fake-mcway-falls",
                name="McWay Falls (fixture)",
                category="do",
                address="Big Sur, CA (fixture)",
                lat=36.1579,
                lng=-121.6726,
            ),
            "big sur bakery": ResolvedPlace(
                google_place_id="fake-big-sur-bakery",
                name="Big Sur Bakery (fixture)",
                category="eat",
                address="Big Sur, CA (fixture)",
                lat=36.2704,
                lng=-121.8081,
            ),
        }
        return fixtures.get(query.strip().lower())

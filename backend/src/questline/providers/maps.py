"""Place-resolution boundary. Only explicit fixture places are supported in fake mode."""

from typing import Protocol

from pydantic import Field

from questline.schemas import Endpoint, Schema


class ResolvedPlace(Schema):
    google_place_id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    category: str
    address: str
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)
    google_maps_uri: str | None = None
    price_level: int | None = Field(default=None, ge=0, le=4)
    est_cost_low: float | None = None
    est_cost_high: float | None = None
    cost_basis: str | None = None


class SearchBounds(Schema):
    south: float
    north: float
    west: float
    east: float

    @classmethod
    def for_trip(cls, origin: Endpoint, destination: Endpoint) -> "SearchBounds":
        # Approximate corridor with padding; this is a matching guard, not a route.
        west, east = sorted((origin.lng, destination.lng))
        if east - west > 180:
            west, east = east, west  # Shorter box crosses the antimeridian.
        return cls(
            south=max(-90, min(origin.lat, destination.lat) - 0.5),
            north=min(90, max(origin.lat, destination.lat) + 0.5),
            west=(west - 0.5 + 180) % 360 - 180,
            east=(east + 0.5 + 180) % 360 - 180,
        )

    def contains(self, lat: float, lng: float) -> bool:
        longitude = (
            self.west <= lng <= self.east
            if self.west <= self.east
            else lng >= self.west or lng <= self.east
        )
        return self.south <= lat <= self.north and longitude

    def google_bias(self) -> dict:
        return {
            "rectangle": {
                "low": {"latitude": self.south, "longitude": self.west},
                "high": {"latitude": self.north, "longitude": self.east},
            }
        }


class MapsProvider(Protocol):
    async def resolve_endpoint(self, query: str) -> Endpoint | None: ...
    async def resolve_place(
        self, query: str, *, bounds: SearchBounds | None = None, mention_text: str | None = None
    ) -> ResolvedPlace | None: ...
    async def price_level(self, google_place_id: str) -> int | None: ...
    async def search_along_route(
        self, query: str, polyline: str, *, bounds: SearchBounds
    ) -> list[ResolvedPlace]: ...


class FakeMaps:
    async def price_level(self, google_place_id: str) -> int | None:
        return 2 if google_place_id == "fake-big-sur-bakery" else None

    async def search_along_route(
        self, query: str, polyline: str, *, bounds: SearchBounds
    ) -> list[ResolvedPlace]:
        # No invented production suggestions; offline builds keep existing fixture waypoints.
        return []

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

    async def resolve_place(
        self, query: str, *, bounds: SearchBounds | None = None, mention_text: str | None = None
    ) -> ResolvedPlace | None:
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

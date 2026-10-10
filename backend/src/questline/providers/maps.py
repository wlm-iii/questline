"""Contract for a future Google Places / Routes adapter; no paid calls yet.

Keep API credentials server-side. Review Google attribution and caching policies
before storing provider content. Place IDs may be retained; don't assume the
same is true for names, coordinates, routes, or travel estimates.
"""

from typing import Protocol

from pydantic import BaseModel


class PlaceResult(BaseModel):
    place_id: str
    display_name: str


class MapsProvider(Protocol):
    async def search_places(self, query: str) -> list[PlaceResult]: ...

    async def travel_seconds(self, origin_place_id: str, destination_place_id: str) -> int: ...

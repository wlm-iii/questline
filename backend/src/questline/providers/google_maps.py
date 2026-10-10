"""Bounded server-side Places API (New) calls; no inferred prices or opening hours."""

import asyncio
import math
import re
import unicodedata

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from questline.providers.errors import ProviderUnavailable
from questline.providers.maps import ResolvedPlace, SearchBounds
from questline.schemas import Endpoint

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.location,"
    "places.googleMapsUri,places.types"
)


class MapsUnavailable(ProviderUnavailable):
    """Safe to show to clients; never includes upstream response text or credentials."""


class Location(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class DisplayName(BaseModel):
    text: str = Field(min_length=1, max_length=255)


class GooglePlace(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(min_length=1, max_length=255)
    displayName: DisplayName
    formattedAddress: str = Field(default="", max_length=1000)
    location: Location
    googleMapsUri: str | None = Field(default=None, max_length=1000)
    types: list[str] = []


def category(types: list[str]) -> str:
    if set(types) & {"hotel", "lodging", "campground", "motel", "resort_hotel"}:
        return "stay"
    if set(types) & {"restaurant", "food", "cafe", "bakery", "bar", "meal_takeaway"}:
        return "eat"
    if set(types) & {"tourist_attraction", "park", "museum", "amusement_park", "hiking_area"}:
        return "do"
    return "along_the_way"


class GoogleMaps:
    def __init__(self, api_key: str, *, transport: httpx.AsyncBaseTransport | None = None):
        if not api_key:
            raise MapsUnavailable("Google Maps requires GOOGLE_MAPS_API_KEY")
        self._api_key = api_key
        self._transport = transport

    async def _search(self, query: str, bounds: SearchBounds | None = None) -> GooglePlace | None:
        if not query.strip():
            return None
        # One result is the Build contract; expose its resolved label, not a claim
        # that an ambiguous query uniquely identified a place. No retries/billing surprises.
        body: dict[str, object] = {"textQuery": query, "pageSize": 1, "languageCode": "en"}
        if bounds is not None:
            body["locationBias"] = bounds.google_bias()
        try:
            async with (
                asyncio.timeout(12),
                httpx.AsyncClient(
                    transport=self._transport, timeout=httpx.Timeout(10.0), follow_redirects=False
                ) as client,
            ):
                response = await client.post(
                    SEARCH_URL,
                    headers={"X-Goog-Api-Key": self._api_key, "X-Goog-FieldMask": FIELD_MASK},
                    json=body,
                )
            if response.status_code != 200:
                raise MapsUnavailable("Google Maps is unavailable. Try again later.")
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Invalid search response")
            places = data.get("places", [])
            if not isinstance(places, list):
                raise ValueError("Invalid search response")
            return GooglePlace.model_validate(places[0]) if places else None
        except (httpx.HTTPError, ValueError, ValidationError, TimeoutError):
            raise MapsUnavailable("Google Maps is unavailable. Try again later.") from None

    async def resolve_endpoint(self, query: str) -> Endpoint | None:
        place = await self._search(query)
        if place is None:
            return None
        return Endpoint(
            label=place.displayName.text,
            google_place_id=place.id,
            lat=place.location.latitude,
            lng=place.location.longitude,
        )

    async def resolve_place(
        self, query: str, *, bounds: SearchBounds | None = None, mention_text: str | None = None
    ) -> ResolvedPlace | None:
        if mention_text is not None and bounds is None:
            return None  # Legacy trips without endpoints cannot ground imported mentions.
        place = await self._search(query, bounds)
        if place is None:
            return None
        if bounds is not None and not bounds.contains(
            place.location.latitude, place.location.longitude
        ):
            return None
        if mention_text is not None:

            def tokens(value: str) -> set[str]:
                normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
                return set(re.findall(r"[a-z0-9]+", normalized.casefold()))

            mentioned = tokens(mention_text)
            matched = mentioned & tokens(place.displayName.text)
            if not mentioned or len(matched) < math.ceil(len(mentioned) * 0.6):
                return None
        return ResolvedPlace(
            google_place_id=place.id,
            name=place.displayName.text,
            category=category(place.types),
            address=place.formattedAddress,
            lat=place.location.latitude,
            lng=place.location.longitude,
            google_maps_uri=place.googleMapsUri,
        )

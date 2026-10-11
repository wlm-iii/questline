"""Bounded discovery overlay: provider facts and local IDs, never post-request group activity."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from questline.models import Trip
from questline.providers.errors import ProviderUnavailable
from questline.providers.maps import MapsProvider, ResolvedPlace, SearchBounds
from questline.providers.routes import LatLng, Router
from questline.schemas import Endpoint
from questline.services.persistence import upsert_place

SuggestionSink = Callable[[list[ResolvedPlace]], Awaitable[dict[str, str]]]
MAX_CANDIDATES = 100


async def register_suggestions(
    sessions: async_sessionmaker[AsyncSession], trip_id: UUID, found: list[ResolvedPlace]
) -> dict[str, str]:
    """Provider calls are finished before this short trip-locked transaction."""
    async with sessions() as session:
        trip = await session.get(Trip, trip_id, with_for_update=True)
        if trip is None:
            raise ValueError("Trip no longer exists")
        ids = {}
        for resolved in found:
            place = await upsert_place(session, trip_id, resolved, source="suggested")
            ids[resolved.google_place_id] = str(place.id)
        trip.revision += 1
        await session.commit()
        return ids


async def discover(
    snapshot: dict[str, Any],
    router: Router,
    maps: MapsProvider,
    sink: SuggestionSink,
    *,
    query_limit: int,
    suggestion_limit: int,
) -> list[str]:
    """Modify only the caller's private overlay. New places cannot be main picks this build."""
    capacity = min(suggestion_limit, MAX_CANDIDATES - len(snapshot["places"]))
    if not query_limit or capacity <= 0 or not router.routed:
        return []
    trip = snapshot["trip"]
    origin, destination = (Endpoint.model_validate(trip[key]) for key in ("origin", "destination"))
    bounds = SearchBounds.for_trip(origin, destination)
    try:
        async with asyncio.timeout(20):
            legs = await router.legs(
                [LatLng(origin.lat, origin.lng), LatLng(destination.lat, destination.lng)]
            )
        if len(legs) != 1 or not legs[0].polyline:
            raise ProviderUnavailable("No discovery polyline")
    except (ProviderUnavailable, TimeoutError):
        return ["Route-based suggestions unavailable; building existing waypoints only"]
    existing = {place["google_place_id"] for place in snapshot["places"]}
    existing.update((origin.google_place_id, destination.google_place_id))
    found: list[ResolvedPlace] = []
    warnings = []
    for query in ("cafes", "tourist attractions")[:query_limit]:
        if len(found) >= capacity:
            break
        try:
            async with asyncio.timeout(15):
                results = await maps.search_along_route(query, legs[0].polyline, bounds=bounds)
        except (ProviderUnavailable, TimeoutError):
            warnings.append(f"Suggestions for {query} unavailable; no retry was made")
            continue
        for result in results[:2]:
            # Revalidate typed objects, including providers that mutate their output.
            try:
                place = ResolvedPlace.model_validate(result.model_dump())
            except ValueError:
                warnings.append("An invalid suggestion was ignored")
                continue
            if (
                place.google_place_id not in existing
                and place.category in ("eat", "do")
                and bounds.contains(place.lat, place.lng)
                and len(found) < capacity
            ):
                existing.add(place.google_place_id)
                found.append(place)
    if not found:
        return warnings
    ids = await sink(found)
    optional = snapshot.setdefault("optional_only_ids", [])
    for place in found:
        pid = str(UUID(ids[place.google_place_id]))
        if any(old["id"] == pid for old in snapshot["places"]) or pid in optional:
            raise ValueError("Invalid suggestion registration")
        snapshot["places"].append(
            {
                **place.model_dump(),
                "id": pid,
                "source": "suggested",
                "source_message_ids": [],
                "mentioned_by": None,
                "mentioned_by_name": None,
                "vote_tallies": {"in": 0, "ok": 0, "out": 0},
            }
        )
        optional.append(pid)
    return warnings

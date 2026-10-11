"""Driving legs between ordered points. Code owns routing; the model never supplies drive times."""

import asyncio
import math
import re
from dataclasses import dataclass
from typing import Protocol

import httpx

from questline.providers.errors import ProviderUnavailable

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
ROUTES_FIELD_MASK = "routes.legs.duration,routes.legs.distanceMeters,routes.legs.polyline"
MAX_INTERMEDIATES = 25

# Straight-line fallback: a road-winding factor and a conservative average speed.
ROAD_FACTOR = 1.3
ESTIMATE_KMH = 60


@dataclass(frozen=True)
class LatLng:
    lat: float
    lng: float


@dataclass(frozen=True)
class Leg:
    drive_min: float
    distance_m: int
    polyline: str | None = None


class RoutesUnavailable(ProviderUnavailable):
    """Safe to show to clients; never includes upstream response text or credentials."""


class Router(Protocol):
    # True when legs come from a routing service rather than straight-line estimates.
    routed: bool

    async def legs(self, points: list[LatLng]) -> list[Leg]:
        """Return len(points) - 1 legs, in order."""
        ...


def straight_line_m(a: LatLng, b: LatLng) -> float:
    radius = 6_371_000
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    dphi, dlmb = phi2 - phi1, math.radians(b.lng - a.lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def estimated_leg(a: LatLng, b: LatLng) -> Leg:
    meters = straight_line_m(a, b) * ROAD_FACTOR
    return Leg(drive_min=round(meters / 1000 / ESTIMATE_KMH * 60, 1), distance_m=round(meters))


class EstimateRouter:
    """Deterministic, offline. Plans that use it say so in their warnings."""

    routed = False

    async def legs(self, points: list[LatLng]) -> list[Leg]:
        return [estimated_leg(a, b) for a, b in zip(points, points[1:], strict=False)]


def _waypoint(point: LatLng) -> dict:
    return {"location": {"latLng": {"latitude": point.lat, "longitude": point.lng}}}


def _seconds(value: object) -> float:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)s", str(value))
    if not match:
        raise ValueError("Invalid duration")
    return float(match.group(1))


class GoogleRoutes:
    routed = True

    def __init__(self, api_key: str, *, transport: httpx.AsyncBaseTransport | None = None):
        if not api_key:
            raise RoutesUnavailable("Google Routes requires GOOGLE_MAPS_API_KEY")
        self._api_key = api_key
        self._transport = transport

    async def legs(self, points: list[LatLng]) -> list[Leg]:
        if len(points) < 2:
            return []
        legs: list[Leg] = []
        # One computeRoutes call per chunk of at most 25 intermediates.
        step = MAX_INTERMEDIATES + 1
        for start in range(0, len(points) - 1, step):
            legs.extend(await self._route(points[start : start + step + 1]))
        return legs

    async def _route(self, points: list[LatLng]) -> list[Leg]:
        body = {
            "origin": _waypoint(points[0]),
            "destination": _waypoint(points[-1]),
            "intermediates": [_waypoint(point) for point in points[1:-1]],
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_UNAWARE",
            "polylineEncoding": "ENCODED_POLYLINE",
        }
        try:
            async with (
                asyncio.timeout(15),
                httpx.AsyncClient(
                    transport=self._transport, timeout=httpx.Timeout(12.0), follow_redirects=False
                ) as client,
            ):
                response = await client.post(
                    ROUTES_URL,
                    headers={
                        "X-Goog-Api-Key": self._api_key,
                        "X-Goog-FieldMask": ROUTES_FIELD_MASK,
                    },
                    json=body,
                )
            if response.status_code != 200:
                raise RoutesUnavailable("Google Routes is unavailable. Try again later.")
            routes = response.json().get("routes") or []
            if not routes:
                raise ValueError("No route")
            raw_legs = routes[0].get("legs") or []
            if len(raw_legs) != len(points) - 1:
                raise ValueError("Unexpected leg count")
            return [
                Leg(
                    drive_min=round(_seconds(leg.get("duration", "0s")) / 60, 1),
                    distance_m=int(leg.get("distanceMeters", 0)),
                    polyline=(leg.get("polyline") or {}).get("encodedPolyline"),
                )
                for leg in raw_legs
            ]
        except RoutesUnavailable:
            raise
        except (httpx.HTTPError, ValueError, TypeError, AttributeError, TimeoutError):
            raise RoutesUnavailable("Google Routes is unavailable. Try again later.") from None

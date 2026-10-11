"""Google encoded polylines and side-quest spurs drawn on the map.

A spur is the part of the provider's route to a side quest after it leaves the main road, so the
map can draw a side quest branching off at its turn-off instead of a straight line from the start
of its leg. Spurs only come from routed geometry; without it there is no spur.
"""

import math

from questline.providers.routes import LatLng

PRECISION = 1e5


def decode(encoded: str) -> list[LatLng]:
    values: list[int] = []
    index = 0
    while index < len(encoded):
        result = shift = 0
        while True:
            if index >= len(encoded):
                raise ValueError("Truncated polyline")
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        values.append(~(result >> 1) if result & 1 else result >> 1)
    if not values or len(values) % 2:
        raise ValueError("Empty or truncated polyline")
    points: list[LatLng] = []
    lat = lng = 0
    for i in range(0, len(values), 2):
        lat += values[i]
        lng += values[i + 1]
        points.append(LatLng(lat / PRECISION, lng / PRECISION))
    return points


def _encode_value(value: int) -> str:
    value = ~(value << 1) if value < 0 else value << 1
    chunks = []
    while value >= 0x20:
        chunks.append(chr((0x20 | (value & 0x1F)) + 63))
        value >>= 5
    chunks.append(chr(value + 63))
    return "".join(chunks)


def encode(points: list[LatLng]) -> str:
    out = []
    prev_lat = prev_lng = 0
    for point in points:
        lat, lng = round(point.lat * PRECISION), round(point.lng * PRECISION)
        out.append(_encode_value(lat - prev_lat) + _encode_value(lng - prev_lng))
        prev_lat, prev_lng = lat, lng
    return "".join(out)


def _xy(point: LatLng, ref_lat: float) -> tuple[float, float]:
    # Local equirectangular projection; plenty for picking the nearest point on a road.
    return point.lng * math.cos(math.radians(ref_lat)), point.lat


def _nearest_on_path(path: list[LatLng], target: LatLng) -> LatLng:
    tx, ty = _xy(target, target.lat)
    best, best_d = path[0], math.inf
    for a, b in zip(path, path[1:] or path, strict=False):
        ax, ay = _xy(a, target.lat)
        bx, by = _xy(b, target.lat)
        dx, dy = bx - ax, by - ay
        length = dx * dx + dy * dy
        t = 0.0 if length == 0 else max(0.0, min(1.0, ((tx - ax) * dx + (ty - ay) * dy) / length))
        px, py = ax + t * dx, ay + t * dy
        d = (px - tx) ** 2 + (py - ty) ** 2
        if d < best_d:
            best_d = d
            best = LatLng(a.lat + t * (b.lat - a.lat), a.lng + t * (b.lng - a.lng))
    return best


def side_spur(
    to_side: str | None,
    main_leg: str | None,
    side: LatLng,
    *,
    a: LatLng | None = None,
    b: LatLng | None = None,
) -> str | None:
    """The encoded route to `side` from where it leaves the main leg, or None.

    `to_side` is the routed A→S leg; `main_leg` the routed A→B leg, or None to use the straight
    segment `a`→`b` as the main road.
    """
    if not to_side:
        return None
    try:
        route = decode(to_side)
        main = decode(main_leg) if main_leg else [p for p in (a, b) if p is not None]
    except ValueError:
        return None
    if not main:
        return None
    turn = _nearest_on_path(main, side)
    tx, ty = _xy(turn, turn.lat)

    def from_turn(point: LatLng) -> float:
        x, y = _xy(point, turn.lat)
        return (x - tx) ** 2 + (y - ty) ** 2

    start = min(range(len(route)), key=lambda i: from_turn(route[i]))
    spur = route[start:]
    return encode(spur) if len(spur) >= 2 else None

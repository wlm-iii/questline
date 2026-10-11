"""Code-owned questline composition (SPEC §8): routing, timing, detours, estimates, conflicts.

Selection (which waypoints are main or side quests, and why) comes from votes or the AI selector.
Everything derived here comes from code: names, coordinates, drive times, arrival times, detour
minutes, estimates, and conflict labels. Nothing in this module invents a place or a price.
"""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from questline.pricing import PRESET_LABELS, PRESET_MAX_LEVEL, dollar_signs, over_budget
from questline.providers.errors import ProviderUnavailable
from questline.providers.routes import (
    EstimateRouter,
    LatLng,
    Leg,
    Router,
    estimated_leg,
    straight_line_m,
)
from questline.schemas import (
    Conflict,
    PlanContent,
    PlanDay,
    PlanEdge,
    PlanGraph,
    PlanNode,
)

DAY_START = time(9, 0)
DAY_END = time(19, 0)
VISIT_MIN = {"eat": 60, "do": 75, "along_the_way": 30, "stay": 30}
PRICED_CATEGORIES = {"eat", "do", "along_the_way"}
VOTE_WORDS = {"in": "I'm in", "ok": "Sure", "out": "Skip"}
WHY_MAX = 300
QUOTE_MAX = 120


@dataclass
class Decisions:
    """The editable part of a plan. Everything else is recomputed from these."""

    main: list[str] = field(default_factory=list)
    # Side quest id -> anchor ("start" or a main id), or None to let code pick the nearest leg.
    side: dict[str, str | None] = field(default_factory=dict)
    why: dict[str, str] = field(default_factory=dict)
    owner: dict[str, str | None] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)

    def ids(self) -> list[str]:
        return [*self.main, *self.side]


def endpoint_ids(snapshot: dict[str, Any]) -> set[str]:
    trip = snapshot["trip"]
    return {
        endpoint["google_place_id"]
        for endpoint in (trip.get("origin"), trip.get("destination"))
        if endpoint
    }


def candidates(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Waypoints that can join a questline. The trip's own endpoints are never stops."""
    skip = endpoint_ids(snapshot)
    return [place for place in snapshot["places"] if place["google_place_id"] not in skip]


def vote_score(place: dict[str, Any]) -> int:
    tallies = place.get("vote_tallies") or {}
    return 2 * tallies.get("in", 0) + tallies.get("ok", 0) - tallies.get("out", 0)


def _members(snapshot: dict[str, Any]) -> dict[str, str]:
    return {member["id"]: member["name"] for member in snapshot["members"]}


def voters(snapshot: dict[str, Any], place_id: str) -> dict[str, list[str]]:
    names = _members(snapshot)
    result: dict[str, list[str]] = {"in": [], "ok": [], "out": []}
    for vote in snapshot["votes"]:
        if vote["place_id"] == place_id:
            result[vote["kind"]].append(names.get(vote["member_id"], "Someone"))
    return {kind: sorted(people) for kind, people in result.items()}


def join_names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def quotes(snapshot: dict[str, Any], place: dict[str, Any]) -> list[tuple[str, str]]:
    """(author, text) for each source message, in chat order."""
    names = _members(snapshot)
    wanted = set(place.get("source_message_ids") or [])
    found = []
    for message in snapshot["messages"]:
        if message["id"] in wanted:
            author = names.get(message.get("member_id") or "", message.get("author_id", "Someone"))
            found.append((author, message["text"]))
    return found


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def vote_parts(snapshot: dict[str, Any], place_id: str) -> list[str]:
    """["Maya voted I'm in", "Sam voted Skip"], from vote rows only."""
    groups = voters(snapshot, place_id)
    return [
        f"{join_names(people)} voted {VOTE_WORDS[kind]}"
        for kind, people in groups.items()
        if people
    ]


def vote_why(snapshot: dict[str, Any], place: dict[str, Any]) -> str:
    """A grounded reason built only from the actual votes and quotes."""
    groups = voters(snapshot, place["id"])
    parts = vote_parts(snapshot, place["id"])
    said = quotes(snapshot, place)
    if said:
        author, text = said[0]
        parts.append(f'{author}: "{_clip(text, QUOTE_MAX)}"')
    elif place.get("source") == "added":
        parts.append("Added by search")
    if not any(groups.values()):
        parts.insert(0, "No votes yet")
    return _clip("; ".join(parts[:-1]) + (". " if len(parts) > 1 else "") + parts[-1], WHY_MAX)


def vote_selection(snapshot: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Deterministic picks (SPEC §8): in +2, ok +1, out -1.

    With no votes at all, every waypoint is a group pick on the main quest. Otherwise a score of
    at least 2 joins the main quest; everything else is a side quest. A Skip deprioritizes a
    waypoint rather than silently vetoing it.
    """
    pool = candidates(snapshot)
    if not snapshot["votes"]:
        return [place["id"] for place in pool], []
    main = [place["id"] for place in pool if vote_score(place) >= 2]
    side = [place["id"] for place in pool if vote_score(place) < 2]
    return main, side


def _point(value: dict[str, Any]) -> LatLng:
    return LatLng(value["lat"], value["lng"])


def route_order(snapshot: dict[str, Any], ids: list[str]) -> list[str]:
    """Order stops along the origin → destination line; loops use nearest neighbour."""
    trip = snapshot["trip"]
    by_id = {place["id"]: place for place in snapshot["places"]}
    origin, destination = _point(trip["origin"]), _point(trip["destination"])
    if straight_line_m(origin, destination) < 2_000:
        pending, order, here = list(ids), [], origin
        while pending:
            nearest = min(pending, key=lambda pid: straight_line_m(here, _point(by_id[pid])))
            pending.remove(nearest)
            order.append(nearest)
            here = _point(by_id[nearest])
        return order
    scale = math.cos(math.radians((origin.lat + destination.lat) / 2))
    dx, dy = (destination.lng - origin.lng) * scale, destination.lat - origin.lat

    def progress(pid: str) -> float:
        place = by_id[pid]
        return ((place["lng"] - origin.lng) * scale * dx + (place["lat"] - origin.lat) * dy) / (
            dx * dx + dy * dy
        )

    return sorted(ids, key=lambda pid: (progress(pid), pid))


def _trip_dates(trip: dict[str, Any]) -> list[date]:
    start = date.fromisoformat(trip["start_date"]) if trip.get("start_date") else None
    end = date.fromisoformat(trip["end_date"]) if trip.get("end_date") else None
    if start is None:
        raise ValueError("Trip needs dates before building a questline")
    end = end if end and end >= start else start
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _fmt_money(low: float, high: float) -> str:
    return f"${low:.0f}" if low == high else f"${low:.0f}–{high:.0f}"


def _stop_ids(content: dict[str, Any] | None) -> tuple[list[str], set[str], dict[str, str]]:
    if not content:
        return [], set(), {}
    nodes = [node for node in content["graph"]["nodes"] if node.get("role") == "stop"]
    main = [node["id"] for node in nodes if node.get("quest") != "side"]
    side = {node["id"] for node in nodes if node.get("quest") == "side"}
    return main, side, {node["id"]: node["title"] for node in nodes}


def changes(previous: dict[str, Any] | None, current: PlanContent) -> list[str]:
    """Factual differences from the previous plan; an empty list for the first plan."""
    if previous is None:
        return []
    old_main, old_side, old_titles = _stop_ids(previous)
    new_main, new_side, new_titles = _stop_ids(current.model_dump(mode="json"))
    titles = {**old_titles, **new_titles}
    result = []
    for pid in new_main:
        if pid in old_side:
            result.append(f"Promoted {titles[pid]} to the main quest")
        elif pid not in old_main:
            result.append(f"Added {titles[pid]} to the main quest")
    for pid in sorted(new_side, key=lambda value: titles[value]):
        if pid in old_main:
            result.append(f"Moved {titles[pid]} to side quests")
        elif pid not in old_side:
            result.append(f"Added {titles[pid]} as a side quest")
    for pid in [*old_main, *sorted(old_side)]:
        if pid not in new_main and pid not in new_side:
            result.append(f"Removed {titles[pid]} from the questline")
    kept_old = [pid for pid in old_main if pid in new_main]
    kept_new = [pid for pid in new_main if pid in old_main]
    if kept_old != kept_new:
        result.append("Reordered the main quest")
    old_estimate = previous.get("per_person_estimate")
    new_estimate = current.per_person_estimate
    if (tuple(old_estimate) if old_estimate else None) != new_estimate:
        before = _fmt_money(*old_estimate) if old_estimate else "unknown"
        after = _fmt_money(*new_estimate) if new_estimate else "unknown"
        result.append(f"Estimate changed from {before} to {after} per person")
    return result or ["No changes from the previous questline"]


async def _detour(router: Router, a: LatLng, s: LatLng, b: LatLng, direct: Leg) -> int | None:
    try:
        legs = await router.legs([a, s, b])
    except ProviderUnavailable:
        return None
    return max(0, round(sum(leg.drive_min for leg in legs) - direct.drive_min))


async def compose(
    snapshot: dict[str, Any],
    decisions: Decisions,
    *,
    budget_preset: str,
    router: Router,
    previous: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> PlanContent:
    trip = snapshot["trip"]
    if not trip.get("origin") or not trip.get("destination"):
        raise ValueError("Trip needs an origin and destination before building a questline")
    places = {place["id"]: place for place in candidates(snapshot)}
    main = [pid for pid in dict.fromkeys(decisions.main) if pid in places]
    side = {
        pid: anchor for pid, anchor in decisions.side.items() if pid in places and pid not in main
    }
    tz = ZoneInfo(snapshot.get("timezone") or trip.get("timezone") or "UTC")
    dates = _trip_dates(trip)
    notes = list(warnings or [])

    origin, destination = trip["origin"], trip["destination"]
    stops = [_point(places[pid]) for pid in main]
    path = [_point(origin), *stops, _point(destination)]
    path_ids = ["start", *main, "end"]
    routed = router.routed
    try:
        legs = await router.legs(path)
    except ProviderUnavailable:
        legs = [estimated_leg(a, b) for a, b in zip(path, path[1:], strict=False)]
        routed = False
        notes.append("Routing was unavailable, so drive times are straight-line estimates")
    if not router.routed:
        notes.append("Drive times are straight-line estimates, not routed directions")

    # ---- schedule the main quest into daily windows
    def window(day: date) -> tuple[datetime, datetime]:
        return datetime.combine(day, DAY_START, tz), datetime.combine(day, DAY_END, tz)

    conflicts: list[Conflict] = []
    day_index = 0
    cursor, day_end = window(dates[0])
    days: list[dict[str, Any]] = [{"date": dates[0], "start_at": cursor, "node_ids": ["start"]}]
    times: dict[str, tuple[datetime, datetime, int]] = {}
    overnight = False
    for index, pid in enumerate(main):
        visit = VISIT_MIN.get(places[pid]["category"], 60)
        drive = timedelta(minutes=legs[index].drive_min)
        arrive = cursor + drive
        depart = arrive + timedelta(minutes=visit)
        if depart > day_end and day_index + 1 < len(dates) and len(days[-1]["node_ids"]) > 0:
            days[-1]["end_at"] = cursor
            day_index += 1
            overnight = True
            cursor, day_end = window(dates[day_index])
            days.append({"date": dates[day_index], "start_at": cursor, "node_ids": []})
            arrive = cursor + drive
            depart = arrive + timedelta(minutes=visit)
        if depart > day_end:
            conflicts.append(
                Conflict(
                    node_id=pid,
                    kind="does_not_fit",
                    detail=f"Runs past {DAY_END:%-I:%M %p} on {days[-1]['date']:%a %b %-d}.",
                )
            )
        times[pid] = (arrive, depart, visit)
        days[-1]["node_ids"].append(pid)
        cursor = depart
    end_arrive = cursor + timedelta(minutes=legs[-1].drive_min)
    if end_arrive > day_end and day_index + 1 < len(dates) and days[-1]["node_ids"]:
        days[-1]["end_at"] = cursor
        day_index += 1
        overnight = True
        cursor, day_end = window(dates[day_index])
        days.append({"date": dates[day_index], "start_at": cursor, "node_ids": []})
        end_arrive = cursor + timedelta(minutes=legs[-1].drive_min)
    days[-1]["node_ids"].append("end")
    days[-1]["end_at"] = end_arrive
    if end_arrive > day_end:
        notes.append(f"Arrival at {destination['label']} is after {DAY_END:%-I:%M %p}")
    if overnight:
        notes.append("Overnight stays aren't planned; add a place to stay as a waypoint")

    # ---- side quests hang off the leg with the smallest detour
    points = dict(zip(path_ids, path, strict=True))
    leg_after = {path_ids[i]: (path_ids[i + 1], legs[i]) for i in range(len(legs))}

    def best_anchor(pid: str) -> str:
        s = _point(places[pid])

        def cost(anchor: str) -> float:
            following, _ = leg_after[anchor]
            a, b = points[anchor], points[following]
            return straight_line_m(a, s) + straight_line_m(s, b) - straight_line_m(a, b)

        return min(path_ids[:-1], key=cost)

    anchors = {
        pid: anchor if anchor in leg_after else best_anchor(pid) for pid, anchor in side.items()
    }
    detours = await asyncio.gather(
        *(
            _detour(
                router if routed else EstimateRouter(),
                points[anchor],
                _point(places[pid]),
                points[leg_after[anchor][0]],
                leg_after[anchor][1],
            )
            for pid, anchor in anchors.items()
        )
    )
    detour_by_id = dict(zip(anchors, detours, strict=True))

    # ---- nodes and edges
    def stop_node(pid: str, quest: str) -> PlanNode:
        place = places[pid]
        arrive, depart, visit = times.get(pid, (None, None, None))
        cost = (
            (place["est_cost_low"], place["est_cost_high"])
            if place.get("est_cost_low") is not None and place.get("est_cost_high") is not None
            else None
        )
        why = decisions.why.get(pid) or vote_why(snapshot, place)
        owner = decisions.owner.get(pid)
        return PlanNode(
            id=pid,
            role="stop",
            quest=quest,  # type: ignore[arg-type]
            anchor=anchors.get(pid),
            title=place["name"],
            notes=decisions.notes.get(pid, ""),
            source_message_ids=place.get("source_message_ids") or [],
            place_id=place["google_place_id"],
            lat=place["lat"],
            lng=place["lng"],
            category=place["category"],
            arrive=arrive,
            depart=depart,
            duration_min=visit,
            detour_min=detour_by_id.get(pid),
            est_cost=cost,
            cost_basis=place.get("cost_basis") if cost else None,
            source=place.get("source", "group"),
            why=_clip(why, WHY_MAX),
            owner_member_id=UUID(str(owner)) if owner else None,
        )

    first_day_start = days[0]["start_at"]
    nodes = [
        PlanNode(
            id="start",
            role="start",
            title=origin["label"],
            place_id=origin["google_place_id"],
            lat=origin["lat"],
            lng=origin["lng"],
            depart=first_day_start,
        ),
        *(stop_node(pid, "main") for pid in main),
        *(stop_node(pid, "side") for pid in anchors),
        PlanNode(
            id="end",
            role="end",
            title=destination["label"],
            place_id=destination["google_place_id"],
            lat=destination["lat"],
            lng=destination["lng"],
            arrive=end_arrive,
        ),
    ]
    edges = [
        PlanEdge(
            id=f"travel-{index}",
            source=path_ids[index],
            target=path_ids[index + 1],
            kind="travel",
            drive_min=leg.drive_min,
            distance_m=leg.distance_m,
            polyline=leg.polyline,
        )
        for index, leg in enumerate(legs)
    ] + [
        PlanEdge(
            id=f"detour-{pid}",
            source=anchor,
            target=pid,
            kind="detour",
            detour_min=detour_by_id[pid],
        )
        for pid, anchor in anchors.items()
    ]

    # ---- conflicts and estimate
    for pid in [*main, *anchors]:
        groups = voters(snapshot, pid)
        if groups["in"] and groups["out"]:
            detail = "; ".join(vote_parts(snapshot, pid))
            conflicts.append(Conflict(node_id=pid, kind="split_vote", detail=detail + "."))
        level = places[pid].get("price_level")
        if over_budget(level, budget_preset):
            assert level is not None
            limit = dollar_signs(PRESET_MAX_LEVEL[budget_preset])
            conflicts.append(
                Conflict(
                    node_id=pid,
                    kind="over_budget",
                    detail=f"{places[pid]['name']} is {dollar_signs(level)}; "
                    f"{PRESET_LABELS[budget_preset]} allows up to {limit}.",
                )
            )
    priced = [pid for pid in main if places[pid]["category"] in PRICED_CATEGORIES]
    known = [pid for pid in priced if places[pid].get("est_cost_low") is not None]
    unpriced = [pid for pid in priced if places[pid].get("est_cost_low") is None]
    estimate = (
        (
            sum(places[pid]["est_cost_low"] for pid in known),
            sum(places[pid]["est_cost_high"] for pid in known),
        )
        if known
        else None
    )
    if main:
        notes.append("Opening hours are unverified for every stop")

    content = PlanContent(
        title=trip["name"],
        budget_preset=budget_preset,  # type: ignore[arg-type]
        timezone=str(tz),
        graph=PlanGraph(nodes=nodes, edges=edges),
        days=[PlanDay(**day) for day in days],
        per_person_estimate=estimate,
        estimate_is_partial=bool(unpriced),
        unpriced_node_ids=unpriced,
        conflicts=conflicts,
        assumptions=[
            f"One-way route from {origin['label']} to {destination['label']}",
            f"Daily window {DAY_START:%-I:%M %p}–{DAY_END:%-I:%M %p} ({tz})",
            "Visits: 60 min meals, 75 min activities, 30 min stops along the way",
            "Costs are app estimates per adult from Google price levels",
            "Main quest order follows the route from start to end",
        ],
        open_questions=(
            [] if places else ["Add waypoints (import the chat or search) to build a questline"]
        ),
        warnings=list(dict.fromkeys(notes)),
    )
    content.changed_from_previous = changes(previous, content)
    return content


def decisions_from(content: dict[str, Any]) -> Decisions:
    """Recover the editable decisions from a saved plan."""
    nodes = [node for node in content["graph"]["nodes"] if node.get("role") == "stop"]
    rank = {}
    for day in content.get("days") or []:
        for node_id in day["node_ids"]:
            rank.setdefault(node_id, len(rank))
    main = sorted(
        (node for node in nodes if node.get("quest") != "side"),
        key=lambda node: rank.get(node["id"], math.inf),
    )
    return Decisions(
        main=[node["id"] for node in main],
        side={node["id"]: node.get("anchor") for node in nodes if node.get("quest") == "side"},
        why={node["id"]: node.get("why", "") for node in nodes if node.get("why")},
        owner={node["id"]: node.get("owner_member_id") for node in nodes},
        notes={node["id"]: node.get("notes", "") for node in nodes if node.get("notes")},
    )

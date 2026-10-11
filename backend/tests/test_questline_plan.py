import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from questline.providers.errors import ProviderUnavailable
from questline.providers.fake import FakePlanner
from questline.providers.gemini_selector import GeminiSelector
from questline.providers.planner import QuestlinePlanner
from questline.providers.routes import EstimateRouter, GoogleRoutes, LatLng, RoutesUnavailable
from questline.schemas import GenerationCreate
from questline.services.questline_plan import (
    Decisions,
    compose,
    decisions_from,
    route_order,
    vote_selection,
)

MAYA, SAM, JORDAN = "m-maya", "m-sam", "m-jordan"
MSG = "00000000-0000-0000-0000-0000000000aa"
ORIGIN = {"label": "San Jose", "google_place_id": "g-sj", "lat": 37.3382, "lng": -121.8863}
DEST = {"label": "Big Sur", "google_place_id": "g-bs", "lat": 36.2704, "lng": -121.8081}


def place(pid, name, lat, lng, category="do", price_level=None, cost=None, messages=()):
    return {
        "id": pid,
        "name": name,
        "google_place_id": f"g-{pid}",
        "category": category,
        "lat": lat,
        "lng": lng,
        "price_level": price_level,
        "est_cost_low": cost[0] if cost else None,
        "est_cost_high": cost[1] if cost else None,
        "cost_basis": "App estimate" if cost else None,
        "source": "group",
        "source_message_ids": list(messages),
    }


def snapshot(votes=(), places=None, start="2026-10-17", end="2026-10-18"):
    places = places or [
        place("bixby", "Bixby Bridge", 36.3715, -121.9017, messages=[MSG]),
        place("bakery", "Big Sur Bakery", 36.2620, -121.8090, "eat", 2, (20, 40)),
        place("nepenthe", "Nepenthe", 36.2216, -121.7590, "eat", 3, (40, 75)),
        place("mcway", "McWay Falls", 36.1579, -121.6726),
        # Extraction can resolve the destination itself; it is never a stop.
        {**place("dest", "Big Sur", 36.2704, -121.8081), "google_place_id": "g-bs"},
    ]
    tallies = {p["id"]: {"in": 0, "ok": 0, "out": 0} for p in places}
    for _member, pid, kind in votes:
        tallies[pid][kind] += 1
    return {
        "trip": {
            "name": "Big Sur weekend",
            "origin": ORIGIN,
            "destination": DEST,
            "start_date": start,
            "end_date": end,
            "timezone": "America/Los_Angeles",
        },
        "timezone": "America/Los_Angeles",
        "members": [
            {"id": MAYA, "name": "Maya"},
            {"id": SAM, "name": "Sam"},
            {"id": JORDAN, "name": "Jordan"},
        ],
        "messages": [
            {
                "id": MSG,
                "member_id": SAM,
                "author_id": "Sam",
                "text": "can we stop at Bixby Bridge on the way down for photos",
            }
        ],
        "places": [{**p, "vote_tallies": tallies[p["id"]]} for p in places],
        "votes": [{"member_id": m, "place_id": pid, "kind": kind} for m, pid, kind in votes],
    }


VOTES = [
    (MAYA, "mcway", "in"),
    (SAM, "mcway", "out"),
    (JORDAN, "mcway", "ok"),
    (MAYA, "bakery", "in"),
    (JORDAN, "bakery", "in"),
    (SAM, "bixby", "in"),
    (MAYA, "nepenthe", "in"),
]


def nodes_by_id(content):
    return {node.id: node for node in content.graph.nodes}


def test_vote_selection_scores_and_skips_endpoints():
    main, side = vote_selection(snapshot())
    assert set(main) == {"bixby", "bakery", "nepenthe", "mcway"}  # No votes: all group picks.
    assert side == []
    main, side = vote_selection(snapshot(VOTES))
    # in +2, ok +1, out -1. McWay (2+1-1) stays main despite a Skip; nothing is silently vetoed.
    assert set(main) == {"bixby", "bakery", "nepenthe", "mcway"}
    main, side = vote_selection(snapshot([(SAM, "mcway", "out"), (MAYA, "bakery", "in")]))
    assert main == ["bakery"]
    assert set(side) == {"bixby", "nepenthe", "mcway"}


def test_route_order_follows_the_trip_direction():
    snap = snapshot()
    assert route_order(snap, ["mcway", "bixby", "bakery"]) == ["bixby", "bakery", "mcway"]


async def test_fake_planner_builds_a_timed_routed_questline():
    snap = snapshot(VOTES)
    content = await FakePlanner().generate(snap, GenerationCreate(budget_preset="comfortable"))
    nodes = nodes_by_id(content)
    assert "dest" not in nodes
    main = [node.id for node in content.graph.nodes if node.role == "stop" and node.quest == "main"]
    assert main == ["bixby", "bakery", "mcway"]
    # Nepenthe is $$$: above Comfortable, so code demotes it to a side quest with a detour.
    assert nodes["nepenthe"].quest == "side"
    assert nodes["nepenthe"].anchor in {"start", *main}
    assert nodes["nepenthe"].detour_min is not None
    kinds = {(c.node_id, c.kind) for c in content.conflicts}
    assert ("mcway", "split_vote") in kinds and ("nepenthe", "over_budget") in kinds
    split = next(c for c in content.conflicts if c.kind == "split_vote")
    assert split.detail == "Maya voted I'm in; Jordan voted Sure; Sam voted Skip."
    # Travel edges form one path start -> main... -> end.
    travel = [edge for edge in content.graph.edges if edge.kind == "travel"]
    assert [edge.source for edge in travel] == ["start", *main]
    assert [edge.target for edge in travel] == [*main, "end"]
    times = [nodes[pid].arrive for pid in main]
    assert all(isinstance(t, datetime) for t in times) and times == sorted(times)
    assert content.days[0].node_ids[0] == "start" and content.days[-1].node_ids[-1] == "end"
    # Only the bakery is priced: a partial estimate, never a $0 for unknown prices.
    assert content.per_person_estimate == (20, 40)
    assert content.estimate_is_partial and set(content.unpriced_node_ids) == {"bixby", "mcway"}
    assert nodes["bixby"].why.startswith("Sam voted I'm in")
    assert '"can we stop at Bixby Bridge' in nodes["bixby"].why
    assert any("straight-line" in warning for warning in content.warnings)
    assert content.changed_from_previous == []


async def test_treat_preset_keeps_pricey_picks_and_reports_changes():
    snap = snapshot(VOTES)
    comfortable = await FakePlanner().generate(snap, GenerationCreate(budget_preset="comfortable"))
    snap["previous_plan"] = comfortable.model_dump(mode="json")
    treat = await FakePlanner().generate(snap, GenerationCreate(budget_preset="treat"))
    assert nodes_by_id(treat)["nepenthe"].quest == "main"
    assert "Promoted Nepenthe to the main quest" in treat.changed_from_previous
    assert any(line.startswith("Estimate changed") for line in treat.changed_from_previous)
    snap["previous_plan"] = treat.model_dump(mode="json")
    again = await FakePlanner().generate(snap, GenerationCreate(budget_preset="treat"))
    assert again.changed_from_previous == ["No changes from the previous questline"]


async def test_long_days_roll_over_and_never_exceed_trip_dates():
    far = [place(f"p{i}", f"Stop {i}", 37.2 - i * 0.12, -121.9 + i * 0.01) for i in range(8)]
    snap = snapshot(places=far)
    content = await FakePlanner().generate(snap, GenerationCreate())
    assert [str(day.date) for day in content.days] == ["2026-10-17", "2026-10-18"]
    assert any("Overnight" in warning for warning in content.warnings)
    one_day = await FakePlanner().generate(
        snapshot(places=far, end="2026-10-17"), GenerationCreate()
    )
    assert len(one_day.days) == 1
    assert any(conflict.kind == "does_not_fit" for conflict in one_day.conflicts)


async def test_decisions_round_trip_and_edits_recompute():
    snap = snapshot(VOTES)
    content = await FakePlanner().generate(snap, GenerationCreate())
    decisions = decisions_from(content.model_dump(mode="json"))
    assert decisions.main == ["bixby", "bakery", "mcway"]
    decisions.main.remove("mcway")
    decisions.side["mcway"] = None
    decisions.owner["bakery"] = "00000000-0000-0000-0000-000000000001"
    edited = await compose(
        snap,
        decisions,
        budget_preset="comfortable",
        router=EstimateRouter(),
        previous=content.model_dump(mode="json"),
    )
    nodes = nodes_by_id(edited)
    assert nodes["mcway"].quest == "side" and nodes["mcway"].detour_min is not None
    assert str(nodes["bakery"].owner_member_id).endswith("1")
    assert "Moved McWay Falls to side quests" in edited.changed_from_previous


class StubClient:
    def __init__(self, text=None, error=None):
        self.aio = self
        self.models = SimpleNamespace(
            generate_content=AsyncMock(return_value=SimpleNamespace(text=text), side_effect=error)
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


def selector(text=None, error=None):
    client = StubClient(text, error)
    return GeminiSelector("key", "model", client_factory=lambda **_: client), client


async def test_gemini_picks_and_reasons_with_code_owned_derivations():
    picks = {
        "main": ["mcway", "bixby"],
        "side": ["bakery"],
        "reasons": [
            {"place_id": "mcway", "why": "Maya voted I'm in; Sam voted Skip over parking."},
            {"place_id": "bixby", "why": "Sam asked to stop for photos."},
            {"place_id": "bakery", "why": "This hidden gem is open until 5."},
        ],
    }
    chooser, client = selector(json.dumps(picks))
    content = await QuestlinePlanner(EstimateRouter(), chooser).generate(
        snapshot(VOTES), GenerationCreate()
    )
    nodes = nodes_by_id(content)
    # Code orders the main quest along the route, regardless of the model's order.
    main = [n.id for n in content.graph.nodes if n.role == "stop" and n.quest == "main"]
    assert main == ["bixby", "mcway"]
    assert nodes["bixby"].why == "Sam asked to stop for photos."
    # A reason that breaks the honesty rules is replaced by a vote-grounded one.
    assert "hidden gem" not in nodes["bakery"].why and "Maya" in nodes["bakery"].why
    assert "nepenthe" not in nodes  # Omitted picks stay candidates.
    payload = json.loads(client.models.generate_content.call_args.kwargs["contents"])
    assert {c["id"] for c in payload["candidates"]} == {"bixby", "bakery", "nepenthe", "mcway"}


@pytest.mark.parametrize(
    "text,error",
    [('{"main": ["invented"], "side": [], "reasons": []}', None), (None, RuntimeError("down"))],
)
async def test_gemini_failure_falls_back_to_votes(text, error):
    chooser, _ = selector(text, error)
    with pytest.raises(ProviderUnavailable):
        await chooser.select(snapshot(VOTES), "comfortable")
    content = await QuestlinePlanner(EstimateRouter(), chooser).generate(
        snapshot(VOTES), GenerationCreate()
    )
    assert any("follows vote scores" in warning for warning in content.warnings)
    assert {n.id for n in content.graph.nodes if n.quest == "main" and n.role == "stop"} == {
        "bixby",
        "bakery",
        "mcway",
    }


async def test_google_routes_parses_legs_and_hides_failures():
    seen = []

    def handler(request):
        seen.append(request)
        body = json.loads(request.content)
        assert len(body["intermediates"]) == 1 and body["travelMode"] == "DRIVE"
        legs = [
            {"duration": "600s", "distanceMeters": 9000, "polyline": {"encodedPolyline": "abc"}},
            {"duration": "90.5s", "distanceMeters": 1000, "polyline": {"encodedPolyline": "def"}},
        ]
        return httpx.Response(200, json={"routes": [{"legs": legs}]})

    router = GoogleRoutes("secret", transport=httpx.MockTransport(handler))
    points = [LatLng(37, -122), LatLng(36.5, -121.9), LatLng(36.2, -121.8)]
    legs = await router.legs(points)
    assert [(leg.drive_min, leg.distance_m, leg.polyline) for leg in legs] == [
        (10.0, 9000, "abc"),
        (1.5, 1000, "def"),
    ]
    assert seen[0].headers["X-Goog-Api-Key"] == "secret"

    failing = GoogleRoutes("secret", transport=httpx.MockTransport(lambda _: httpx.Response(403)))
    with pytest.raises(RoutesUnavailable) as caught:
        await failing.legs(points)
    assert "secret" not in str(caught.value)
    # A routing outage still builds, with estimates and an explicit warning.
    content = await compose(
        snapshot(VOTES),
        Decisions(main=["bixby"], side={"mcway": None}),
        budget_preset="comfortable",
        router=failing,
    )
    assert any("Routing was unavailable" in warning for warning in content.warnings)
    assert all(edge.polyline is None for edge in content.graph.edges)

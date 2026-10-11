"""Regression tests for additions to the merged planner, not a second planning engine."""

import asyncio
import copy
import json
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from test_google_maps import PLACE
from test_questline_plan import MSG, VOTES, nodes_by_id, place, selector, snapshot

from questline.config import Settings
from questline.pricing import apply_estimate, estimate
from questline.providers.errors import ProviderUnavailable
from questline.providers.google_maps import WAYPOINT_FIELD_MASK, GoogleMaps, MapsUnavailable
from questline.providers.maps import FakeMaps, ResolvedPlace
from questline.providers.planner import QuestlinePlanner
from questline.providers.routes import EstimateRouter, Leg, RequestRouter
from questline.schemas import GenerationCreate
from questline.services.questline_plan import Decisions, PlanningError, changes, compose


class CountingRouter:
    routed = True

    def __init__(self, *, fail=False):
        self.calls = []
        self.active = self.peak = 0
        self.fail = fail

    async def legs(self, points):
        self.calls.append(points)
        if self.fail:
            raise ProviderUnavailable("private failure")
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0)
        self.active -= 1
        return [Leg(1.01, 100, "polyline") for _ in points[1:]]


def suggestion(gid="new-cafe", category="eat", lat=36.8):
    return ResolvedPlace(
        google_place_id=gid,
        name=gid,
        category=category,
        address="California",
        lat=lat,
        lng=-121.8,
        price_level=1,
    )


async def test_discovery_is_bounded_optional_and_does_not_mutate_snapshot():
    snap = snapshot(VOTES)
    frozen = copy.deepcopy(snap)
    router = CountingRouter()
    maps = FakeMaps()
    # Duplicate existing IDs and unsafe categories/coordinates never reach persistence.
    maps.search_along_route = AsyncMock(
        side_effect=[
            [suggestion("g-bakery"), suggestion()],
            [suggestion(), suggestion("second", "stay")],
        ]
    )
    pid = str(uuid4())
    sink = AsyncMock(return_value={"new-cafe": pid})
    content = await QuestlinePlanner(router, maps=maps, register_suggestions=sink).generate(
        snap, GenerationCreate()
    )
    assert snap == frozen
    sink.assert_awaited_once()
    assert [p.google_place_id for p in sink.call_args.args[0]] == ["new-cafe"]
    node = nodes_by_id(content)[pid]
    assert node.quest == "side" and node.source == "suggested"
    assert node.source_message_ids == [] and "No votes yet" in node.why
    assert node.est_cost == (10, 20)
    assert len(router.calls) <= 7 and maps.search_along_route.await_count == 2
    assert router.peak <= 2


@pytest.mark.parametrize("queries,limit,count", [(0, 4, 0), (2, 0, 0), (2, 1, 1)])
async def test_discovery_limits_and_disabled_calls(queries, limit, count):
    router = CountingRouter()
    maps = FakeMaps()
    maps.search_along_route = AsyncMock(return_value=[suggestion(), suggestion("second")])
    sink = AsyncMock(return_value={"new-cafe": str(uuid4()), "second": str(uuid4())})
    await QuestlinePlanner(
        router,
        maps=maps,
        register_suggestions=sink,
        suggestion_queries=queries,
        suggestion_limit=limit,
        detour_limit=0,
    ).generate(snapshot(), GenerationCreate())
    assert maps.search_along_route.await_count == count
    if count:
        assert len(sink.call_args.args[0]) == 1
    else:
        sink.assert_not_awaited()
        assert len(router.calls) == 1  # Main route only, no discovery baseline.


async def test_discovery_skips_capacity_offline_and_missing_sink():
    snap = snapshot(places=[place(str(i), str(i), 36.8, -121.8) for i in range(100)])
    router = CountingRouter()
    maps = FakeMaps()
    maps.search_along_route = AsyncMock()
    sink = AsyncMock()
    await QuestlinePlanner(router, maps=maps, register_suggestions=sink).generate(
        snap, GenerationCreate()
    )
    assert len(router.calls) == 1
    await QuestlinePlanner(router, maps=maps).generate(snapshot(), GenerationCreate())
    await QuestlinePlanner(EstimateRouter(), maps=maps, register_suggestions=sink).generate(
        snapshot(), GenerationCreate()
    )
    maps.search_along_route.assert_not_awaited()
    sink.assert_not_awaited()


async def test_failed_discovery_baseline_is_not_retried_for_identical_main_route():
    router = CountingRouter(fail=True)
    maps = FakeMaps()
    maps.search_along_route = AsyncMock()
    sink = AsyncMock()
    snap = snapshot()
    snap["places"] = []
    content = await QuestlinePlanner(router, maps=maps, register_suggestions=sink).generate(
        snap, GenerationCreate()
    )
    assert len(router.calls) == 1
    assert any("suggestions unavailable" in line for line in content.warnings)
    assert any("Routing was unavailable" in line for line in content.warnings)
    maps.search_along_route.assert_not_awaited()


async def test_identical_baseline_reused_on_success():
    router = CountingRouter()
    maps = FakeMaps()
    sink = AsyncMock()
    snap = snapshot()
    snap["places"] = []
    await QuestlinePlanner(router, maps=maps, register_suggestions=sink).generate(
        snap, GenerationCreate()
    )
    assert len(router.calls) == 1


async def test_optional_discovery_failure_does_not_fail_existing_plan():
    maps = FakeMaps()
    maps.search_along_route = AsyncMock(side_effect=MapsUnavailable("down"))
    sink = AsyncMock()
    content = await QuestlinePlanner(
        CountingRouter(), maps=maps, register_suggestions=sink
    ).generate(snapshot(), GenerationCreate())
    assert any("Suggestions for cafes unavailable" in line for line in content.warnings)
    assert nodes_by_id(content)["bixby"].quest == "main"
    sink.assert_not_awaited()


async def test_detours_cap_concurrency_rounding_and_unknowns():
    router = CountingRouter()
    snap = snapshot(places=[place(str(i), str(i), 36.8 + i * 0.01, -121.8) for i in range(8)])
    content = await compose(
        snap,
        Decisions(side={str(i): "start" for i in range(8)}),
        budget_preset="comfortable",
        router=router,
        detour_limit=3,
    )
    assert len(router.calls) == 4 and router.peak <= 2
    nodes = nodes_by_id(content)
    # 1.01 + 1.01 - 1.01 minutes => 2, without rounding each leg first.
    assert [nodes[str(i)].detour_min for i in range(3)] == [2] * 3
    assert all(nodes[str(i)].detour_min is None for i in range(3, 8))
    assert any("5 side-quest detours unknown" in line for line in content.warnings)
    assert all(
        e.detour_min == nodes[e.target].detour_min
        for e in content.graph.edges
        if e.kind == "detour"
    )


async def test_detour_deadline_preserves_main_and_cancellation_propagates(monkeypatch):
    import questline.services.questline_plan as module

    class SlowDetours(CountingRouter):
        async def legs(self, points):
            if len(points) == 3:
                await asyncio.sleep(10)
            return await super().legs(points)

    monkeypatch.setattr(module, "DETOUR_DEADLINE_SECONDS", 0.01)
    content = await compose(
        snapshot(),
        Decisions(side={"bixby": "start"}),
        budget_preset="comfortable",
        router=SlowDetours(),
    )
    assert nodes_by_id(content)["bixby"].detour_min is None
    task = asyncio.create_task(
        compose(
            snapshot(),
            Decisions(side={"bixby": "start"}),
            budget_preset="comfortable",
            router=SlowDetours(),
        )
    )
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_overall_deadline_is_not_an_unbounded_fallback(monkeypatch):
    import questline.providers.planner as module

    class SlowRouter(CountingRouter):
        async def legs(self, points):
            await asyncio.sleep(10)
            return await super().legs(points)

    monkeypatch.setattr(module, "PLANNING_DEADLINE_SECONDS", 0.01)
    with pytest.raises(TimeoutError):
        await QuestlinePlanner(SlowRouter()).generate(snapshot(), GenerationCreate())


@pytest.mark.parametrize(
    "reason",
    [
        {"place_id": "bakery", "message_ids": [MSG]},
        {"place_id": "bixby", "message_ids": [str(uuid4())]},
        {"place_id": "bixby", "message_ids": [], "why": "Invented consensus"},
    ],
)
async def test_selector_rejects_foreign_evidence_and_freeform_claims(reason):
    chooser, _ = selector(
        json.dumps({"main": ["bixby", "bakery"], "side": [], "reasons": [reason]})
    )
    with pytest.raises(ProviderUnavailable):
        await chooser.select(snapshot(VOTES), "comfortable")


async def test_selector_cannot_promote_new_discovery():
    from questline.providers.gemini_selector import Selection

    chooser = AsyncMock()
    # Even a selector that ignores optional_only cannot make a new suggestion main.
    chooser.select.return_value = Selection(["bixby"], [], {})
    # Regular selected candidate stays main; newly discovered candidate remains side.
    maps = FakeMaps()
    maps.search_along_route = AsyncMock(return_value=[suggestion()])
    pid = str(uuid4())
    chooser.select.return_value = Selection(["bixby", pid], [], {})
    content = await QuestlinePlanner(
        CountingRouter(),
        chooser,
        maps=maps,
        register_suggestions=AsyncMock(return_value={"new-cafe": pid}),
    ).generate(snapshot(), GenerationCreate())
    assert nodes_by_id(content)[pid].quest == "side"


def test_price_unknown_free_explicit_and_scope():
    assert estimate("eat", None) is None
    assert estimate("eat", 0)[:2] == (0, 0)
    assert estimate("stay", 2) is None and estimate("along_the_way", 2) is None
    explicit = {
        "category": "eat",
        "price_level": None,
        "est_cost_low": 15,
        "est_cost_high": 25,
        "cost_basis": "Supplied menu estimate",
    }
    frozen = explicit.copy()
    apply_estimate(explicit)
    assert explicit == frozen
    explicit["cost_basis"] = "App estimate from Google price level $$; per adult"
    apply_estimate(explicit)
    assert explicit["est_cost_low"] is None and explicit["cost_basis"] is None


async def test_richer_changes_and_along_the_way_exclusion():
    snap = snapshot(
        places=[
            place("food", "Food", 36.8, -121.8, "eat", cost=(0, 0)),
            place("road", "Road stop", 36.9, -121.8, "along_the_way", 4, (80, 150)),
        ]
    )
    # Explicit prices, not coarse estimates; retain free as a known price.
    snap["places"][0]["cost_basis"] = "Supplied estimate"
    first = await compose(
        snap, Decisions(main=["food", "road"]), budget_preset="comfortable", router=EstimateRouter()
    )
    assert first.per_person_estimate == (0, 0)
    assert not first.estimate_is_partial
    assert nodes_by_id(first)["road"].est_cost is None
    assert not first.conflicts
    old = first.model_dump(mode="json")
    updated = first.model_copy(deep=True)
    updated.budget_preset = "treat"
    updated.estimate_is_partial = True
    updated.unpriced_node_ids = ["food"]
    updated.graph.nodes[1].est_cost = None
    lines = changes(old, updated)
    assert any("Budget preset" in line for line in lines)
    assert any("price coverage" in line for line in lines)
    assert any("$0 to unknown" in line for line in lines)
    old["graph"]["nodes"][1].update(quest="side", anchor="start")
    updated.graph.nodes[1].quest = "side"
    updated.graph.nodes[1].anchor = "road"
    assert any("Changed side-quest anchor" in line for line in changes(old, updated))


async def test_stay_ends_day_and_dst_elapsed_duration():
    snap = snapshot(
        places=[
            place("hotel", "Hotel", 36.8, -121.8, "stay"),
            place("food", "Food", 36.7, -121.8, "eat"),
        ],
        start="2026-10-31",
        end="2026-11-01",
    )
    content = await compose(
        snap,
        Decisions(main=["hotel", "food"]),
        budget_preset="comfortable",
        router=CountingRouter(),
    )
    nodes = nodes_by_id(content)
    assert nodes["hotel"].depart.hour == 9 and str(nodes["hotel"].depart.date()) == "2026-11-01"
    assert nodes["hotel"].duration_min == 24 * 60 + 60 - 2  # 09:02 arrival, fall-back night.
    assert nodes["food"].arrive.date() == nodes["hotel"].depart.date()
    assert content.days[1].node_ids[0] == "hotel"
    assert any("not booked" in line for line in content.warnings)
    assert not any("accommodation is unplanned" in line for line in content.warnings)
    snap["trip"]["end_date"] = "2026-10-31"
    with pytest.raises(PlanningError, match="Stay needs another trip date"):
        await compose(
            snap, Decisions(main=["hotel"]), budget_preset="comfortable", router=CountingRouter()
        )


async def test_google_discovery_and_price_refresh_request_contracts():
    calls = []

    def handler(request):
        calls.append(request)
        if request.method == "GET":
            assert request.headers["X-Goog-FieldMask"] == "id,priceLevel"
            return httpx.Response(
                200, json={"id": "google-place-1", "priceLevel": "PRICE_LEVEL_FREE"}
            )
        body = json.loads(request.content)
        assert body["pageSize"] == 2
        assert body["searchAlongRouteParameters"] == {"polyline": {"encodedPolyline": "route"}}
        assert request.headers["X-Goog-FieldMask"] == WAYPOINT_FIELD_MASK
        return httpx.Response(
            200, json={"places": [PLACE, {**PLACE, "location": {"latitude": 0, "longitude": 0}}]}
        )

    from questline.providers.maps import SearchBounds

    maps = GoogleMaps("secret", transport=httpx.MockTransport(handler))
    results = await maps.search_along_route(
        "cafes", "route", bounds=SearchBounds(south=36, north=38, west=-123, east=-121)
    )
    assert len(results) == 1 and results[0].price_level == 2
    assert await maps.price_level("google-place-1") == 0
    assert len(calls) == 2


@pytest.mark.parametrize(
    "payload", [{"id": "wrong"}, {"id": "google-place-1", "priceLevel": 2}, []]
)
async def test_price_refresh_rejects_malformed_response(payload):
    maps = GoogleMaps(
        "secret", transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    )
    with pytest.raises(MapsUnavailable):
        await maps.price_level("google-place-1")


@pytest.mark.parametrize(
    "setting,value",
    [
        ("planner_detour_limit", 21),
        ("planner_suggestion_query_limit", 3),
        ("planner_suggestion_limit", 5),
    ],
)
def test_configuration_limits(setting, value):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **{setting: value})


async def test_bad_route_leg_count_degrades_safely():
    router = CountingRouter()
    router.legs = AsyncMock(return_value=[])
    with pytest.raises(ProviderUnavailable):
        await RequestRouter(router).legs([])
    content = await compose(
        snapshot(), Decisions(main=["bixby"]), budget_preset="comfortable", router=router
    )
    assert any("Routing was unavailable" in line for line in content.warnings)


@pytest.mark.parametrize("bad", ["capacity", "dates", "duplicate"])
async def test_invalid_inputs_rejected_before_provider_calls(bad):
    snap = snapshot()
    if bad == "capacity":
        snap["places"] = [place(str(i), str(i), 36.8, -121.8) for i in range(101)]
    elif bad == "dates":
        snap["trip"]["end_date"] = "2026-10-20"
    else:
        snap["places"].append(snap["places"][0].copy())
    router = CountingRouter()
    with pytest.raises(PlanningError):
        await QuestlinePlanner(router).generate(snap, GenerationCreate())
    assert router.calls == []


async def test_discovery_rejects_unsafe_provider_facts_and_caps_results():
    maps = FakeMaps()
    maps.search_along_route = AsyncMock(
        side_effect=[
            [
                suggestion("outside", lat=0),
                suggestion("lodging", category="stay"),
                suggestion("ignored"),
            ],
            [suggestion("accepted"), suggestion("accepted")],
        ]
    )
    sink = AsyncMock(return_value={"accepted": str(uuid4())})
    await QuestlinePlanner(CountingRouter(), maps=maps, register_suggestions=sink).generate(
        snapshot(),
        GenerationCreate(),
    )
    assert [p.google_place_id for p in sink.call_args.args[0]] == ["accepted"]


async def test_missing_and_invalid_detour_legs_stay_unknown():
    class FailedDetourRouter(CountingRouter):
        async def legs(self, points):
            return [] if len(points) == 3 else await super().legs(points)

    content = await compose(
        snapshot(),
        Decisions(side={"bixby": "start"}),
        budget_preset="comfortable",
        router=FailedDetourRouter(),
    )
    assert nodes_by_id(content)["bixby"].detour_min is None

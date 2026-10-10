import importlib.util
import json
import re
import sys
from itertools import count
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

SCRIPT = Path(__file__).parents[1] / "scripts" / "seed_demo.py"
DEMO_FILE = Path(__file__).parents[2] / "demo" / "trip.json"

_spec = importlib.util.spec_from_file_location("seed_demo", SCRIPT)
assert _spec and _spec.loader
seed_demo = importlib.util.module_from_spec(_spec)
sys.modules["seed_demo"] = seed_demo
_spec.loader.exec_module(seed_demo)

FIXTURE_PLACES = {
    "mcway falls": "McWay Falls (fixture)",
    "big sur bakery": "Big Sur Bakery (fixture)",
}
TRIP = {
    "name": "Big Sur weekend",
    "origin": "San Jose, CA",
    "destination": "Big Sur, CA",
    "start_date": "2026-10-17",
    "end_date": "2026-10-18",
    "timezone": "America/Los_Angeles",
    "organizer_name": "Maya",
}


def _error(status: int, message: str) -> httpx.Response:
    return httpx.Response(status, json={"error": {"code": "error", "message": message}})


class FakeApi:
    """In-memory stand-in for the slice of SPEC §10 the seed script drives."""

    def __init__(self, *, import_polls: int = 1, build_polls: int = 1, build_fails: bool = False):
        self.requests: list[tuple[str, str, dict | None]] = []
        self.trips: dict[str, dict] = {}
        self.import_polls = import_polls
        self.build_polls = build_polls
        self.build_fails = build_fails
        self.generations: dict[str, dict] = {}
        self._ids = count(1)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def _id(self) -> str:
        return f"00000000-0000-0000-0000-{next(self._ids):012d}"

    def _member(self, trip: dict, name: str) -> dict:
        member = {"id": self._id(), "trip_id": trip["trip"]["id"], "name": name}
        trip["members"].append(member)
        return {"member": member, "member_token": f"token-{name}"}

    def _place(self, trip: dict, name: str) -> dict:
        for place in trip["places"]:
            if place["name"] == name:
                return place
        place = {"id": self._id(), "trip_id": trip["trip"]["id"], "name": name}
        trip["places"].append(place)
        return place

    def handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        path = request.url.path
        self.requests.append((request.method, path, body))
        assert request.headers["authorization"] == "Bearer secret"
        if path == "/health/ready":
            return httpx.Response(200, json={"status": "ready"})
        route = f"{request.method} {path.removeprefix('/api/v1')}"
        if route == "POST /trips":
            trip_id = self._id()
            trip = {
                "trip": {"id": trip_id, "name": body["name"], "unresolved_mentions": []},
                "members": [],
                "places": [],
                "votes": [],
                "imports": [],
            }
            self.trips[trip_id] = trip
            return httpx.Response(201, json={"trip": trip["trip"], **self._member(trip, "Maya")})
        if match := re.fullmatch(r"GET /trips/([\w-]+)", route):
            trip = self.trips.get(match[1])
            if trip is None:
                return _error(404, "Trip not found")
            for imported in trip["imports"]:
                imported["polls"] -= 1
                if imported["polls"] <= 0:
                    imported["status"] = "succeeded"
            return httpx.Response(200, json=trip)
        if match := re.fullmatch(r"POST /trips/([\w-]+)/members", route):
            return httpx.Response(201, json=self._member(self.trips[match[1]], body["name"]))
        if match := re.fullmatch(r"POST /trips/([\w-]+)/import", route):
            trip = self.trips[match[1]]
            imported = {"id": self._id(), "status": "queued", "polls": self.import_polls}
            trip["imports"].append(imported)
            for key, name in FIXTURE_PLACES.items():
                if key in body["text"].lower():
                    self._place(trip, name)
            if "mystery cafe" in body["text"].lower():
                trip["trip"]["unresolved_mentions"].append({"mention_text": "Mystery Cafe"})
            return httpx.Response(202, json={"import_id": imported["id"], "status": "queued"})
        if match := re.fullmatch(r"POST /trips/([\w-]+)/places", route):
            name = FIXTURE_PLACES.get(body["query"].lower())
            if name is None:
                return _error(404, "Couldn't find that place")
            return httpx.Response(201, json={"place": self._place(self.trips[match[1]], name)})
        if match := re.fullmatch(r"POST /places/([\w-]+)/votes", route):
            trip = next(
                t for t in self.trips.values() if any(p["id"] == match[1] for p in t["places"])
            )
            vote = {"place_id": match[1], "member_id": body["member_id"], "kind": body["kind"]}
            if vote in trip["votes"]:
                trip["votes"].remove(vote)  # the real endpoint toggles
                return httpx.Response(200, json={"vote": None})
            trip["votes"].append(vote)
            return httpx.Response(200, json={"vote": vote})
        if match := re.fullmatch(r"POST /trips/([\w-]+)/plan-generations", route):
            assert request.headers["idempotency-key"]
            generation = {"id": self._id(), "status": "queued", "plan_id": None, "error": None}
            self.generations[generation["id"]] = {**generation, "polls": self.build_polls}
            return httpx.Response(202, json={"generation": generation})
        if match := re.fullmatch(r"GET /plan-generations/([\w-]+)", route):
            generation = self.generations[match[1]]
            generation["polls"] -= 1
            if generation["polls"] <= 0:
                if self.build_fails:
                    generation.update(status="failed", error="Planner exploded")
                else:
                    generation.update(status="succeeded", plan_id=str(uuid4()))
            return httpx.Response(200, json={"generation": generation})
        raise AssertionError(f"Unexpected request: {route}")

    def calls(self, method: str, pattern: str) -> list[dict | None]:
        return [
            body
            for m, path, body in self.requests
            if m == method and re.fullmatch(pattern, path.removeprefix("/api/v1"))
        ]


def run(api: FakeApi, spec: dict, **kwargs) -> tuple[str, list[str]]:
    lines: list[str] = []
    client = seed_demo.make_client("http://api.test", "secret", transport=api.transport())
    trip_id = seed_demo.seed(
        client,
        seed_demo.DemoSpec.model_validate(spec),
        web_url="http://web.test",
        out=lines.append,
        sleep=lambda _: None,
        **kwargs,
    )
    return trip_id, lines


def test_creates_the_trip_joins_members_and_prints_the_link():
    api = FakeApi()
    trip_id, lines = run(api, {"trip": TRIP, "members": ["Sam", "Jordan"]})
    assert api.calls("POST", "/trips") == [TRIP]
    assert api.calls("POST", r"/trips/[\w-]+/members") == [{"name": "Sam"}, {"name": "Jordan"}]
    assert f"http://web.test/t/{trip_id}" in "\n".join(lines)


def test_prints_member_tokens_so_teammates_can_open_the_trip_as_someone():
    api = FakeApi()
    _, lines = run(api, {"trip": TRIP, "members": ["Sam"]})
    output = "\n".join(lines)
    assert "Maya: token-Maya" in output
    assert "Sam: token-Sam" in output


def test_import_waits_for_extraction_and_reports_places_it_could_not_place():
    api = FakeApi(import_polls=3)
    chat = "Maya: McWay Falls!\nSam: what about Mystery Cafe\n"
    _, lines = run(api, {"trip": TRIP, "chat": chat})
    assert api.calls("POST", r"/trips/[\w-]+/import") == [{"text": chat}]
    output = "\n".join(lines)
    assert "Couldn't place: Mystery Cafe" in output
    assert "McWay Falls (fixture)" in output


def test_import_that_never_finishes_raises():
    api = FakeApi(import_polls=10_000)
    with pytest.raises(seed_demo.SeedError, match="import"):
        run(api, {"trip": TRIP, "chat": "Maya: McWay Falls"}, import_timeout=3)


def test_votes_match_waypoints_by_name_and_skip_unknown_places():
    api = FakeApi()
    spec = {
        "trip": TRIP,
        "members": ["Sam"],
        "chat": "Maya: McWay Falls?",
        "votes": [
            {"member": "Maya", "place": "McWay Falls", "kind": "in"},
            {"member": "Sam", "place": "mcway falls", "kind": "out"},
            {"member": "Sam", "place": "Nowhere Diner", "kind": "in"},
        ],
    }
    _, lines = run(api, spec)
    trip = next(iter(api.trips.values()))
    names = {m["id"]: m["name"] for m in trip["members"]}
    assert sorted((names[v["member_id"]], v["kind"]) for v in trip["votes"]) == [
        ("Maya", "in"),
        ("Sam", "out"),
    ]
    assert any("Nowhere Diner" in line and "no waypoint" in line for line in lines)


def test_vote_from_an_unknown_member_is_rejected_before_any_request():
    api = FakeApi()
    spec = {"trip": TRIP, "votes": [{"member": "Ghost", "place": "McWay Falls", "kind": "in"}]}
    with pytest.raises(ValidationError, match="Ghost"):
        run(api, spec)
    assert api.requests == []


def test_rerunning_on_an_existing_trip_keeps_votes_instead_of_toggling_them_off():
    api = FakeApi()
    spec = {
        "trip": TRIP,
        "members": ["Sam"],
        "chat": "Maya: McWay Falls?",
        "votes": [{"member": "Sam", "place": "McWay Falls", "kind": "out"}],
    }
    trip_id, _ = run(api, spec)
    run(api, spec, trip_id=trip_id)
    assert len(api.trips[trip_id]["votes"]) == 1
    assert len(api.calls("POST", r"/places/[\w-]+/votes")) == 1


def test_existing_trip_mode_skips_create_and_existing_members():
    api = FakeApi()
    trip_id, _ = run(api, {"trip": TRIP, "members": ["Sam"]})
    run(api, {"members": ["Sam", "Jordan"]}, trip_id=trip_id)
    assert len(api.calls("POST", "/trips")) == 1
    assert api.calls("POST", r"/trips/[\w-]+/members") == [{"name": "Sam"}, {"name": "Jordan"}]


def test_spec_without_a_trip_needs_an_existing_trip_id():
    with pytest.raises(seed_demo.SeedError, match="--trip"):
        run(FakeApi(), {"members": ["Sam"]})


def test_add_places_by_search_and_warn_on_misses():
    api = FakeApi()
    spec = {
        "trip": TRIP,
        "add_places": [{"query": "Big Sur Bakery"}, {"query": "Atlantis"}],
    }
    _, lines = run(api, spec)
    assert api.calls("POST", r"/trips/[\w-]+/places") == [
        {"query": "Big Sur Bakery"},
        {"query": "Atlantis"},
    ]
    assert any("Atlantis" in line and "Couldn't find" in line for line in lines)


def test_build_polls_until_the_plan_is_ready():
    api = FakeApi(build_polls=3)
    _, lines = run(api, {"trip": TRIP, "build": {"budget_preset": "treat"}})
    assert api.calls("POST", r"/trips/[\w-]+/plan-generations") == [{"budget_preset": "treat"}]
    assert len(api.calls("GET", r"/plan-generations/[\w-]+")) == 3
    assert any("Plan ready" in line for line in lines)


def test_skip_build_does_not_request_a_plan():
    api = FakeApi()
    run(api, {"trip": TRIP, "build": {}}, skip_build=True)
    assert api.calls("POST", r"/trips/[\w-]+/plan-generations") == []


def test_failed_build_raises_with_the_server_error():
    api = FakeApi(build_fails=True)
    with pytest.raises(seed_demo.SeedError, match="Planner exploded"):
        run(api, {"trip": TRIP, "build": {}})


def test_api_errors_raise_with_the_error_message():
    api = FakeApi()
    with pytest.raises(seed_demo.SeedError, match="Trip not found"):
        run(api, {"members": ["Sam"]}, trip_id=str(uuid4()))


def test_main_exits_nonzero_and_prints_the_error(tmp_path, capsys, monkeypatch):
    spec_file = tmp_path / "trip.json"
    spec_file.write_text(json.dumps({"members": ["Sam"]}))
    monkeypatch.setenv("API_TOKEN", "secret")
    assert seed_demo.main([str(spec_file), "--api", "http://127.0.0.1:9"]) == 1
    assert "error:" in capsys.readouterr().err


def test_checked_in_demo_file_is_valid():
    spec = seed_demo.DemoSpec.model_validate_json(DEMO_FILE.read_text())
    assert spec.trip is not None
    assert spec.chat
    assert any(v.kind == "in" for v in spec.votes) and any(v.kind == "out" for v in spec.votes)

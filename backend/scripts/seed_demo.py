"""Seed a realistic demo trip through the public API (SPEC §20).

Creates a trip (or uses an existing one), joins members, imports a pasted chat, adds places by
search, casts votes, and builds a plan, then prints the trip link and member tokens.

    uv run python scripts/seed_demo.py ../demo/trip.json
    uv run python scripts/seed_demo.py ../demo/trip.json --trip <trip id> --skip-build

`--api` defaults to $BASE_URL or http://localhost:8000; the Bearer token comes from $API_TOKEN.
"""

import argparse
import math
import os
import sys
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

POLL_SECONDS = 1.0


class SeedError(Exception):
    pass


class _Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TripSpec(_Spec):
    name: str
    origin: str
    destination: str
    start_date: date
    end_date: date
    timezone: str
    organizer_name: str


class VoteSpec(_Spec):
    member: str
    place: str
    kind: Literal["in", "ok", "out"]


class AddPlaceSpec(_Spec):
    query: str


class BuildSpec(_Spec):
    budget_preset: Literal["shoestring", "comfortable", "treat"] = "comfortable"


class DemoSpec(_Spec):
    trip: TripSpec | None = None
    members: list[str] = Field(default_factory=list)
    chat: str | None = None
    add_places: list[AddPlaceSpec] = Field(default_factory=list)
    votes: list[VoteSpec] = Field(default_factory=list)
    build: BuildSpec | None = None

    @model_validator(mode="after")
    def _voters_are_members(self) -> "DemoSpec":
        if self.trip is None:
            return self  # Existing trip: members are checked against the API at run time.
        known = {_key(name) for name in [self.trip.organizer_name, *self.members]}
        unknown = sorted({v.member for v in self.votes if _key(v.member) not in known})
        if unknown:
            raise ValueError(f"votes name people who are not members: {', '.join(unknown)}")
        return self


def _key(name: str) -> str:
    return name.strip().casefold()


class Api:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.TransportError as exc:
            raise SeedError(f"can't reach the API at {self._client.base_url}: {exc}") from exc
        if response.is_error:
            status = response.status_code
            raise SeedError(f"{method} {path} failed ({status}): {_message(response)}")
        return response

    def get(self, path: str) -> dict[str, Any]:
        return self.request("GET", path).json()

    def post(self, path: str, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return self.request("POST", path, json=body, **kwargs).json()


def _message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.reason_phrase
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code"))
    return str(payload)


def make_client(
    api_url: str, token: str, *, transport: httpx.BaseTransport | None = None
) -> httpx.Client:
    return httpx.Client(
        base_url=api_url.rstrip("/"),
        headers={"Authorization": f"Bearer {token}"},
        transport=transport,
        timeout=30,
    )


def seed(
    client: httpx.Client,
    spec: DemoSpec,
    *,
    trip_id: str | None = None,
    skip_build: bool = False,
    web_url: str = "http://localhost:5173",
    out: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
    import_timeout: float = 60,
    build_timeout: float = 180,
) -> str:
    """Seed `spec` into a new trip (or `trip_id`) and return the trip id."""
    api = Api(client)
    tokens: dict[str, str] = {}

    if trip_id is None:
        if spec.trip is None:
            raise SeedError('the file has no "trip"; pass --trip <id> to seed an existing trip')
        api.request("GET", "/health/ready")
        created = api.post("/api/v1/trips", spec.trip.model_dump(mode="json"))
        trip_id = str(created["trip"]["id"])
        tokens[created["member"]["name"]] = created["member_token"]
        out(f"Created trip {created['trip']['name']!r} ({trip_id})")
    base = f"/api/v1/trips/{trip_id}"
    state = api.get(base)

    existing = {_key(m["name"]) for m in state["members"]}
    for name in spec.members:
        if _key(name) in existing:
            continue
        joined = api.post(f"{base}/members", {"name": name})
        tokens[name] = joined["member_token"]
        existing.add(_key(name))
    if tokens:
        out(f"Members: {', '.join(tokens)}")

    if spec.chat:
        state = _import_chat(api, base, spec.chat, out, sleep, import_timeout)

    for add in spec.add_places:
        try:
            place = api.post(f"{base}/places", {"query": add.query})["place"]
        except SeedError as exc:
            out(f"Couldn't find {add.query!r}: {exc}")
            continue
        out(f"Added waypoint {place['name']}")

    if spec.votes:
        state = api.get(base)
        _vote(api, state, spec.votes, out)

    if spec.build and not skip_build:
        _build(api, base, spec.build, out, sleep, build_timeout)

    if tokens:
        out("Member tokens (send as X-Member-Token to act as that person):")
        for name, token in tokens.items():
            out(f"  {name}: {token}")
    out(f"Trip link: {web_url.rstrip('/')}/t/{trip_id}")
    return trip_id


def _attempts(timeout: float) -> int:
    return max(1, math.ceil(timeout / POLL_SECONDS))


def _import_chat(
    api: Api,
    base: str,
    chat: str,
    out: Callable[[str], None],
    sleep: Callable[[float], None],
    timeout: float,
) -> dict[str, Any]:
    import_id = str(api.post(f"{base}/import", {"text": chat})["import_id"])
    out("Imported chat; waiting for place extraction...")
    for _ in range(_attempts(timeout)):
        state = api.get(base)
        job = next((i for i in state["imports"] if str(i["id"]) == import_id), None)
        if job and job["status"] == "failed":
            raise SeedError(f"import failed: {job.get('error') or 'no reason given'}")
        if job and job["status"] == "succeeded":
            names = ", ".join(p["name"] for p in state["places"]) or "none"
            out(f"Waypoints: {names}")
            for mention in state["trip"].get("unresolved_mentions", []):
                out(f"Couldn't place: {mention['mention_text']}")
            return state
        sleep(POLL_SECONDS)
    raise SeedError(f"import did not finish within {timeout:g}s; is the worker running?")


def _match_place(places: list[dict[str, Any]], wanted: str) -> dict[str, Any] | str:
    key = _key(wanted)
    exact = [p for p in places if _key(p["name"]) == key]
    if exact:
        return exact[0]
    partial = [p for p in places if key in _key(p["name"])]
    if len(partial) == 1:
        return partial[0]
    if partial:
        return f"matches several waypoints ({', '.join(p['name'] for p in partial)})"
    return "matches no waypoint"


def _vote(
    api: Api, state: dict[str, Any], votes: list[VoteSpec], out: Callable[[str], None]
) -> None:
    members = {_key(m["name"]): str(m["id"]) for m in state["members"]}
    cast = {(str(v["place_id"]), str(v["member_id"]), v["kind"]) for v in state["votes"]}
    for vote in votes:
        member_id = members.get(_key(vote.member))
        if member_id is None:
            out(f"Skipped vote: {vote.member!r} is not a member of this trip")
            continue
        place = _match_place(state["places"], vote.place)
        if isinstance(place, str):
            out(f"Skipped vote: {vote.place!r} {place}")
            continue
        # The vote endpoint toggles, so re-sending an existing vote would remove it.
        if (str(place["id"]), member_id, vote.kind) in cast:
            continue
        api.post(f"/api/v1/places/{place['id']}/votes", {"kind": vote.kind, "member_id": member_id})
        cast.add((str(place["id"]), member_id, vote.kind))
        out(f"{vote.member} voted {vote.kind} on {place['name']}")


def _build(
    api: Api,
    base: str,
    build: BuildSpec,
    out: Callable[[str], None],
    sleep: Callable[[float], None],
    timeout: float,
) -> None:
    generation = api.post(
        f"{base}/plan-generations",
        build.model_dump(),
        headers={"Idempotency-Key": str(uuid4())},
    )["generation"]
    out(f"Building plan ({build.budget_preset})...")
    for _ in range(_attempts(timeout)):
        generation = api.get(f"/api/v1/plan-generations/{generation['id']}")["generation"]
        if generation["status"] == "failed":
            raise SeedError(f"build failed: {generation.get('error') or 'no reason given'}")
        if generation["status"] == "succeeded":
            out(f"Plan ready: {generation['plan_id']}")
            return
        sleep(POLL_SECONDS)
    raise SeedError(f"build did not finish within {timeout:g}s; is the worker running?")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed a demo trip through the Questline API.")
    parser.add_argument("spec", type=Path, help="demo trip file, e.g. ../demo/trip.json")
    parser.add_argument("--api", default=os.getenv("BASE_URL", "http://localhost:8000"))
    parser.add_argument("--web", default=os.getenv("WEB_BASE_URL", "http://localhost:5173"))
    parser.add_argument("--trip", help="seed into this existing trip instead of creating one")
    parser.add_argument("--skip-build", action="store_true", help="don't request a plan")
    args = parser.parse_args(argv)

    token = os.getenv("API_TOKEN", "local-development-only")
    try:
        spec = DemoSpec.model_validate_json(args.spec.read_text())
        with make_client(args.api, token) as client:
            seed(client, spec, trip_id=args.trip, skip_build=args.skip_build, web_url=args.web)
    except (OSError, ValueError, SeedError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

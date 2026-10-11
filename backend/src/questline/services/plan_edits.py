"""Apply decision-only operations (SPEC §8 Edits) and offer grounded resolutions (SPEC §8 Resolve).

Operations change membership, quest, order, anchor, owner, and notes. Callers then recompute every
derived field with `compose`. Resolution options are built from actual votes and places only, and
every option is validated by applying it before it is offered.
"""

import copy
from typing import Any

from questline.operations import (
    Add,
    AssignOwner,
    Drop,
    Move,
    Operation,
    SetAnchor,
    SetNote,
    SetQuest,
)
from questline.providers.routes import LatLng, straight_line_m
from questline.schemas import Schema
from questline.services.questline_plan import (
    Decisions,
    candidates,
    route_order,
    vote_parts,
    voters,
)

FOLLOW_THROUGH = (AssignOwner, SetNote)


class InvalidOperation(ValueError):
    """Safe to show to clients."""


class ResolutionOption(Schema):
    label: str
    rationale: str
    operations: list[Operation]


def only_follow_through(operations: list[Operation]) -> bool:
    """Owners and notes are follow-through; they never return an accepted plan to draft."""
    return all(isinstance(operation, FOLLOW_THROUGH) for operation in operations)


def _insert_main(snapshot: dict[str, Any], main: list[str], pid: str, after: str | None) -> None:
    if after == "start":
        main.insert(0, pid)
    elif after is not None:
        if after not in main:
            raise InvalidOperation("Insert after a stop on the main quest")
        main.insert(main.index(after) + 1, pid)
    else:
        ordered = route_order(snapshot, [*main, pid])
        main.insert(ordered.index(pid), pid)


def apply_operations(
    snapshot: dict[str, Any], decisions: Decisions, operations: list[Operation]
) -> Decisions:
    result = copy.deepcopy(decisions)
    places = {place["id"] for place in candidates(snapshot)}
    members = {member["id"] for member in snapshot["members"]}

    def require_stop(node_id: str) -> None:
        if node_id not in result.main and node_id not in result.side:
            raise InvalidOperation("That stop is not in the questline")

    def valid_anchor(anchor: str) -> bool:
        return anchor == "start" or anchor in result.main

    for operation in operations:
        if isinstance(operation, SetQuest):
            require_stop(operation.node_id)
            pid = operation.node_id
            if operation.quest == "side" and pid in result.main:
                result.main.remove(pid)
                result.side[pid] = None
                # Side quests anchored to the demoted stop pick a new leg.
                for other, anchor in result.side.items():
                    if anchor == pid:
                        result.side[other] = None
            elif operation.quest == "main" and pid in result.side:
                anchor = result.side.pop(pid)
                _insert_main(snapshot, result.main, pid, anchor if anchor else None)
        elif isinstance(operation, Move):
            if operation.node_id not in result.main or operation.after == operation.node_id:
                raise InvalidOperation("Only main quest stops can be reordered")
            result.main.remove(operation.node_id)
            _insert_main(snapshot, result.main, operation.node_id, operation.after)
        elif isinstance(operation, SetAnchor):
            if operation.node_id not in result.side or not valid_anchor(operation.anchor):
                raise InvalidOperation("Anchor a side quest to the start or a main quest stop")
            result.side[operation.node_id] = operation.anchor
        elif isinstance(operation, Drop):
            require_stop(operation.node_id)
            if operation.node_id in result.main:
                result.main.remove(operation.node_id)
                for other, anchor in result.side.items():
                    if anchor == operation.node_id:
                        result.side[other] = None
            result.side.pop(operation.node_id, None)
        elif isinstance(operation, Add):
            pid = str(operation.place_id)
            if pid not in places:
                raise InvalidOperation("Add a waypoint from this trip")
            if pid in result.main or pid in result.side:
                raise InvalidOperation("That waypoint is already in the questline")
            if operation.quest == "main":
                _insert_main(snapshot, result.main, pid, operation.after)
            else:
                if operation.anchor is not None and not valid_anchor(operation.anchor):
                    raise InvalidOperation("Anchor a side quest to the start or a main quest stop")
                result.side[pid] = operation.anchor
        elif isinstance(operation, AssignOwner):
            require_stop(operation.node_id)
            member = str(operation.member_id) if operation.member_id else None
            if member is not None and member not in members:
                raise InvalidOperation("Owner must be a member of this trip")
            result.owner[operation.node_id] = member
        elif isinstance(operation, SetNote):
            require_stop(operation.node_id)
            result.notes[operation.node_id] = operation.notes
    return result


def _vote_summary(snapshot: dict[str, Any], pid: str) -> str:
    return "; ".join(vote_parts(snapshot, pid)) or "No votes yet"


def resolution_options(
    snapshot: dict[str, Any], decisions: Decisions, node_id: str
) -> list[ResolutionOption]:
    """Up to three options, each grounded in votes and validated against the current plan."""
    places = {place["id"]: place for place in candidates(snapshot)}
    if node_id not in places or (node_id not in decisions.main and node_id not in decisions.side):
        raise InvalidOperation("Resolve a stop in the questline")
    place = places[node_id]
    name = place["name"]
    votes = _vote_summary(snapshot, node_id)
    raw: list[dict[str, Any]] = []
    if node_id in decisions.main:
        raw.append(
            {
                "label": "Make it a side quest",
                "rationale": f"{votes}. As a side quest, {name} stays optional "
                "for whoever wants it.",
                "operations": [{"op": "set_quest", "node_id": node_id, "quest": "side"}],
            }
        )
    else:
        raw.append(
            {
                "label": "Put it on the main quest",
                "rationale": f"{votes}. Promoting {name} adds it to the route for everyone.",
                "operations": [{"op": "set_quest", "node_id": node_id, "quest": "main"}],
            }
        )
    # A nearby alternative of the same kind that nobody skipped and that isn't already in place.
    quest = "main" if node_id in decisions.main else "side"
    here = LatLng(place["lat"], place["lng"])
    taken = set(decisions.main) | (set(decisions.side) if quest == "side" else set())
    alternatives = sorted(
        (
            other
            for other in places.values()
            if other["id"] != node_id
            and other["id"] not in taken
            and other["category"] == place["category"]
            and not voters(snapshot, other["id"])["out"]
        ),
        key=lambda other: straight_line_m(here, LatLng(other["lat"], other["lng"])),
    )
    if alternatives:
        other = alternatives[0]
        km = straight_line_m(here, LatLng(other["lat"], other["lng"])) / 1000
        bring = (
            {"op": "set_quest", "node_id": other["id"], "quest": "main"}
            if other["id"] in decisions.side
            else {"op": "add", "place_id": other["id"], "quest": quest}
        )
        raw.append(
            {
                "label": f"Swap for {other['name']}",
                "rationale": f"{votes} on {name}. {other['name']} is about {km:.0f} km away "
                f"(straight line); {_vote_summary(snapshot, other['id'])} on it.",
                "operations": [bring, {"op": "drop", "node_id": node_id}],
            }
        )
    raw.append(
        {
            "label": "Drop it",
            "rationale": f"{votes}. Dropping {name} removes it from the questline; "
            "it stays in Waypoints.",
            "operations": [{"op": "drop", "node_id": node_id}],
        }
    )
    options = []
    for candidate in raw:
        option = ResolutionOption.model_validate(candidate)
        try:
            apply_operations(snapshot, decisions, option.operations)
        except InvalidOperation:
            continue
        options.append(option)
    return options[:3]

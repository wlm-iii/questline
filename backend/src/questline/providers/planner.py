import asyncio
import copy
from typing import Any, Protocol

from questline.pricing import apply_estimate, over_budget
from questline.providers.errors import ProviderUnavailable
from questline.providers.gemini_selector import GeminiSelector
from questline.providers.maps import MapsProvider
from questline.providers.routes import RequestRouter, Router
from questline.schemas import GenerationCreate, PlanContent
from questline.services.questline_plan import (
    Decisions,
    candidates,
    compose,
    decisions_from,
    route_order,
    validate_context,
    vote_selection,
)
from questline.services.suggestions import SuggestionSink, discover

PLANNING_DEADLINE_SECONDS = 180


class Planner(Protocol):
    async def generate(self, snapshot: dict[str, Any], request: GenerationCreate) -> PlanContent:
        """Generate from the immutable request snapshot; transcript text is untrusted."""
        ...


class QuestlinePlanner:
    """Selection from votes (or Gemini when configured); everything derived comes from code."""

    def __init__(
        self,
        router: Router,
        selector: GeminiSelector | None = None,
        *,
        maps: MapsProvider | None = None,
        register_suggestions: SuggestionSink | None = None,
        detour_limit: int = 5,
        suggestion_queries: int = 2,
        suggestion_limit: int = 4,
    ):
        if not (
            0 <= detour_limit <= 20 and 0 <= suggestion_queries <= 2 and 0 <= suggestion_limit <= 4
        ):
            raise ValueError("Invalid planning lookup limits")
        self._router, self._selector = router, selector
        self._maps, self._sink = maps, register_suggestions
        self._detour_limit = detour_limit
        self._suggestion_queries, self._suggestion_limit = suggestion_queries, suggestion_limit

    async def generate(self, snapshot: dict[str, Any], request: GenerationCreate) -> PlanContent:
        async with asyncio.timeout(PLANNING_DEADLINE_SECONDS):
            return await self._generate(copy.deepcopy(snapshot), request)

    async def _generate(self, snapshot: dict[str, Any], request: GenerationCreate) -> PlanContent:
        validate_context(snapshot)
        router = RequestRouter(self._router)
        preset = request.budget_preset
        warnings: list[str] = []
        if self._maps is not None and self._sink is not None:
            warnings.extend(
                await discover(
                    snapshot,
                    router,
                    self._maps,
                    self._sink,
                    query_limit=self._suggestion_queries,
                    suggestion_limit=self._suggestion_limit,
                )
            )
        for place in snapshot["places"]:
            apply_estimate(place)
            place["vote_tallies"] = {
                kind: sum(
                    v["place_id"] == place["id"] and v["kind"] == kind for v in snapshot["votes"]
                )
                for kind in ("in", "ok", "out")
            }
        main, side = vote_selection(snapshot)
        why: dict[str, str] = {}
        if self._selector is not None:
            try:
                picked = await self._selector.select(snapshot, preset)
                main, side, why = picked.main, picked.side, picked.why
            except ProviderUnavailable:
                warnings.append("AI picks were unavailable, so this questline follows vote scores")
        by_id = {place["id"]: place for place in candidates(snapshot)}
        # New discovery facts have no request-time group support and must remain optional.
        optional = snapshot.get("optional_only_ids", [])
        for pid in optional:
            if pid in main:
                main.remove(pid)
            if pid not in side:
                side.append(pid)
        # The preset is enforced in code: over-budget picks become side quests, never dropped.
        demoted = [
            pid
            for pid in main
            if by_id[pid]["category"] in ("eat", "do")
            and over_budget(by_id[pid].get("price_level"), preset)
        ]
        main = [pid for pid in main if pid not in demoted]
        side = [*side, *(pid for pid in demoted if pid not in side)]
        previous = snapshot.get("previous_plan")
        # Owners and notes are group decisions; keep them across rebuilds.
        kept = decisions_from(previous) if previous else Decisions()
        decisions = Decisions(
            main=route_order(snapshot, main),
            side={pid: None for pid in side},
            why=why,
            owner=kept.owner,
            notes=kept.notes,
        )
        return await compose(
            snapshot,
            decisions,
            budget_preset=preset,
            router=router,
            detour_limit=self._detour_limit,
            previous=previous,
            warnings=warnings,
        )

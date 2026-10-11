from typing import Any, Protocol

from questline.pricing import over_budget
from questline.providers.errors import ProviderUnavailable
from questline.providers.gemini_selector import GeminiSelector
from questline.providers.routes import Router
from questline.schemas import GenerationCreate, PlanContent
from questline.services.questline_plan import (
    Decisions,
    candidates,
    compose,
    decisions_from,
    route_order,
    vote_selection,
)


class Planner(Protocol):
    async def generate(self, snapshot: dict[str, Any], request: GenerationCreate) -> PlanContent:
        """Generate from the immutable request snapshot; transcript text is untrusted."""
        ...


class QuestlinePlanner:
    """Selection from votes (or Gemini when configured); everything derived comes from code."""

    def __init__(self, router: Router, selector: GeminiSelector | None = None):
        self._router = router
        self._selector = selector

    async def generate(self, snapshot: dict[str, Any], request: GenerationCreate) -> PlanContent:
        preset = request.budget_preset
        warnings: list[str] = []
        main, side = vote_selection(snapshot)
        why: dict[str, str] = {}
        if self._selector is not None:
            try:
                picked = await self._selector.select(snapshot, preset)
                main, side, why = picked.main, picked.side, picked.why
            except ProviderUnavailable:
                warnings.append("AI picks were unavailable, so this questline follows vote scores")
        by_id = {place["id"]: place for place in candidates(snapshot)}
        # The preset is enforced in code: over-budget picks become side quests, never dropped.
        demoted = [pid for pid in main if over_budget(by_id[pid].get("price_level"), preset)]
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
            router=self._router,
            previous=previous,
            warnings=warnings,
        )

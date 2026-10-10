from typing import Any

from questline.schemas import GenerationCreate, PlanContent, PlanGraph


class FakePlanner:
    async def generate(self, snapshot: dict[str, Any], request: GenerationCreate) -> PlanContent:
        # No fictional waypoint is presented as resolved. Candidates land in a later slice.
        return PlanContent(
            title="Example questline draft",
            graph=PlanGraph(),
            budget_preset=request.budget_preset,
            timezone=snapshot.get("timezone", "UTC"),
            assumptions=["Planning uses the snapshot captured when Build was requested"],
            open_questions=["Add resolved candidate waypoints to build a routed questline"],
            warnings=["Mock output only: no AI, place lookup, or travel estimates were used."],
        )

from questline.schemas import (
    GenerationCreate,
    MessageRead,
    PlanContent,
    PlanGraph,
    PlanNode,
)


class FakePlanner:
    async def generate(
        self, transcript: list[MessageRead], request: GenerationCreate
    ) -> PlanContent:
        # Intentionally not an AI approximation: stable output for UI work and tests.
        return PlanContent(
            title="Example trip draft",
            graph=PlanGraph(
                nodes=[
                    PlanNode(
                        id="activity-1",
                        kind="activity",
                        title="Choose an activity together",
                        source_message_ids=[message.id for message in transcript[:1]],
                    )
                ]
            ),
            assumptions=[f"Planning timezone: {request.timezone}"],
            open_questions=["What destination, dates, and budget should the trip use?"],
            warnings=["Mock output only: no AI, place lookup, or travel estimates were used."],
        )

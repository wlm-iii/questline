from typing import Protocol

from questline.schemas import GenerationCreate, MessageRead, PlanContent


class Planner(Protocol):
    async def generate(
        self, transcript: list[MessageRead], request: GenerationCreate
    ) -> PlanContent:
        """Generate a draft from the entire snapshot; treat transcript text as untrusted."""
        ...

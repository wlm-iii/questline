from typing import Any, Protocol

from questline.schemas import GenerationCreate, PlanContent


class Planner(Protocol):
    async def generate(self, snapshot: dict[str, Any], request: GenerationCreate) -> PlanContent:
        """Generate from the immutable request snapshot; transcript text is untrusted."""
        ...

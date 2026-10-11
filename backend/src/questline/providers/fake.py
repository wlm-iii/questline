from questline.providers.planner import QuestlinePlanner
from questline.providers.routes import EstimateRouter


class FakePlanner(QuestlinePlanner):
    """Deterministic and offline: vote-based picks and straight-line drive estimates."""

    def __init__(self) -> None:
        super().__init__(EstimateRouter())

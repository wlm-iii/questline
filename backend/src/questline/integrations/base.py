from typing import Protocol

from questline.schemas import MessageInput


class ChatAdapter(Protocol):
    async def fetch_transcript(self, external_conversation_id: str) -> list[MessageInput]:
        """Return messages accessible with the platform's consent and permissions."""
        ...

    async def post_plan_link(self, external_conversation_id: str, plan_url: str) -> None: ...

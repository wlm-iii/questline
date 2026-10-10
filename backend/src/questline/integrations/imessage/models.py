from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class ImsgMessage(BaseModel):
    """The fields of an `imsg` message row (imsg docs/json.md) that the relay uses."""

    model_config = ConfigDict(extra="ignore")

    id: int  # chat.db rowid; the watch cursor
    guid: str
    chat_id: int
    chat_guid: str | None = None
    is_group: bool = False
    sender: str = ""
    sender_name: str | None = None
    is_from_me: bool = False
    text: str | None = None
    created_at: datetime
    is_reaction: bool = False
    reaction_type: str | None = None
    is_reaction_add: bool | None = None
    reacted_to_guid: str | None = None
    thread_originator_guid: str | None = None

    @field_validator("created_at")
    @classmethod
    def assume_local_time(cls, value: datetime) -> datetime:
        # chat.db times are rendered in the relay Mac's zone when no offset is given.
        return value if value.tzinfo else value.astimezone()

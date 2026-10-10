import os
import tempfile
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field


class RelayState(BaseModel):
    """Local relay state on the relay Mac: watch cursor, chat links, and `I'm <name>` names."""

    last_rowid: int = Field(default=0, ge=0)
    chats: dict[str, UUID] = Field(default_factory=dict)  # chat_guid → trip_id
    names: dict[str, str] = Field(default_factory=dict)  # handle → name

    @classmethod
    def load(cls, path: Path) -> "RelayState":
        if not path.exists():
            return cls()
        return cls.model_validate_json(path.read_text())

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write then rename so a crash never leaves a truncated state file.
        fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        try:
            with os.fdopen(fd, "w") as file:
                file.write(self.model_dump_json(indent=2))
            os.replace(temp_name, path)
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise

import re
from dataclasses import dataclass
from typing import Literal

Preset = Literal["shoestring", "comfortable", "treat"]
PRESETS: tuple[Preset, ...] = ("shoestring", "comfortable", "treat")
_PRESET_BY_NAME: dict[str, Preset] = {preset: preset for preset in PRESETS}
MAX_NAME_CHARS = 60

_PREFIX = re.compile(r"^\s*@questline(?:\s+|$)(.*)$", re.IGNORECASE | re.DOTALL)
# Trip IDs are random URL-safe text (SPEC §9), not UUIDs.
_TRIP_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SET_NAME = re.compile(r"^i['’]m\s+(.+)$", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class Link:
    trip_id: str | None


@dataclass(frozen=True)
class Unlink:
    pass


@dataclass(frozen=True)
class Build:
    preset: Preset | None


@dataclass(frozen=True)
class Add:
    query: str


@dataclass(frozen=True)
class SetName:
    name: str


@dataclass(frozen=True)
class Help:
    pass


Command = Link | Unlink | Build | Add | SetName | Help


def parse_command(text: str) -> Command | None:
    """Return the command in a `@questline …` message, or None for ordinary chat."""
    match = _PREFIX.match(text)
    if match is None:
        return None
    rest = match.group(1).strip()
    if not rest:
        return Help()
    if name_match := _SET_NAME.match(rest):
        name = " ".join(name_match.group(1).split())
        return SetName(name) if len(name) <= MAX_NAME_CHARS else Help()
    verb, *remainder = rest.split(maxsplit=1)
    verb, argument = verb.lower(), remainder[0].strip() if remainder else ""
    if verb == "link":
        if not argument:
            return Link(None)
        return Link(argument) if _TRIP_ID.match(argument) else Help()
    if verb == "unlink" and not argument:
        return Unlink()
    if verb == "build":
        if not argument:
            return Build(None)
        preset = _PRESET_BY_NAME.get(argument.lower())
        return Build(preset) if preset else Help()
    if verb == "add" and argument:
        return Add(argument)
    return Help()

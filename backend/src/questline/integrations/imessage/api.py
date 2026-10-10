from typing import Any, Literal
from urllib.parse import quote
from uuid import UUID

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from questline.integrations.imessage.commands import Preset


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message


class NotFound(ApiError):
    pass


class Conflict(ApiError):
    pass


class Rejected(ApiError):
    """Permanent rejection (validation or size); retrying the same request won't help."""


class Unavailable(ApiError):
    """Transient: network failure or 5xx. Safe to retry later."""


class _Outgoing(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Incoming(BaseModel):
    model_config = ConfigDict(extra="ignore")


class BatchMessage(_Outgoing):
    guid: str
    handle: str
    display_name: str | None = None
    sent_at: AwareDatetime
    text: str = Field(min_length=1, max_length=10_000)
    reply_to_guid: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("display_name")
    @classmethod
    def _fit_display_name(cls, value: str | None) -> str | None:
        # The backend rejects the whole batch for a blank or >60-char name; contact names vary.
        if value is None:
            return None
        return value.strip()[:60] or None


class Reaction(_Outgoing):
    handle: str
    target_guid: str
    kind: Literal["love", "like", "dislike"]
    added: bool


class Trip(_Incoming):
    id: str
    name: str


class Generation(_Incoming):
    id: UUID
    status: Literal["queued", "running", "succeeded", "failed"]
    plan_id: UUID | None = None
    error: str | None = None


class PlanSummary(_Incoming):
    main_quests: int
    estimate: tuple[float, float] | None
    estimate_is_partial: bool

    @classmethod
    def from_content(cls, content: dict[str, Any]) -> "PlanSummary":
        nodes = content.get("graph", {}).get("nodes", [])
        main_stops = [n for n in nodes if n.get("role") == "stop" and n.get("quest") == "main"]
        estimate = content.get("per_person_estimate")
        return cls(
            main_quests=len(main_stops),
            estimate=tuple(estimate) if estimate else None,
            estimate_is_partial=bool(content.get("estimate_is_partial")),
        )


def _segment(value: str) -> str:
    return quote(value, safe="")


class QuestlineClient:
    """Typed client for the relay's slice of the SPEC §10 API (Bearer `API_TOKEN` only)."""

    def __init__(
        self,
        base_url: str,
        api_token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/api/v1",
            headers={"Authorization": f"Bearer {api_token}"},
            transport=transport,
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.TransportError as exc:
            raise Unavailable(0, "unavailable", type(exc).__name__) from exc
        if response.is_success:
            return response
        code, message = _error_details(response)
        status = response.status_code
        if status == 404:
            raise NotFound(status, code, message)
        if status == 409:
            raise Conflict(status, code, message)
        if status >= 500 or status == 429:
            raise Unavailable(status, code, message)
        raise Rejected(status, code, message)

    async def lookup_chat(self, chat_guid: str) -> str | None:
        try:
            response = await self._request("GET", f"/channels/imessage/{_segment(chat_guid)}")
        except NotFound:
            return None
        return response.json()["trip_id"]

    async def link_chat(self, trip_id: str, chat_guid: str) -> Trip:
        response = await self._request(
            "POST", f"/trips/{_segment(trip_id)}/channels/imessage", json={"chat_guid": chat_guid}
        )
        return Trip.model_validate(response.json()["trip"])

    async def unlink_chat(self, trip_id: str) -> None:
        await self._request("DELETE", f"/trips/{_segment(trip_id)}/channels/imessage")

    async def post_batch(self, trip_id: str, messages: list[BatchMessage]) -> int:
        payload = [m.model_dump(mode="json", exclude_none=True) for m in messages]
        response = await self._request(
            "POST", f"/trips/{_segment(trip_id)}/imessage/batch", json={"messages": payload}
        )
        return response.json()["inserted"]

    async def post_reactions(self, trip_id: str, reactions: list[Reaction]) -> None:
        payload = [r.model_dump(mode="json") for r in reactions]
        await self._request(
            "POST", f"/trips/{_segment(trip_id)}/imessage/reactions", json={"reactions": payload}
        )

    async def add_place(self, trip_id: str, query: str) -> str:
        response = await self._request(
            "POST", f"/trips/{_segment(trip_id)}/places", json={"query": query}
        )
        return response.json()["place"]["name"]

    async def create_generation(
        self, trip_id: str, preset: Preset | None, *, idempotency_key: str
    ) -> Generation:
        response = await self._request(
            "POST",
            f"/trips/{_segment(trip_id)}/plan-generations",
            json={"budget_preset": preset} if preset else {},
            headers={"Idempotency-Key": idempotency_key},
        )
        return Generation.model_validate(response.json()["generation"])

    async def get_generation(self, generation_id: UUID) -> Generation:
        response = await self._request("GET", f"/plan-generations/{generation_id}")
        return Generation.model_validate(response.json()["generation"])

    async def get_plan(self, plan_id: UUID) -> PlanSummary:
        response = await self._request("GET", f"/plans/{plan_id}")
        return PlanSummary.from_content(response.json()["plan"]["content"])

    async def rename_member(self, trip_id: str, handle: str, name: str) -> None:
        await self._request(
            "PATCH",
            f"/trips/{_segment(trip_id)}/imessage/members/{_segment(handle)}",
            json={"name": name},
        )


def _error_details(response: httpx.Response) -> tuple[str, str]:
    try:
        payload = response.json()
    except ValueError:
        return "http_error", response.reason_phrase
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            return str(error.get("code", "http_error")), str(error.get("message", ""))
        if "detail" in payload:
            return "http_error", str(payload["detail"])
    return "http_error", response.reason_phrase

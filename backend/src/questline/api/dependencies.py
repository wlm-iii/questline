import hashlib
import secrets
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from questline.config import Settings
from questline.models import Member

bearer = HTTPBearer(auto_error=False)


def settings_for_request(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(settings_for_request)]


async def session_for_request(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessions() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(session_for_request)]


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Access:
    def __init__(self, member: Member | None):
        self.member = member

    def check_trip(self, trip_id: UUID) -> None:
        if self.member and self.member.trip_id != trip_id:
            raise HTTPException(422, {"code": "cross_trip_reference", "message": "Wrong trip"})

    def require_service(self) -> None:
        if self.member is not None:
            raise HTTPException(403, {"code": "service_only", "message": "Service token required"})


async def access_for_request(
    settings: SettingsDep,
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    member_token: Annotated[str | None, Header(alias="X-Member-Token", max_length=200)] = None,
) -> Access:
    if credentials is not None and secrets.compare_digest(
        credentials.credentials.encode(), settings.api_token.get_secret_value().encode()
    ):
        return Access(None)
    if member_token:
        member = await session.scalar(
            select(Member).where(Member.token_hash == token_hash(member_token))
        )
        if member:
            return Access(member)
    raise HTTPException(401, "Invalid token", headers={"WWW-Authenticate": "Bearer"})


AccessDep = Annotated[Access, Depends(access_for_request)]

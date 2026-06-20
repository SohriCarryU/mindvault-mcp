from __future__ import annotations

from dataclasses import dataclass

from .config import AppConfig
from .enums import Library
from .models import Agent, Card


class AuthError(PermissionError):
    pass


@dataclass(frozen=True)
class AuthContext:
    token: str
    agent: Agent


class AuthService:
    def __init__(self, config: AppConfig):
        self._agents_by_token = {
            item.token: Agent(
                agent_id=item.agent_id,
                trust_level=item.trust_level,
                allowed_libraries=item.allowed_libraries,
            )
            for item in config.auth.agents
        }

    def authenticate(self, token: str) -> AuthContext:
        agent = self._agents_by_token.get(token)
        if agent is None:
            raise AuthError("Invalid or missing agent token.")
        return AuthContext(token=token, agent=agent)

    def require_library_access(self, ctx: AuthContext, library: Library | str) -> None:
        library_value = Library(library)
        if library_value not in ctx.agent.allowed_libraries:
            raise AuthError(f"Agent '{ctx.agent.agent_id}' is not allowed to access {library_value.value}.")

    def require_read_card(self, ctx: AuthContext, card: Card) -> None:
        self.require_library_access(ctx, card.library)
        if ctx.agent.trust_level < card.privacy_level:
            raise AuthError("Agent trust level is lower than card privacy level.")

    def require_write_library(self, ctx: AuthContext, library: Library | str) -> None:
        library_value = Library(library)
        self.require_library_access(ctx, library_value)
        if library_value == Library.STAGING and ctx.agent.trust_level < 3:
            raise AuthError("Writing staging requires trust level >= 3.")
        if library_value == Library.PRIMARY and ctx.agent.trust_level < 8:
            raise AuthError("Writing primary requires trust level >= 8.")

    def require_approve(self, ctx: AuthContext) -> None:
        if ctx.agent.trust_level < 8:
            raise AuthError("Approving cards requires trust level >= 8.")
        self.require_library_access(ctx, Library.PRIMARY)
        self.require_library_access(ctx, Library.STAGING)

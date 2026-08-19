from __future__ import annotations

from dataclasses import dataclass

from app.config.settings import Settings
from database import (
    delete_vexmod_role_transfer,
    upsert_vexmod_role_transfer,
    vexmod_role_transfers_available,
)


@dataclass(slots=True)
class VerificationIntegration:
    db: object
    settings: Settings

    @property
    def enabled(self) -> bool:
        return self.settings.verification_integration == "postgres"

    async def health(self) -> tuple[bool, str]:
        if not self.enabled:
            return True, "disabled"

        available = await vexmod_role_transfers_available(
            self.db,
            self.settings.vexmod_roles_schema,
        )

        return available, "postgres" if available else "missing_table"

    async def register_transfer(
        self,
        guild_id: int,
        onboarding_role_id: int,
        verified_role_id: int,
        name: str,
        configured_by: int,
    ) -> None:
        if not self.enabled:
            return

        await upsert_vexmod_role_transfer(
            self.db,
            self.settings.vexmod_roles_schema,
            guild_id,
            onboarding_role_id,
            verified_role_id,
            name,
            configured_by,
        )

    async def remove_transfer(
        self,
        guild_id: int,
        onboarding_role_id: int,
    ) -> bool:
        if not self.enabled:
            return True

        return await delete_vexmod_role_transfer(
            self.db,
            self.settings.vexmod_roles_schema,
            guild_id,
            onboarding_role_id,
        )

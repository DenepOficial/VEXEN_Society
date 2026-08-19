from __future__ import annotations

import logging
import re
from functools import lru_cache

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("vexen_society.settings")
_SCHEMA_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")


class Settings(BaseSettings):
    discord_token: str = ""
    guild_id: int | None = None
    owner_id: int | None = None
    allowed_roles: str = ""

    database_url: str = ""
    society_db_schema: str = "vexen_society"

    verification_integration: str = "disabled"
    vexmod_roles_schema: str = "vexmod_temp_roles"

    sync_commands: bool = True
    log_level: str = "INFO"

    @field_validator("guild_id", "owner_id", mode="before")
    @classmethod
    def parse_optional_positive_id(
        cls, value: object, info: ValidationInfo
    ) -> int | None:
        if value is None or value == "":
            return None
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            log.warning("%s inválido; se tratará como no configurado.", info.field_name.upper())
            return None
        if parsed <= 0:
            log.warning("%s inválido; se tratará como no configurado.", info.field_name.upper())
            return None
        return parsed

    @field_validator("society_db_schema", "vexmod_roles_schema")
    @classmethod
    def validate_schema_name(cls, value: str) -> str:
        value = value.strip()
        if not _SCHEMA_PATTERN.fullmatch(value):
            raise ValueError("Schema PostgreSQL inválido.")
        return value

    @field_validator("verification_integration")
    @classmethod
    def validate_verification_integration(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"postgres", "disabled"}:
            raise ValueError("VERIFICATION_INTEGRATION debe ser 'postgres' o 'disabled'.")
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL inválido.")
        return value

    @property
    def allowed_role_ids(self) -> set[int]:
        result: set[int] = set()
        for raw in self.allowed_roles.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                role_id = int(raw)
            except ValueError:
                log.warning("Se ignoró un valor no numérico en ALLOWED_ROLES.")
                continue
            if role_id > 0:
                result.add(role_id)
        return result

    @property
    def development_mode(self) -> bool:
        return self.society_db_schema.endswith("_dev")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

from __future__ import annotations

from dataclasses import dataclass, field
import logging

import discord

from app.config.settings import Settings
from app.society.identity import parse_society_display_identity
from database import (
    get_onboarding_prompt_config,
    list_associates,
    set_onboarding_prompt_config,
)

log = logging.getLogger("vexen_society.onboarding")
MAX_PROMPT_OPTIONS = 50


class OnboardingIntegrationError(RuntimeError):
    pass


@dataclass(slots=True)
class OnboardingSyncReport:
    configured: bool = False
    prompt_title: str | None = None
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    conflicts: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OnboardingIntegration:
    db: object
    settings: Settings

    @staticmethod
    def _ensure_supported() -> None:
        if not hasattr(discord.Guild, "onboarding") or not hasattr(
            discord.Guild,
            "edit_onboarding",
        ):
            raise OnboardingIntegrationError(
                "La incorporación automática requiere discord.py 2.6 o superior."
            )

    @staticmethod
    def _identity(display_name: str):
        identity = parse_society_display_identity(display_name)
        if not identity.text:
            raise OnboardingIntegrationError(
                "El nombre del asociado necesita texto además del emoji."
            )
        return identity

    @staticmethod
    def _emoji_matches(current, desired_markup: str | None) -> bool:
        # Si el nombre no define emoji personalizado, conservamos cualquier
        # emoji existente que haya sido configurado manualmente.
        if desired_markup is None:
            return True

        if current is None:
            return False

        desired = discord.PartialEmoji.from_str(desired_markup)
        desired_id = getattr(desired, "id", None)
        current_id = getattr(current, "id", None)

        if desired_id is not None:
            return current_id == desired_id

        return str(current) == str(desired)

    async def list_prompts(self, guild: discord.Guild):
        self._ensure_supported()
        onboarding = await guild.onboarding()
        return onboarding.prompts

    async def _config(self, guild_id: int):
        return await get_onboarding_prompt_config(
            self.db,
            self.settings.society_db_schema,
            guild_id,
        )

    @staticmethod
    def _find_prompt_by_identifier(onboarding, identifier: str):
        value = identifier.strip()
        if value.isdigit():
            wanted = int(value)
            for index, prompt in enumerate(onboarding.prompts):
                if prompt.id == wanted:
                    return index, prompt

        folded = value.casefold()
        exact = [
            (index, prompt)
            for index, prompt in enumerate(onboarding.prompts)
            if prompt.title.strip().casefold() == folded
        ]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            raise OnboardingIntegrationError(
                "Hay varias preguntas con ese mismo título; selecciónala desde el autocompletado."
            )
        raise OnboardingIntegrationError(
            "No encontré esa pregunta en la incorporación actual de Discord."
        )

    async def _resolve_configured_prompt(self, guild: discord.Guild, onboarding, active_rows=None):
        config = await self._config(guild.id)
        if not config or not config["onboarding_prompt_id"]:
            return None, None, None

        prompt_id = int(config["onboarding_prompt_id"])
        prompt_title = str(config["onboarding_prompt_title"] or "").strip()

        for index, prompt in enumerate(onboarding.prompts):
            if prompt.id == prompt_id:
                return index, prompt, config

        if prompt_title:
            matches = [
                (index, prompt)
                for index, prompt in enumerate(onboarding.prompts)
                if prompt.title.strip().casefold() == prompt_title.casefold()
            ]
            if len(matches) == 1:
                return matches[0][0], matches[0][1], config

        # Si Discord regeneró IDs o el administrador renombró la pregunta,
        # intentamos reconocerla por los roles INT administrados por Society.
        if active_rows:
            int_roles = {
                int(row["integration_role_id"])
                for row in active_rows
                if row["integration_role_id"]
            }
            candidates = []
            for index, prompt in enumerate(onboarding.prompts):
                if any(option.role_ids & int_roles for option in prompt.options):
                    candidates.append((index, prompt))
            if len(candidates) == 1:
                return candidates[0][0], candidates[0][1], config

        raise OnboardingIntegrationError(
            "La pregunta configurada ya no se encuentra. Ejecuta `/society config incorporacion` nuevamente."
        )

    @staticmethod
    def _clone_option(
        option,
        *,
        title: str | None = None,
        roles=None,
        emoji_marker="__KEEP__",
    ):
        kwargs = {
            "title": title if title is not None else option.title,
            "description": option.description,
            "channels": list(option.channel_ids),
            "roles": list(option.role_ids if roles is None else roles),
        }

        if emoji_marker == "__KEEP__":
            if option.emoji is not None:
                kwargs["emoji"] = option.emoji
        elif emoji_marker is not None:
            kwargs["emoji"] = emoji_marker

        return discord.OnboardingPromptOption(**kwargs)

    @staticmethod
    def _clone_prompt(prompt, options):
        return discord.OnboardingPrompt(
            type=prompt.type,
            title=prompt.title,
            options=list(options),
            single_select=prompt.single_select,
            required=prompt.required,
            in_onboarding=prompt.in_onboarding,
        )

    async def _edit_target_prompt(
        self,
        guild: discord.Guild,
        onboarding,
        target_index: int,
        options,
        actor_id: int,
        reason: str,
    ):
        prompts = list(onboarding.prompts)
        prompts[target_index] = self._clone_prompt(
            prompts[target_index],
            options,
        )
        updated = await guild.edit_onboarding(
            prompts=prompts,
            reason=reason,
        )
        if target_index >= len(updated.prompts):
            raise OnboardingIntegrationError(
                "Discord devolvió una incorporación inesperada después de actualizarla."
            )
        updated_prompt = updated.prompts[target_index]
        await set_onboarding_prompt_config(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            updated_prompt.id,
            updated_prompt.title,
            actor_id,
        )
        return updated_prompt

    async def configure_and_sync(
        self,
        guild: discord.Guild,
        prompt_identifier: str,
        actor_id: int,
    ) -> OnboardingSyncReport:
        self._ensure_supported()
        onboarding = await guild.onboarding()
        target_index, target = self._find_prompt_by_identifier(
            onboarding,
            prompt_identifier,
        )
        await set_onboarding_prompt_config(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            target.id,
            target.title,
            actor_id,
        )
        return await self.sync_all(
            guild,
            actor_id,
            onboarding=onboarding,
            target_index=target_index,
            target=target,
        )

    async def sync_all(
        self,
        guild: discord.Guild,
        actor_id: int,
        *,
        onboarding=None,
        target_index=None,
        target=None,
    ) -> OnboardingSyncReport:
        self._ensure_supported()
        rows = [
            row
            for row in await list_associates(
                self.db,
                self.settings.society_db_schema,
                guild.id,
            )
            if row["status"] == "active" and row["integration_role_id"]
        ]

        if onboarding is None:
            onboarding = await guild.onboarding()

        if target is None or target_index is None:
            target_index, target, config = await self._resolve_configured_prompt(
                guild,
                onboarding,
                rows,
            )
            if target is None:
                return OnboardingSyncReport(configured=False)

        report = OnboardingSyncReport(
            configured=True,
            prompt_title=target.title,
        )

        by_int_role = {
            int(row["integration_role_id"]): row
            for row in rows
            if row["integration_role_id"]
        }
        by_community_role = {
            int(row["community_role_id"]): row
            for row in rows
            if row["community_role_id"]
        }
        found_users: set[int] = set()
        new_options = []
        changed = False

        for option in target.options:
            int_matches = option.role_ids & set(by_int_role)
            if len(int_matches) == 1:
                int_role_id = next(iter(int_matches))
                row = by_int_role[int_role_id]
                found_users.add(int(row["user_id"]))
                identity = self._identity(
                    str(row["display_name"])
                )
                wanted_title = identity.text
                title_changed = option.title != wanted_title
                emoji_changed = not self._emoji_matches(
                    option.emoji,
                    identity.custom_emoji,
                )

                if title_changed or emoji_changed:
                    new_options.append(
                        self._clone_option(
                            option,
                            title=wanted_title,
                            emoji_marker=(
                                identity.custom_emoji
                                if identity.custom_emoji is not None
                                else "__KEEP__"
                            ),
                        )
                    )
                    report.updated += 1
                    changed = True
                else:
                    new_options.append(option)
                    report.unchanged += 1
                continue

            # Migración segura de una opción manual antigua: si el título
            # corresponde a este asociado/comunidad y entregaba su rol final,
            # sustituimos solo ese rol final por INT-Comunidad.
            migrated = False
            community_matches = option.role_ids & set(by_community_role)
            if len(community_matches) == 1:
                community_role_id = next(iter(community_matches))
                row = by_community_role[community_role_id]
                identity = self._identity(
                    str(row["display_name"])
                )
                aliases = {
                    identity.text.casefold(),
                    str(row["community_name"]).strip().casefold(),
                }
                if option.title.strip().casefold() in aliases:
                    int_role_id = int(row["integration_role_id"])
                    roles = set(option.role_ids)
                    roles.discard(community_role_id)
                    roles.add(int_role_id)
                    new_options.append(
                        self._clone_option(
                            option,
                            title=identity.text,
                            roles=roles,
                            emoji_marker=(
                                identity.custom_emoji
                                if identity.custom_emoji is not None
                                else "__KEEP__"
                            ),
                        )
                    )
                    found_users.add(int(row["user_id"]))
                    report.updated += 1
                    changed = True
                    migrated = True
            if migrated:
                continue

            new_options.append(option)

        occupied_titles = {
            option.title.strip().casefold()
            for option in new_options
        }

        for row in rows:
            user_id = int(row["user_id"])
            if user_id in found_users:
                continue

            identity = self._identity(
                str(row["display_name"])
            )
            title = identity.text
            folded = title.casefold()
            if folded in occupied_titles:
                report.conflicts.append(
                    f"{title}: ya existe una respuesta con ese nombre y no pertenece a su rol INT."
                )
                continue

            if len(new_options) >= MAX_PROMPT_OPTIONS:
                report.conflicts.append(
                    f"{title}: la pregunta ya alcanzó el límite de {MAX_PROMPT_OPTIONS} respuestas."
                )
                continue

            option_kwargs = {
                "title": title,
                "roles": [int(row["integration_role_id"])],
            }
            if identity.custom_emoji is not None:
                option_kwargs["emoji"] = identity.custom_emoji

            new_options.append(
                discord.OnboardingPromptOption(
                    **option_kwargs
                )
            )
            occupied_titles.add(folded)
            found_users.add(user_id)
            report.added += 1
            changed = True

        if changed:
            updated_prompt = await self._edit_target_prompt(
                guild,
                onboarding,
                target_index,
                new_options,
                actor_id,
                "VEXEN Society: sincronizar asociados en incorporación",
            )
            report.prompt_title = updated_prompt.title
        else:
            await set_onboarding_prompt_config(
                self.db,
                self.settings.society_db_schema,
                guild.id,
                target.id,
                target.title,
                actor_id,
            )

        return report

    async def upsert_associate_option(
        self,
        guild: discord.Guild,
        *,
        associate_user_id: int,
        display_name: str,
        community_name: str,
        integration_role_id: int,
        actor_id: int,
    ) -> str:
        self._ensure_supported()
        config = await self._config(guild.id)
        if not config or not config["onboarding_prompt_id"]:
            return "not_configured"

        rows = await list_associates(
            self.db,
            self.settings.society_db_schema,
            guild.id,
        )
        onboarding = await guild.onboarding()
        target_index, target, _ = await self._resolve_configured_prompt(
            guild,
            onboarding,
            rows,
        )

        identity = self._identity(display_name)
        title = identity.text
        options = list(target.options)

        for index, option in enumerate(options):
            if integration_role_id in option.role_ids:
                title_ok = option.title == title
                emoji_ok = self._emoji_matches(
                    option.emoji,
                    identity.custom_emoji,
                )

                if title_ok and emoji_ok:
                    await set_onboarding_prompt_config(
                        self.db,
                        self.settings.society_db_schema,
                        guild.id,
                        target.id,
                        target.title,
                        actor_id,
                    )
                    return "already"

                options[index] = self._clone_option(
                    option,
                    title=title,
                    emoji_marker=(
                        identity.custom_emoji
                        if identity.custom_emoji is not None
                        else "__KEEP__"
                    ),
                )
                updated_prompt = await self._edit_target_prompt(
                    guild,
                    onboarding,
                    target_index,
                    options,
                    actor_id,
                    f"VEXEN Society: actualizar incorporación de {community_name}",
                )

                if not any(
                    integration_role_id in candidate.role_ids
                    and candidate.title == title
                    for candidate in updated_prompt.options
                ):
                    raise OnboardingIntegrationError(
                        "Discord no confirmó la actualización de la opción de incorporación."
                    )

                return "updated"

        if any(option.title.strip().casefold() == title.casefold() for option in options):
            raise OnboardingIntegrationError(
                f"Ya existe una respuesta llamada `{title}` en esa pregunta. No la sobrescribí."
            )

        if len(options) >= MAX_PROMPT_OPTIONS:
            raise OnboardingIntegrationError(
                f"La pregunta ya alcanzó el límite de {MAX_PROMPT_OPTIONS} respuestas."
            )

        option_kwargs = {
            "title": title,
            "roles": [integration_role_id],
        }
        if identity.custom_emoji is not None:
            option_kwargs["emoji"] = identity.custom_emoji

        options.append(
            discord.OnboardingPromptOption(
                **option_kwargs
            )
        )
        updated_prompt = await self._edit_target_prompt(
            guild,
            onboarding,
            target_index,
            options,
            actor_id,
            f"VEXEN Society: agregar {title} a incorporación",
        )

        if not any(
            integration_role_id in candidate.role_ids
            and candidate.title == title
            for candidate in updated_prompt.options
        ):
            raise OnboardingIntegrationError(
                "Discord no confirmó la creación de la opción de incorporación."
            )

        return "added"

    async def remove_associate_option(
        self,
        guild: discord.Guild,
        *,
        integration_role_id: int,
        community_name: str,
        actor_id: int,
    ) -> str:
        self._ensure_supported()
        config = await self._config(guild.id)
        if not config or not config["onboarding_prompt_id"]:
            return "not_configured"

        rows = await list_associates(
            self.db,
            self.settings.society_db_schema,
            guild.id,
        )
        onboarding = await guild.onboarding()
        target_index, target, _ = await self._resolve_configured_prompt(
            guild,
            onboarding,
            rows,
        )

        options = [
            option
            for option in target.options
            if integration_role_id not in option.role_ids
        ]
        if len(options) == len(target.options):
            return "missing"

        updated_prompt = await self._edit_target_prompt(
            guild,
            onboarding,
            target_index,
            options,
            actor_id,
            f"VEXEN Society: retirar {community_name} de incorporación",
        )

        if any(
            integration_role_id in option.role_ids
            for option in updated_prompt.options
        ):
            raise OnboardingIntegrationError(
                "Discord no confirmó la eliminación de la opción de incorporación."
            )

        return "removed"

    async def status(self, guild: discord.Guild) -> dict:
        config = await self._config(guild.id)
        if not config or not config["onboarding_prompt_id"]:
            return {
                "configured": False,
                "prompt_title": None,
                "prompt_found": False,
                "managed_options": 0,
                "active_societies": 0,
                "error": None,
            }

        rows = [
            row
            for row in await list_associates(
                self.db,
                self.settings.society_db_schema,
                guild.id,
            )
            if row["status"] == "active" and row["integration_role_id"]
        ]

        try:
            self._ensure_supported()
            onboarding = await guild.onboarding()
            _, prompt, _ = await self._resolve_configured_prompt(
                guild,
                onboarding,
                rows,
            )
            int_roles = {
                int(row["integration_role_id"])
                for row in rows
                if row["integration_role_id"]
            }
            managed = sum(
                1
                for option in prompt.options
                if option.role_ids & int_roles
            )
            return {
                "configured": True,
                "prompt_title": prompt.title,
                "prompt_found": True,
                "managed_options": managed,
                "active_societies": len(rows),
                "error": None,
            }
        except Exception as exc:
            return {
                "configured": True,
                "prompt_title": str(config["onboarding_prompt_title"] or ""),
                "prompt_found": False,
                "managed_options": 0,
                "active_societies": len(rows),
                "error": f"{type(exc).__name__}: {str(exc)[:180]}",
            }

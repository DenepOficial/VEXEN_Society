from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import discord

from app.config.settings import Settings
from app.integrations.verification import VerificationIntegration
from app.society.permissions import (
    apply_staff_only,
    base_category_overwrites,
)
from app.society.template_parser import ParsedTemplate, render_category_name
from app.society.templates import template_from_row
from app.society.welcome import (
    disable_welcome_button,
    publish_welcome,
)
from database import (
    add_audit_log,
    delete_associate_channel_record,
    delete_associate_record,
    get_active_template,
    get_associate,
    get_base_category,
    get_associate_channel,
    get_associate_space,
    list_associate_channels,
    save_associate_channel,
    save_associate_space,
    set_associate_space_status,
    update_associate_community_role,
)

log = logging.getLogger("vexen_society.spaces")


class SocietySpaceError(RuntimeError):
    pass


@dataclass(slots=True)
class DeleteReport:
    deleted: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.errors


class SpaceService:
    def __init__(self, bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings
        self._locks: dict[tuple[int, int], asyncio.Lock] = {}

    @property
    def db(self):
        if self.bot.db is None:
            raise SocietySpaceError("PostgreSQL no está disponible.")
        return self.bot.db

    def _lock(self, guild_id: int, user_id: int) -> asyncio.Lock:
        return self._locks.setdefault(
            (guild_id, user_id),
            asyncio.Lock(),
        )

    async def create_space(
        self,
        guild: discord.Guild,
        associate_user_id: int,
        actor_id: int,
    ) -> dict:
        async with self._lock(guild.id, associate_user_id):
            associate_row = await get_associate(
                self.db,
                self.settings.society_db_schema,
                guild.id,
                associate_user_id,
            )

            if associate_row is None:
                raise SocietySpaceError(
                    "El asociado no está registrado."
                )

            existing = await get_associate_space(
                self.db,
                self.settings.society_db_schema,
                guild.id,
                associate_user_id,
            )

            if (
                existing is not None
                and existing["status"] == "active"
            ):
                raise SocietySpaceError(
                    "Este asociado ya tiene un espacio Society activo."
                )

            member = guild.get_member(associate_user_id)

            if member is None:
                try:
                    member = await guild.fetch_member(
                        associate_user_id
                    )
                except discord.HTTPException as exc:
                    raise SocietySpaceError(
                        "El asociado no está disponible en el servidor."
                    ) from exc

            template_row = await get_active_template(
                self.db,
                self.settings.society_db_schema,
                guild.id,
            )

            if template_row is None:
                raise SocietySpaceError(
                    "No existe una plantilla activa."
                )

            parsed = template_from_row(template_row)

            display_name = associate_row["display_name"].strip()
            community_name = associate_row["community_name"].strip()

            self._validate_names(community_name)

            final_category_name = render_category_name(
                parsed,
                display_name,
                community_name,
            )

            role_names = {
                "community": community_name,
                "integration": f"INT-{community_name}",
                "staff": f"Staff-{community_name}",
            }

            existing_role_names = {
                role.name.casefold()
                for role in guild.roles
            }

            collisions = [
                name
                for name in role_names.values()
                if name.casefold() in existing_role_names
            ]

            if collisions:
                raise SocietySpaceError(
                    "Ya existe uno de los roles requeridos: "
                    + ", ".join(collisions)
                )

            if any(
                category.name.casefold()
                == final_category_name.casefold()
                for category in guild.categories
            ):
                raise SocietySpaceError(
                    "Ya existe una categoría con el nombre final."
                )

            created_roles: list[discord.Role] = []
            created_channels: list[
                discord.abc.GuildChannel
            ] = []

            category: discord.CategoryChannel | None = None

            await save_associate_space(
                self.db,
                self.settings.society_db_schema,
                guild.id,
                associate_user_id,
                template_id=template_row["template_id"],
                template_version=template_row["version"],
                status="creating",
            )

            try:
                community_role = await guild.create_role(
                    name=role_names["community"],
                    reason=(
                        "VEXEN Society: rol de comunidad "
                        f"{community_name}"
                    ),
                )
                created_roles.append(community_role)

                integration_role = await guild.create_role(
                    name=role_names["integration"],
                    reason=(
                        "VEXEN Society: rol temporal "
                        f"{community_name}"
                    ),
                )
                created_roles.append(integration_role)

                staff_role = await guild.create_role(
                    name=role_names["staff"],
                    colour=community_role.colour,
                    reason=(
                        "VEXEN Society: Staff "
                        f"{community_name}"
                    ),
                )
                created_roles.append(staff_role)

                await self._order_society_roles(
                    guild,
                    staff_role,
                    community_role,
                    integration_role,
                )

                overwrites = base_category_overwrites(
                    guild,
                    member,
                    community_role,
                    staff_role,
                )

                category = await guild.create_category(
                    final_category_name,
                    overwrites=overwrites,
                    reason=(
                        "VEXEN Society: espacio "
                        f"{community_name}"
                    ),
                )

                await self._place_society_category(
                    guild,
                    category,
                )

                await save_associate_space(
                    self.db,
                    self.settings.society_db_schema,
                    guild.id,
                    associate_user_id,
                    category_id=category.id,
                    community_role_id=community_role.id,
                    integration_role_id=integration_role.id,
                    staff_role_id=staff_role.id,
                    template_id=template_row["template_id"],
                    template_version=template_row["version"],
                    status="creating",
                )

                await update_associate_community_role(
                    self.db,
                    self.settings.society_db_schema,
                    guild.id,
                    associate_user_id,
                    community_role.id,
                )

                for definition in parsed.channels:
                    channel = await self._create_channel_from_definition(
                        guild,
                        category,
                        definition.channel_type,
                        definition.name,
                        community_role,
                        staff_role,
                    )

                    created_channels.append(channel)

                    await save_associate_channel(
                        self.db,
                        self.settings.society_db_schema,
                        guild.id,
                        associate_user_id,
                        channel.id,
                        definition.channel_key,
                        definition.channel_type,
                        is_template=True,
                    )

                await self._reorder_template_channels(
                    guild,
                    category,
                    associate_user_id,
                    parsed,
                )

                verification = VerificationIntegration(
                    self.db,
                    self.settings,
                )

                await verification.register_transfer(
                    guild.id,
                    integration_role.id,
                    community_role.id,
                    community_name,
                    actor_id,
                )

                await save_associate_space(
                    self.db,
                    self.settings.society_db_schema,
                    guild.id,
                    associate_user_id,
                    category_id=category.id,
                    community_role_id=community_role.id,
                    integration_role_id=integration_role.id,
                    staff_role_id=staff_role.id,
                    template_id=template_row["template_id"],
                    template_version=template_row["version"],
                    status="active",
                )

                onboarding_state = "not_configured"
                onboarding_error = None
                if self.bot.onboarding_integration is not None:
                    try:
                        onboarding_state = (
                            await self.bot.onboarding_integration.upsert_associate_option(
                                guild,
                                associate_user_id=associate_user_id,
                                display_name=display_name,
                                community_name=community_name,
                                integration_role_id=integration_role.id,
                                actor_id=actor_id,
                            )
                        )
                    except Exception as exc:
                        log.exception(
                            "La Society se creó, pero no se pudo sincronizar la incorporación."
                        )
                        onboarding_error = (
                            f"{type(exc).__name__}: {str(exc)[:300]}"
                        )

                await add_audit_log(
                    self.db,
                    self.settings.society_db_schema,
                    guild.id,
                    "SOCIETY_CREATED",
                    actor_id,
                    associate_user_id,
                    community_name,
                    {
                        "category_id": category.id,
                        "community_role_id": community_role.id,
                        "integration_role_id": integration_role.id,
                        "staff_role_id": staff_role.id,
                        "template_version": template_row["version"],
                        "onboarding_state": onboarding_state,
                        "onboarding_error": onboarding_error,
                    },
                )

                welcome_message, welcome_error = await publish_welcome(
                    self.bot,
                    self.settings,
                    guild,
                    associate_user_id,
                    display_name,
                    community_name,
                    community_role.id,
                    actor_id,
                )

                return {
                    "category": category,
                    "community_role": community_role,
                    "integration_role": integration_role,
                    "staff_role": staff_role,
                    "channels": tuple(created_channels),
                    "template_version": template_row["version"],
                    "welcome_message": welcome_message,
                    "welcome_error": welcome_error,
                    "onboarding_state": onboarding_state,
                    "onboarding_error": onboarding_error,
                }

            except Exception:
                log.exception(
                    "Falló la creación de Society; ejecutando rollback."
                )

                for channel in reversed(created_channels):
                    try:
                        await channel.delete(
                            reason="Rollback VEXEN Society"
                        )
                    except (
                        discord.NotFound,
                        discord.Forbidden,
                        discord.HTTPException,
                    ):
                        pass

                if category is not None:
                    try:
                        await category.delete(
                            reason="Rollback VEXEN Society"
                        )
                    except (
                        discord.NotFound,
                        discord.Forbidden,
                        discord.HTTPException,
                    ):
                        pass

                for role in reversed(created_roles):
                    try:
                        await role.delete(
                            reason="Rollback VEXEN Society"
                        )
                    except (
                        discord.NotFound,
                        discord.Forbidden,
                        discord.HTTPException,
                    ):
                        pass

                try:
                    await set_associate_space_status(
                        self.db,
                        self.settings.society_db_schema,
                        guild.id,
                        associate_user_id,
                        "error",
                    )
                except Exception:
                    pass

                raise

    async def delete_space(
        self,
        guild: discord.Guild,
        associate_user_id: int,
        actor_id: int,
    ) -> DeleteReport:
        async with self._lock(guild.id, associate_user_id):
            associate = await get_associate(
                self.db,
                self.settings.society_db_schema,
                guild.id,
                associate_user_id,
            )

            if associate is None:
                raise SocietySpaceError(
                    "El asociado no está registrado."
                )

            space = await get_associate_space(
                self.db,
                self.settings.society_db_schema,
                guild.id,
                associate_user_id,
            )

            if space is None:
                raise SocietySpaceError(
                    "El asociado no tiene un espacio Society registrado."
                )

            report = DeleteReport()

            await set_associate_space_status(
                self.db,
                self.settings.society_db_schema,
                guild.id,
                associate_user_id,
                "deleting",
            )

            await add_audit_log(
                self.db,
                self.settings.society_db_schema,
                guild.id,
                "SOCIETY_DELETE_REQUESTED",
                actor_id,
                associate_user_id,
                associate["community_name"],
                {
                    "category_id": space["category_id"],
                    "community_role_id": space["community_role_id"],
                    "integration_role_id": space["integration_role_id"],
                    "staff_role_id": space["staff_role_id"],
                },
            )

            await disable_welcome_button(
                self.bot,
                self.settings,
                guild,
                space,
                associate["community_name"],
            )

            integration_role_id = space[
                "integration_role_id"
            ]

            onboarding_delete_failed = False

            if integration_role_id and self.bot.onboarding_integration is not None:
                try:
                    onboarding_state = (
                        await self.bot.onboarding_integration.remove_associate_option(
                            guild,
                            integration_role_id=integration_role_id,
                            community_name=associate["community_name"],
                            actor_id=actor_id,
                        )
                    )
                    if onboarding_state == "removed":
                        report.deleted.append("Opción de incorporación")
                    elif onboarding_state == "missing":
                        report.missing.append("Opción de incorporación")
                except Exception as exc:
                    onboarding_delete_failed = True
                    report.errors.append(
                        "Incorporación: "
                        f"{type(exc).__name__}"
                    )

            # Si no podemos retirar la opción que referencia INT-Comunidad,
            # detenemos la eliminación para no dejar Onboarding apuntando
            # a un rol que ya no existe.
            if onboarding_delete_failed:
                await set_associate_space_status(
                    self.db,
                    self.settings.society_db_schema,
                    guild.id,
                    associate_user_id,
                    "error",
                )
                await add_audit_log(
                    self.db,
                    self.settings.society_db_schema,
                    guild.id,
                    "SOCIETY_DELETE_BLOCKED_ONBOARDING",
                    actor_id,
                    associate_user_id,
                    associate["community_name"],
                    {
                        "integration_role_id": integration_role_id,
                        "errors": report.errors,
                    },
                )
                return report

            if integration_role_id:
                try:
                    verification = VerificationIntegration(
                        self.db,
                        self.settings,
                    )
                    await verification.remove_transfer(
                        guild.id,
                        integration_role_id,
                    )
                    report.deleted.append(
                        "Mapping VEXMOD"
                    )
                except Exception as exc:
                    report.errors.append(
                        "Mapping VEXMOD: "
                        f"{type(exc).__name__}"
                    )

            category = (
                guild.get_channel(space["category_id"])
                if space["category_id"]
                else None
            )

            channels_to_delete: dict[
                int,
                discord.abc.GuildChannel,
            ] = {}

            if isinstance(
                category,
                discord.CategoryChannel,
            ):
                for channel in category.channels:
                    channels_to_delete[
                        channel.id
                    ] = channel
            elif space["category_id"]:
                report.missing.append("Categoría")

            rows = await list_associate_channels(
                self.db,
                self.settings.society_db_schema,
                guild.id,
                associate_user_id,
            )

            for row in rows:
                channel = guild.get_channel(
                    row["channel_id"]
                )
                if channel is not None:
                    channels_to_delete[
                        channel.id
                    ] = channel

            for channel in list(
                channels_to_delete.values()
            ):
                try:
                    await channel.delete(
                        reason=(
                            "Eliminar VEXEN Society "
                            f"{associate['community_name']}"
                        )
                    )
                    report.deleted.append(
                        f"Canal {channel.name}"
                    )
                except discord.NotFound:
                    report.missing.append(
                        f"Canal {channel.id}"
                    )
                except (
                    discord.Forbidden,
                    discord.HTTPException,
                ) as exc:
                    report.errors.append(
                        f"Canal {channel.name}: "
                        f"{type(exc).__name__}"
                    )

            if isinstance(
                category,
                discord.CategoryChannel,
            ):
                try:
                    await category.delete(
                        reason=(
                            "Eliminar VEXEN Society "
                            f"{associate['community_name']}"
                        )
                    )
                    report.deleted.append(
                        "Categoría"
                    )
                except discord.NotFound:
                    report.missing.append(
                        "Categoría"
                    )
                except (
                    discord.Forbidden,
                    discord.HTTPException,
                ) as exc:
                    report.errors.append(
                        "Categoría: "
                        f"{type(exc).__name__}"
                    )

            role_specs = [
                ("Staff", space["staff_role_id"]),
                ("INT", space["integration_role_id"]),
                (
                    "Comunidad",
                    space["community_role_id"],
                ),
            ]

            for label, role_id in role_specs:
                if not role_id:
                    report.missing.append(
                        f"Rol {label}"
                    )
                    continue

                role = guild.get_role(role_id)

                if role is None:
                    report.missing.append(
                        f"Rol {label}"
                    )
                    continue

                try:
                    await role.delete(
                        reason=(
                            "Eliminar VEXEN Society "
                            f"{associate['community_name']}"
                        )
                    )
                    report.deleted.append(
                        f"Rol {label}"
                    )
                except discord.NotFound:
                    report.missing.append(
                        f"Rol {label}"
                    )
                except (
                    discord.Forbidden,
                    discord.HTTPException,
                ) as exc:
                    report.errors.append(
                        f"Rol {label}: "
                        f"{type(exc).__name__}"
                    )

            if report.complete:
                await delete_associate_record(
                    self.db,
                    self.settings.society_db_schema,
                    guild.id,
                    associate_user_id,
                )

                await add_audit_log(
                    self.db,
                    self.settings.society_db_schema,
                    guild.id,
                    "SOCIETY_DELETED",
                    actor_id,
                    associate_user_id,
                    associate["community_name"],
                    {
                        "deleted": report.deleted,
                        "missing": report.missing,
                    },
                )
            else:
                await set_associate_space_status(
                    self.db,
                    self.settings.society_db_schema,
                    guild.id,
                    associate_user_id,
                    "error",
                )

                await add_audit_log(
                    self.db,
                    self.settings.society_db_schema,
                    guild.id,
                    "SOCIETY_DELETE_PARTIAL",
                    actor_id,
                    associate_user_id,
                    associate["community_name"],
                    {
                        "deleted": report.deleted,
                        "missing": report.missing,
                        "errors": report.errors,
                    },
                )

            return report

    async def create_custom_channel(
        self,
        guild: discord.Guild,
        associate_user_id: int,
        actor_id: int,
        channel_type: str,
        name: str,
    ) -> discord.abc.GuildChannel:
        channel_type = channel_type.upper()

        if channel_type not in {
            "TXT",
            "STAFF-TXT",
            "VOICE",
            "STAFF-VOICE",
        }:
            raise SocietySpaceError(
                "Tipo de canal personalizado no válido."
            )

        name = name.strip()

        if not name or len(name) > 100:
            raise SocietySpaceError(
                "Nombre de canal inválido."
            )

        space = await get_associate_space(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            associate_user_id,
        )

        if (
            space is None
            or space["status"] != "active"
        ):
            raise SocietySpaceError(
                "La Society no está activa."
            )

        category = guild.get_channel(
            space["category_id"]
        )
        community_role = guild.get_role(
            space["community_role_id"]
        )
        staff_role = guild.get_role(
            space["staff_role_id"]
        )

        if (
            not isinstance(
                category,
                discord.CategoryChannel,
            )
            or community_role is None
            or staff_role is None
        ):
            raise SocietySpaceError(
                "La configuración de Discord está incompleta."
            )

        channel = await self._create_channel_from_definition(
            guild,
            category,
            channel_type,
            name,
            community_role,
            staff_role,
        )

        await save_associate_channel(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            associate_user_id,
            channel.id,
            f"custom_{channel.id}",
            channel_type,
            is_template=False,
        )

        await add_audit_log(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            "CUSTOM_CHANNEL_CREATED",
            actor_id,
            associate_user_id,
            metadata={
                "channel_id": channel.id,
                "type": channel_type,
                "name": name,
            },
        )

        return channel

    async def rename_category(
        self,
        guild: discord.Guild,
        associate_user_id: int,
        actor_id: int,
        new_name: str,
    ) -> None:
        new_name = new_name.strip()

        if not new_name or len(new_name) > 100:
            raise SocietySpaceError(
                "Nombre de categoría inválido."
            )

        space = await get_associate_space(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            associate_user_id,
        )

        if space is None:
            raise SocietySpaceError(
                "No existe el espacio Society."
            )

        category = guild.get_channel(
            space["category_id"]
        )

        if not isinstance(
            category,
            discord.CategoryChannel,
        ):
            raise SocietySpaceError(
                "La categoría no existe en Discord."
            )

        await category.edit(
            name=new_name,
            reason=(
                "VEXEN Society: renombrar categoría"
            ),
        )

        await add_audit_log(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            "CATEGORY_RENAMED",
            actor_id,
            associate_user_id,
            metadata={
                "category_id": category.id,
                "name": new_name,
            },
        )

    async def rename_channel(
        self,
        guild: discord.Guild,
        associate_user_id: int,
        actor_id: int,
        channel_id: int,
        new_name: str,
    ) -> None:
        new_name = new_name.strip()

        if not new_name or len(new_name) > 100:
            raise SocietySpaceError(
                "Nombre de canal inválido."
            )

        row = await get_associate_channel(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            channel_id,
        )

        if (
            row is None
            or row["associate_user_id"]
            != associate_user_id
        ):
            raise SocietySpaceError(
                "Ese canal no pertenece a esta Society."
            )

        channel = guild.get_channel(channel_id)

        if channel is None:
            raise SocietySpaceError(
                "El canal ya no existe en Discord."
            )

        await channel.edit(
            name=new_name,
            reason=(
                "VEXEN Society: renombrar canal"
            ),
        )

        await add_audit_log(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            "CHANNEL_RENAMED",
            actor_id,
            associate_user_id,
            metadata={
                "channel_id": channel_id,
                "name": new_name,
            },
        )

    async def delete_custom_channel(
        self,
        guild: discord.Guild,
        associate_user_id: int,
        actor_id: int,
        channel_id: int,
    ) -> None:
        row = await get_associate_channel(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            channel_id,
        )

        if (
            row is None
            or row["associate_user_id"]
            != associate_user_id
        ):
            raise SocietySpaceError(
                "Ese canal no pertenece a esta Society."
            )

        if row["is_template"]:
            raise SocietySpaceError(
                "Los canales de plantilla están protegidos."
            )

        channel = guild.get_channel(channel_id)

        if channel is not None:
            await channel.delete(
                reason=(
                    "VEXEN Society: eliminar canal personalizado"
                )
            )

        await delete_associate_channel_record(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            channel_id,
        )

        await add_audit_log(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            "CUSTOM_CHANNEL_DELETED",
            actor_id,
            associate_user_id,
            metadata={
                "channel_id": channel_id,
            },
        )

    async def sync_template(
        self,
        guild: discord.Guild,
        associate_user_id: int,
        actor_id: int,
    ) -> int:
        space = await get_associate_space(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            associate_user_id,
        )

        if (
            space is None
            or space["status"] != "active"
        ):
            raise SocietySpaceError(
                "La Society no está activa."
            )

        category = guild.get_channel(
            space["category_id"]
        )
        community_role = guild.get_role(
            space["community_role_id"]
        )
        staff_role = guild.get_role(
            space["staff_role_id"]
        )

        if (
            not isinstance(
                category,
                discord.CategoryChannel,
            )
            or community_role is None
            or staff_role is None
        ):
            raise SocietySpaceError(
                "La configuración de Discord está incompleta."
            )

        template_row = await get_active_template(
            self.db,
            self.settings.society_db_schema,
            guild.id,
        )

        if template_row is None:
            raise SocietySpaceError(
                "No existe plantilla activa."
            )

        parsed = template_from_row(
            template_row
        )

        rows = await list_associate_channels(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            associate_user_id,
        )

        by_key = {
            row["channel_key"]: row
            for row in rows
            if row["is_template"]
        }

        created = 0

        for definition in parsed.channels:
            current = by_key.get(
                definition.channel_key
            )

            if (
                current is not None
                and guild.get_channel(
                    current["channel_id"]
                )
                is not None
            ):
                continue

            channel = (
                await self._create_channel_from_definition(
                    guild,
                    category,
                    definition.channel_type,
                    definition.name,
                    community_role,
                    staff_role,
                )
            )

            await save_associate_channel(
                self.db,
                self.settings.society_db_schema,
                guild.id,
                associate_user_id,
                channel.id,
                definition.channel_key,
                definition.channel_type,
                True,
            )

            created += 1

        await self._reorder_template_channels(
            guild,
            category,
            associate_user_id,
            parsed,
        )

        await save_associate_space(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            associate_user_id,
            template_id=template_row["template_id"],
            template_version=template_row["version"],
            status="active",
        )

        await add_audit_log(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            "TEMPLATE_SYNCED",
            actor_id,
            associate_user_id,
            metadata={
                "created_channels": created,
                "template_version": (
                    template_row["version"]
                ),
            },
        )

        return created

    async def _reorder_template_channels(
        self,
        guild: discord.Guild,
        category: discord.CategoryChannel,
        associate_user_id: int,
        parsed: ParsedTemplate,
    ) -> None:
        """Restaura el orden lógico de la plantilla tras una sincronización.

        Discord siempre coloca canales de voz debajo de los de texto, por lo
        que ordenamos ambos bloques por separado respetando el orden del TXT.
        """
        rows = await list_associate_channels(
            self.db,
            self.settings.society_db_schema,
            guild.id,
            associate_user_id,
        )

        by_key = {
            row["channel_key"]: row
            for row in rows
            if row["is_template"]
        }

        text_channels: list[discord.abc.GuildChannel] = []
        voice_channels: list[discord.abc.GuildChannel] = []

        for definition in parsed.channels:
            row = by_key.get(definition.channel_key)
            if row is None:
                continue

            channel = guild.get_channel(row["channel_id"])
            if channel is None or getattr(channel, "category_id", None) != category.id:
                continue

            if definition.channel_type in {"ANN", "TXT", "STAFF-TXT"}:
                text_channels.append(channel)
            elif definition.channel_type in {"VOICE", "STAFF-VOICE"}:
                voice_channels.append(channel)

        async def arrange(
            channels: list[discord.abc.GuildChannel],
        ) -> None:
            if not channels:
                return

            await channels[0].move(
                beginning=True,
                category=category,
                reason="VEXEN Society: restaurar orden de plantilla",
            )

            previous = channels[0]
            for channel in channels[1:]:
                await channel.move(
                    after=previous,
                    category=category,
                    reason="VEXEN Society: restaurar orden de plantilla",
                )
                previous = channel

        await arrange(text_channels)
        await arrange(voice_channels)

    async def _order_society_roles(
        self,
        guild: discord.Guild,
        staff_role: discord.Role,
        community_role: discord.Role,
        integration_role: discord.Role,
    ) -> None:
        current_positions = [
            staff_role.position,
            community_role.position,
            integration_role.position,
        ]

        base = max(1, min(current_positions))

        me = guild.me
        if me is None:
            raise SocietySpaceError(
                "No se pudo determinar la jerarquía del bot."
            )

        highest_allowed = me.top_role.position - 1
        if highest_allowed < 3:
            raise SocietySpaceError(
                "El rol del bot debe estar por encima de los roles Society."
            )

        if base + 2 > highest_allowed:
            base = max(1, highest_allowed - 2)

        await guild.edit_role_positions(
            positions={
                integration_role: base,
                community_role: base + 1,
                staff_role: base + 2,
            },
            reason=(
                "VEXEN Society: jerarquía Staff > Comunidad > INT"
            ),
        )

    async def _place_society_category(
        self,
        guild: discord.Guild,
        category: discord.CategoryChannel,
    ) -> None:
        existing_society = [
            item
            for item in guild.categories
            if item.id != category.id
            and "{ vxs }" in item.name.casefold()
        ]

        anchor: discord.CategoryChannel | None = None

        if existing_society:
            anchor = max(
                existing_society,
                key=lambda item: item.position,
            )
        else:
            configured_id = await get_base_category(
                self.db,
                self.settings.society_db_schema,
                guild.id,
            )

            configured = (
                guild.get_channel(configured_id)
                if configured_id
                else None
            )

            if isinstance(configured, discord.CategoryChannel):
                anchor = configured
            else:
                anchor = next(
                    (
                        item
                        for item in guild.categories
                        if item.name.casefold() == "comunidad"
                    ),
                    None,
                )

        if anchor is None:
            return

        await category.move(
            after=anchor,
            reason="VEXEN Society: posicionar categoría Society",
        )

    @staticmethod
    def _normalize_text_channel_name(name: str) -> str:
        # Discord reemplaza espacios por guiones en canales de texto.
        # Eliminamos únicamente los espacios alrededor del separador visual
        # para conservar nombres como: 💬┃general.
        return name.replace(" ┃ ", "┃").replace(" ┃", "┃").replace("┃ ", "┃")

    async def _create_channel_from_definition(
        self,
        guild: discord.Guild,
        category: discord.CategoryChannel,
        channel_type: str,
        name: str,
        community_role: discord.Role,
        staff_role: discord.Role,
    ) -> discord.abc.GuildChannel:
        if channel_type in {
            "ANN",
            "TXT",
            "STAFF-TXT",
        }:
            name = self._normalize_text_channel_name(name)
            channel = await guild.create_text_channel(
                name,
                category=category,
                reason=(
                    "VEXEN Society: "
                    f"{channel_type}"
                ),
            )
        elif channel_type in {
            "VOICE",
            "STAFF-VOICE",
        }:
            channel = await guild.create_voice_channel(
                name,
                category=category,
                reason=(
                    "VEXEN Society: "
                    f"{channel_type}"
                ),
            )
        else:
            raise SocietySpaceError(
                f"Tipo de canal desconocido: {channel_type}"
            )

        if channel_type in {
            "STAFF-TXT",
            "STAFF-VOICE",
        }:
            await apply_staff_only(
                channel,
                community_role,
                staff_role,
            )

        return channel

    @staticmethod
    def _validate_names(
        community_name: str,
    ) -> None:
        if (
            not community_name
            or len(community_name) > 80
        ):
            raise SocietySpaceError(
                "El nombre de comunidad debe tener entre 1 y 80 caracteres."
            )

        for role_name in (
            community_name,
            f"INT-{community_name}",
            f"Staff-{community_name}",
        ):
            if len(role_name) > 100:
                raise SocietySpaceError(
                    f"El rol '{role_name}' supera 100 caracteres."
                )

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from app.config.settings import Settings
from app.society.welcome import CommunityRoleView
from database import (
    clear_announcement_join_message,
    delete_announcement_mirror,
    find_associate_by_announcement_channel,
    get_announcement_mirror,
    get_associate,
    get_announcement_button_style,
    get_community_entry_channel_id,
    get_global_announcements_channel,
    list_active_announcement_role_button_bindings,
    list_announcement_ctas_for_associate,
    list_recent_announcement_mirrors_for_associate,
    save_announcement_mirror,
    set_announcement_join_message,
)

log = logging.getLogger("vexen_society.announcements")
RELAY_WEBHOOK_NAME = "VEXEN Society Relay"


class AnnouncementsCog(commands.Cog):
    def __init__(self, bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings

    async def _get_or_create_relay_webhook(
        self,
        channel: discord.TextChannel,
    ) -> discord.Webhook:
        webhooks = await channel.webhooks()
        preferred = None
        for webhook in webhooks:
            if webhook.name != RELAY_WEBHOOK_NAME:
                continue
            if (
                self.bot.user is not None
                and webhook.user is not None
                and webhook.user.id == self.bot.user.id
            ):
                return webhook
            preferred = preferred or webhook

        if preferred is not None:
            return preferred

        return await channel.create_webhook(
            name=RELAY_WEBHOOK_NAME,
            reason=(
                "VEXEN Society: retransmisión de anuncios "
                "con autor original"
            ),
        )

    @staticmethod
    async def _attachment_files(
        message: discord.Message,
    ) -> list[discord.File]:
        files: list[discord.File] = []
        for attachment in message.attachments[:10]:
            try:
                files.append(await attachment.to_file(use_cached=True))
            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException,
            ):
                log.warning(
                    "No se pudo copiar el adjunto %s del anuncio %s.",
                    attachment.id,
                    message.id,
                )
        return files

    @staticmethod
    def _message_content(
        message: discord.Message,
    ) -> str | None:
        parts: list[str] = []
        if message.content:
            parts.append(message.content)
        for sticker in message.stickers:
            url = getattr(sticker, "url", None)
            if url:
                parts.append(str(url))
        content = "\n".join(parts).strip()
        return content or None

    async def _relay_message(
        self,
        message: discord.Message,
        target: discord.TextChannel,
    ) -> discord.WebhookMessage:
        webhook = await self._get_or_create_relay_webhook(target)
        files = await self._attachment_files(message)
        return await webhook.send(
            content=self._message_content(message),
            username=message.author.display_name[:80],
            avatar_url=str(message.author.display_avatar.url),
            files=files,
            allowed_mentions=discord.AllowedMentions(
                everyone=False,
                users=True,
                roles=True,
                replied_user=False,
            ),
            wait=True,
        )

    async def _send_join_message(
        self,
        target: discord.TextChannel,
        relayed: discord.Message,
        guild_id: int,
        associate,
    ) -> discord.Message | None:
        entry_channel_id = await get_community_entry_channel_id(
            self.bot.db,
            self.settings.society_db_schema,
            guild_id,
            associate["user_id"],
        )
        role_id = associate["community_role_id"]
        button_style = await get_announcement_button_style(
            self.bot.db,
            self.settings.society_db_schema,
            guild_id,
        )
        if not entry_channel_id or not role_id:
            log.warning(
                "No se pudo crear el botón de comunidad para %s: "
                "falta entry_channel_id o community_role_id.",
                associate["community_name"],
            )
            return None

        try:
            return await target.send(
                content=(
                    "✨ ¿Quieres formar parte de "
                    f"**{associate['community_name']}**?"
                ),
                view=CommunityRoleView(
                    role_id,
                    entry_channel_id,
                    associate["community_name"],
                    button_style=button_style,
                ),
                reference=relayed,
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            log.exception(
                "El anuncio se retransmitió, pero no se pudo publicar "
                "el botón para unirse a la comunidad."
            )
            return None

    @staticmethod
    async def _delete_target_message(
        target: discord.TextChannel,
        message_id: int | None,
    ) -> bool:
        if not message_id:
            return True
        try:
            message = await target.fetch_message(message_id)
            await message.delete()
            return True
        except discord.NotFound:
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False

    async def _resolve_text_channel(
        self,
        guild: discord.Guild,
        channel_id: int,
    ) -> discord.TextChannel | None:
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        try:
            fetched = await self.bot.fetch_channel(channel_id)
        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            return None
        return fetched if isinstance(fetched, discord.TextChannel) else None

    async def _remove_previous_ctas(
        self,
        guild: discord.Guild,
        associate_user_id: int,
        current_source_message_id: int,
    ) -> None:
        # IMPORTANTE: se filtra por associate_user_id. Nunca es una limpieza global.
        rows = await list_announcement_ctas_for_associate(
            self.bot.db,
            self.settings.society_db_schema,
            guild.id,
            associate_user_id,
            exclude_source_message_id=current_source_message_id,
        )
        for row in rows:
            target = await self._resolve_text_channel(
                guild,
                row["target_channel_id"],
            )
            if target is None:
                continue
            removed = await self._delete_target_message(
                target,
                row["join_message_id"],
            )
            if removed:
                await clear_announcement_join_message(
                    self.bot.db,
                    self.settings.society_db_schema,
                    guild.id,
                    row["source_message_id"],
                )

    async def _publish_and_store(
        self,
        message: discord.Message,
        target: discord.TextChannel,
        associate,
    ) -> None:
        relayed = await self._relay_message(message, target)
        join_message = await self._send_join_message(
            target,
            relayed,
            message.guild.id,
            associate,
        )

        await save_announcement_mirror(
            self.bot.db,
            self.settings.society_db_schema,
            message.guild.id,
            associate["user_id"],
            message.channel.id,
            message.id,
            target.id,
            relayed.id,
            join_message.id if join_message else None,
        )

        # Solo movemos el CTA si el nuevo CTA se publicó bien.
        # De este modo un fallo puntual no deja la Society sin botón.
        if join_message is not None:
            await self._remove_previous_ctas(
                message.guild,
                associate["user_id"],
                message.id,
            )

    async def _restore_previous_cta(
        self,
        guild: discord.Guild,
        associate_user_id: int,
    ) -> None:
        associate = await get_associate(
            self.bot.db,
            self.settings.society_db_schema,
            guild.id,
            associate_user_id,
        )
        if associate is None or not associate["community_role_id"]:
            return

        rows = await list_recent_announcement_mirrors_for_associate(
            self.bot.db,
            self.settings.society_db_schema,
            guild.id,
            associate_user_id,
        )

        for row in rows:
            target = await self._resolve_text_channel(
                guild,
                row["target_channel_id"],
            )
            if target is None:
                continue
            try:
                relayed = await target.fetch_message(row["target_message_id"])
            except discord.NotFound:
                continue
            except (discord.Forbidden, discord.HTTPException):
                return

            join_message = await self._send_join_message(
                target,
                relayed,
                guild.id,
                associate,
            )
            if join_message is None:
                return

            await set_announcement_join_message(
                self.bot.db,
                self.settings.society_db_schema,
                guild.id,
                row["source_message_id"],
                join_message.id,
            )
            await self._remove_previous_ctas(
                guild,
                associate_user_id,
                row["source_message_id"],
            )
            return

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if (
            message.guild is None
            or message.author.bot
            or message.webhook_id is not None
            or self.bot.db is None
        ):
            return
        if (
            self.settings.guild_id is None
            or message.guild.id != self.settings.guild_id
        ):
            return

        target_id = await get_global_announcements_channel(
            self.bot.db,
            self.settings.society_db_schema,
            message.guild.id,
        )
        if not target_id or target_id == message.channel.id:
            return

        associate = await find_associate_by_announcement_channel(
            self.bot.db,
            self.settings.society_db_schema,
            message.guild.id,
            message.channel.id,
        )
        if associate is None:
            return

        target = message.guild.get_channel(target_id)
        if not isinstance(target, discord.TextChannel):
            return

        try:
            await self._publish_and_store(message, target, associate)
        except (discord.Forbidden, discord.HTTPException):
            log.exception(
                "No se pudo retransmitir el anuncio Society mediante webhook. "
                "Revisa Administrar webhooks en el canal global."
            )

    @commands.Cog.listener()
    async def on_message_edit(
        self,
        before: discord.Message,
        after: discord.Message,
    ) -> None:
        del before
        if (
            after.guild is None
            or after.author.bot
            or after.webhook_id is not None
            or self.bot.db is None
        ):
            return

        mirror = await get_announcement_mirror(
            self.bot.db,
            self.settings.society_db_schema,
            after.guild.id,
            after.id,
        )
        if mirror is None:
            return

        target = after.guild.get_channel(mirror["target_channel_id"])
        if not isinstance(target, discord.TextChannel):
            return

        associate = await find_associate_by_announcement_channel(
            self.bot.db,
            self.settings.society_db_schema,
            after.guild.id,
            after.channel.id,
        )
        if associate is None:
            return

        await self._delete_target_message(target, mirror["join_message_id"])
        await self._delete_target_message(target, mirror["target_message_id"])

        # Como el relay editado vuelve a publicarse al final, pasa a ser
        # el último anuncio visual de ESE asociado y recibe su único CTA.
        try:
            await self._publish_and_store(after, target, associate)
        except (discord.Forbidden, discord.HTTPException):
            log.exception(
                "No se pudo actualizar el anuncio Society mediante webhook."
            )

    @commands.Cog.listener()
    async def on_raw_message_delete(
        self,
        payload: discord.RawMessageDeleteEvent,
    ) -> None:
        if payload.guild_id is None or self.bot.db is None:
            return

        mirror = await get_announcement_mirror(
            self.bot.db,
            self.settings.society_db_schema,
            payload.guild_id,
            payload.message_id,
        )
        if mirror is None:
            return

        had_active_cta = bool(mirror["join_message_id"])
        associate_user_id = mirror["associate_user_id"]
        guild = self.bot.get_guild(payload.guild_id)

        if guild is not None:
            target = await self._resolve_text_channel(
                guild,
                mirror["target_channel_id"],
            )
            if target is not None:
                await self._delete_target_message(
                    target,
                    mirror["join_message_id"],
                )
                await self._delete_target_message(
                    target,
                    mirror["target_message_id"],
                )

        await delete_announcement_mirror(
            self.bot.db,
            self.settings.society_db_schema,
            payload.guild_id,
            payload.message_id,
        )

        # Si era el anuncio con CTA, el botón vuelve al anuncio anterior
        # que todavía exista, siempre del MISMO associate_user_id.
        if had_active_cta and guild is not None:
            await self._restore_previous_cta(
                guild,
                associate_user_id,
            )


async def restore_announcement_role_views(bot, settings: Settings) -> int:
    if bot.db is None or settings.guild_id is None:
        return 0

    rows = await list_active_announcement_role_button_bindings(
        bot.db,
        settings.society_db_schema,
        settings.guild_id,
    )
    button_style = await get_announcement_button_style(
        bot.db,
        settings.society_db_schema,
        settings.guild_id,
    )

    restored = 0
    seen_associates: set[int] = set()

    for row in rows:
        associate_user_id = int(row["associate_user_id"])
        if (
            not row["join_message_id"]
            or not row["community_role_id"]
            or not row["entry_channel_id"]
        ):
            continue

        if associate_user_id not in seen_associates:
            bot.add_view(
                CommunityRoleView(
                    row["community_role_id"],
                    row["entry_channel_id"],
                    row["community_name"],
                    button_style=button_style,
                ),
                message_id=row["join_message_id"],
            )
            seen_associates.add(associate_user_id)
            restored += 1
            continue

        # Migración/saneamiento de v1.3: los CTA más viejos del MISMO
        # asociado se eliminan, sin tocar CTA de otros asociados.
        try:
            channel = bot.get_channel(row["target_channel_id"])
            if not isinstance(channel, discord.TextChannel):
                fetched = await bot.fetch_channel(row["target_channel_id"])
                channel = fetched if isinstance(fetched, discord.TextChannel) else None
            if channel is None:
                continue

            try:
                stale = await channel.fetch_message(row["join_message_id"])
                await stale.delete()
            except discord.NotFound:
                pass

            await clear_announcement_join_message(
                bot.db,
                settings.society_db_schema,
                settings.guild_id,
                row["source_message_id"],
            )
        except (discord.Forbidden, discord.HTTPException):
            log.warning(
                "No se pudo limpiar un CTA antiguo del asociado %s.",
                associate_user_id,
            )

    return restored

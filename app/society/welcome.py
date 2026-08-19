from __future__ import annotations

import logging

import discord

from app.config.settings import Settings
from app.society.button_config import (
    DEFAULT_COMMUNITY_BUTTON_STYLE,
    DEFAULT_WELCOME_BUTTON_STYLE,
    build_community_join_label,
    normalize_community_button_style,
)
from app.society.welcome_config import (
    DEFAULT_WELCOME_COLOR_HEX,
    welcome_color_to_int,
)
from database import (
    add_audit_log,
    get_welcome_button_style,
    get_community_entry_channel_id,
    get_welcome_channel,
    get_welcome_color,
    list_active_announcement_role_button_bindings,
    list_active_role_button_bindings,
    save_associate_space,
)

log = logging.getLogger("vexen_society.welcome")


class CommunityAccessLinkView(discord.ui.View):
    def __init__(self, guild_id: int, channel_id: int) -> None:
        super().__init__(timeout=120)
        self.add_item(
            discord.ui.Button(
                label="Ir a la comunidad",
                emoji="🚪",
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{guild_id}/{channel_id}",
            )
        )


class CommunityRoleButton(discord.ui.Button):
    def __init__(
        self,
        role_id: int,
        entry_channel_id: int,
        community_name: str,
        *,
        button_style: str = DEFAULT_COMMUNITY_BUTTON_STYLE,
        disabled: bool = False,
    ) -> None:
        normalized_style = normalize_community_button_style(button_style)
        super().__init__(
            label=build_community_join_label(community_name),
            style=getattr(discord.ButtonStyle, normalized_style),
            custom_id=(
                f"vxs:join:{role_id}:{entry_channel_id}"
            ),
            disabled=disabled,
        )
        self.role_id = role_id
        self.entry_channel_id = entry_channel_id
        self.community_name = community_name

    async def callback(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        member = interaction.user

        if guild is None or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "❌ Este botón solo funciona dentro del servidor.",
                ephemeral=True,
            )
            return

        role = guild.get_role(self.role_id)
        if role is None:
            await interaction.response.send_message(
                "❌ El rol de esta comunidad ya no está disponible.",
                ephemeral=True,
            )
            return

        if role in member.roles:
            await interaction.response.send_message(
                f"✅ Ya formas parte de **{self.community_name}**.",
                view=CommunityAccessLinkView(guild.id, self.entry_channel_id),
                ephemeral=True,
            )
            return

        try:
            await member.add_roles(
                role,
                reason=f"VEXEN Society: acceso a {self.community_name}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ No puedo asignar ese rol. Revisa la jerarquía del bot.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ Discord no permitió asignar el rol en este momento.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"✅ ¡Listo! Ya formas parte de **{self.community_name}**.",
            view=CommunityAccessLinkView(guild.id, self.entry_channel_id),
            ephemeral=True,
        )


class CommunityRoleView(discord.ui.View):
    def __init__(
        self,
        role_id: int,
        entry_channel_id: int,
        community_name: str,
        *,
        button_style: str = DEFAULT_COMMUNITY_BUTTON_STYLE,
        disabled: bool = False,
    ) -> None:
        super().__init__(timeout=None)
        self.add_item(
            CommunityRoleButton(
                role_id,
                entry_channel_id,
                community_name,
                button_style=button_style,
                disabled=disabled,
            )
        )


def build_welcome_embed(
    associate_user_id: int,
    community_role_id: int,
    color_hex: str = DEFAULT_WELCOME_COLOR_HEX,
) -> discord.Embed:
    associate_mention = f"<@{associate_user_id}>"

    embed = discord.Embed(
        description=(
            "Hoy le damos oficialmente la bienvenida a "
            f"{associate_mention} y a toda su comunidad. ✨\n\n"
            "Nos alegra tenerlos formando parte de **VEXEN Society** "
            "y abrirles un espacio propio dentro de nuestra comunidad.\n\n"
            "**🤝 UNA NUEVA COMUNIDAD SE UNE A VEXEN**\n\n"
            f"A partir de hoy, {associate_mention} y su comunidad cuentan "
            "con su propio espacio para reunirse, compartir contenido, "
            "organizar actividades y seguir creciendo juntos.\n\n"
            "Puedes formar parte de su comunidad obteniendo:\n\n"
            f"<@&{community_role_id}>\n\n"
            "Gracias por confiar en **VEXEN** para esta nueva etapa.\n\n"
            f"**Bienvenidos {associate_mention} y su comunidad.**\n"
            "Nos alegra tenerlos aquí. ✨"
        ),
        color=welcome_color_to_int(color_hex),
    )
    embed.set_footer(text="VEXEN • SOCIETY")
    return embed


async def publish_welcome(
    bot,
    settings: Settings,
    guild: discord.Guild,
    associate_user_id: int,
    associate_name: str,
    community_name: str,
    community_role_id: int,
    actor_id: int,
) -> tuple[discord.Message | None, str | None]:
    if bot.db is None:
        return None, "PostgreSQL no está disponible."

    configured_channel_id = await get_welcome_channel(
        bot.db,
        settings.society_db_schema,
        guild.id,
    )

    if not configured_channel_id:
        return None, None

    welcome_channel = guild.get_channel(configured_channel_id)
    if not isinstance(welcome_channel, discord.TextChannel):
        return None, "El canal de bienvenida configurado ya no existe o no es de texto."

    entry_channel_id = await get_community_entry_channel_id(
        bot.db,
        settings.society_db_schema,
        guild.id,
        associate_user_id,
    )

    if not entry_channel_id:
        return None, "No se encontró un canal de entrada para la comunidad."

    color_hex = await get_welcome_color(
        bot.db,
        settings.society_db_schema,
        guild.id,
    )
    button_style = await get_welcome_button_style(
        bot.db,
        settings.society_db_schema,
        guild.id,
    )

    try:
        message = await welcome_channel.send(
            content="# 🎉 ¡BIENVENIDOS A VEXEN SOCIETY!",
            embed=build_welcome_embed(
                associate_user_id,
                community_role_id,
                color_hex,
            ),
            view=CommunityRoleView(
                community_role_id,
                entry_channel_id,
                community_name,
                button_style=button_style,
            ),
            allowed_mentions=discord.AllowedMentions(
                everyone=False,
                roles=True,
                users=True,
            ),
        )
    except (discord.Forbidden, discord.HTTPException) as exc:
        log.exception("No se pudo publicar la bienvenida Society.")
        return None, f"{type(exc).__name__}: no se pudo publicar la bienvenida."

    await save_associate_space(
        bot.db,
        settings.society_db_schema,
        guild.id,
        associate_user_id,
        welcome_channel_id=welcome_channel.id,
        welcome_message_id=message.id,
        status="active",
    )

    await add_audit_log(
        bot.db,
        settings.society_db_schema,
        guild.id,
        "WELCOME_PUBLISHED",
        actor_id,
        associate_user_id,
        community_name,
        {
            "welcome_channel_id": welcome_channel.id,
            "welcome_message_id": message.id,
            "community_role_id": community_role_id,
            "entry_channel_id": entry_channel_id,
            "welcome_color_hex": color_hex,
            "community_button_style": button_style,
        },
    )

    return message, None


async def disable_welcome_button(
    bot,
    settings: Settings,
    guild: discord.Guild,
    space,
    community_name: str,
) -> None:
    channel_id = space["welcome_channel_id"]
    message_id = space["welcome_message_id"]
    role_id = space["community_role_id"]

    if not channel_id or not message_id or not role_id:
        return

    channel = guild.get_channel(channel_id)
    if not isinstance(channel, discord.TextChannel):
        return

    entry_channel_id = await get_community_entry_channel_id(
        bot.db,
        settings.society_db_schema,
        guild.id,
        space["associate_user_id"],
    )

    if not entry_channel_id:
        entry_channel_id = channel.id

    button_style = await get_welcome_button_style(
        bot.db,
        settings.society_db_schema,
        guild.id,
    )

    try:
        message = await channel.fetch_message(message_id)
        await message.edit(
            view=CommunityRoleView(
                role_id,
                entry_channel_id,
                community_name,
                button_style=button_style,
                disabled=True,
            )
        )
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass


async def restore_persistent_role_views(
    bot,
    settings: Settings,
) -> int:
    if bot.db is None or settings.guild_id is None:
        return 0

    rows = await list_active_role_button_bindings(
        bot.db,
        settings.society_db_schema,
        settings.guild_id,
    )

    button_style = await get_welcome_button_style(
        bot.db,
        settings.society_db_schema,
        settings.guild_id,
    )

    restored = 0

    for row in rows:
        if not row["entry_channel_id"]:
            continue

        bot.add_view(
            CommunityRoleView(
                row["community_role_id"],
                row["entry_channel_id"],
                row["community_name"],
                button_style=button_style,
            ),
            message_id=row["welcome_message_id"],
        )
        restored += 1

    return restored


async def _resolve_text_channel(bot, guild: discord.Guild, channel_id: int):
    channel = guild.get_channel(channel_id)
    if isinstance(channel, discord.TextChannel):
        return channel
    try:
        fetched = await bot.fetch_channel(channel_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None
    return fetched if isinstance(fetched, discord.TextChannel) else None


async def refresh_welcome_button_styles(
    bot, settings: Settings, guild: discord.Guild, button_style: str
) -> dict[str, int]:
    if bot.db is None:
        return {"updated": 0, "failed": 0}
    normalized = normalize_community_button_style(button_style)
    rows = await list_active_role_button_bindings(
        bot.db, settings.society_db_schema, guild.id
    )
    counters = {"updated": 0, "failed": 0}
    for row in rows:
        if not row["entry_channel_id"]:
            continue
        channel = await _resolve_text_channel(bot, guild, row["welcome_channel_id"])
        if channel is None:
            counters["failed"] += 1
            continue
        try:
            message = await channel.fetch_message(row["welcome_message_id"])
            await message.edit(view=CommunityRoleView(
                row["community_role_id"], row["entry_channel_id"], row["community_name"],
                button_style=normalized,
            ))
            counters["updated"] += 1
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            counters["failed"] += 1
    return counters


async def refresh_announcement_button_styles(
    bot, settings: Settings, guild: discord.Guild, button_style: str
) -> dict[str, int]:
    if bot.db is None:
        return {"updated": 0, "failed": 0}
    normalized = normalize_community_button_style(button_style)
    rows = await list_active_announcement_role_button_bindings(
        bot.db, settings.society_db_schema, guild.id
    )
    counters = {"updated": 0, "failed": 0}
    for row in rows:
        if not row["entry_channel_id"] or not row["join_message_id"]:
            continue
        channel = await _resolve_text_channel(bot, guild, row["target_channel_id"])
        if channel is None:
            counters["failed"] += 1
            continue
        try:
            message = await channel.fetch_message(row["join_message_id"])
            await message.edit(view=CommunityRoleView(
                row["community_role_id"], row["entry_channel_id"], row["community_name"],
                button_style=normalized,
            ))
            counters["updated"] += 1
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            counters["failed"] += 1
    return counters

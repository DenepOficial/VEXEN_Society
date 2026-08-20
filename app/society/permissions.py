from __future__ import annotations

import discord


def full_associate_overwrite() -> discord.PermissionOverwrite:
    allow = discord.Permissions.all_channel()
    deny = discord.Permissions.none()
    return discord.PermissionOverwrite.from_pair(allow, deny)


def community_overwrite() -> discord.PermissionOverwrite:
    return discord.PermissionOverwrite(
        view_channel=True,
        read_message_history=True,
        send_messages=True,
        send_messages_in_threads=True,
        create_public_threads=True,
        create_private_threads=True,
        add_reactions=True,
        attach_files=True,
        embed_links=True,
        use_external_emojis=True,
        use_external_stickers=True,
        connect=True,
        speak=True,
        stream=True,
        use_voice_activation=True,
    )


def staff_overwrite() -> discord.PermissionOverwrite:
    """Permisos locales del rol Staff-{Comunidad}.

    Solo establece en ``True`` los permisos aprobados para la categoría
    Society. Los permisos sensibles no incluidos (Administrador, gestionar
    canales/permisos/roles/webhooks, eventos, apps, etc.) permanecen en
    estado neutral y se resuelven mediante la configuración superior de
    Discord.
    """
    return discord.PermissionOverwrite(
        # Categoría / membresía
        view_channel=True,
        create_instant_invite=True,

        # Texto
        send_messages=True,
        send_messages_in_threads=True,
        create_public_threads=True,
        create_private_threads=True,
        embed_links=True,
        attach_files=True,
        add_reactions=True,
        use_external_emojis=True,
        use_external_stickers=True,
        mention_everyone=True,
        manage_messages=True,
        pin_messages=True,
        bypass_slowmode=True,
        manage_threads=True,
        read_message_history=True,
        send_polls=True,

        # Voz
        connect=True,
        speak=True,
        stream=True,
        use_soundboard=True,
        use_external_sounds=True,
        use_voice_activation=True,
        priority_speaker=True,
        mute_members=True,
        deafen_members=True,
        move_members=True,
        set_voice_channel_status=True,
    )


def base_category_overwrites(
    guild: discord.Guild,
    associate: discord.Member,
    community_role: discord.Role,
    staff_role: discord.Role,
) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        associate: full_associate_overwrite(),
        community_role: community_overwrite(),
        staff_role: staff_overwrite(),
    }

    if guild.me is not None:
        overwrites[guild.me] = full_associate_overwrite()

    return overwrites


async def apply_staff_only(
    channel: discord.abc.GuildChannel,
    community_role: discord.Role,
    staff_role: discord.Role,
) -> None:
    await channel.set_permissions(
        community_role,
        view_channel=False,
        reason="VEXEN Society: canal privado de Staff",
    )

    await channel.set_permissions(
        staff_role,
        overwrite=staff_overwrite(),
        reason="VEXEN Society: acceso Staff",
    )

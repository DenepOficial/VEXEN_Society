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
    return discord.PermissionOverwrite(
        view_channel=True,
        read_message_history=True,
        send_messages=True,
        send_messages_in_threads=True,
        create_public_threads=True,
        create_private_threads=True,
        manage_messages=True,
        manage_threads=True,
        add_reactions=True,
        attach_files=True,
        embed_links=True,
        use_external_emojis=True,
        use_external_stickers=True,
        connect=True,
        speak=True,
        stream=True,
        use_voice_activation=True,
        mute_members=True,
        deafen_members=True,
        move_members=True,
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

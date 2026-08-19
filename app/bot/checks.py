from __future__ import annotations

import discord

from app.config.settings import Settings
from database import list_allowed_roles


async def guild_is_authorized(
    interaction: discord.Interaction,
    settings: Settings,
) -> bool:
    return (
        interaction.guild_id is not None
        and settings.guild_id is not None
        and interaction.guild_id == settings.guild_id
    )


async def is_society_admin(
    interaction: discord.Interaction,
    settings: Settings,
    db,
) -> bool:
    if interaction.user.id == settings.owner_id:
        return True

    role_ids = {role.id for role in getattr(interaction.user, "roles", ())}

    if role_ids.intersection(settings.allowed_role_ids):
        return True

    if db is None or interaction.guild_id is None:
        return False

    db_role_ids = set(
        await list_allowed_roles(
            db,
            settings.society_db_schema,
            interaction.guild_id,
        )
    )

    return bool(role_ids.intersection(db_role_ids))


async def require_admin(
    interaction: discord.Interaction,
    settings: Settings,
    db,
) -> bool:
    if not await guild_is_authorized(interaction, settings):
        await _ephemeral(interaction, "❌ Este servidor no está autorizado.")
        return False

    if not await is_society_admin(interaction, settings, db):
        await _ephemeral(
            interaction,
            "❌ Solo OWNER o los roles autorizados de VEXEN Society pueden usar esta acción.",
        )
        return False

    return True


async def _ephemeral(
    interaction: discord.Interaction,
    message: str,
) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)

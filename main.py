from __future__ import annotations

import logging

import discord
from discord import app_commands

from app.bot.client import VexenSocietyBot
from app.config.settings import get_settings


def configure_logging(
    level: str,
) -> None:
    logging.basicConfig(
        level=getattr(
            logging,
            level,
            logging.INFO,
        ),
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )


def main() -> None:
    settings = get_settings()

    configure_logging(
        settings.log_level
    )

    if not settings.discord_token.strip():
        raise RuntimeError(
            "Falta DISCORD_TOKEN en .env"
        )

    if settings.guild_id is None:
        raise RuntimeError(
            "Falta GUILD_ID en .env"
        )

    if settings.owner_id is None:
        raise RuntimeError(
            "Falta OWNER_ID en .env"
        )

    if not settings.database_url.strip():
        raise RuntimeError(
            "Falta DATABASE_URL en .env"
        )

    bot = VexenSocietyBot(
        settings
    )

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        original = getattr(
            error,
            "original",
            error,
        )

        logging.getLogger(
            "vexen_society.commands"
        ).error(
            "Slash command error: %s",
            type(original).__name__,
            exc_info=(
                type(original),
                original,
                original.__traceback__,
            ),
        )

        message = (
            "❌ No se pudo completar "
            "la operación."
        )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    message,
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    message,
                    ephemeral=True,
                )
        except (
            discord.NotFound,
            discord.Forbidden,
            discord.HTTPException,
        ):
            pass

    bot.run(
        settings.discord_token,
        log_handler=None,
    )


if __name__ == "__main__":
    main()

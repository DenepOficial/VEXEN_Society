from __future__ import annotations

import discord


class OwnerBoundView(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        *,
        timeout: float = 600,
    ) -> None:
        super().__init__(timeout=timeout)
        self.owner_id = owner_id

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "❌ Este panel pertenece a otra interacción.",
                ephemeral=True,
            )
            return False

        return True


class CreateSpaceView(OwnerBoundView):
    def __init__(
        self,
        owner_id: int,
        bot,
        associate_user_id: int,
        rollback_associate_on_error: bool = False,
    ) -> None:
        super().__init__(owner_id)
        self.bot = bot
        self.associate_user_id = associate_user_id
        self.rollback_associate_on_error = (
            rollback_associate_on_error
        )

    async def _cleanup_pending_associate(self) -> None:
        if not self.rollback_associate_on_error:
            return
        try:
            from database import delete_associate_record
            await delete_associate_record(
                self.bot.db,
                self.bot.settings.society_db_schema,
                self.bot.settings.guild_id,
                self.associate_user_id,
            )
        except Exception:
            pass

    async def on_timeout(self) -> None:
        await self._cleanup_pending_associate()

    @discord.ui.button(
        label="Crear espacio",
        emoji="🏗️",
        style=discord.ButtonStyle.success,
    )
    async def create(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button

        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        guild = interaction.guild

        if guild is None:
            await interaction.followup.send(
                "❌ Debes usarlo dentro del servidor.",
                ephemeral=True,
            )
            return

        try:
            result = (
                await self.bot.space_service.create_space(
                    guild,
                    self.associate_user_id,
                    interaction.user.id,
                )
            )
        except Exception as exc:
            if self.rollback_associate_on_error:
                try:
                    from database import (
                        delete_associate_record,
                    )

                    await delete_associate_record(
                        self.bot.db,
                        self.bot.settings.society_db_schema,
                        guild.id,
                        self.associate_user_id,
                    )
                except Exception:
                    pass

            await interaction.followup.send(
                "❌ No se pudo crear el espacio.\n"
                f"`{type(exc).__name__}: {str(exc)[:700]}`",
                ephemeral=True,
            )
            return

        self.stop()

        try:
            await interaction.edit_original_response(
                view=None
            )
        except discord.HTTPException:
            pass

        welcome_line = ""
        if result.get("welcome_message") is not None:
            welcome_line = "\nBienvenida: ✅ publicada"
        elif result.get("welcome_error"):
            welcome_line = (
                "\nBienvenida: ⚠️ "
                + str(result["welcome_error"])[:250]
            )
        else:
            welcome_line = "\nBienvenida: no configurada"

        onboarding_line = ""
        if result.get("onboarding_error"):
            onboarding_line = (
                "\nIncorporación: ⚠️ "
                + str(result["onboarding_error"])[:250]
            )
        elif result.get("onboarding_state") == "not_configured":
            onboarding_line = "\nIncorporación: no configurada"
        elif result.get("onboarding_state"):
            onboarding_line = "\nIncorporación: ✅ sincronizada"

        await interaction.followup.send(
            "✅ **Society creada correctamente.**\n"
            f"Categoría: {result['category'].mention}\n"
            f"Comunidad: {result['community_role'].mention}\n"
            f"INT: {result['integration_role'].mention}\n"
            f"Staff: {result['staff_role'].mention}\n"
            f"Canales: **{len(result['channels'])}**\n"
            f"Plantilla: **v{result['template_version']}**"
            + welcome_line
            + onboarding_line,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Cancelar",
        emoji="✖️",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button
        await self._cleanup_pending_associate()
        self.stop()
        await interaction.response.edit_message(
            content="Operación cancelada.",
            embed=None,
            view=None,
        )


class TemplateConfirmView(OwnerBoundView):
    def __init__(
        self,
        owner_id: int,
        bot,
        raw: str,
        name: str,
    ) -> None:
        super().__init__(owner_id)
        self.bot = bot
        self.raw = raw
        self.name = name

    @discord.ui.button(
        label="Activar plantilla",
        emoji="✅",
        style=discord.ButtonStyle.success,
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button

        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        from app.society.templates import (
            save_uploaded_template,
        )

        template_id, version = (
            await save_uploaded_template(
                self.bot.db,
                self.bot.settings,
                interaction.guild_id,
                interaction.user.id,
                self.raw,
                self.name,
            )
        )

        self.stop()

        try:
            await interaction.edit_original_response(
                view=None
            )
        except discord.HTTPException:
            pass

        await interaction.followup.send(
            f"✅ Plantilla **v{version}** activada. "
            f"ID `{template_id}`.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Cancelar",
        emoji="✖️",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button
        self.stop()

        await interaction.response.edit_message(
            content="Carga cancelada.",
            embed=None,
            view=None,
        )


class DeleteConfirmationModal(discord.ui.Modal):
    def __init__(
        self,
        view: "DeleteSocietyView",
        expected: str,
    ) -> None:
        super().__init__(
            title="Confirmar eliminación"
        )

        self.parent_view = view
        self.expected = expected

        self.confirmation = discord.ui.TextInput(
            label="Escribe el nombre exacto",
            placeholder=expected[:100],
            required=True,
            max_length=80,
        )

        self.add_item(
            self.confirmation
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if (
            self.confirmation.value
            != self.expected
        ):
            await interaction.response.send_message(
                "❌ Confirmación incorrecta. "
                "Debes escribir exactamente "
                f"**{self.expected}**.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        guild = interaction.guild

        if guild is None:
            await interaction.followup.send(
                "❌ Servidor no disponible.",
                ephemeral=True,
            )
            return

        try:
            report = (
                await self.parent_view.bot.space_service.delete_space(
                    guild,
                    self.parent_view.associate_user_id,
                    interaction.user.id,
                )
            )
        except Exception as exc:
            await interaction.followup.send(
                "❌ No se pudo iniciar la eliminación: "
                f"`{type(exc).__name__}: "
                f"{str(exc)[:600]}`",
                ephemeral=True,
            )
            return

        self.parent_view.stop()

        if report.complete:
            text = (
                "✅ **Society eliminada correctamente.**"
            )
        else:
            text = (
                "⚠️ **Eliminación parcial.** "
                "El registro se conserva con estado "
                "`error` para poder revisar/reintentar."
            )

        if report.deleted:
            text += (
                "\n\n**Eliminado:**\n"
                + "\n".join(
                    f"• {item}"
                    for item in report.deleted[:20]
                )
            )

        if report.missing:
            text += (
                "\n\n**Ya no existía:**\n"
                + "\n".join(
                    f"• {item}"
                    for item in report.missing[:20]
                )
            )

        if report.errors:
            text += (
                "\n\n**Errores:**\n"
                + "\n".join(
                    f"• {item}"
                    for item in report.errors[:20]
                )
            )

        await interaction.followup.send(
            text[:1900],
            ephemeral=True,
        )


class DeleteSocietyView(OwnerBoundView):
    def __init__(
        self,
        owner_id: int,
        bot,
        associate_user_id: int,
        community_name: str,
    ) -> None:
        super().__init__(owner_id)

        self.bot = bot
        self.associate_user_id = (
            associate_user_id
        )
        self.community_name = community_name

    @discord.ui.button(
        label="Eliminar Society",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
    )
    async def delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button

        await interaction.response.send_modal(
            DeleteConfirmationModal(
                self,
                self.community_name,
            )
        )

    @discord.ui.button(
        label="Cancelar",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button
        self.stop()

        await interaction.response.edit_message(
            content="Eliminación cancelada.",
            embed=None,
            view=None,
        )


class NameModal(discord.ui.Modal):
    def __init__(
        self,
        title: str,
        label: str,
        callback_fn,
        default: str | None = None,
    ) -> None:
        super().__init__(title=title)

        self.callback_fn = callback_fn

        self.value_input = discord.ui.TextInput(
            label=label,
            default=default,
            required=True,
            max_length=100,
        )

        self.add_item(
            self.value_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await self.callback_fn(
            interaction,
            self.value_input.value,
        )


class ManageSocietyView(OwnerBoundView):
    def __init__(
        self,
        owner_id: int,
        bot,
        associate_user_id: int,
    ) -> None:
        super().__init__(owner_id)

        self.bot = bot
        self.associate_user_id = (
            associate_user_id
        )

    async def _create_channel(
        self,
        interaction: discord.Interaction,
        channel_type: str,
    ) -> None:
        async def submit(
            modal_interaction: discord.Interaction,
            name: str,
        ) -> None:
            await modal_interaction.response.defer(
                ephemeral=True,
                thinking=True,
            )

            try:
                channel = (
                    await self.bot.space_service.create_custom_channel(
                        modal_interaction.guild,
                        self.associate_user_id,
                        modal_interaction.user.id,
                        channel_type,
                        name,
                    )
                )
            except Exception as exc:
                await modal_interaction.followup.send(
                    f"❌ `{type(exc).__name__}: "
                    f"{str(exc)[:600]}`",
                    ephemeral=True,
                )
                return

            await modal_interaction.followup.send(
                f"✅ Canal creado: {channel.mention}",
                ephemeral=True,
            )

        await interaction.response.send_modal(
            NameModal(
                "Crear canal",
                "Nombre del canal",
                submit,
            )
        )

    @discord.ui.button(
        label="Texto",
        emoji="💬",
        style=discord.ButtonStyle.primary,
        row=0,
    )
    async def create_text(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button
        await self._create_channel(
            interaction,
            "TXT",
        )

    @discord.ui.button(
        label="Voz",
        emoji="🔊",
        style=discord.ButtonStyle.primary,
        row=0,
    )
    async def create_voice(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button
        await self._create_channel(
            interaction,
            "VOICE",
        )

    @discord.ui.button(
        label="Staff texto",
        emoji="🛡️",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def create_staff_text(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button
        await self._create_channel(
            interaction,
            "STAFF-TXT",
        )

    @discord.ui.button(
        label="Staff voz",
        emoji="🔐",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def create_staff_voice(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button
        await self._create_channel(
            interaction,
            "STAFF-VOICE",
        )

    @discord.ui.button(
        label="Renombrar categoría",
        emoji="✏️",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def rename_category(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button

        async def submit(
            modal_interaction: discord.Interaction,
            name: str,
        ) -> None:
            await modal_interaction.response.defer(
                ephemeral=True,
                thinking=True,
            )

            try:
                await self.bot.space_service.rename_category(
                    modal_interaction.guild,
                    self.associate_user_id,
                    modal_interaction.user.id,
                    name,
                )
            except Exception as exc:
                await modal_interaction.followup.send(
                    f"❌ `{type(exc).__name__}: "
                    f"{str(exc)[:600]}`",
                    ephemeral=True,
                )
                return

            await modal_interaction.followup.send(
                "✅ Categoría renombrada.",
                ephemeral=True,
            )

        await interaction.response.send_modal(
            NameModal(
                "Renombrar categoría",
                "Nuevo nombre",
                submit,
            )
        )

    @discord.ui.button(
        label="Gestionar canal",
        emoji="⚙️",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def manage_channel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button

        from database import (
            list_associate_channels,
        )

        rows = await list_associate_channels(
            self.bot.db,
            self.bot.settings.society_db_schema,
            interaction.guild_id,
            self.associate_user_id,
        )

        options: list[
            discord.SelectOption
        ] = []

        for row in rows[:25]:
            channel = interaction.guild.get_channel(
                row["channel_id"]
            )

            if channel is None:
                continue

            options.append(
                discord.SelectOption(
                    label=channel.name[:100],
                    value=str(channel.id),
                    description=(
                        "Plantilla"
                        if row["is_template"]
                        else "Personalizado"
                    ),
                )
            )

        if not options:
            await interaction.response.send_message(
                "No hay canales disponibles.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Selecciona el canal:",
            view=ChannelSelectView(
                interaction.user.id,
                self.bot,
                self.associate_user_id,
                options,
            ),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Sincronizar plantilla",
        emoji="🔄",
        style=discord.ButtonStyle.success,
        row=1,
    )
    async def sync(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button

        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        try:
            created = (
                await self.bot.space_service.sync_template(
                    interaction.guild,
                    self.associate_user_id,
                    interaction.user.id,
                )
            )
        except Exception as exc:
            await interaction.followup.send(
                f"❌ `{type(exc).__name__}: "
                f"{str(exc)[:600]}`",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            "✅ Sincronización completada. "
            f"Canales agregados/recreados: **{created}**.",
            ephemeral=True,
        )


class ChannelSelect(discord.ui.Select):
    def __init__(
        self,
        parent_view: "ChannelSelectView",
        options: list[discord.SelectOption],
    ) -> None:
        self.parent_view = parent_view

        super().__init__(
            placeholder="Selecciona un canal",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        from database import (
            get_associate_channel,
        )

        channel_id = int(
            self.values[0]
        )

        row = await get_associate_channel(
            self.parent_view.bot.db,
            self.parent_view.bot.settings.society_db_schema,
            interaction.guild_id,
            channel_id,
        )

        channel = interaction.guild.get_channel(
            channel_id
        )

        if channel is None or row is None:
            await interaction.response.send_message(
                "❌ Canal no disponible.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"Canal seleccionado: {channel.mention}\n"
            "Origen: **"
            + (
                "Plantilla (protegido)"
                if row["is_template"]
                else "Personalizado"
            )
            + "**",
            view=ChannelActionView(
                interaction.user.id,
                self.parent_view.bot,
                self.parent_view.associate_user_id,
                channel_id,
                bool(row["is_template"]),
            ),
            ephemeral=True,
        )


class ChannelSelectView(OwnerBoundView):
    def __init__(
        self,
        owner_id: int,
        bot,
        associate_user_id: int,
        options: list[discord.SelectOption],
    ) -> None:
        super().__init__(owner_id)

        self.bot = bot
        self.associate_user_id = (
            associate_user_id
        )

        self.add_item(
            ChannelSelect(
                self,
                options,
            )
        )


class DeleteChannelModal(discord.ui.Modal):
    def __init__(
        self,
        view: "ChannelActionView",
        expected_name: str,
    ) -> None:
        super().__init__(
            title="Eliminar canal personalizado"
        )

        self.parent_view = view
        self.expected_name = expected_name

        self.confirmation = discord.ui.TextInput(
            label="Escribe el nombre exacto",
            placeholder=expected_name[:100],
            required=True,
            max_length=100,
        )

        self.add_item(
            self.confirmation
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if (
            self.confirmation.value
            != self.expected_name
        ):
            await interaction.response.send_message(
                "❌ Confirmación incorrecta.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        try:
            await self.parent_view.bot.space_service.delete_custom_channel(
                interaction.guild,
                self.parent_view.associate_user_id,
                interaction.user.id,
                self.parent_view.channel_id,
            )
        except Exception as exc:
            await interaction.followup.send(
                f"❌ `{type(exc).__name__}: "
                f"{str(exc)[:600]}`",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            "✅ Canal eliminado.",
            ephemeral=True,
        )


class ChannelActionView(OwnerBoundView):
    def __init__(
        self,
        owner_id: int,
        bot,
        associate_user_id: int,
        channel_id: int,
        is_template: bool,
    ) -> None:
        super().__init__(owner_id)

        self.bot = bot
        self.associate_user_id = (
            associate_user_id
        )
        self.channel_id = channel_id
        self.is_template = is_template

    @discord.ui.button(
        label="Renombrar",
        emoji="✏️",
        style=discord.ButtonStyle.primary,
    )
    async def rename(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button

        channel = interaction.guild.get_channel(
            self.channel_id
        )

        if channel is None:
            await interaction.response.send_message(
                "❌ Canal no disponible.",
                ephemeral=True,
            )
            return

        async def submit(
            modal_interaction: discord.Interaction,
            name: str,
        ) -> None:
            await modal_interaction.response.defer(
                ephemeral=True,
                thinking=True,
            )

            try:
                await self.bot.space_service.rename_channel(
                    modal_interaction.guild,
                    self.associate_user_id,
                    modal_interaction.user.id,
                    self.channel_id,
                    name,
                )
            except Exception as exc:
                await modal_interaction.followup.send(
                    f"❌ `{type(exc).__name__}: "
                    f"{str(exc)[:600]}`",
                    ephemeral=True,
                )
                return

            await modal_interaction.followup.send(
                "✅ Canal renombrado.",
                ephemeral=True,
            )

        await interaction.response.send_modal(
            NameModal(
                "Renombrar canal",
                "Nuevo nombre",
                submit,
                default=channel.name,
            )
        )

    @discord.ui.button(
        label="Eliminar",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
    )
    async def delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button

        if self.is_template:
            await interaction.response.send_message(
                "❌ Este canal pertenece a la plantilla "
                "y está protegido.",
                ephemeral=True,
            )
            return

        channel = interaction.guild.get_channel(
            self.channel_id
        )

        if channel is None:
            await interaction.response.send_message(
                "❌ Canal no disponible.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            DeleteChannelModal(
                self,
                channel.name,
            )
        )

"""Boutons de validation pour les taches TikTok.

View Discord avec boutons d'action : approuver, refuser,
regenerer script, regenerer image, modifier.
"""

from typing import Any

import discord
from discord.ext import commands

from utils.logger import logger


class ValidationView(discord.ui.View):
    """View avec boutons pour valider ou modifier un script.

    Chaque bouton a un custom_id contenant l'ID de la tache
    pour permettre le routage des interactions.

    Attributes:
        task_id: Identifiant de la tache associee.
        task_manager: Reference au gestionnaire de taches.
        bot: Reference au bot Discord.
    """

    def __init__(
        self,
        task_id: str,
        task_manager: Any,
        bot: commands.Bot,
        *args,
        **kwargs,
    ):
        """Initialise la view de validation.

        Args:
            task_id: ID de la tache a valider.
            task_manager: Instance du TaskManager.
            bot: Instance du bot Discord.
        """
        super().__init__(*args, timeout=None, **kwargs)
        self.task_id = task_id
        self.task_manager = task_manager
        self.bot = bot

    @discord.ui.button(
        label="Approuver",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="validate_approve",
    )
    async def approve_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        """Approuve la tache et archive dans #scripts.

        Args:
            button: Bouton clique.
            interaction: Interaction Discord.
        """
        await interaction.response.defer(ephemeral=True)
        try:
            success = self.task_manager.approve_task(self.task_id)
            if success:
                await interaction.followup.send(
                    "✅ Tache approuvee ! Archivee dans #scripts.",
                    ephemeral=True,
                )
                logger.info(
                    "Tache %s approuvee par %s",
                    self.task_id,
                    interaction.user,
                )
            else:
                await interaction.followup.send(
                    "❌ Impossible d'approuver la tache.",
                    ephemeral=True,
                )
        except Exception as exc:
            logger.error(
                "Erreur approbation %s: %s", self.task_id, exc
            )
            await interaction.followup.send(
                "❌ Erreur lors de l'approbation.",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Refuser",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="validate_reject",
    )
    async def reject_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        """Refuse la tache et enregistre le motif.

        Ouvre un modal pour saisir la raison du refus.

        Args:
            button: Bouton clique.
            interaction: Interaction Discord.
        """
        modal = RejectReasonModal(self.task_id, self.task_manager)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Nouveau Script",
        style=discord.ButtonStyle.primary,
        emoji="🔄",
        custom_id="validate_new_script",
    )
    async def new_script_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        """Regenere le script en conservant l'image.

        Args:
            button: Bouton clique.
            interaction: Interaction Discord.
        """
        await interaction.response.defer(ephemeral=True)
        try:
            success = self.task_manager.regenerate_script(
                self.task_id
            )
            if success:
                await interaction.followup.send(
                    "🔄 Regeneration du script lancee...",
                    ephemeral=True,
                )
                logger.info(
                    "Regeneration script %s demandee par %s",
                    self.task_id,
                    interaction.user,
                )
            else:
                await interaction.followup.send(
                    "❌ Impossible de regenerer le script.",
                    ephemeral=True,
                )
        except Exception as exc:
            logger.error(
                "Erreur regeneration script %s: %s",
                self.task_id,
                exc,
            )
            await interaction.followup.send(
                "❌ Erreur lors de la regeneration.",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Nouvelle Image",
        style=discord.ButtonStyle.secondary,
        emoji="🖼️",
        custom_id="validate_new_image",
    )
    async def new_image_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        """Regenere l'image en conservant le script.

        Args:
            button: Bouton clique.
            interaction: Interaction Discord.
        """
        await interaction.response.defer(ephemeral=True)
        try:
            success = self.task_manager.regenerate_image(
                self.task_id
            )
            if success:
                await interaction.followup.send(
                    "🖼️ Regeneration de l'image lancee...",
                    ephemeral=True,
                )
                logger.info(
                    "Regeneration image %s demandee par %s",
                    self.task_id,
                    interaction.user,
                )
            else:
                await interaction.followup.send(
                    "❌ Impossible de regenerer l'image.",
                    ephemeral=True,
                )
        except Exception as exc:
            logger.error(
                "Erreur regeneration image %s: %s",
                self.task_id,
                exc,
            )
            await interaction.followup.send(
                "❌ Erreur lors de la regeneration.",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Modifier",
        style=discord.ButtonStyle.gray,
        emoji="✏️",
        custom_id="validate_modify",
    )
    async def modify_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        """Ouvre un thread pour modification du script.

        Args:
            button: Bouton clique.
            interaction: Interaction Discord.
        """
        await interaction.response.defer(ephemeral=True)
        try:
            thread = await interaction.channel.create_thread(
                name=f"Modification {self.task_id}",
                type=discord.ChannelType.public_thread,
                reason="Modification de script demandee",
            )
            await thread.send(
                f"✏️ Modification du script `{self.task_id}`\n"
                f"Demande par {interaction.user.mention}\n\n"
                "Decrivez les modifications souhaitees :"
            )
            await interaction.followup.send(
                f"Thread cree : {thread.mention}",
                ephemeral=True,
            )
            logger.info(
                "Thread modification %s cree par %s",
                self.task_id,
                interaction.user,
            )
        except Exception as exc:
            logger.error(
                "Erreur creation thread %s: %s",
                self.task_id,
                exc,
            )
            await interaction.followup.send(
                "❌ Erreur lors de la creation du thread.",
                ephemeral=True,
            )


class RejectReasonModal(discord.ui.Modal):
    """Modal pour saisir le motif de refus."""

    def __init__(
        self,
        task_id: str,
        task_manager: Any,
    ) -> None:
        """Initialise le modal de refus.

        Args:
            task_id: ID de la tache a refuser.
            task_manager: Instance du TaskManager.
        """
        super().__init__(title="Motif du refus")
        self.task_id = task_id
        self.task_manager = task_manager

        self.reason_input = discord.ui.TextInput(
            label="Raison du refus",
            style=discord.TextStyle.paragraph,
            placeholder=(
                "Expliquez pourquoi ce script est refuse..."
            ),
            required=True,
            max_length=500,
        )
        self.add_item(self.reason_input)

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Traite la soumission du motif de refus.

        Args:
            interaction: Interaction Discord.
        """
        await interaction.response.defer(ephemeral=True)
        reason = self.reason_input.value
        try:
            success = self.task_manager.reject_task(
                self.task_id,
                reason=reason,
            )
            if success:
                await interaction.followup.send(
                    f"❌ Tache refusee : {reason}",
                    ephemeral=True,
                )
                logger.info(
                    "Tache %s refusee par %s: %s",
                    self.task_id,
                    interaction.user,
                    reason,
                )
            else:
                await interaction.followup.send(
                    "❌ Impossible de refuser la tache.",
                    ephemeral=True,
                )
        except Exception as exc:
            logger.error("Erreur refus %s: %s", self.task_id, exc)
            await interaction.followup.send(
                "❌ Erreur lors du refus.",
                ephemeral=True,
            )

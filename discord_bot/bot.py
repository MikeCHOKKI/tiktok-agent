"""Client Discord pour le tiktok-agent.

Configure le bot Discord, charge les commandes et les views,
et maintient les references aux differents gestionnaires.
"""

from typing import Any, Optional

import discord
from discord.ext import commands

from agent.scheduler import TaskScheduler
from agent.script_generator import ScriptGenerator
from agent.state_store import StateStore
from agent.task_manager import TaskManager
from config import Settings
from discord_bot.channels import ensure_channels_exist
from utils.logger import logger


class TikTokBot(commands.Bot):
    """Bot Discord pour la gestion de l'agent TikTok.

    Points d'entree principal pour les interactions utilisateur.
    Maintient les references a tous les sous-systemes.

    Attributes:
        settings: Configuration du projet.
        state_store: Store de persistance.
        task_manager: Gestionnaire de taches.
        script_generator: Generateur de scripts LLM.
        scheduler: Planificateur de taches.
    """

    def __init__(self, settings: Settings, *args, **kwargs):
        """Initialise le bot Discord.

        Args:
            settings: Configuration du projet.
        """
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            *args,
            **kwargs,
        )

        self.settings = settings
        self.state_store: Optional[StateStore] = None
        self.task_manager: Optional[TaskManager] = None
        self.script_generator: Optional[ScriptGenerator] = None
        self.image_router: Optional[Any] = None
        self.scheduler: Optional[TaskScheduler] = None

    async def setup_hook(self) -> None:
        """Hook d'initialisation du bot.

        Charge les commandes et synchronise l'arbre de commandes.
        Appele automatiquement par discord.py au demarrage.
        """
        logger.info("Initialisation du bot...")

        from discord_bot.commands import register_commands

        await register_commands(self)

        logger.info("Commandes enregistrees")

    async def on_ready(self) -> None:
        """Evenement declenche quand le bot est connecte et pre.

        Synchronise les commandes et verifie les channels.
        """
        logger.info(
            "Bot connecte en tant que %s (ID: %s)",
            self.user,
            self.user.id,
        )

        try:
            synced = await self.tree.sync()
            logger.info(
                "%d commande(s) slash synchronisee(s)",
                len(synced),
            )
        except Exception as exc:
            logger.warning(
                "Echec synchronisation commandes: %s", exc
            )

        await ensure_channels_exist(self)

        guild = self.get_guild(self.settings.DISCORD_GUILD_ID)
        if guild:
            logger.info(
                "Connecte sur le serveur: %s (ID: %d)",
                guild.name,
                guild.id,
            )

        # Message de bienvenue dans le channel commandes
        try:
            channel = self.get_channel(
                self.settings.CHANNEL_COMMANDES
            )
            if channel:
                await channel.send(
                    "🤖 **Agent TikTok prete !** "
                    "Tape `/aide` pour voir les commandes disponibles."
                )
                logger.info("Message de bienvenue envoye dans #commandes")
        except Exception as exc:
            logger.warning(
                "Impossible d'envoyer le message de bienvenue: %s",
                exc,
            )

    async def on_message(self, message: discord.Message) -> None:
        """Gestionnaire de messages pour le chat-agent.

        Dans le channel #chat-agent, répond aux messages utilisateur
        via le LLM en mode conseiller stratégique.
        Ignore les commandes et les messages des bots.

        Args:
            message: Message Discord reçu.
        """
        if message.author.bot:
            return

        if message.channel.id != self.settings.CHANNEL_CHAT_AGENT:
            return

        if message.content.startswith("/"):
            return

        if not self.script_generator:
            logger.warning(
                "ScriptGenerator non disponible pour le chat"
            )
            return

        logger.info(
            "Chat message de %s: %s...",
            message.author,
            message.content[:80],
        )

        try:
            niche = "Tech & IA"
            recent_tasks = []
            current_trends = None

            if self.state_store:
                config = self.state_store.get_config()
                niche = config.get("niche", "Tech & IA")

                tasks = self.state_store.get_tasks()
                recent_tasks = tasks[-5:] if tasks else []

                current_trends = self.state_store.get_cached_trends()

            async with message.channel.typing():
                response = await self.script_generator.chat_response(
                    user_message=message.content,
                    context={
                        "niche": niche,
                        "recent_tasks": recent_tasks,
                        "current_trends": current_trends,
                    },
                )
                await message.reply(
                    response, mention_author=False
                )
                logger.info("Reponse chat envoyee a %s", message.author)

        except Exception as exc:
            logger.error(
                "Erreur chat_response pour %s: %s",
                message.author,
                exc,
            )
            await message.reply(
                "Desole, je rencontre un probleme technique. "
                "Reessaye dans quelques instants.",
                mention_author=False,
            )

    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: discord.app_commands.Command,
    ) -> None:
        """Loggue la completion d'une commande.

        Args:
            interaction: Interaction terminee.
            command: Commande executee.
        """
        logger.info(
            "Commande %s executee par %s",
            command.name,
            interaction.user,
        )

    async def on_error(
        self,
        event_method: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Gestionnaire global d'erreurs.

        Args:
            event_method: Methode d'evenement en erreur.
        """
        logger.error(
            "Erreur evenement %s: args=%s kwargs=%s",
            event_method,
            args,
            kwargs,
        )

    def run_bot(self) -> None:
        """Demarre le bot avec le token configure."""
        token = self.settings.DISCORD_BOT_TOKEN
        if not token:
            raise ValueError("DISCORD_BOT_TOKEN non configure")

        logger.info("Demarrage du bot Discord...")
        self.run(token)

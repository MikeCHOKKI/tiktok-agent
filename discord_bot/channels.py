"""Gestion des canaux Discord pour le tiktok-agent.

Definit les noms symboliques des channels et fournit
des fonctions de routage par identifiant.
"""

from typing import Optional

import discord
from discord.ext import commands

from utils.logger import logger

# Noms symboliques des channels
COMMANDES = "commandes"
VALIDATION = "validation"
SCRIPTS = "scripts"
TENDANCES = "tendances"
RAPPORTS = "rapports"
CHAT_AGENT = "chat-agent"

# Mapping nom symbolique -> attribut Settings
CHANNEL_CONFIG_MAP = {
    COMMANDES: "CHANNEL_COMMANDES",
    VALIDATION: "CHANNEL_VALIDATION",
    SCRIPTS: "CHANNEL_SCRIPTS",
    TENDANCES: "CHANNEL_TENDANCES",
    RAPPORTS: "CHANNEL_RAPPORTS",
    CHAT_AGENT: "CHANNEL_CHAT_AGENT",
}


async def get_channel_by_name(
    bot: commands.Bot,
    channel_name: str,
) -> Optional[discord.TextChannel]:
    """Retourne l'objet channel a partir de son nom symbolique.

    Args:
        bot: Instance du bot Discord.
        channel_name: Nom symbolique du channel (ex: 'validation').

    Returns:
        Objet TextChannel ou None si introuvable.
    """
    config_attr = CHANNEL_CONFIG_MAP.get(channel_name)
    if not config_attr:
        logger.warning("Nom de channel inconnu: %s", channel_name)
        return None

    channel_id = getattr(bot.settings, config_attr, 0)
    if not channel_id:
        logger.warning(
            "Channel ID non configure pour: %s", channel_name
        )
        return None

    channel = bot.get_channel(channel_id)
    if not channel:
        logger.warning(
            "Channel introuvable sur le serveur: %s (%d)",
            channel_name,
            channel_id,
        )
        return None

    return channel


async def ensure_channels_exist(
    bot: commands.Bot,
) -> None:
    """Verifie que tous les channels configures existent.

    Parcourt tous les channels definis dans la configuration
    et logge un avertissement pour chaque channel manquant.

    Args:
        bot: Instance du bot Discord.
    """
    guild = bot.get_guild(bot.settings.DISCORD_GUILD_ID)
    if not guild:
        logger.error(
            "Guild introuvable: %d", bot.settings.DISCORD_GUILD_ID
        )
        return

    missing = []
    for channel_name, config_attr in CHANNEL_CONFIG_MAP.items():
        channel_id = getattr(bot.settings, config_attr, 0)
        if not channel_id:
            missing.append(f"{channel_name} (ID non configure)")
            continue

        channel = guild.get_channel(channel_id)
        if not channel:
            missing.append(f"{channel_name} (ID {channel_id})")

    if missing:
        logger.warning(
            "Channels manquants ou non configures:\n%s",
            "\n".join(f"  - {m}" for m in missing),
        )
    else:
        logger.info("Tous les channels Discord sont configures")

"""Slash commands du bot Discord pour tiktok-agent.

Toutes les commandes disponibles :
/generer, /tendances, /niche, /statut, /rapport,
/planifier, /historique, /config, /aide

Chaque callback est défini au niveau module pour permettre
l'import direct par les tests.  register_commands() les câble
dans l'arbre du bot.
"""

import datetime
from typing import Any, Dict, Optional

import discord
from discord import app_commands

from agent.scheduler import TaskScheduler
from agent.script_generator import ScriptGenerator
from agent.state_store import StateStore
from agent.task_manager import TaskManager
from discord_bot.buttons import ValidationView
from discord_bot.channels import get_channel_by_name
from discord_bot.notifier import send_report, send_simple_message, send_validation
from utils.logger import logger


# ---------------------------------------------------------------------------
# Callbacks des commandes (module-level pour testabilité)
# ---------------------------------------------------------------------------


@app_commands.describe(
    sujet="Sujet de la video TikTok",
    niche="Niche de contenu (defaut: config actuelle)",
)
async def generer(
    interaction: discord.Interaction,
    sujet: str,
    niche: Optional[str] = None,
) -> None:
    """Genere un script TikTok pour le sujet donne.

    Integre les tendances recentes dans le prompt si disponibles.

    Args:
        interaction: Interaction Discord.
        sujet: Sujet de la video.
        niche: Niche de contenu (optionnelle).
    """
    bot = interaction.client
    await interaction.response.defer()
    logger.info("Commande /generer: sujet=%s", sujet)

    task_manager: TaskManager = bot.task_manager
    config = bot.state_store.get_config()
    niche = niche or config.get("niche", "Tech & IA")
    style = config.get("style", "educatif")

    # Enrichir le sujet avec les tendances recentes si disponibles
    enriched_subject = sujet
    if hasattr(bot, "trend_analyzer") and bot.trend_analyzer:
        try:
            trends = bot.trend_analyzer.analyze(niche=niche)
            suggested = trends.get("suggested_topics", [])
            if suggested:
                trending = suggested[0]["title"]
                enriched_subject = f"{sujet} (en lien avec : {trending})"
                logger.info("Sujet enrichi avec tendance: %s", trending)
        except (RuntimeError, OSError) as exc:
            logger.warning(
                "Impossible d'enrichir avec les tendances: %s", exc
            )

    try:
        task = task_manager.create_task(
            subject=enriched_subject,
            niche=niche,
            style=style,
        )

        script_data = await task_manager.generate_script(
            task["task_id"]
        )

        if not script_data:
            await interaction.followup.send(
                "❌ Erreur lors de la generation du script. "
                "Consultez les logs.",
            )
            return

        success = await send_validation(
            bot=bot,
            task=task,
            script_data=script_data,
            image_path=None,
        )

        if success:
            await interaction.followup.send(
                f"✅ Script genere avec succes !\n"
                f"Tache: `{task['task_id']}`\n"
                f"Sujet: {sujet}\n"
                f"Niche: {niche}\n"
                f"Rendez-vous dans le channel #validation.",
            )
        else:
            await interaction.followup.send(
                "✅ Script genere mais impossible "
                "d'envoyer en validation.",
            )

    except (ValueError, RuntimeError) as exc:
        logger.error("Erreur commande /generer: %s", exc)
        await interaction.followup.send(
            f"❌ Erreur: {str(exc)[:200]}",
        )


async def tendances(
    interaction: discord.Interaction,
) -> None:
    """Analyse les tendances via TrendAnalyzer et poste dans #tendances.

    Args:
        interaction: Interaction Discord.
    """
    bot = interaction.client
    await interaction.response.defer()
    logger.info("Commande /tendances")

    if not hasattr(bot, "trend_analyzer") or not bot.trend_analyzer:
        await interaction.followup.send(
            "❌ Analyseur de tendances non configure.",
        )
        return

    try:
        config = bot.state_store.get_config()
        niche = config.get("niche", "Tech & IA")
        trends = bot.trend_analyzer.analyze(niche=niche)

        if hasattr(bot, "notifier") and hasattr(bot.notifier, "send_trends"):
            await bot.notifier.send_trends(trends)
        else:
            # Fallback : utiliser le notifier du module
            from discord_bot.notifier import send_trends as st
            await st(bot, trends)

        total = len(trends.get("general_trends", []))
        niche_count = len(trends.get("niche_trends", []))
        await interaction.followup.send(
            f"📈 Analyse des tendances terminee !\n"
            f"**{total}** tendances generales, "
            f"**{niche_count}** tendances niche.\n"
            f"Resultats dans #tendances.",
        )

    except (RuntimeError, OSError) as exc:
        logger.error("Erreur commande /tendances: %s", exc)
        await interaction.followup.send(
            f"❌ Erreur analyse tendances: {str(exc)[:200]}",
        )


@app_commands.describe(
    niche="Niche de contenu (ex: Tech, Cuisine, Sport)",
)
async def niche_cmd(
    interaction: discord.Interaction,
    niche: str,
) -> None:
    """Definit ou change la niche de contenu.

    Args:
        interaction: Interaction Discord.
        niche: Nouvelle niche de contenu.
    """
    bot = interaction.client
    await interaction.response.defer()
    logger.info("Commande /niche: %s", niche)

    state_store: StateStore = bot.state_store
    state_store.update_config("niche", niche)

    await interaction.followup.send(
        f"✅ Niche mise a jour : **{niche}**\n"
        "Tous les nouveaux scripts utiliseront cette niche "
        "par defaut.",
    )


async def statut(
    interaction: discord.Interaction,
) -> None:
    """Affiche le statut de la file de taches et les jobs planifies.

    Args:
        interaction: Interaction Discord.
    """
    bot = interaction.client
    await interaction.response.defer()
    logger.info("Commande /statut")

    task_manager: TaskManager = bot.task_manager
    summary = task_manager.get_queue_summary()

    # Infos scheduler
    scheduler_info = ""
    if hasattr(bot, "scheduler") and bot.scheduler:
        scheduler_info = "\n\n" + bot.scheduler.get_jobs_info()

    # Infos tendances
    trends_info = ""
    if hasattr(bot, "trend_analyzer") and bot.trend_analyzer:
        cache_status = "en cache" if bot.trend_analyzer._cached_result else "vide"
        trends_info = f"\n\n📈 Cache tendances: {cache_status}"

    await interaction.followup.send(
        summary + scheduler_info + trends_info
    )


async def rapport(
    interaction: discord.Interaction,
) -> None:
    """Genere et envoie un rapport via ReportBuilder.

    Args:
        interaction: Interaction Discord.
    """
    bot = interaction.client
    await interaction.response.defer()
    logger.info("Commande /rapport")

    if not hasattr(bot, "report_builder") or not bot.report_builder:
        # Fallback sur l'ancien comportement
        state_store: StateStore = bot.state_store
        stats = state_store.get_weekly_stats()
        config_state = state_store.get_config()

        now = datetime.datetime.now()
        week_key = now.strftime("%Y-W%W")
        week_stats = stats.get(week_key, {
            "approved": 0,
            "rejected": 0,
            "total": 0,
        })

        report_data = {
            "period": f"Semaine {week_key}",
            "stats": week_stats,
            "extra": {
                "Niche": config_state.get("niche", "?"),
                "Style": config_state.get("style", "?"),
                "Generation auto": (
                    "Oui" if config_state.get("auto_generate") else "Non"
                ),
            },
        }

        success = await send_report(bot, report_data)
        if success:
            await interaction.followup.send(
                "📊 Rapport envoye dans #rapports.",
            )
        else:
            await interaction.followup.send(
                "❌ Erreur lors de l'envoi du rapport.",
            )
        return

    try:
        report = bot.report_builder.build_weekly_report()

        if hasattr(bot, "notifier") and hasattr(bot.notifier, "send_report"):
            await bot.notifier.send_report(report)
        else:
            from discord_bot.notifier import send_report as sr
            await sr(bot, report)

        week = report.get("week", "?")
        total = report.get("production", {}).get("total_generated", 0)
        await interaction.followup.send(
            f"📊 Rapport de la semaine {week} envoye dans #rapports.\n"
            f"**{total}** taches generees cette semaine.",
        )

    except (RuntimeError, OSError) as exc:
        logger.error("Erreur commande /rapport: %s", exc)
        await interaction.followup.send(
            f"❌ Erreur generation rapport: {str(exc)[:200]}",
        )


@app_commands.describe(
    sujet="Sujet de la video",
    jour="Jour (AAAA-MM-JJ)",
    heure="Heure (HH:MM, format 24h)",
)
async def planifier(
    interaction: discord.Interaction,
    sujet: str,
    jour: str,
    heure: str,
) -> None:
    """Planifie une generation a une date/heure precise.

    Args:
        interaction: Interaction Discord.
        sujet: Sujet de la video.
        jour: Date au format AAAA-MM-JJ.
        heure: Heure au format HH:MM.
    """
    bot = interaction.client
    await interaction.response.defer()
    logger.info("Commande /planifier: sujet=%s jour=%s heure=%s", sujet, jour, heure)

    try:
        datetime.datetime.strptime(jour, "%Y-%m-%d")
    except ValueError:
        await interaction.followup.send(
            "❌ Format de date invalide. Utilisez AAAA-MM-JJ "
            "(ex: 2026-06-22).",
        )
        return

    try:
        datetime.datetime.strptime(heure, "%H:%M")
    except ValueError:
        await interaction.followup.send(
            "❌ Format d'heure invalide. Utilisez HH:MM "
            "(ex: 14:30).",
        )
        return

    task_manager: TaskManager = bot.task_manager
    config_state = bot.state_store.get_config()

    task = task_manager.create_task(
        subject=sujet,
        niche=config_state.get("niche", "Tech & IA"),
        style=config_state.get("style", "educatif"),
    )

    await interaction.followup.send(
        f"📅 Generation planifiee !\n"
        f"Tache: `{task['task_id']}`\n"
        f"Sujet: {sujet}\n"
        f"Date: {jour} à {heure}\n"
        "La generation automatique se chargera du traitement.",
    )


@app_commands.describe(
    n="Nombre de scripts a afficher (defaut: 10)",
)
async def historique(
    interaction: discord.Interaction,
    n: int = 10,
) -> None:
    """Affiche l'historique des derniers scripts.

    Args:
        interaction: Interaction Discord.
        n: Nombre de scripts a afficher.
    """
    bot = interaction.client
    await interaction.response.defer()
    logger.info("Commande /historique: n=%d", n)

    n = max(1, min(n, 50))
    task_manager: TaskManager = bot.task_manager
    history = task_manager.get_history(n)

    if not history:
        await interaction.followup.send(
            "Aucun historique pour le moment."
        )
        return

    lines = [
        "**━ Historique "
        f"({len(history)} dernieres taches) ━**"
    ]
    for task in history:
        task_id = task.get("task_id", "?")
        subject = task.get("subject", "?")
        status = task.get("status", "?")
        created = task.get("created_at", "?")[:10]

        status_emoji = {
            "approved": "✅",
            "rejected": "❌",
            "awaiting_validation": "🔍",
            "generating": "⚙️",
            "pending": "📝",
            "error": "⚠️",
        }.get(status, "❓")

        lines.append(
            f"{status_emoji} `{task_id}` | {created} | "
            f"{subject[:50]} | {status}"
        )

    await interaction.followup.send("\n".join(lines))


@app_commands.describe(
    parametre=(
        "Parametre: niche, style, langue, "
        "auto_generate, watermark_text"
    ),
    valeur="Nouvelle valeur",
)
async def config_cmd(
    interaction: discord.Interaction,
    parametre: str,
    valeur: str,
) -> None:
    """Modifie un parametre de configuration.

    Args:
        interaction: Interaction Discord.
        parametre: Nom du parametre.
        valeur: Nouvelle valeur.
    """
    bot = interaction.client
    await interaction.response.defer()
    logger.info("Commande /config: %s=%s", parametre, valeur)

    allowed_params = [
        "niche",
        "style",
        "langue",
        "watermark_text",
    ]
    bool_params = ["auto_generate"]

    if (
        parametre not in allowed_params
        and parametre not in bool_params
    ):
        await interaction.followup.send(
            f"❌ Parametre inconnu: `{parametre}`\n"
            "Disponibles: "
            + ", ".join(allowed_params + bool_params),
        )
        return

    state_store: StateStore = bot.state_store

    if parametre in bool_params:
        normalized = valeur.lower() in (
            "true", "oui", "1", "yes"
        )
        state_store.update_config(parametre, normalized)
    else:
        state_store.update_config(parametre, valeur)

    await interaction.followup.send(
        f"✅ Configuration mise a jour :\n"
        f"`{parametre}` = `{valeur}`",
    )


async def aide(
    interaction: discord.Interaction,
) -> None:
    """Affiche l'aide complete du bot.

    Args:
        interaction: Interaction Discord.
    """
    bot = interaction.client
    await interaction.response.defer()
    logger.info("Commande /aide")

    embed = discord.Embed(
        title="🤖 tiktok-agent - Aide",
        description=(
            "Agent IA autonome pour la generation de "
            "contenu TikTok.\n\n"
            "**Commandes disponibles :**"
        ),
        color=discord.Color.purple(),
    )

    commands_info = [
        (
            "/generer <sujet> [niche]",
            "Genere un script TikTok + image pour un sujet. "
            "La niche est optionnelle (utilise la config).",
        ),
        (
            "/tendances",
            "Analyse les tendances TikTok immediatement.",
        ),
        (
            "/niche <niche>",
            "Change la niche de contenu par defaut "
            "(ex: Tech, Cuisine, Sport).",
        ),
        (
            "/statut",
            "Affiche la file de taches et les statistiques.",
        ),
        (
            "/rapport",
            "Genere un rapport d'activite immediat.",
        ),
        (
            "/planifier <sujet> <jour> <heure>",
            "Planifie une generation. "
            "Jour: AAAA-MM-JJ, Heure: HH:MM.",
        ),
        (
            "/historique [n]",
            "Affiche les n derniers scripts "
            "(defaut: 10, max: 50).",
        ),
        (
            "/config <parametre> <valeur>",
            "Modifie un parametre (niche, style, langue, "
            "auto_generate, watermark_text).",
        ),
        (
            "/aide",
            "Affiche ce message.",
        ),
    ]

    for name, desc in commands_info:
        embed.add_field(name=name, value=desc, inline=False)

    embed.set_footer(
        text="tiktok-agent v2.0 | "
        "Tapez /commandes dans #commandes"
    )

    await interaction.followup.send(embed=embed)


# ---------------------------------------------------------------------------
# Enregistrement dans l'arbre de commandes Discord
# ---------------------------------------------------------------------------


async def register_commands(bot: discord.ext.commands.Bot) -> None:
    """Enregistre toutes les slash commands sur l'arbre du bot.

    Args:
        bot: Instance du bot Discord.
    """
    tree = bot.tree

    tree.command(
        name="generer",
        description="Genere un script TikTok + image pour un sujet",
    )(generer)

    tree.command(
        name="tendances",
        description="Declenche une analyse immediate des tendances TikTok",
    )(tendances)

    tree.command(
        name="niche",
        description="Change la niche de contenu par defaut",
    )(niche_cmd)

    tree.command(
        name="statut",
        description="Affiche la file de taches et les statistiques",
    )(statut)

    tree.command(
        name="rapport",
        description="Genere un rapport d'activite immediat",
    )(rapport)

    tree.command(
        name="planifier",
        description="Planifie une generation de script",
    )(planifier)

    tree.command(
        name="historique",
        description="Affiche les derniers scripts generes",
    )(historique)

    tree.command(
        name="config",
        description="Modifie un parametre de configuration",
    )(config_cmd)

    tree.command(
        name="aide",
        description="Affiche la liste de toutes les commandes disponibles",
    )(aide)

#!/usr/bin/env python3
"""Point d'entree principal du tiktok-agent (Phase 3 - Autonome).

Initialise tous les sous-systemes et demarre le bot Discord
ainsi que le planificateur de taches automatise.

Nouveautes Phase 3 :
- TrendAnalyzer (analyse tendances Google + YouTube)
- ReportBuilder (rapports hebdomadaires structures)
- Jobs scheduler reels (generation auto, nettoyage, rappels)

Usage:
    python app.py

Variables d'environnement requises (fichier .env):
    HF_TOKEN, DISCORD_BOT_TOKEN, DISCORD_GUILD_ID,
    CHANNEL_COMMANDES, CHANNEL_VALIDATION, CHANNEL_SCRIPTS,
    CHANNEL_TENDANCES, CHANNEL_RAPPORTS, CHANNEL_CHAT_AGENT
"""

import asyncio
import os
import signal
import sys
from typing import Any, Dict

from agent.report_builder import ReportBuilder
from agent.scheduler import TaskScheduler
from agent.script_generator import ScriptGenerator
from agent.state_store import StateStore
from agent.task_manager import TaskManager
from agent.trend_analyzer import TrendAnalyzer
from config import Settings
from discord_bot.bot import TikTokBot
from image.router import ImageRouter
from utils.logger import logger

# Nom du fichier d'etat persistant
STATE_FILE = "state.json"


def initialize_systems() -> Dict[str, Any]:
    """Initialise tous les sous-systemes du projet.

    Ordre d'initialisation (Phase 3) :
    1. Settings (configuration)
    2. StateStore (persistance)
    3. ScriptGenerator (LLM)
    4. ImageRouter (pipeline image, optionnel)
    5. TaskManager (gestion taches)
    6. TrendAnalyzer (analyse tendances multi-sources)
    7. ReportBuilder (rapports hebdomadaires)
    8. TaskScheduler (planification automatique)

    Returns:
        Dict avec les references aux systemes initialises.

    Raises:
        ValueError: Si un composant obligatoire est mal configure.
        RuntimeError: Si l'initialisation d'un composant critique echoue.
    """
    logger.info("=" * 50)
    logger.info("Initialisation du tiktok-agent (Phase 3 - Autonome)")
    logger.info("=" * 50)

    # 1. Configuration
    try:
        settings = Settings()
        settings.validate()
        logger.info("Configuration validee")
    except ValueError as exc:
        logger.critical("Erreur de configuration: %s", exc)
        raise

    # 2. State Store (Phase 4: avec persistance HF Dataset)
    try:
        hf_dataset_name = os.getenv("HF_DATASET_NAME", "")
        state_store = StateStore(
            file_path=STATE_FILE,
            hf_dataset_name=hf_dataset_name,
            hf_token=settings.HF_TOKEN,
        )
        logger.info("StateStore initialise: %s", STATE_FILE)

        # Tentative de restauration depuis HF Dataset
        if hf_dataset_name and state_store.hf_store:
            try:
                loop = asyncio.get_event_loop()
                restored = loop.run_until_complete(
                    state_store.hf_store.pull_state()
                )
                if restored and restored.get("tasks"):
                    tasks = restored["tasks"]
                    existing = state_store.get_tasks()
                    # Restaure uniquement si le fichier local est vide
                    if not existing:
                        for task in tasks:
                            state_store.add_task(task)
                        logger.info(
                            "%d taches restaurees depuis HF Dataset",
                            len(tasks),
                        )
                    else:
                        logger.info(
                            "Etat local present, restauration HF ignoree "
                            "(%d taches existantes)",
                            len(existing),
                        )
            except RuntimeError as exc:
                logger.warning(
                    "Restauration HF Dataset non disponible: %s", exc
                )
    except Exception as exc:
        logger.critical("Erreur StateStore: %s", exc)
        raise RuntimeError("Echec initialisation StateStore") from exc

    # 3. Script Generator
    try:
        script_generator = ScriptGenerator(hf_token=settings.HF_TOKEN)
        logger.info(
            "ScriptGenerator initialise (modele: %s)",
            script_generator.model_id,
        )
    except ValueError as exc:
        logger.critical("Erreur ScriptGenerator: %s", exc)
        raise

    # 4. Pipeline Image
    try:
        image_router = ImageRouter(settings=settings)
        image_router.initialize()
        logger.info("ImageRouter initialise avec pipeline image")
    except ValueError as exc:
        image_router = None
        logger.warning("Pipeline image non disponible: %s", exc)

    # 5. Task Manager
    task_manager = TaskManager(
        state_store=state_store,
        script_generator=script_generator,
        image_router=image_router,
    )
    logger.info("TaskManager initialise")

    # 6. Trend Analyzer (Phase 3)
    try:
        trend_analyzer = TrendAnalyzer(
            google_trends_url=settings.GOOGLE_TRENDS_RSS_URL,
            youtube_api_key=settings.YOUTUBE_API_KEY,
            niche_urls=settings.FEED_NICHE_URLS,
        )
        logger.info(
            "TrendAnalyzer initialise (Google Trends + %s)",
            "YouTube API" if settings.YOUTUBE_API_KEY else "pas de YouTube API",
        )
    except Exception as exc:
        trend_analyzer = None
        logger.warning("TrendAnalyzer non disponible: %s", exc)

    # 7. Report Builder (Phase 3)
    try:
        report_builder = ReportBuilder(
            state_store=state_store,
            trend_analyzer=trend_analyzer,
        )
        logger.info("ReportBuilder initialise")
    except Exception as exc:
        report_builder = None
        logger.warning("ReportBuilder non disponible: %s", exc)

    # 8. Scheduler
    try:
        scheduler = TaskScheduler()
        scheduler.setup(
            trend_analyzer=trend_analyzer,
            notifier_module=None,  # Sera injecte apres creation du bot
            task_manager=task_manager,
            report_builder=report_builder,
            settings=settings,
        )
        logger.info("TaskScheduler initialise avec dependances")
    except Exception as exc:
        scheduler = None
        logger.warning("TaskScheduler non disponible: %s", exc)

    return {
        "settings": settings,
        "state_store": state_store,
        "script_generator": script_generator,
        "image_router": image_router,
        "task_manager": task_manager,
        "trend_analyzer": trend_analyzer,
        "report_builder": report_builder,
        "scheduler": scheduler,
    }


def setup_signal_handlers(
    bot: TikTokBot, state_store: StateStore
) -> None:
    """Configure les gestionnaires de signaux pour un arret propre.

    Phase 4 : ajout de la sauvegarde finale et du push HF Dataset
    avant l'arret.

    Args:
        bot: Instance du bot Discord.
        state_store: Store de persistance pour sauvegarde finale.
    """

    def signal_handler(sig: int, frame: Any) -> None:
        """Gestionnaire d'arret avec sauvegarde finale.

        Args:
            sig: Signal recu.
            frame: Frame d'execution courante.
        """
        signal_name = signal.Signals(sig).name
        logger.info("Signal %s recu. Arret en cours...", signal_name)

        try:
            # 1. Arret du scheduler
            if bot.scheduler:
                bot.scheduler.stop()
                logger.info("Scheduler arrete")

            # 2. Sauvegarde finale de l'etat
            state_store.save()
            logger.info("Etat sauvegarde avant arret")

            # 3. Push HF Dataset si configure
            if state_store.hf_store:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(
                        state_store.hf_store.push_state(
                            state_store._data
                        )
                    )
                    loop.close()
                    logger.info("HF Dataset push final effectue")
                except Exception as exc:
                    logger.warning(
                        "Push final HF Dataset echoue: %s", exc
                    )

        except Exception as exc:
            logger.error("Erreur lors de l'arret: %s", exc)

        logger.info("tiktok-agent termine proprement")
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    logger.info("Gestionnaires de signaux installes (avec sauvegarde)")


def main() -> None:
    """Point d'entree principal.

    Initialise tout, demarre le scheduler, puis lance le bot.
    """
    try:
        systems = initialize_systems()
    except (ValueError, RuntimeError) as exc:
        logger.critical("Arret: echec initialisation - %s", exc)
        sys.exit(1)

    settings = systems["settings"]
    state_store = systems["state_store"]
    script_generator = systems["script_generator"]
    image_router = systems["image_router"]
    task_manager = systems["task_manager"]
    trend_analyzer = systems["trend_analyzer"]
    report_builder = systems["report_builder"]
    scheduler = systems["scheduler"]

    # Creation du bot
    bot = TikTokBot(settings=settings)
    bot.state_store = state_store
    bot.task_manager = task_manager
    bot.script_generator = script_generator
    bot.image_router = image_router
    bot.scheduler = scheduler
    bot.trend_analyzer = trend_analyzer
    bot.report_builder = report_builder

    # Injection du bot comme notifier dans le scheduler
    # (permet d'envoyer des messages Discord depuis les callbacks)
    if scheduler:
        try:
            import discord_bot.notifier as notifier_module
            scheduler.notifier = notifier_module
            scheduler.bot = bot
            logger.info("Notifier injecte dans le scheduler")
        except ImportError as exc:
            logger.warning("Module notifier non disponible: %s", exc)

    # Demarrage du scheduler (apres la creation du bot pour
    # que les dependances Discord soient disponibles)
    if scheduler:
        try:
            config = state_store.get_config()
            hours = config.get("schedule_hours", [6, 18])
            logger.info("Demarrage du scheduler (heures: %s)...", hours)
            scheduler.start()
        except Exception as exc:
            logger.error("Erreur demarrage scheduler: %s", exc)

    # Verification d'integrite des dossiers
    try:
        temp_dir = "/tmp/tiktok-agent/"
        os.makedirs(temp_dir, exist_ok=True)
        logger.info("Repertoire temporaire verifie: %s", temp_dir)

        # Verification des modules critiques
        modules_ok = 0
        modules_total = 0
        for module_name in [
            "agent.script_generator",
            "agent.task_manager",
            "agent.state_store",
            "agent.trend_analyzer",
            "agent.report_builder",
            "agent.scheduler",
            "image.router",
            "discord_bot.bot",
            "discord_bot.commands",
            "discord_bot.notifier",
            "discord_bot.buttons",
            "discord_bot.channels",
            "utils.logger",
            "utils.helpers",
            "config",
        ]:
            modules_total += 1
            try:
                __import__(module_name)
                modules_ok += 1
            except ImportError as exc:
                logger.warning(
                    "Module non disponible: %s (%s)",
                    module_name,
                    exc,
                )

        logger.info(
            "Integrite modules: %d/%d OK",
            modules_ok,
            modules_total,
        )
    except OSError as exc:
        logger.warning(
            "Verification d'integrité partielle: %s", exc
        )

    # Signaux (Phase 4: avec sauvegarde finale)
    setup_signal_handlers(bot, state_store)

    logger.info("=" * 50)
    logger.info("tiktok-agent Phase 3 pret. Demarrage du bot Discord...")
    logger.info("=" * 50)

    # Demarrage du bot (bloquant)
    bot.run_bot()


if __name__ == "__main__":
    main()

"""Planificateur de taches pour le tiktok-agent.

Utilise APScheduler pour gerer:
- Generation automatique toutes les 12h (6h et 18h UTC)
- Rapport hebdomadaire (lundi 8h UTC)
- Nettoyage du repertoire temporaire (toutes les 2h)
- Verification des taches obsoletes (toutes les 30min)
- Analyse immediate des tendances (declenchee manuellement)
"""

import os
import shutil
import time
from typing import Any, Callable, Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pytz import UTC

from utils.logger import logger

TEMP_DIR = "/tmp/tiktok-agent/"
STALE_TASK_HOURS = 24
CLEANUP_AGE_SECONDS = 7200  # 2h


class TaskScheduler:
    """Planificateur central des taches automatiques.

    Attributes:
        scheduler: Instance APScheduler asynchrone.
        _started: Flag indiquant si le scheduler tourne.
        trend_analyzer: Analyseur de tendances (injecté).
        notifier: Notification Discord (injecté).
        task_manager: Gestionnaire de taches (injecté).
        report_builder: Constructeur de rapports (injecté).
        settings: Configuration du projet (injecté).
        bot: Référence au bot Discord (injecté après setup).
    """

    def __init__(self) -> None:
        """Initialise le planificateur vide.

        Les dépendances sont injectées via setup() après création.
        """
        self.scheduler = AsyncIOScheduler(timezone=UTC)
        self._started = False

        # Dépendances (injectées après construction)
        self.trend_analyzer: Any = None
        self.notifier: Any = None
        self.task_manager: Any = None
        self.report_builder: Any = None
        self.settings: Any = None
        self.bot: Any = None

    def setup(
        self,
        trend_analyzer: Any,
        notifier_module: Any,
        task_manager: Any,
        report_builder: Any,
        settings: Any,
    ) -> None:
        """Injecte les dépendances nécessaires aux callbacks.

        Args:
            trend_analyzer: Instance du TrendAnalyzer.
            notifier_module: Module notifier (ou bot) avec send_*.
            task_manager: Instance du TaskManager.
            report_builder: Instance du ReportBuilder.
            settings: Instance des Settings.
        """
        self.trend_analyzer = trend_analyzer
        self.notifier = notifier_module
        self.task_manager = task_manager
        self.report_builder = report_builder
        self.settings = settings
        logger.info("Dépendances injectées dans le scheduler")

    def start(self) -> None:
        """Demarre tous les jobs planifies."""
        if self._started:
            logger.warning("Scheduler déjà démarré")
            return

        self.add_daily_jobs()
        self.add_weekly_report()
        self.add_cleanup_job()
        self.add_stale_check()

        self.scheduler.start()
        self._started = True

        logger.info(
            "Scheduler démarré avec %d jobs",
            len(self.scheduler.get_jobs()),
        )

    def stop(self) -> None:
        """Arrete proprement le scheduler."""
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False
            logger.info("Scheduler arrêté")

    def add_daily_jobs(
        self,
        hours: Optional[List[int]] = None,
    ) -> None:
        """Ajoute les jobs de génération automatique.

        Tous les jours aux heures définies (ex: 6h et 18h UTC).
        Analyse les tendances puis génère du contenu si auto_generate.

        Args:
            hours: Liste des heures (ex: [6, 18]).
                   Si None, utilise [6, 18].
        """
        hours = hours or [6, 18]

        for hour in hours:
            trigger = CronTrigger(hour=hour, minute=0, timezone=UTC)
            self.scheduler.add_job(
                self._scheduled_generation,
                trigger=trigger,
                id=f"auto_gen_{hour}h",
                name=f"Génération auto {hour}h",
                replace_existing=True,
                misfire_grace_time=300,
            )
            logger.info("Job planifié: génération auto %dh", hour)

    def add_weekly_report(
        self,
    ) -> None:
        """Ajoute le job de rapport hebdomadaire.

        Déclenché chaque lundi à 8h UTC.
        """
        trigger = CronTrigger(
            day_of_week="mon",
            hour=8,
            minute=0,
            timezone=UTC,
        )
        self.scheduler.add_job(
            self._weekly_report_job,
            trigger=trigger,
            id="weekly_report",
            name="Rapport hebdomadaire",
            replace_existing=True,
            misfire_grace_time=600,
        )
        logger.info("Job planifié: rapport hebdo (lundi 8h)")

    def add_cleanup_job(
        self,
    ) -> None:
        """Ajoute le job de nettoyage /tmp/tiktok-agent/.

        Toutes les 2 heures, supprime les fichiers de plus de 2h.
        """
        trigger = IntervalTrigger(hours=2, timezone=UTC)
        self.scheduler.add_job(
            self._cleanup_temp_job,
            trigger=trigger,
            id="cleanup_tmp",
            name="Nettoyage /tmp",
            replace_existing=True,
            misfire_grace_time=600,
        )
        logger.info("Job planifié: nettoyage /tmp (toutes les 2h)")

    def add_stale_check(
        self,
    ) -> None:
        """Ajoute le job de vérification des tâches obsolètes.

        Toutes les 30 minutes, vérifie les tâches en attente
        depuis plus de REMINDER_HOURS heures.
        """
        trigger = IntervalTrigger(minutes=30, timezone=UTC)
        self.scheduler.add_job(
            self._stale_check_job,
            trigger=trigger,
            id="stale_check",
            name="Vérification tâches obsolètes",
            replace_existing=True,
            misfire_grace_time=600,
        )
        logger.info("Job planifié: vérif tâches (30min)")

    def trigger_immediate_trends(
        self,
    ) -> None:
        """Déclenche une analyse immédiate des tendances.

        Ajoute un job 'date' exécuté immédiatement.
        """
        self.scheduler.add_job(
            self._immediate_trends_job,
            trigger="date",
            run_date=None,
            id="immediate_trends",
            name="Analyse tendances immédiate",
            replace_existing=True,
        )
        logger.info("Analyse tendances immédiate planifiée")

    def get_jobs_info(self) -> str:
        """Retourne un résumé des jobs planifiés.

        Returns:
            Chaîne formatée avec la liste des jobs.
        """
        jobs = self.scheduler.get_jobs()
        if not jobs:
            return "Aucun job planifié."

        lines = ["**━ Jobs planifiés ━**"]
        for job in jobs:
            next_run = job.next_run_time
            next_str = next_run.strftime("%Y-%m-%d %H:%M UTC") if next_run else "immédiat"
            lines.append(f"- `{job.id}`: {job.name} (prochain: {next_str})")
        return "\n".join(lines)

    # ─── Callbacks réels ────────────────────────────────────────

    async def _scheduled_generation(self) -> None:
        """Job : génération automatique programmée.

        Analyse les tendances → notifie → si AUTO_GENERATE, crée une
        tâche et lance la génération du script.
        """
        logger.info("=== Génération automatique déclenchée ===")

        if not self._check_deps("génération auto"):
            return

        try:
            niche = self.settings.DEFAULT_NICHE if self.settings else "Tech & IA"
            trends = self.trend_analyzer.analyze(niche=niche)
            logger.info("Tendances analysées: %d tendances générales", len(trends.get("general_trends", [])))

            # Envoi des tendances dans Discord
            if self.notifier and hasattr(self.notifier, "send_trends"):
                await self.notifier.send_trends(trends)

            # Génération automatique si activée
            if self.settings and getattr(self.settings, "AUTO_GENERATE", False):
                suggested = trends.get("suggested_topics", [])
                if suggested:
                    topic = suggested[0]
                    task = self.task_manager.create_task(
                        subject=topic["title"],
                        niche=niche,
                    )
                    logger.info(
                        "Génération auto lancée: %s — %s",
                        task["task_id"],
                        topic["title"],
                    )
                    await self.task_manager.generate_script(task["task_id"])
                else:
                    logger.warning("Aucun sujet suggéré pour la génération auto")
            else:
                logger.info("Génération auto désactivée (AUTO_GENERATE=False)")

        except (RuntimeError, OSError, ValueError) as exc:
            logger.error("Erreur génération auto: %s", exc)

    async def _weekly_report_job(self) -> None:
        """Job : rapport hebdomadaire.

        Construit le rapport via ReportBuilder et l'envoie dans Discord.
        """
        logger.info("=== Rapport hebdomadaire déclenché ===")

        if not self._check_deps("rapport hebdo"):
            return

        try:
            report = self.report_builder.build_weekly_report()
            logger.info(
                "Rapport construit: semaine %s — %d générations",
                report.get("week", "?"),
                report.get("production", {}).get("total_generated", 0),
            )

            if self.notifier and hasattr(self.notifier, "send_report"):
                await self.notifier.send_report(report)

        except (RuntimeError, OSError) as exc:
            logger.error("Erreur rapport hebdo: %s", exc)

    async def _cleanup_temp_job(self) -> None:
        """Job : nettoyage des fichiers temporaires.

        Supprime les fichiers de /tmp/tiktok-agent/ plus vieux que 2h.
        """
        logger.info("=== Nettoyage /tmp déclenché ===")

        if not os.path.exists(TEMP_DIR):
            logger.info("Répertoire %s inexistant, rien à nettoyer", TEMP_DIR)
            return

        removed = 0
        errors = 0
        now = time.time()

        try:
            for filename in os.listdir(TEMP_DIR):
                filepath = os.path.join(TEMP_DIR, filename)
                try:
                    if os.path.isfile(filepath) and (now - os.path.getmtime(filepath)) > CLEANUP_AGE_SECONDS:
                        os.remove(filepath)
                        removed += 1
                    elif os.path.isdir(filepath):
                        # Nettoyage récursif des sous-dossiers
                        shutil.rmtree(filepath, ignore_errors=True)
                        removed += 1
                except OSError as exc:
                    logger.warning("Erreur suppression %s: %s", filename, exc)
                    errors += 1

            logger.info(
                "Nettoyage terminé: %d fichiers supprimés, %d erreurs",
                removed,
                errors,
            )

        except OSError as exc:
            logger.error("Erreur parcours %s: %s", TEMP_DIR, exc)

    async def _stale_check_job(self) -> None:
        """Job : vérification des tâches en attente.

        Cherche les tâches en awaiting_validation depuis > REMINDER_HOURS
        et envoie un rappel Discord.
        """
        logger.info("=== Vérification tâches obsolètes ===")

        if not self._check_deps("vérif tâches"):
            return

        try:
            reminder_hours = STALE_TASK_HOURS
            if self.settings:
                reminder_hours = getattr(self.settings, "REMINDER_HOURS", STALE_TASK_HOURS)

            stale_tasks = self._get_stale_tasks(hours=reminder_hours)

            if not stale_tasks:
                logger.info("Aucune tâche obsolète trouvée")
                return

            logger.info(
                "%d tâche(s) en attente depuis >%dh",
                len(stale_tasks),
                reminder_hours,
            )

            for task in stale_tasks:
                task_id = task.get("task_id", "?")
                subject = task.get("subject", "?")
                created = task.get("created_at", "?")

                message = (
                    f"⏰ **Rappel : tâche en attente**\n"
                    f"`{task_id}` — {subject}\n"
                    f"Créée le: {created}\n"
                    f"Utilisez les boutons de validation dans #validation."
                )

                if self.notifier and hasattr(self.notifier, "_send_to_channel"):
                    await self.notifier._send_to_channel("validation", message)
                elif self.bot:
                    try:
                        from discord_bot.channels import get_channel_by_name
                        channel = await get_channel_by_name(self.bot, "validation")
                        if channel:
                            await channel.send(message)
                    except Exception as exc:
                        logger.warning("Impossible d'envoyer le rappel: %s", exc)

        except (RuntimeError, OSError) as exc:
            logger.error("Erreur vérif tâches obsolètes: %s", exc)

    async def _immediate_trends_job(self) -> None:
        """Job : analyse immédiate des tendances (déclenché par /tendances)."""
        logger.info("=== Analyse tendances immédiate ===")

        if not self._check_deps("analyse tendances"):
            return

        try:
            niche = self.settings.DEFAULT_NICHE if self.settings else "Tech & IA"
            trends = self.trend_analyzer.analyze(niche=niche)

            if self.notifier and hasattr(self.notifier, "send_trends"):
                await self.notifier.send_trends(trends)

            logger.info("Analyse tendances immédiate terminée")
        except (RuntimeError, OSError) as exc:
            logger.error("Erreur analyse tendances immédiate: %s", exc)

    # ─── Méthodes internes ──────────────────────────────────────

    def _get_stale_tasks(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Retourne les tâches en attente depuis plus de N heures.

        Args:
            hours: Nombre d'heures seuil.

        Returns:
            Liste des tâches obsolètes.
        """
        if not self.task_manager:
            return []

        tasks = self.task_manager.state_store.get_tasks()
        now = time.time()
        stale = []

        for task in tasks:
            if task.get("status") != "awaiting_validation":
                continue

            created = task.get("created_at", "")
            if not created:
                continue

            # Parsing du timestamp ISO 8601
            try:
                from datetime import datetime
                created_dt = datetime.fromisoformat(created)
                age_hours = (datetime.now() - created_dt).total_seconds() / 3600
                if age_hours >= hours:
                    stale.append(task)
            except (ValueError, TypeError):
                continue

        return stale

    def _check_deps(self, job_name: str) -> bool:
        """Vérifie que les dépendances nécessaires sont injectées.

        Args:
            job_name: Nom du job pour le log.

        Returns:
            True si les dépendances principales sont présentes.
        """
        if not self.trend_analyzer:
            logger.warning("Job %s: trend_analyzer non injecté", job_name)
            return False
        if not self.task_manager:
            logger.warning("Job %s: task_manager non injecté", job_name)
            return False
        return True

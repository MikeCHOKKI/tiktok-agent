"""Constructeur de rapports hebdomadaires pour le tiktok-agent.

Agrège les statistiques de production, les tendances de la semaine,
et produit un rapport structuré prêt à être affiché en embed Discord.
"""

import datetime
import os
import time
from typing import Any, Dict, List, Optional

from utils.logger import logger

# Sera importé au moment de l'appel pour éviter les imports circulaires
try:
    from agent.trend_analyzer import TrendAnalyzer
except ImportError:
    TrendAnalyzer = None  # type: ignore


class ReportBuilder:
    """Constructeur de rapports hebdomadaires.

    Attributes:
        state_store: Store de persistance pour les stats.
        trend_analyzer: Analyseur de tendances (optionnel).
        _start_time: Timestamp de démarrage pour l'uptime.
    """

    def __init__(
        self,
        state_store: Any,
        trend_analyzer: Optional[Any] = None,
    ) -> None:
        """Initialise le constructeur de rapports.

        Args:
            state_store: Instance du StateStore.
            trend_analyzer: Instance du TrendAnalyzer (optionnel).
        """
        self.state_store = state_store
        self.trend_analyzer = trend_analyzer
        self._start_time = time.time()

    def build_weekly_report(self) -> Dict[str, Any]:
        """Construit le rapport hebdomadaire complet.

        Returns:
            Dict structuré avec production, niche_analysis, quality,
            planning, et system.
        """
        now = datetime.datetime.now()
        week_number = now.strftime("%Y-W%W")

        # Stats de production depuis le state store
        weekly_stats = self.state_store.get_weekly_stats()
        current_week_stats = weekly_stats.get(week_number, {})

        total_generated = current_week_stats.get("total", 0)
        approved = current_week_stats.get("approved", 0)
        rejected = current_week_stats.get("rejected", 0)
        pending = current_week_stats.get("pending", 0)
        error_count = current_week_stats.get("errors", 0)

        approval_rate = round(approved / total_generated, 3) if total_generated > 0 else 0.0
        avg_time = current_week_stats.get("avg_generation_time_s", 0)

        # Analyse des raisons de rejet
        rejection_reasons: Dict[str, int] = {}
        tasks = self.state_store.get_tasks()
        for task in tasks:
            if task.get("status") == "rejected":
                reason = task.get("rejection_reason", "non spécifié")
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

        # Analyse des niches
        niche_counts: Dict[str, int] = {}
        niche_subjects: Dict[str, List[str]] = {}
        for task in tasks:
            t_niche = task.get("niche", "Inconnue")
            niche_counts[t_niche] = niche_counts.get(t_niche, 0) + 1
            if t_niche not in niche_subjects:
                niche_subjects[t_niche] = []
            subject = task.get("subject", "")
            if subject:
                niche_subjects[t_niche].append(subject)

        primary_niche = (
            max(niche_counts, key=lambda k: niche_counts.get(k, 0))
            if niche_counts
            else "Aucune"
        )
        top_subjects = niche_subjects.get(primary_niche, [])[:3]

        # Suggestions de sujets depuis l'analyseur
        suggested_topics_next_week: List[Dict[str, Any]] = []
        anticipated_trends = ""
        if self.trend_analyzer:
            try:
                topics = self.trend_analyzer.suggest_topics(
                    niche=primary_niche if primary_niche != "Aucune" else None,
                    count=5,
                )
                suggested_topics_next_week = topics

                # Brève analyse des tendances anticipées
                trends = self.trend_analyzer.analyze(
                    niche=primary_niche if primary_niche != "Aucune" else None
                )
                if trends.get("general_trends"):
                    top_trends = trends["general_trends"][:3]
                    anticipated_trends = (
                        "Tendances détectées : "
                        + ", ".join(t["title"] for t in top_trends)
                    )
            except (RuntimeError, OSError) as exc:
                logger.warning("Impossible d'obtenir les tendances pour le rapport: %s", exc)
                anticipated_trends = "Analyse des tendances non disponible"

        # Stats système
        uptime_seconds = time.time() - self._start_time
        uptime_hours = round(uptime_seconds / 3600, 1)
        estimated_api_calls = total_generated * 2 + error_count  # script + image par tâche

        # Améliorations suggérées
        improvement_suggestions = self._generate_improvements(
            approval_rate, rejection_reasons, avg_time
        )

        # Configuration recommandée
        config = self.state_store.get_config()
        recommended_config = {
            "style": config.get("style", "educatif"),
            "frequency": f"{config.get('schedule_hours', [6, 18])} générations/jour",
        }

        report: Dict[str, Any] = {
            "week": week_number,
            "production": {
                "total_generated": total_generated,
                "approved": approved,
                "rejected": rejected,
                "pending": pending,
                "approval_rate": approval_rate,
                "avg_generation_time_s": avg_time,
            },
            "niche_analysis": {
                "primary_niche": primary_niche,
                "top_subjects": top_subjects,
                "suggested_topics_next_week": [
                    {
                        "title": t.get("title", ""),
                        "reason": t.get("reason", ""),
                    }
                    for t in suggested_topics_next_week
                ],
            },
            "quality": {
                "rejection_reasons": rejection_reasons,
                "improvement_suggestions": improvement_suggestions,
            },
            "planning": {
                "pre_generated_topics": [
                    t.get("title", "")
                    for t in suggested_topics_next_week[:5]
                ],
                "anticipated_trends": anticipated_trends,
                "recommended_config": recommended_config,
            },
            "system": {
                "uptime_hours": uptime_hours,
                "error_count": error_count,
                "estimated_api_calls": estimated_api_calls,
            },
        }

        logger.info("Rapport hebdomadaire %s construit", week_number)
        return report

    def _generate_improvements(
        self,
        approval_rate: float,
        rejection_reasons: Dict[str, int],
        avg_time: float,
    ) -> str:
        """Génère des suggestions d'amélioration basées sur les stats.

        Args:
            approval_rate: Taux d'approbation (0-1).
            rejection_reasons: Dict {raison: nombre}.
            avg_time: Temps moyen de génération en secondes.

        Returns:
            Texte de suggestions.
        """
        suggestions: List[str] = []

        if approval_rate < 0.5:
            suggestions.append(
                "🔴 Le taux d'approbation est faible. "
                "Enrichir le prompt LLM avec des exemples validés."
            )
        elif approval_rate < 0.7:
            suggestions.append(
                "🟡 Taux d'approbation moyen. "
                "Ajouter plus de contexte de niche dans les sujets."
            )

        if rejection_reasons:
            top_reason = max(
                rejection_reasons,
                key=lambda k: rejection_reasons.get(k, 0),
            )
            suggestions.append(
                f"📌 La raison de rejet la plus fréquente est "
                f"'{top_reason}' ({rejection_reasons[top_reason]} fois)."
            )

        if avg_time > 60:
            suggestions.append(
                "⏱️ Le temps de génération est élevé. "
                "Vérifier la latence de l'API HF."
            )
        elif avg_time > 0:
            suggestions.append(
                f"✅ Temps de génération correct ({avg_time}s en moyenne)."
            )

        if not suggestions:
            suggestions.append("✅ Aucune amélioration majeure suggérée.")

        return "\n".join(suggestions)

"""Gestionnaire de taches pour le tiktok-agent.

Gerer le cycle de vie complet des taches :
pending -> generating -> awaiting_validation -> approved/rejected/error
Integre le pipeline image pour la generation automatique
de visuels apres chaque script.
"""

import datetime
import json
from typing import Any, Dict, List, Optional

from agent.script_generator import ScriptGenerator
from agent.state_store import StateStore
from utils.helpers import generate_task_id, format_timestamp
from utils.logger import logger

# Import conditionnel du routeur image (evite l'echec au demarrage
# si le module image n'est pas encore installe)
try:
    from image.router import ImageRouter
except ImportError:
    ImageRouter = None  # type: ignore


TASK_STATUS_PENDING = "pending"
TASK_STATUS_GENERATING = "generating"
TASK_STATUS_AWAITING_VALIDATION = "awaiting_validation"
TASK_STATUS_APPROVED = "approved"
TASK_STATUS_REJECTED = "rejected"
TASK_STATUS_ERROR = "error"

VALID_TRANSITIONS: Dict[str, List[str]] = {
    TASK_STATUS_PENDING: [TASK_STATUS_GENERATING],
    TASK_STATUS_GENERATING: [
        TASK_STATUS_AWAITING_VALIDATION,
        TASK_STATUS_ERROR,
    ],
    TASK_STATUS_AWAITING_VALIDATION: [
        TASK_STATUS_APPROVED,
        TASK_STATUS_REJECTED,
        TASK_STATUS_GENERATING,
    ],
    TASK_STATUS_APPROVED: [],
    TASK_STATUS_REJECTED: [],
    TASK_STATUS_ERROR: [TASK_STATUS_PENDING],
}


class TaskManager:
    """Gere le cycle de vie des taches de generation.

    Attributes:
        state_store: Store de persistance.
        script_generator: Generateur de scripts LLM.
        image_router: Routeur du pipeline image (optionnel).
        _task_counter: Compteur pour IDs uniques.
        _image_retry_count: Compteur de tentatives image par tache.
    """

    def __init__(
        self,
        state_store: StateStore,
        script_generator: ScriptGenerator,
        image_router: Optional[Any] = None,
    ):
        """Initialise le gestionnaire de taches.

        Args:
            state_store: Instance du StateStore.
            script_generator: Instance du ScriptGenerator.
            image_router: Instance du ImageRouter (optionnel).
        """
        self.state_store = state_store
        self.script_generator = script_generator
        self.image_router = image_router
        self._task_counter = 0
        self._image_retry_count: Dict[str, int] = {}

    def create_task(
        self,
        subject: str,
        niche: str,
        style: str = "educatif",
    ) -> Dict[str, Any]:
        """Cree une nouvelle tache de generation.

        Args:
            subject: Sujet du script.
            niche: Niche de contenu.
            style: Style de video.

        Returns:
            La tache creee.
        """
        self._task_counter += 1
        now = datetime.datetime.now()
        task_id = f"task_{now.strftime('%Y%m%d')}_{self._task_counter:03d}"

        task = {
            "task_id": task_id,
            "subject": subject,
            "niche": niche,
            "style": style,
            "status": TASK_STATUS_PENDING,
            "created_at": format_timestamp(now),
            "updated_at": format_timestamp(now),
            "script_data": None,
            "image_path": None,
            "rejection_reason": None,
            "notes": "",
        }

        self.state_store.add_task(task)
        logger.info("Tache creee: %s - %s", task_id, subject)

        return task

    async def generate_script(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Genere le script et l'image pour une tache.

        Passe le statut de 'generating' a 'awaiting_validation'.
        Apres la generation du script, lance automatiquement le
        pipeline image si le routeur est disponible.

        Args:
            task_id: Identifiant de la tache.

        Returns:
            Les donnees du script genere, ou None si erreur.
        """
        task = self.state_store.get_task(task_id)
        if not task:
            logger.error("Tache introuvable: %s", task_id)
            return None

        if not self._transition(task, TASK_STATUS_GENERATING):
            return None

        try:
            script_data = self.script_generator.generate_script(
                subject=task["subject"],
                niche=task["niche"],
                style=task["style"],
            )

            # Generation image associee (non-bloquante pour le retour)
            image_path = None
            if self.image_router:
                try:
                    config = self.state_store.get_config()
                    image_path = self.image_router.generate_image(
                        task=task,
                        script_data=script_data,
                        config=config,
                    )
                    if image_path:
                        logger.info(
                            "Image generee pour tache %s: %s",
                            task_id,
                            image_path,
                        )
                        self._image_retry_count[task_id] = 0
                    else:
                        logger.warning(
                            "Aucune image generee pour tache %s",
                            task_id,
                        )
                        self._increment_image_retry(task_id)
                except (ValueError, RuntimeError) as img_exc:
                    logger.error(
                        "Echec generation image %s: %s",
                        task_id,
                        img_exc,
                    )
                    self._increment_image_retry(task_id)

            self.state_store.update_task(task_id, {
                "script_data": script_data,
                "image_path": image_path,
                "status": TASK_STATUS_AWAITING_VALIDATION,
                "updated_at": format_timestamp(),
            })

            logger.info("Script genere pour tache %s", task_id)
            return script_data

        except (ValueError, RuntimeError) as exc:
            logger.error("Echec generation script %s: %s", task_id, exc)
            self.state_store.update_task(task_id, {
                "status": TASK_STATUS_ERROR,
                "notes": str(exc),
                "updated_at": format_timestamp(),
            })
            return None

    def approve_task(
        self,
        task_id: str,
        notes: str = "",
    ) -> bool:
        """Approuve une tache.

        Args:
            task_id: Identifiant de la tache.
            notes: Notes optionnelles.

        Returns:
            True si l'approbation a reussi.
        """
        task = self.state_store.get_task(task_id)
        if not task:
            return False

        if not self._transition(task, TASK_STATUS_APPROVED):
            return False

        self.state_store.update_task(task_id, {
            "status": TASK_STATUS_APPROVED,
            "notes": notes or task.get("notes", ""),
            "updated_at": format_timestamp(),
        })

        self._update_weekly_stats_approved()
        logger.info("Tache approuvee: %s", task_id)
        return True

    def reject_task(
        self,
        task_id: str,
        reason: str = "Non specifie",
    ) -> bool:
        """Rejette une tache.

        Args:
            task_id: Identifiant de la tache.
            reason: Motif du rejet.

        Returns:
            True si le rejet a reussi.
        """
        task = self.state_store.get_task(task_id)
        if not task:
            return False

        if not self._transition(task, TASK_STATUS_REJECTED):
            return False

        self.state_store.update_task(task_id, {
            "status": TASK_STATUS_REJECTED,
            "rejection_reason": reason,
            "updated_at": format_timestamp(),
        })

        logger.info("Tache rejetee: %s - Raison: %s", task_id, reason)
        return True

    def regenerate_script(self, task_id: str) -> bool:
        """Relance la generation du script d'une tache.

        Args:
            task_id: Identifiant de la tache.

        Returns:
            True si la regeneration a ete lancee.
        """
        task = self.state_store.get_task(task_id)
        if not task:
            return False

        self.state_store.update_task(task_id, {
            "status": TASK_STATUS_PENDING,
            "script_data": None,
            "updated_at": format_timestamp(),
        })

        logger.info("Regeneration script demandee: %s", task_id)
        return True

    def regenerate_image(self, task_id: str) -> bool:
        """Relance la generation de l'image d'une tache.

        Efface le chemin image actuel et reinitialise le compteur
        de tentatives. La regeneration effective aura lieu lors
        du prochain appel a generate_script() ou via le scheduler.

        Args:
            task_id: Identifiant de la tache.

        Returns:
            True si la regeneration a ete lancee.
        """
        task = self.state_store.get_task(task_id)
        if not task:
            return False

        self.state_store.update_task(task_id, {
            "image_path": None,
            "updated_at": format_timestamp(),
        })

        # Relance immediate si le routeur est disponible
        if self.image_router and task.get("script_data"):
            try:
                config = self.state_store.get_config()
                image_path = self.image_router.generate_image(
                    task=task,
                    script_data=task["script_data"],
                    config=config,
                )
                if image_path:
                    self.state_store.update_task(task_id, {
                        "image_path": image_path,
                        "updated_at": format_timestamp(),
                    })
                    logger.info(
                        "Image regeneree pour tache %s: %s",
                        task_id,
                        image_path,
                    )
                    return True
            except (ValueError, RuntimeError) as exc:
                logger.error(
                    "Echec regeneration image %s: %s", task_id, exc
                )

        logger.info("Regeneration image demandee (differee): %s", task_id)
        return True

    def get_queue_summary(self) -> str:
        """Retourne un resume de la file de taches.

        Returns:
            Chaine formatee avec le resume.
        """
        tasks = self.state_store.get_tasks()

        counts = {
            TASK_STATUS_PENDING: 0,
            TASK_STATUS_GENERATING: 0,
            TASK_STATUS_AWAITING_VALIDATION: 0,
            TASK_STATUS_APPROVED: 0,
            TASK_STATUS_REJECTED: 0,
            TASK_STATUS_ERROR: 0,
        }

        pending_list = []
        for task in tasks:
            status = task.get("status", TASK_STATUS_PENDING)
            if status in counts:
                counts[status] += 1
            if status in (
                TASK_STATUS_PENDING,
                TASK_STATUS_AWAITING_VALIDATION,
            ):
                pending_list.append(
                    f"- `{task['task_id']}`: {task['subject']} "
                    f"({status})"
                )

        lines = [
            "**━ File de taches ━**",
            f"📝 En attente: {counts[TASK_STATUS_PENDING]}",
            f"⚙️ En generation: {counts[TASK_STATUS_GENERATING]}",
            f"🔍 En validation: {counts[TASK_STATUS_AWAITING_VALIDATION]}",
            f"✅ Approuvees: {counts[TASK_STATUS_APPROVED]}",
            f"❌ Rejetees: {counts[TASK_STATUS_REJECTED]}",
            f"⚠️ En erreur: {counts[TASK_STATUS_ERROR]}",
            "",
        ]

        total = sum(counts.values())
        if total == 0:
            lines.append("Aucune tache pour le moment.")
        elif pending_list:
            lines.append("**Taches en attente/validation:**")
            lines.extend(pending_list[:10])
            if len(pending_list) > 10:
                lines.append(
                    f"*... et {len(pending_list) - 10} autre(s)*"
                )

        return "\n".join(lines)

    def get_history(self, n: int = 10) -> List[Dict[str, Any]]:
        """Retourne les n dernieres taches.

        Args:
            n: Nombre de taches a retourner (defaut: 10).

        Returns:
            Liste des n dernieres taches.
        """
        tasks = self.state_store.get_tasks()
        return tasks[-n:]

    def _increment_image_retry(self, task_id: str) -> int:
        """Incremente et retourne le compteur de tentatives image.

        Args:
            task_id: Identifiant de la tache.

        Returns:
            Nombre de tentatives apres incrementation.
        """
        current = self._image_retry_count.get(task_id, 0)
        current += 1
        self._image_retry_count[task_id] = current

        if current >= 3:
            logger.warning(
                "Trop de tentatives image pour tache %s (%d)",
                task_id,
                current,
            )

        return current

    def _transition(
        self,
        task: Dict[str, Any],
        new_status: str,
    ) -> bool:
        """Verifie et effectue une transition de statut.

        Args:
            task: Tache a transitionner.
            new_status: Nouveau statut souhaite.

        Returns:
            True si la transition est valide.
        """
        current = task.get("status", TASK_STATUS_PENDING)
        allowed = VALID_TRANSITIONS.get(current, [])

        if new_status not in allowed:
            logger.warning(
                "Transition invalide: %s -> %s pour tache %s",
                current,
                new_status,
                task.get("task_id"),
            )
            return False

        return True

    def _update_weekly_stats_approved(self) -> None:
        """Incremente le compteur hebdomadaire d'approbations."""
        stats = self.state_store.get_weekly_stats()

        now = datetime.datetime.now()
        week_key = now.strftime("%Y-W%W")

        if week_key not in stats:
            stats[week_key] = {
                "approved": 0,
                "rejected": 0,
                "total": 0,
            }

        stats[week_key]["approved"] += 1
        stats[week_key]["total"] += 1
        self.state_store.update_weekly_stats(stats)

"""Persistance JSON de l'etat du tiktok-agent.

Charge et sauvegarde state.json de facon thread-safe.
Cree automatiquement le fichier s'il n'existe pas.

Phase 4 : ajout de HFDatasetStore pour la persistance longue durée
sur Hugging Face Dataset, avec sauvegarde périodique (toutes les
10 modifications).
"""

import json
import os
import threading
from typing import Any, Dict, List, Optional

from utils.logger import logger


CHANGE_THRESHOLD = 10  # Sauvegarde HF Dataset toutes les 10 modifs


class HFDatasetStore:
    """Stockage longue durée via Hugging Face Dataset.

    Sauvegarde périodique de l'état complet vers un dataset HF
    pour restauration en cas de redémarrage du Space.

    Attributes:
        dataset_name: Nom du dataset HF (ex: user/tiktok-agent-history).
        token: Token Hugging Face.
        _dirty: Flag indiquant si des modifications sont en attente.
        _change_count: Compteur de modifications depuis dernier push.
    """

    def __init__(self, dataset_name: str, token: str):
        """Initialise le stockage HF Dataset.

        Args:
            dataset_name: Nom du dataset HF.
            token: Token Hugging Face.
        """
        self.dataset_name = dataset_name
        self.token = token
        self._dirty = False
        self._change_count = 0

    async def push_state(self, state: dict) -> bool:
        """Push l'état complet vers HF Dataset.

        Convertit les tâches en format Dataset et upload vers
        hf.co/datasets/{dataset_name}.

        Args:
            state: État complet à sauvegarder.

        Returns:
            True si la sauvegarde a réussi.
        """
        try:
            from datasets import Dataset, DatasetDict

            tasks = state.get("tasks", [])
            if not tasks:
                logger.info("HF Dataset : aucune tâche à sauvegarder")
                return True

            df_data = []
            for task in tasks:
                row = {
                    "task_id": task.get("task_id", ""),
                    "subject": task.get("subject", ""),
                    "niche": task.get("niche", ""),
                    "style": task.get("style", ""),
                    "status": task.get("status", ""),
                    "created_at": task.get("created_at", ""),
                    "updated_at": task.get("updated_at", ""),
                    "rejection_reason": task.get(
                        "rejection_reason", ""
                    ),
                    "hook": (
                        task.get("script_data", {}).get("hook", "")
                        if task.get("script_data")
                        else ""
                    ),
                    "cta": (
                        task.get("script_data", {}).get("cta", "")
                        if task.get("script_data")
                        else ""
                    ),
                }
                df_data.append(row)

            dataset = Dataset.from_list(df_data)
            dataset_dict = DatasetDict({"tasks": dataset})
            dataset_dict.push_to_hub(
                self.dataset_name,
                token=self.token,
                private=True,
            )

            self._dirty = False
            self._change_count = 0
            logger.info(
                "HF Dataset push reussi : %d tâches vers %s",
                len(df_data),
                self.dataset_name,
            )
            return True

        except Exception as exc:
            logger.error(
                "HF Dataset push echoue : %s", exc
            )
            return False

    async def pull_state(self) -> Optional[Dict[str, Any]]:
        """Pull le dernier état depuis HF Dataset.

        Returns:
            État restauré ou None si indisponible.
        """
        try:
            from datasets import load_dataset

            dataset_dict = load_dataset(
                self.dataset_name,
                token=self.token,
                split="tasks",
            )

            tasks = []
            for row in dataset_dict:
                task = {
                    "task_id": row.get("task_id", ""),
                    "subject": row.get("subject", ""),
                    "niche": row.get("niche", ""),
                    "style": row.get("style", ""),
                    "status": row.get("status", "pending"),
                    "created_at": row.get("created_at", ""),
                    "updated_at": row.get("updated_at", ""),
                    "rejection_reason": row.get(
                        "rejection_reason", None
                    ),
                    "script_data": (
                        {
                            "hook": row.get("hook", ""),
                            "cta": row.get("cta", ""),
                        }
                        if row.get("hook")
                        else None
                    ),
                    "image_path": None,
                    "notes": "",
                }
                tasks.append(task)

            logger.info(
                "HF Dataset pull reussi : %d tâches restaurees",
                len(tasks),
            )
            return {"tasks": tasks}

        except Exception as exc:
            logger.warning(
                "HF Dataset pull indisponible : %s", exc
            )
            return None

    def mark_dirty(self):
        """Marque l'état comme modifié et incrémente le compteur."""
        self._dirty = True
        self._change_count += 1

    @property
    def should_push(self) -> bool:
        """Vrai si le seuil de modifications est atteint.

        Returns:
            True si >= CHANGE_THRESHOLD modifications depuis dernier push.
        """
        return self._change_count >= CHANGE_THRESHOLD


class StateStore:
    """Gestionnaire de persistance JSON thread-safe.

    Phase 4 : intègre HFDatasetStore pour la persistance longue durée
    avec sauvegarde périodique automatique.

    Attributes:
        file_path: Chemin vers le fichier state.json.
        hf_store: Stockage HF Dataset (optionnel).
        _lock: Lock threading pour acces concurrent.
        _data: Donnees en memoire.
    """

    def __init__(
        self,
        file_path: str = "state.json",
        hf_dataset_name: str = "",
        hf_token: str = "",
    ):
        """Initialise le StateStore.

        Args:
            file_path: Chemin vers le fichier d'etat.
            hf_dataset_name: Nom du dataset HF (optionnel).
            hf_token: Token HF pour le dataset (optionnel).
        """
        self.file_path = file_path
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {}

        self.hf_store: Optional[HFDatasetStore] = None
        if hf_dataset_name and hf_token:
            self.hf_store = HFDatasetStore(
                dataset_name=hf_dataset_name, token=hf_token
            )
            logger.info(
                "HFDatasetStore initialise : %s", hf_dataset_name
            )

        self.load()

    def load(self) -> Dict[str, Any]:
        """Charge les donnees depuis le fichier JSON.

        Cree le fichier avec l'etat initial s'il n'existe pas.

        Returns:
            Donnees chargees.
        """
        with self._lock:
            if not os.path.exists(self.file_path):
                logger.info("Fichier state.json introuvable, creation...")
                self._data = self._default_state()
                self._write()
                return self._data

            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.info("Etat charge depuis %s", self.file_path)
            except (json.JSONDecodeError, IOError) as exc:
                logger.warning(
                    "Erreur lecture state.json: %s. Utilisation defaut.", exc
                )
                self._data = self._default_state()
                self._write()

            return self._data

    def save(self) -> None:
        """Sauvegarde les donnees actuelles dans le fichier JSON.

        Si HFDatasetStore est configuré, marque l'état comme modifié.
        Le push effectif vers HF Dataset est déclenché automatiquement
        après CHANGE_THRESHOLD modifications.
        """
        with self._lock:
            self._write()
            if self.hf_store:
                self.hf_store.mark_dirty()

    def get_cached_trends(self) -> List[str]:
        """Retourne les tendances mises en cache.

        Returns:
            Liste des sujets tendances en cache (ou liste vide).
        """
        cache = self._data.get("trends_cache", {})
        cached = cache.get("cached_result")
        if cached and isinstance(cached, dict):
            suggested = cached.get("suggested_topics", [])
            return [s.get("title", "") for s in suggested if s.get("title")]
        return []

    def _write(self) -> None:
        """Ecriture interne (doit etre appelee avec le lock)."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except IOError as exc:
            logger.error("Impossible d'ecrire state.json: %s", exc)

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Recherche une tache par son identifiant.

        Args:
            task_id: Identifiant de la tache.

        Returns:
            Tache trouvee ou None.
        """
        tasks = self._data.get("tasks", [])
        for task in tasks:
            if task.get("task_id") == task_id:
                return task
        return None

    def add_task(self, task: Dict[str, Any]) -> None:
        """Ajoute une tache a la file.

        Args:
            task: Dictionnaire representant la tache.
        """
        with self._lock:
            if "tasks" not in self._data:
                self._data["tasks"] = []
            self._data["tasks"].append(task)
            self._write()

    def update_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """Met a jour une tache existante.

        Args:
            task_id: Identifiant de la tache.
            updates: Dictionnaire des champs a mettre a jour.

        Returns:
            True si la tache a ete trouvee et mise a jour.
        """
        with self._lock:
            tasks = self._data.get("tasks", [])
            for task in tasks:
                if task.get("task_id") == task_id:
                    task.update(updates)
                    self._write()
                    return True
            logger.warning("Tache %s introuvable pour mise a jour", task_id)
            return False

    def get_weekly_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques hebdomadaires.

        Returns:
            Dict des stats hebdomadaires.
        """
        return self._data.get("weekly_stats", {})

    def update_weekly_stats(self, stats: Dict[str, Any]) -> None:
        """Met a jour les statistiques hebdomadaires.

        Args:
            stats: Nouvelles statistiques.
        """
        with self._lock:
            self._data["weekly_stats"] = stats
            self._write()

    def get_config(self) -> Dict[str, Any]:
        """Retourne la configuration actuelle.

        Returns:
            Dict de configuration.
        """
        return self._data.get("config", {})

    def update_config(self, key: str, value: Any) -> None:
        """Met a jour un parametre de configuration.

        Args:
            key: Nom du parametre.
            value: Nouvelle valeur.
        """
        with self._lock:
            if "config" not in self._data:
                self._data["config"] = {}
            self._data["config"][key] = value
            self._write()

    def get_tasks(self) -> List[Dict[str, Any]]:
        """Retourne toutes les taches.

        Returns:
            Liste des taches.
        """
        return self._data.get("tasks", [])

    @staticmethod
    def _default_state() -> Dict[str, Any]:
        """Etat initial par defaut.

        Returns:
            Dictionnaire d'etat initial.
        """
        return {
            "config": {
                "niche": "Tech & IA",
                "style": "educatif",
                "langue": "fr",
                "schedule_hours": [6, 18],
                "auto_generate": True,
                "watermark_text": "@tiktok_agent",
            },
            "tasks": [],
            "weekly_stats": {},
            "trends_cache": {
                "last_scan": None,
                "cached_result": None,
            },
        }

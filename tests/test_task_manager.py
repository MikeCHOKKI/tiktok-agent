"""Tests unitaires pour TaskManager.

Modules testés :
- test_create_task : création et ID unique
- test_task_lifecycle : cycle de vie complet
- test_approve_task : changement de statut
- test_reject_task_with_reason : stockage du motif
- test_get_queue_summary : compteurs
- test_regenerate_script : régénération
"""

from unittest.mock import MagicMock, patch

import pytest

from agent.task_manager import (
    TaskManager,
    TASK_STATUS_PENDING,
    TASK_STATUS_GENERATING,
    TASK_STATUS_AWAITING_VALIDATION,
    TASK_STATUS_APPROVED,
    TASK_STATUS_REJECTED,
    TASK_STATUS_ERROR,
)


class TestTaskManager:
    """Tests du gestionnaire de tâches."""

    def test_create_task(self, mock_state_store):
        """Vérifie la création d'une tâche avec les bons attributs.

        Validation : ID unique, statut initial pending,
        sujet/niche/style corrects.
        """
        task_manager = TaskManager(
            state_store=mock_state_store,
            script_generator=MagicMock(),
        )

        task = task_manager.create_task(
            subject="Mon sujet test",
            niche="Tech & IA",
            style="liste_educative",
        )

        assert task["task_id"].startswith("task_")
        assert task["subject"] == "Mon sujet test"
        assert task["niche"] == "Tech & IA"
        assert task["style"] == "liste_educative"
        assert task["status"] == TASK_STATUS_PENDING
        assert task["script_data"] is None
        assert task["image_path"] is None
        assert task["rejection_reason"] is None
        assert "created_at" in task
        assert "updated_at" in task
        mock_state_store.add_task.assert_called_once_with(task)

    def test_create_task_increments_id(self, mock_state_store):
        """Vérifie que chaque tâche reçoit un ID unique incrémental."""
        task_manager = TaskManager(
            state_store=mock_state_store,
            script_generator=MagicMock(),
        )

        task1 = task_manager.create_task(
            subject="Sujet 1", niche="Tech", style="educatif"
        )
        task2 = task_manager.create_task(
            subject="Sujet 2", niche="Tech", style="educatif"
        )

        assert task1["task_id"] != task2["task_id"]

    def test_task_lifecycle(self, mock_state_store, mock_hf_client):
        """Vérifie le cycle de vie complet pending → generating → awaiting_validation → approved.

        Utilise un TaskManager réel avec ScriptGenerator mocké.
        """
        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            '{"hook": "H", "transition": "T", "body_points": ["P1"], '
            '"cta": "C", "hashtags": ["#h"], "description": "D", '
            '"music_suggestion": "M", "visual_notes": "V"}'
        )
        mock_hf_client.chat.completions.create.return_value = mock_response

        from agent.script_generator import ScriptGenerator

        script_gen = ScriptGenerator(hf_token="fake_token")
        task_manager = TaskManager(
            state_store=mock_state_store,
            script_generator=script_gen,
        )

        import json

        saved_tasks = []

        def add_task_side_effect(task):
            saved_tasks.append(task)
            task_copy = dict(task)
            mock_state_store.get_task.return_value = task_copy
            return None

        def update_task_side_effect(task_id, updates):
            for t in saved_tasks:
                if t["task_id"] == task_id:
                    t.update(updates)
                    mock_state_store.get_task.return_value = dict(t)
                    return True
            return False

        mock_state_store.add_task.side_effect = add_task_side_effect
        mock_state_store.update_task.side_effect = update_task_side_effect

        task = task_manager.create_task(
            subject="Test lifecycle",
            niche="Tech",
            style="liste_educative",
        )
        assert task["status"] == TASK_STATUS_PENDING

        import asyncio
        result = asyncio.run(
            task_manager.generate_script(task["task_id"])
        )
        assert result is not None

        updated = mock_state_store.get_task(task["task_id"])
        assert updated["status"] == TASK_STATUS_AWAITING_VALIDATION
        assert updated["script_data"] is not None
        assert updated["script_data"]["hook"] == "H"

    def test_approve_task(self, mock_state_store, sample_task):
        """Vérifie le changement de statut lors de l'approbation."""
        awaiting_task = {
            **sample_task,
            "status": TASK_STATUS_AWAITING_VALIDATION,
        }
        mock_state_store.get_task.return_value = dict(awaiting_task)
        mock_state_store.update_task.return_value = True

        task_manager = TaskManager(
            state_store=mock_state_store,
            script_generator=MagicMock(),
        )

        result = task_manager.approve_task(
            sample_task["task_id"], notes="Super script !"
        )
        assert result is True

        mock_state_store.update_task.assert_called_with(
            sample_task["task_id"],
            {
                "status": TASK_STATUS_APPROVED,
                "notes": "Super script !",
                "updated_at": mock_state_store.update_task.call_args[
                    0
                ][1]["updated_at"],
            },
        )

    def test_reject_task_with_reason(self, mock_state_store, sample_task):
        """Vérifie le stockage du motif de rejet."""
        awaiting_task = {
            **sample_task,
            "status": TASK_STATUS_AWAITING_VALIDATION,
        }
        mock_state_store.get_task.return_value = dict(awaiting_task)

        task_manager = TaskManager(
            state_store=mock_state_store,
            script_generator=MagicMock(),
        )

        result = task_manager.reject_task(
            sample_task["task_id"],
            reason="Hors sujet pour la niche",
        )
        assert result is True

        mock_state_store.update_task.assert_called_with(
            sample_task["task_id"],
            {
                "status": TASK_STATUS_REJECTED,
                "rejection_reason": "Hors sujet pour la niche",
                "updated_at": mock_state_store.update_task.call_args[
                    0
                ][1]["updated_at"],
            },
        )

    def test_reject_task_missing_id(self, mock_state_store):
        """Vérifie que rejeter une tâche inexistante retourne False."""
        mock_state_store.get_task.return_value = None

        task_manager = TaskManager(
            state_store=mock_state_store,
            script_generator=MagicMock(),
        )

        result = task_manager.reject_task(
            "task_inexistante", reason="Test"
        )
        assert result is False

    def test_get_queue_summary(
        self, mock_state_store, sample_task
    ):
        """Vérifie les compteurs du résumé de file."""
        tasks = [
            {**sample_task, "task_id": "task_001", "status": "pending"},
            {
                **sample_task,
                "task_id": "task_002",
                "status": "awaiting_validation",
            },
            {
                **sample_task,
                "task_id": "task_003",
                "status": "approved",
            },
            {
                **sample_task,
                "task_id": "task_004",
                "status": "rejected",
            },
            {
                **sample_task,
                "task_id": "task_005",
                "status": "error",
            },
        ]
        mock_state_store.get_tasks.return_value = tasks

        task_manager = TaskManager(
            state_store=mock_state_store,
            script_generator=MagicMock(),
        )

        summary = task_manager.get_queue_summary()

        assert "En attente: 1" in summary
        assert "En validation: 1" in summary
        assert "Approuvees: 1" in summary
        assert "Rejetees: 1" in summary
        assert "En erreur: 1" in summary
        assert "task_001" in summary
        assert "task_002" in summary

    def test_regenerate_script(self, mock_state_store, sample_task):
        """Vérifie que la régénération réinitialise le statut et les données."""
        mock_state_store.get_task.return_value = dict(sample_task)

        task_manager = TaskManager(
            state_store=mock_state_store,
            script_generator=MagicMock(),
        )

        result = task_manager.regenerate_script(
            sample_task["task_id"]
        )
        assert result is True

        mock_state_store.update_task.assert_called_with(
            sample_task["task_id"],
            {
                "status": TASK_STATUS_PENDING,
                "script_data": None,
                "updated_at": mock_state_store.update_task.call_args[
                    0
                ][1]["updated_at"],
            },
        )

    def test_get_queue_summary_empty(self, mock_state_store):
        """Vérifie le résumé quand il n'y a aucune tâche."""
        mock_state_store.get_tasks.return_value = []

        task_manager = TaskManager(
            state_store=mock_state_store,
            script_generator=MagicMock(),
        )

        summary = task_manager.get_queue_summary()

        assert "Aucune tache" in summary
        assert "En attente: 0" in summary

    def test_get_history(self, mock_state_store, sample_task):
        """Vérifie la récupération de l'historique."""
        tasks = [
            {**sample_task, "task_id": f"task_{i:03d}"}
            for i in range(5)
        ]
        mock_state_store.get_tasks.return_value = tasks

        task_manager = TaskManager(
            state_store=mock_state_store,
            script_generator=MagicMock(),
        )

        history = task_manager.get_history(n=3)
        assert len(history) == 3
        assert history[-1]["task_id"] == "task_004"

    def test_approve_task_invalid_transition(
        self, mock_state_store, sample_task
    ):
        """Vérifie qu'approuver une tâche déjà approuvée échoue."""
        approved_task = {**sample_task, "status": "approved"}
        mock_state_store.get_task.return_value = approved_task

        task_manager = TaskManager(
            state_store=mock_state_store,
            script_generator=MagicMock(),
        )

        result = task_manager.approve_task(
            sample_task["task_id"]
        )
        assert result is False

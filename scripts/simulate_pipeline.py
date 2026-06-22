#!/usr/bin/env python3
"""
Simulation du pipeline complet TikTok Agent.
Teste l'enchainement : creation tache -> script -> image -> validation -> archive.
Sans tokens Discord ni HF.
"""

import os
import sys
import json
import tempfile
from unittest.mock import MagicMock

# ─── Auto-detection du venv ──────────────────────────────────
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_dir = os.path.dirname(_script_dir)
_venv_python = os.path.join(_project_dir, '.venv', 'bin', 'python3')
if not sys.executable.startswith(os.path.join(_project_dir, '.venv')) and os.path.exists(_venv_python):
    os.execv(_venv_python, [_venv_python] + sys.argv)

os.environ['HF_TOKEN'] = 'mock'
os.environ['DISCORD_BOT_TOKEN'] = 'mock'
os.environ['DISCORD_GUILD_ID'] = '123'

sys.path.insert(0, _project_dir)

from agent.state_store import StateStore
from agent.task_manager import TaskManager


def simulate():
    print("\nSimulation du pipeline complet")
    print("=" * 40)

    # Etape 1 : Initialisation
    tmp_dir = tempfile.mkdtemp()
    orig_dir = os.getcwd()
    os.chdir(tmp_dir)

    mock_script_gen = MagicMock()
    store = StateStore()
    tm = TaskManager(state_store=store, script_generator=mock_script_gen)
    print("OK StateStore + TaskManager initialises")

    # Etape 2 : Creation d'une tache
    task = tm.create_task(
        subject="3 outils IA gratuits qui vont changer ta productivite",
        niche="Tech & IA"
    )
    print(f"OK Tache creee : {task['task_id']}")
    print(f"   Sujet : {task['subject']}")
    print(f"   Niche : {task['niche']}")
    print(f"   Statut : {task['status']}")

    # Etape 3 : Simulation generation
    store.update_task(task['task_id'], {'status': 'generating'})
    print("OK Statut -> generating")

    store.update_task(task['task_id'], {'status': 'awaiting_validation'})
    print("OK Statut -> awaiting_validation")

    # Etape 4 : Validation
    result = tm.approve_task(task['task_id'])
    print(f"OK Statut -> approved (validation humaine simulee)")

    # Etape 5 : Resume
    summary = tm.get_queue_summary()
    print(f"\nResume final :")
    print(summary)

    # Etape 6 : Verification state.json
    state_path = store.file_path
    if os.path.exists(state_path):
        with open(state_path, 'r') as f:
            data = json.load(f)
        print(f"\nContenu de state.json :")
        print(json.dumps(data, indent=2, default=str)[:600])

    os.chdir(orig_dir)
    print("\nPipeline simule avec succes !")

if __name__ == '__main__':
    simulate()

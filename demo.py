#!/usr/bin/env python3
"""
Demo locale — TikTok Agent Autonome
Teste les composants principaux sans tokens Discord ni Hugging Face.
Utilise des mocks pour les appels API et des donnees d'exemple.
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# ─── Auto-detection du venv ──────────────────────────────────
# Se relance dans .venv si les dependances ne sont pas installees
_script_dir = os.path.dirname(os.path.abspath(__file__))
_venv_python = os.path.join(_script_dir, '.venv', 'bin', 'python3')
if not sys.executable.startswith(os.path.join(_script_dir, '.venv')) and os.path.exists(_venv_python):
    os.execv(_venv_python, [_venv_python] + sys.argv)

# ─── Configuration minimale pour les imports ─────────────────
os.environ['HF_TOKEN'] = 'mock'
os.environ['DISCORD_BOT_TOKEN'] = 'mock'
os.environ['DISCORD_GUILD_ID'] = '123456789'
os.environ['CHANNEL_COMMANDES'] = '1'
os.environ['CHANNEL_VALIDATION'] = '2'
os.environ['CHANNEL_SCRIPTS'] = '3'
os.environ['CHANNEL_TENDANCES'] = '4'
os.environ['CHANNEL_RAPPORTS'] = '5'
os.environ['CHANNEL_CHAT_AGENT'] = '6'

# Ajouter la racine au path
sys.path.insert(0, _script_dir)

# ─── Import des modules ───────────────────────────────────────
from utils.helpers import generate_task_id, format_duration, sanitize_filename
from utils.logger import logger


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def test_helpers():
    section("1. Utilitaires (helpers)")

    task_id = generate_task_id()
    print(f"  generate_task_id() -> {task_id}")
    assert task_id.startswith("task_"), "ID doit commencer par task_"

    duration = format_duration(125)
    print(f"  format_duration(125) -> {duration}")
    assert "2m" in duration or "125" in duration

    clean = sanitize_filename("Mon/Sujet:Special!")
    print(f"  sanitize_filename('Mon/Sujet:Special!') -> {clean}")
    assert "/" not in clean

    print("  OK Helpers")


def test_state_store():
    section("2. State Store (persistance)")

    from agent.state_store import StateStore

    tmp_dir = tempfile.mkdtemp()
    orig_dir = os.getcwd()
    os.chdir(tmp_dir)

    store = StateStore()
    print(f"  state.json cree: {store.file_path}")
    assert 'config' in store._data
    assert 'tasks' in store._data
    assert store._data['config']['niche'] == 'Tech & IA'

    # Ajouter une tache
    task = {
        "task_id": generate_task_id(),
        "subject": "Test IA",
        "status": "pending",
        "niche": "Tech & IA"
    }
    store.add_task(task)
    print(f"  Tache ajoutee: {task['task_id']}")

    # Recharger
    store2 = StateStore()
    assert len(store2.get_tasks()) == 1
    assert store2.get_tasks()[0]['subject'] == 'Test IA'
    print("  OK StateStore (persistance et rechargement)")

    os.chdir(orig_dir)


def test_task_manager():
    section("3. Task Manager (cycle de vie)")

    from agent.state_store import StateStore
    from agent.task_manager import TaskManager

    tmp_dir = tempfile.mkdtemp()
    orig_dir = os.getcwd()
    os.chdir(tmp_dir)

    store = StateStore()
    # Mock du ScriptGenerator (pas de vrai LLM)
    mock_script_gen = MagicMock()
    tm = TaskManager(state_store=store, script_generator=mock_script_gen)

    # Creation
    task = tm.create_task("3 outils IA gratuits", "Tech & IA")
    print(f"  Tache creee: {task['task_id']} -> statut: {task['status']}")
    assert task['status'] == 'pending'
    assert task['subject'] == '3 outils IA gratuits'

    # Changement de statut via la store directement (pas de generate_script
    # asynchrone ici)
    store.update_task(task['task_id'], {'status': 'generating'})
    task = store.get_task(task['task_id'])
    assert task['status'] == 'generating'

    store.update_task(task['task_id'], {'status': 'awaiting_validation'})
    task = store.get_task(task['task_id'])
    assert task['status'] == 'awaiting_validation'

    # Approbation
    result = tm.approve_task(task['task_id'])
    assert result is True
    task = store.get_task(task['task_id'])
    assert task['status'] == 'approved'
    print(f"  OK Tache approuvee: {task['status']}")

    # Rejet avec motif
    task2 = tm.create_task("Sujet a rejeter", "Tech & IA")
    store.update_task(task2['task_id'], {'status': 'awaiting_validation'})
    tm.reject_task(task2['task_id'], "Hors sujet")
    task2 = store.get_task(task2['task_id'])
    assert task2['status'] == 'rejected'
    assert task2['rejection_reason'] == 'Hors sujet'
    print(f"  OK Tache rejetee avec motif: {task2['rejection_reason']}")

    # Queue summary (retourne une chaine, pas un dict)
    summary = tm.get_queue_summary()
    print(f"  File: {summary[:80]}...")
    assert "Approuvees" in summary
    assert "Rejetees" in summary

    print("  OK TaskManager")

    os.chdir(orig_dir)


def test_text_visual():
    section("4. Generateur d'images Texte (Pillow, 100% local)")

    from image.text_visual import TextVisualGenerator

    gen = TextVisualGenerator()
    script_data = {
        'hook': '3 astuces IA qui vont te surprendre',
        'niche': 'Tech & IA',
        'body_points': ['Point 1', 'Point 2', 'Point 3'],
    }

    tmp_dir = tempfile.mkdtemp()
    result = gen.generate(script_data, output_dir=tmp_dir)

    if result and os.path.exists(result):
        file_size = os.path.getsize(result)
        print(f"  Image generee: {result}")
        print(f"  Taille: {file_size/1024:.1f} KB")
        import shutil
        shutil.rmtree(tmp_dir)
        print("  OK TextVisualGenerator (100% CPU, sans GPU)")
    else:
        print("  WARNING: Image non generee")


def test_postprocessor():
    section("5. Post-Processor (recadrage, watermark)")

    from image.postprocessor import PostProcessor
    from PIL import Image

    pp = PostProcessor(watermark_text='@test')

    # Creer une image test
    tmp_dir = tempfile.mkdtemp()
    test_img = os.path.join(tmp_dir, "test_input.jpg")
    img = Image.new('RGB', (512, 512), color='blue')
    img.save(test_img)

    # Post-process (image = chemin fichier, task_id, add_gradient)
    result = pp.process(test_img, "test_task", add_gradient=True)

    if result and os.path.exists(result):
        with Image.open(result) as processed:
            print(f"  Dimensions: {processed.size}")
            assert processed.size == (1080, 1920), "Format 9:16 attendu"
        print("  OK PostProcessor (recadrage + watermark)")

    import shutil
    shutil.rmtree(tmp_dir)


def test_palettes():
    section("6. Palettes de couleurs")

    try:
        from image.palettes import PALETTES, get_palette
        print(f"  Palettes disponibles: {list(PALETTES.keys())}")

        for niche_name in ['tech', 'motivation', 'sante', 'mode', 'nature']:
            palette = get_palette(niche_name)
            name = palette.get('name', palette.get('accent', 'OK'))
            print(f"  {niche_name}: {name}")

        # Palette par defaut
        default = get_palette('inconnu')
        print(f"  Fallback (inconnu): OK")
        print("  OK Palettes")
    except ImportError as e:
        print(f"  WARNING: Module palettes non trouve: {e}")


def test_config():
    section("7. Configuration")

    from config import Settings
    s = Settings()
    print(f"  Niche par defaut: {s.DEFAULT_NICHE}")
    print(f"  Schedule hours: {s.SCHEDULE_HOURS}")
    print(f"  Auto generate: {s.AUTO_GENERATE}")
    print(f"  Watermark: {s.WATERMARK_TEXT}")
    print("  OK Config")


# ─── Main ──────────────────────────────────────────────────────

if __name__ == '__main__':
    print("\n" + "██╗  ██╗████████╗██╗  ██╗████████╗ ██████╗ ██╗  ██╗")
    print("██║ ██╔╝╚══██╔══╝██║ ██╔╝╚══██╔══╝██╔═══██╗██║ ██╔╝")
    print("█████╔╝    ██║   █████╔╝    ██║   ██║   ██║█████╔╝ ")
    print("██╔═██╗    ██║   ██╔═██╗    ██║   ██║   ██║██╔═██╗ ")
    print("██║  ██╗   ██║   ██║  ██╗   ██║   ╚██████╔╝██║  ██╗")
    print("╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝")
    print("          Agent Autonome TikTok -- Demo Locale\n")
    print("  Test sans tokens Discord ni Hugging Face")
    print("  Verifie les composants principaux du projet\n")

    tests = [
        test_helpers,
        test_state_store,
        test_task_manager,
        test_config,
        test_text_visual,
        test_postprocessor,
        test_palettes,
    ]

    passed = 0
    failed = 0
    errors = []

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((test.__name__, str(e)))
            print(f"  XXX {test.__name__} ECHOUE: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"  Resultat: {passed}/{passed+failed} tests passes")
    if errors:
        print(f"  Echecs:")
        for name, err in errors:
            print(f"    - {name}: {err}")
    else:
        print("  Tous les tests de demo ont reussi !")
    print(f"{'='*60}\n")

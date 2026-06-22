# Guide de test local — TikTok Agent Autonome

## Objectif
Tester les composants du projet **sans avoir besoin** de tokens Discord ou Hugging Face.

## 1. Pre-requis
- Python 3.11+
- Git

## 2. Installation
```bash
git clone <votre-repo>
cd tiktok-agent

# Creer et activer le venv
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# ou .\venv\Scripts\activate  # Windows

# Installer les dependances
pip install -r requirements.txt
pip install pytest pytest-asyncio  # Pour les tests
```

## 3. Lancer la demo rapide
```bash
python3 demo.py
```
Teste sans aucun token : helpers, state store, task manager, config,
generateur d'images texte (Pillow, 100% CPU), post-processeur, palettes.

## 4. Lancer les tests unitaires
```bash
pytest tests/ -v
```
46 tests couvrent : script generator, task manager, trend analyzer,
image router, commands Discord.

## 5. Tester un composant specifique
```bash
# Tester uniquement le gestionnaire de taches
pytest tests/test_task_manager.py -v

# Tester le generateur de scripts (avec mock LLM)
pytest tests/test_script_generator.py -v

# Tester le routeur d'images
pytest tests/test_image_router.py -v
```

## 6. Simulation du pipeline complet (sans Discord)
```bash
python3 scripts/simulate_pipeline.py
```
Simule le pipeline de A a Z sans Discord :
1. Cree une tache
2. Simule la generation
3. Simule la validation
4. Affiche le resume

## 7. Test avec un vrai token HF (optionnel)
Si tu as un token Hugging Face (gratuit sur hf.co/settings/tokens) :
```bash
export HF_TOKEN=hf_votre_token
python3 -c "
from agent.script_generator import ScriptGenerator
gen = ScriptGenerator()
# Test LLM reel (peut prendre 30s)
print(gen.generate_sync('L\'IA en 2025'))
"
```

## 8. Verification avant deploiement
- [ ] `python3 demo.py` -> tous les tests passent
- [ ] `pytest tests/ -v` -> 46/46 OK
- [ ] `.env.example` configure avec tes valeurs
- [ ] Projet pushe sur le HF Space

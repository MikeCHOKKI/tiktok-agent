# TikTok Agent Autonome 🎬🤖

Agent IA automatisé pour la création de contenu TikTok, contrôlé entièrement via Discord.

## ✨ Fonctionnalités

- **Génération de scripts viraux** via Llama 3 (HF InferenceClient)
- **Pipeline image** (SDXL-Turbo, SD 2.1, Kandinsky 2.2, Pillow)
- **Analyse des tendances** toutes les 12h (Google Trends RSS)
- **Rapport hebdomadaire** automatique
- **Validation humaine** par boutons Discord
- **Zéro coût d'infrastructure** (Hugging Face Spaces CPU gratuit)

## 🏗 Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Discord     │────▶│  Agent Central    │────▶│  HF Serverless   │
│  (Bot + UI)  │     │  (HF Space)       │     │  (LLM + Images)  │
└─────────────┘     └──────────────────┘     └─────────────────┘
                            │
                     ┌──────┴──────┐
                     │  state.json  │
                     │  HF Dataset  │
                     └─────────────┘
```

## 🚀 Démarrage rapide

### Prérequis

- Compte Hugging Face (gratuit)
- Serveur Discord
- Python 3.11+

### Installation

1. Créer un Space HF (CPU Basic Free)
2. Copier les fichiers dans le Space
3. Configurer les secrets (cf. `.env.example`)
4. Lancer le Space

### Configuration locale

```bash
git clone https://github.com/votre-compte/tiktok-agent.git
cd tiktok-agent

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Éditer .env avec vos tokens Discord et Hugging Face

python app.py
```

## 📋 Commandes Discord

| Commande | Description |
|----------|-------------|
| `/generer <sujet> [niche]` | Génère un script TikTok + image |
| `/tendances` | Analyse les tendances immédiatement |
| `/niche <niche>` | Change la niche de contenu |
| `/statut` | Affiche la file de tâches et les jobs |
| `/rapport` | Génère un rapport d'activité |
| `/planifier <sujet> <jour> <heure>` | Planifie une génération |
| `/historique [n]` | Affiche les derniers scripts |
| `/config <paramètre> <valeur>` | Modifie la configuration |
| `/aide` | Liste toutes les commandes |

## 💬 Chat Agent

Le channel `#chat-agent` permet de discuter avec l'agent en mode conseiller stratégique. Posez vos questions sur la stratégie de contenu, les tendances, ou demandez des recommandations personnalisées.

## 🛠 Stack

- **Python 3.11** — Langage principal
- **discord.py** — Interface utilisateur Discord
- **Hugging Face Hub** — LLM (Llama 3) et génération d'images
- **APScheduler** — Planification automatique
- **Pillow** — Génération de visuels texte 100% CPU
- **feedparser** — Analyse des flux RSS Google Trends

## 📂 Structure du projet

```
tiktok-agent/
├── agent/                  # Logique métier
│   ├── script_generator.py # Génération de scripts LLM
│   ├── task_manager.py     # Gestion du cycle de vie des tâches
│   ├── state_store.py      # Persistance JSON + HF Dataset
│   ├── trend_analyzer.py   # Analyse multi-sources des tendances
│   ├── report_builder.py   # Rapports hebdomadaires
│   └── scheduler.py        # Planification APScheduler
├── discord_bot/            # Interface Discord
│   ├── bot.py              # Client Discord principal
│   ├── commands.py         # Slash commands
│   ├── buttons.py          # Boutons de validation
│   ├── channels.py         # Gestion des canaux
│   └── notifier.py         # Envoi de notifications
├── image/                  # Pipeline de génération d'images
│   ├── router.py           # Routeur vers le bon générateur
│   ├── thumbnail.py        # Miniatures SDXL Turbo
│   ├── background.py       # Fonds Stable Diffusion 2.1
│   ├── text_visual.py      # Visuels texte 100% Pillow
│   ├── illustration.py     # Illustrations Kandinsky 2.2
│   └── postprocessor.py    # Post-processing (watermark, etc.)
├── utils/                  # Utilitaires
│   ├── logger.py           # Logger structuré
│   └── helpers.py          # Fonctions utilitaires
├── config.py               # Configuration centralisée
├── app.py                  # Point d'entrée principal
├── .env.example            # Exemple de configuration
├── requirements.txt        # Dépendances Python
└── README.md               # Documentation
```

## 🧪 Tests

```bash
# Installer les dépendances de test
pip install pytest

# Lancer tous les tests
pytest tests/ -v

# Lancer un module spécifique
pytest tests/test_script_generator.py -v
```

## 🎮 Tester sans tokens

```bash
# Démo rapide — teste les composants sans aucun token
python3 demo.py

# Simulation du pipeline complet
python3 scripts/simulate_pipeline.py

# Lance les 46 tests unitaires
pytest tests/ -v
```

Voir [docs/TEST_LOCAL.md](docs/TEST_LOCAL.md) pour le guide complet.

## 📄 License

[MIT](LICENSE) — © 2026 Mike E.S. Chokki

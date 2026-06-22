# Cahier des Charges Technique — Agent Autonome TikTok + Discord

**Version :** 1.0
**Date :** Juin 2025
**Statut :** Production — Confidentiel
**Infrastructure :** Hugging Face Spaces (CPU Free)
**Interface utilisateur :** Discord (Bot + Webhooks)

---

## Table des matieres
1. Vision & Objectifs du Projet
2. Architecture Technique
3. Bot Discord — Specification Complete
4. Module Generation de Scripts TikTok
5. Module Generation d'Images
6. Module Analyse des Tendances
7. Gestionnaire de Taches (Task Manager)
8. Rapport Hebdomadaire Automatique
9. Scheduler & Fonctionnement Autonome
10. Configuration & Variables Secretes
11. Plan de Developpement
12. Tests & Criteres d'Acceptance
13. Guide de Deploiement Pas a Pas
14. Glossaire
15. Annexes

---

## 1. Vision & Objectifs du Projet

### 1.1 Vision
Creer un agent IA entierement autonome capable de produire du contenu TikTok viral,
de la generation du script a la creation du visuel, en passant par l'analyse des tendances
et la publication, le tout controle via une interface Discord intuitive.

### 1.2 Objectifs strategiques
- Automatiser la creation de contenu TikTok a grande echelle
- Zero cout d'infrastructure (Hugging Face Spaces gratuit)
- Intervention humaine minimale (validation uniquement)
- Adaptation continue aux tendances

### 1.3 Perimetre
- **Inclus :** Generation de scripts, images, analyse de tendances, planification,
  validation humaine, rapports hebdomadaires
- **Exclus :** Publication automatique sur TikTok (visee Phase 5), hebergement GPU

---

## 2. Architecture Technique

### 2.1 Vue d'ensemble
```
+-------------+     +------------------+     +-----------------+
|  Discord     |---->|  Agent Central    |---->|  HF Serverless   |
|  (Bot + UI)  |     |  (HF Space)       |     |  (LLM + Images)  |
+-------------+     +------------------+     +-----------------+
                            |
                     +------+------+
                     |  state.json  |
                     |  HF Dataset  |
                     +-------------+
```

### 2.2 Stack technique
- **Python 3.11** — Langage principal
- **discord.py 2.3+** — Interface utilisateur Discord
- **Hugging Face Hub / InferenceClient** — LLM (Llama 3) et generation d'images
- **APScheduler 3.10+** — Planification automatique
- **Pillow 10+** — Generation de visuels texte 100% CPU
- **feedparser 6.0+** — Analyse des flux RSS Google Trends
- **Hugging Face Datasets** — Persistance longue duree (Phase 4)

### 2.3 Structure du projet
```
tiktok-agent/
+-- agent/                  # Logique metier
|   +-- script_generator.py # Generation de scripts LLM
|   +-- task_manager.py     # Gestion du cycle de vie des taches
|   +-- state_store.py      # Persistance JSON + HF Dataset
|   +-- trend_analyzer.py   # Analyse multi-sources des tendances
|   +-- report_builder.py   # Rapports hebdomadaires
|   +-- scheduler.py        # Planification APScheduler
+-- discord_bot/            # Interface Discord
|   +-- bot.py              # Client Discord principal
|   +-- commands.py         # Slash commands
|   +-- buttons.py          # Boutons de validation
|   +-- channels.py         # Gestion des canaux
|   +-- notifier.py         # Envoi de notifications
+-- image/                  # Pipeline de generation d'images
|   +-- router.py           # Routeur vers le bon generateur
|   +-- thumbnail.py        # Miniatures SDXL Turbo
|   +-- background.py       # Fonds Stable Diffusion 2.1
|   +-- text_visual.py      # Visuels texte 100% Pillow
|   +-- illustration.py     # Illustrations Kandinsky 2.2
|   +-- postprocessor.py    # Post-processing (watermark, etc.)
|   +-- palettes.py         # Palettes de couleurs par niche
+-- utils/                  # Utilitaires
|   +-- logger.py           # Logger structure
|   +-- helpers.py          # Fonctions utilitaires
+-- config.py               # Configuration centralisee
+-- app.py                  # Point d'entree principal
+-- demo.py                 # Script de demo locale
+-- scripts/                # Scripts auxiliaires
|   +-- simulate_pipeline.py# Simulation du pipeline complet
+-- tests/                  # Tests unitaires (46 tests)
+-- docs/                   # Documentation
|   +-- TEST_LOCAL.md       # Guide de test local
|   +-- CAHIER_DES_CHARGES.md  # Ce document
+-- .env.example            # Exemple de configuration
+-- requirements.txt        # Dependances Python
```

---

## 3. Bot Discord — Specification Complete

### 3.1 Commandes
| Commande | Description | Permission |
|----------|-------------|------------|
| `/generer <sujet> [niche]` | Genere un script TikTok + image | Tous |
| `/tendances` | Analyse les tendances immediatement | Tous |
| `/niche <niche>` | Change la niche de contenu | Admin |
| `/statut` | Affiche la file de taches | Tous |
| `/rapport` | Genere un rapport d'activite | Tous |
| `/planifier <sujet> <jour> <heure>` | Planifie une generation | Tous |
| `/historique [n]` | Affiche les derniers scripts | Tous |
| `/config <parametre> <valeur>` | Modifie la configuration | Admin |
| `/aide` | Liste toutes les commandes | Tous |

### 3.2 Canaux dedies
- **commandes** : Slash commands
- **validation** : Boutons Approuver/Rejeter/Regenerer
- **scripts** : Scripts generes automatiquement
- **tendances** : Analyses de tendances
- **rapports** : Rapports hebdomadaires
- **chat-agent** : Mode conseiller strategique

### 3.3 Systeme de validation
- Chaque script genere est soumis a validation humaine (boutons Discord)
- Statuts : pending -> generating -> awaiting_validation -> approved/rejected/error
- Possibilite de regenerer le script ou l'image
- Motif de rejet obligatoire pour feedback

---

## 4. Module Generation de Scripts TikTok

### 4.1 Modele LLM
- Modele : Llama 3 via Hugging Face InferenceClient (gratuit)
- Temperature : 0.7 (equilibre creativite/coherence)
- Max tokens : 1024
- Format de sortie : JSON structure

### 4.2 Structure d'un script genere
```json
{
  "hook": "Accroche qui capte l'attention",
  "transition": "Phrase de transition",
  "body_points": ["Point 1", "Point 2", "Point 3"],
  "cta": "Appel a l'action",
  "hashtags": ["#hashtag1", "#hashtag2"],
  "description": "Description de la video",
  "music_suggestion": "Son recommande",
  "visual_notes": "Notes pour le montage"
}
```

### 4.3 Contraintes
- Script en francais
- Duree cible : 30-60 secondes
- Tone adapte a la niche (educatif, divertissant, inspirant...)
- Hook dans les 3 premieres secondes

---

## 5. Module Generation d'Images

### 5.1 Types de visuels
| Type | Moteur | Usage |
|------|--------|-------|
| `text_visual` | Pillow (100% CPU) | Texte sur fond degrade |
| `thumbnail` | SDXL Turbo (HF) | Miniatures accrocheuses |
| `background` | Stable Diffusion 2.1 (HF) | Fonds thematiques |
| `illustration` | Kandinsky 2.2 (HF) | Illustrations artistiques |

### 5.2 Mapping niche -> type de visuel
- tech/motivation -> text_visual
- sante/nature -> background
- mode -> illustration
- cuisine/sport -> thumbnail

### 5.3 Post-processing (applications systematiques)
1. Recadrage au format 9:16 (1080x1920)
2. Watermark semi-transparent (bas droite)
3. Optimisation JPEG (< 8 MB pour Discord)
4. Gradient sombre optionnel (lisibilite)
5. Nettoyage automatique des fichiers de +2h

### 5.4 Palettes de couleurs par niche
- tech : Noir/#1A1A2E, texte blanc, accent bleu
- motivation : Orange/Orange fonce, texte blanc, accent or
- sante : Blanc/gris clair, texte fonce, accent vert
- mode : Violet fonce/violet, texte blanc, accent lavande
- nature : Vert fonce/vert, texte blanc, accent vert clair
- cuisine : Rouge bordeaux/rose, texte blanc, accent or
- sport : Bleu fonce/bleu, texte blanc, accent rouge

---

## 6. Module Analyse des Tendances

### 6.1 Sources
- Google Trends RSS (daily trending searches, geo=FR)
- YouTube API (optionnel, necessite cle API)
- Flux RSS niches personnalisables

### 6.2 Frequence
- Auto : Toutes les 12h (6h et 18h)
- Manuel : Commande `/tendances`

### 6.3 Cache
- Resultat mis en cache dans state.json
- Invalide apres chaque scan

---

## 7. Gestionnaire de Taches (Task Manager)

### 7.1 Cycle de vie d'une tache
```
pending -> generating -> awaiting_validation -> approved
                                              -> rejected
                                              -> generating (regeneration)
         -> error -> pending (retry)
```

### 7.2 Transitions valides
| De | Vers |
|----|------|
| pending | generating |
| generating | awaiting_validation, error |
| awaiting_validation | approved, rejected, generating |
| approved | (terminal) |
| rejected | (terminal) |
| error | pending |

### 7.3 Persistance
- Fichier local : `state.json`
- Cloud (optionnel) : Hugging Face Dataset (push toutes les 10 modifications)
- Restauration automatique au demarrage si fichier local vide

---

## 8. Rapport Hebdomadaire Automatique

### 8.1 Contenu
- Nombre de scripts generes / approuves / rejetes
- Tendances de la semaine
- Performance par niche
- Recommendations

### 8.2 Format
- Message Discord structure (embeds)
- Envoi automatique chaque lundi a 9h

---

## 9. Scheduler & Fonctionnement Autonome

### 9.1 Taches planifiees
| Tache | Frequence | Heures |
|-------|-----------|--------|
| Analyse tendances | 2x/jour | 6h, 18h |
| Generation automatique | 2x/jour | 6h, 18h |
| Rappel validation | 1x/jour | 9h |
| Rapport hebdomadaire | 1x/semaine | Lundi 9h |
| Nettoyage fichiers | 1x/jour | 3h |

### 9.2 Comportement
- Mode autonome : `AUTO_GENERATE=true`
- Mode semi-auto : validation humaine requise pour chaque script
- Arret propre avec sauvegarde finale (SIGTERM/SIGINT)

---

## 10. Configuration & Variables Secretes

### 10.1 Variables obligatoires
| Variable | Description |
|----------|-------------|
| `HF_TOKEN` | Token Hugging Face (gratuit) |
| `DISCORD_BOT_TOKEN` | Token du bot Discord |
| `DISCORD_GUILD_ID` | ID du serveur Discord |
| `CHANNEL_COMMANDES` | ID du channel commandes |
| `CHANNEL_VALIDATION` | ID du channel validation |
| `CHANNEL_SCRIPTS` | ID du channel scripts |
| `CHANNEL_TENDANCES` | ID du channel tendances |
| `CHANNEL_RAPPORTS` | ID du channel rapports |
| `CHANNEL_CHAT_AGENT` | ID du channel chat agent |

### 10.2 Variables optionnelles
| Variable | Defaut | Description |
|----------|--------|-------------|
| `DEFAULT_NICHE` | Tech & IA | Niche par defaut |
| `WATERMARK_TEXT` | @tiktok_agent | Texte du filigrane |
| `YOUTUBE_API_KEY` | (vide) | Cle API YouTube |
| `HF_DATASET_NAME` | (vide) | Dataset HF pour backup |

---

## 11. Plan de Developpement

### Phase 1 — Socle (termine)
- [x] Structure du projet
- [x] Configuration centralisee
- [x] Logger structure
- [x] Helpers utilitaires
- [x] StateStore (persistance JSON)
- [x] Tests unitaires du StateStore

### Phase 2 — Discord + Generation (termine)
- [x] Bot Discord avec slash commands
- [x] ScriptGenerator (LLM via HF InferenceClient)
- [x] TaskManager (cycle de vie des taches)
- [x] Pipeline image (router + generateurs)
- [x] PostProcessor (recadrage, watermark, optimisation)
- [x] Systeme de validation par boutons
- [x] Tests du script generator, task manager, image router

### Phase 3 — Autonome (termine)
- [x] TrendAnalyzer (Google Trends RSS + YouTube)
- [x] ReportBuilder (rapports hebdomadaires)
- [x] TaskScheduler (APScheduler)
- [x] Generation automatique planifiee
- [x] Mode autonome (AUTO_GENERATE)
- [x] Gestion des erreurs et retry
- [x] Tests des tendances et commandes

### Phase 4 — Robustesse (termine)
- [x] Persistance HF Dataset (longue duree)
- [x] Sauvegarde periodique (toutes les 10 modifs)
- [x] Restauration au demarrage
- [x] Arret propre avec sauvegarde finale
- [x] Gestion des signaux (SIGTERM/SIGINT)

### Phase 5 — Extended (a venir)
- [ ] Publication automatique TikTok API
- [ ] Multi-comptes TikTok
- [ ] Dashboard web (Streamlit)
- [ ] Modele fine-tune sur les scripts valides
- [ ] A/B testing des accroches

---

## 12. Tests & Criteres d'Acceptance

### 12.1 Tests unitaires (46 tests)
- test_script_generator.py : Generation, format JSON, fallback
- test_task_manager.py : Cycle de vie, transitions, approbation/rejet
- test_trend_analyzer.py : Analyse RSS, parsing, cache
- test_image_router.py : Routage, types de visuels, fallback
- test_commands.py : Commandes Discord, validation

### 12.2 Demo locale (7 tests)
- helpers : generate_task_id, format_duration, sanitize_filename
- state_store : creation, ajout tache, rechargement
- task_manager : cycle de vie, approbation, rejet, file
- config : chargement, valeurs par defaut
- text_visual : generation image Pillow
- postprocessor : recadrage 9:16, watermark
- palettes : chargement, fallback

### 12.3 Criteres d'acceptance
- [ ] python3 demo.py -> 7/7 OK
- [ ] pytest tests/ -v -> 46/46 OK
- [ ] python3 scripts/simulate_pipeline.py -> pipeline OK
- [ ] Arret propre avec sauvegarde finale
- [ ] Pas de cout d'infrastructure (CPU free)
- [ ] Scripts generes en francais, format JSON valide

---

## 13. Guide de Deploiement Pas a Pas

### 13.1 Sur Hugging Face Spaces
1. Creer un Space HF (CPU Basic Free, Docker/Python)
2. Copier tous les fichiers dans le Space
3. Configurer les secrets (Settings -> Repository Secrets)
4. Redemarrer le Space
5. Inviter le bot Discord sur le serveur

### 13.2 En local
```bash
git clone <repo>
cd tiktok-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Editer .env avec vos tokens
python app.py
```

### 13.3 Verification pre-deploiement
- [ ] `python3 demo.py` -> OK
- [ ] `pytest tests/ -v` -> 46/46 OK
- [ ] `.env.example` configure
- [ ] Secrets configures sur HF Spaces
- [ ] Bot Discord invite avec les bonnes permissions

---

## 14. Glossaire

| Terme | Definition |
|-------|------------|
| **HF** | Hugging Face (hebergeur du Space) |
| **LLM** | Modele de langage (Llama 3) |
| **Niche** | Theme de contenu (Tech, Mode, Sante...) |
| **Hook** | Accroche (3 premieres secondes de la video) |
| **CTA** | Appel a l'action |
| **Space** | Application hebergee sur Hugging Face |
| **State.json** | Fichier de persistance locale |
| **Task** | Tache de generation (script + image) |
| **Watermark** | Filigrane (texte semi-transparent) |
| **9:16** | Format vertical TikTok (1080x1920) |

---

## 15. Annexes

### 15.1 Commandes de maintenance
```bash
# Demo rapide
python3 demo.py

# Tests
pytest tests/ -v

# Pipeline simule
python3 scripts/simulate_pipeline.py

# Nettoyage
rm -rf /tmp/tiktok-agent/
```

### 15.2 Liens utiles
- Hugging Face Tokens : https://hf.co/settings/tokens
- Discord Developer Portal : https://discord.com/developers/applications
- Google Trends RSS : https://trends.google.com/trends/trendingsearches/daily/rss

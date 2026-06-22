"""Generation de scripts TikTok via LLM (Hugging Face Inference).

Utilise le modele Meta-Llama-3-8B-Instruct via l'API serverless
de Hugging Face pour generer des scripts viraux structures en JSON.
"""

import json
import time
from typing import Any, Dict, List, Optional

from huggingface_hub import InferenceClient
from huggingface_hub.utils import HfHubHTTPError

from utils.logger import logger

SYSTEM_PROMPT = (
    "Tu es un expert en creation de contenu viral TikTok "
    "et en strategie de monetisation des createurs. Tu maitrises "
    "les algorithmes de retention TikTok, les techniques de "
    "copywriting pour les formats courts, et les mecanismes de "
    "monetisation (Beta Createur, affiliation, sponsoring).\n\n"
    "Regles imperatives :\n"
    "- Chaque script doit maximiser le taux de retention "
    "sur les 3 premieres secondes\n"
    "- Les phrases font maximum 10 mots (format TikTok oral)\n"
    "- Le ton est conversationnel, direct, jamais scolaire\n"
    "- Le CTA doit etre naturel, pas commercial\n"
    "- Inclure des suggestions de visuels pour chaque partie\n"
    "- Repondre toujours en JSON structure"
)

STYLES_AVAILABLE = [
    "storytelling",
    "liste_educative",
    "debat",
    "tutoriel",
    "reaction",
    "challenge",
]

MODEL_ID = "meta-llama/Meta-Llama-3-8B-Instruct"


class ScriptGenerator:
    """Generateur de scripts TikTok via LLM.

    Attributes:
        client: Client Hugging Face Inference.
        model_id: Identifiant du modele.
    """

    def __init__(self, hf_token: str, model_id: str = MODEL_ID):
        """Initialise le generateur de scripts.

        Args:
            hf_token: Token Hugging Face pour l'API Inference.
            model_id: Identifiant du modele (defaut: Meta-Llama-3-8B).
        """
        if not hf_token:
            raise ValueError("HF_TOKEN requis pour ScriptGenerator")
        self.client = InferenceClient(token=hf_token)
        self.model_id = model_id

    def generate_script(
        self,
        subject: str,
        niche: str = "Tech & IA",
        style: str = "educatif",
    ) -> Dict[str, Any]:
        """Genere un script TikTok structure en JSON.

        Args:
            subject: Sujet de la video.
            niche: Niche de contenu.
            style: Style de video (storytelling, liste_educative, etc.).

        Returns:
            Dict structure avec hook, body_points, cta, hashtags, etc.

        Raises:
            ValueError: Si le style est invalide.
            RuntimeError: Si la generation echoue apres 3 tentatives.
        """
        if style not in STYLES_AVAILABLE:
            raise ValueError(
                f"Style '{style}' invalide. "
                f"Disponibles: {', '.join(STYLES_AVAILABLE)}"
            )

        user_prompt = (
            f"Genere un script TikTok viral pour le sujet suivant :\n"
            f"Sujet : {subject}\n"
            f"Niche : {niche}\n"
            f"Style : {style}\n"
            f"Langue : francais\n\n"
            f"Format JSON attendu :\n"
            f"{{\n"
            f'  "hook": "phrase d accroche max 10 mots",\n'
            f'  "transition": "transition vers le contenu",\n'
            f'  "body_points": ["point 1", "point 2", "point 3"],\n'
            f'  "cta": "appel a action naturel",\n'
            f'  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"],\n'
            f'  "description": "description courte pour la video",\n'
            f'  "music_suggestion": "suggestion musicale",\n'
            f'  "visual_notes": "notes visuelles pour le montage"\n'
            f"}}"
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        max_retries = 3
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    "Generation script [tentative %d/%d] : %s",
                    attempt,
                    max_retries,
                    subject,
                )

                response = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    max_tokens=1024,
                    temperature=0.8,
                    top_p=0.95,
                )

                content = response.choices[0].message.content.strip()
                if not content:
                    raise RuntimeError("Reponse vide du modele")

                script_data = self._parse_response(content)
                script_data["subject"] = subject
                script_data["niche"] = niche
                script_data["style"] = style
                logger.info("Script genere avec succes: %s", subject)
                return script_data

            except HfHubHTTPError as exc:
                last_error = exc
                logger.warning(
                    "Erreur API HF (tentative %d/%d): %s",
                    attempt,
                    max_retries,
                    exc,
                )
                if attempt < max_retries:
                    wait = attempt * 2
                    logger.info("Nouvelle tentative dans %ds...", wait)
                    time.sleep(wait)

            except (json.JSONDecodeError, KeyError) as exc:
                last_error = exc
                logger.warning(
                    "Erreur parsing JSON (tentative %d/%d): %s",
                    attempt,
                    max_retries,
                    exc,
                )

        raise RuntimeError(
            f"Echec generation script apres {max_retries} tentatives: {last_error}"
        )

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse la reponse JSON du LLM.

        Extrait le bloc JSON de la reponse (entre ```json et ``` si present).

        Args:
            content: Texte brut retourne par le LLM.

        Returns:
            Dict structure du script.

        Raises:
            json.JSONDecodeError: Si le parsing echoue.
        """
        cleaned = content.strip()

        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        parsed = json.loads(cleaned)

        expected_keys = [
            "hook", "transition", "body_points", "cta",
            "hashtags", "description", "music_suggestion", "visual_notes",
        ]
        for key in expected_keys:
            if key not in parsed:
                parsed[key] = self._default_for_key(key)

        if not isinstance(parsed.get("body_points", []), list):
            parsed["body_points"] = [str(parsed["body_points"])]
        if not isinstance(parsed.get("hashtags", []), list):
            parsed["hashtags"] = [str(parsed["hashtags"])]

        return parsed

    @staticmethod
    def _default_for_key(key: str) -> Any:
        """Valeur par defaut pour une cle manquante.

        Args:
            key: Nom de la cle.

        Returns:
            Valeur par defaut selon le type attendu.
        """
        defaults = {
            "hook": "Accroche par defaut",
            "transition": "Transition par defaut",
            "body_points": ["Point principal"],
            "cta": "Like et follow pour plus",
            "hashtags": ["#tiktok", "#viral"],
            "description": "Description par defaut",
            "music_suggestion": "Musique tendance du moment",
            "visual_notes": "Montage dynamique",
        }
        return defaults.get(key, "")

    async def chat_response(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Mode dialogue stratégique pour #chat-agent.

        Utilise un prompt système différent (conseiller stratégique,
        pas générateur de script) pour aider le créateur à affiner
        sa stratégie de contenu.

        Args:
            user_message: Message de l'utilisateur.
            context: Contexte optionnel (niche, recent_tasks, trends).

        Returns:
            Réponse textuelle du conseiller.
        """
        context = context or {}
        chat_system_prompt = (
            "Tu es un conseiller strategique en creation de "
            "contenu TikTok. Tu aides le createur a affiner sa "
            "strategie, analyser ses performances, et decider "
            "quel contenu produire.\n\n"
            "Regles :\n"
            "- Reponds en francais, ton conseil et precis\n"
            "- Base-toi sur les tendances actuelles et "
            "l'historique du createur\n"
            "- Propose des actions concretes (pas de theorie)\n"
            "- Maximum 3 paragraphes"
        )

        recent_subjects = [
            t.get("subject", "?")
            for t in (context.get("recent_tasks") or [])
        ]
        current_trends = context.get("current_trends") or "Non disponible"
        niche = context.get("niche", "Non specifiee")

        user_prompt = (
            f"Contexte actuel :\n"
            f"- Niche : {niche}\n"
            f"- Derniers sujets traites : "
            f"{recent_subjects if recent_subjects else 'Aucun'}\n"
            f"- Tendances recentes : {current_trends}\n\n"
            f"Message du createur :\n{user_message}"
        )

        messages = [
            {"role": "system", "content": chat_system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                max_tokens=500,
                temperature=0.7,
                top_p=0.95,
            )

            content = response.choices[0].message.content.strip()
            if not content:
                return (
                    "Je n'ai pas pu formuler de reponse. "
                    "Peux-tu reformuler ta question ?"
                )
            return content

        except Exception as exc:
            logger.error(
                "Erreur chat_response: %s", exc
            )
            return (
                "Desole, je rencontre un probleme technique. "
                "Reessaye dans quelques instants."
            )

    def get_styles(self) -> List[str]:
        """Retourne la liste des styles disponibles.

        Returns:
            Liste des noms de styles.
        """
        return STYLES_AVAILABLE.copy()

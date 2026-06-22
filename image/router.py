"""Routeur principal du pipeline image.

Aiguille la generation vers le bon module selon le type de visuel :
- thumbnail : Miniatures SDXL Turbo
- background : Fonds Stable Diffusion 2.1
- text_visual : Visuels texte 100% Pillow
- illustration : Illustrations Kandinsky 2.2
"""

import time
from typing import Any, Dict, List, Optional

from config import Settings
from image.background import BackgroundGenerator
from image.illustration import IllustrationGenerator
from image.postprocessor import PostProcessor
from image.text_visual import TextVisualGenerator
from image.thumbnail import ThumbnailGenerator
from utils.logger import logger

# Types de visuels disponibles
VISUAL_TYPE_THUMBNAIL = "thumbnail"
VISUAL_TYPE_BACKGROUND = "background"
VISUAL_TYPE_TEXT = "text_visual"
VISUAL_TYPE_ILLUSTRATION = "illustration"

VISUAL_TYPES: List[str] = [
    VISUAL_TYPE_THUMBNAIL,
    VISUAL_TYPE_BACKGROUND,
    VISUAL_TYPE_TEXT,
    VISUAL_TYPE_ILLUSTRATION,
]

# Mapping niche -> type de visuel par defaut
DEFAULT_VISUAL_MAP: Dict[str, str] = {
    "tech": VISUAL_TYPE_TEXT,
    "motivation": VISUAL_TYPE_TEXT,
    "sante": VISUAL_TYPE_BACKGROUND,
    "mode": VISUAL_TYPE_ILLUSTRATION,
    "nature": VISUAL_TYPE_BACKGROUND,
    "cuisine": VISUAL_TYPE_THUMBNAIL,
    "sport": VISUAL_TYPE_THUMBNAIL,
}


class ImageRouter:
    """Routeur du pipeline image.

    Initialise tous les generateurs et le post-processeur,
    puis aiguille chaque tache vers le module approprie.
    """

    def __init__(self, settings: Settings):
        """Initialise le routeur et tous les sous-modules.

        Args:
            settings: Configuration du projet.
        """
        self.hf_token = settings.HF_TOKEN
        self.watermark_text = settings.WATERMARK_TEXT

        self.thumbnail: Optional[ThumbnailGenerator] = None
        self.background: Optional[BackgroundGenerator] = None
        self.text_visual: Optional[TextVisualGenerator] = None
        self.illustration: Optional[IllustrationGenerator] = None
        self.postprocessor: Optional[PostProcessor] = None

        self._initialized = False
        logger.info("ImageRouter cree (en attente d'initialisation)")

    def initialize(self) -> None:
        """Initialise tous les sous-modules.

        Cree les generateurs et le post-processeur.

        Raises:
            ValueError: Si HF_TOKEN est manquant.
        """
        if self._initialized:
            return

        try:
            self.thumbnail = ThumbnailGenerator(hf_token=self.hf_token)
            self.background = BackgroundGenerator(hf_token=self.hf_token)
            self.illustration = IllustrationGenerator(hf_token=self.hf_token)
            logger.info("Generateurs HF initialises")
        except ValueError:
            logger.warning(
                "HF_TOKEN non disponible, generateurs HF desactives"
            )

        self.text_visual = TextVisualGenerator()
        self.postprocessor = PostProcessor(
            watermark_text=self.watermark_text
        )

        self._initialized = True
        logger.info("ImageRouter initialise avec tous les modules")

    def generate_image(
        self,
        task: Dict[str, Any],
        script_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Genere une image pour une tache selon son type de visuel.

        Args:
            task: Donnees de la tache.
            script_data: Donnees du script genere.
            config: Configuration optionnelle.

        Returns:
            Chemin absolu de l'image finale, ou None si erreur.
        """
        if not self._initialized:
            self.initialize()

        if not self.postprocessor:
            logger.error("PostProcessor non disponible")
            return None

        task_id = task.get("task_id", "unknown")
        niche = task.get("niche", "tech")
        hook = script_data.get("hook", "")
        visual_notes = script_data.get("visual_notes", "")
        body_text = " ".join(
            script_data.get("body_points", [])
        )

        # Determination du type de visuel
        visual_type = task.get("visual_type", "")
        if not visual_type or visual_type not in VISUAL_TYPES:
            niche_lower = niche.lower().strip()
            visual_type = DEFAULT_VISUAL_MAP.get(niche_lower, VISUAL_TYPE_TEXT)

        logger.info(
            "Generation image [%s] - tache: %s, niche: %s, type: %s",
            task_id,
            task.get("subject", ""),
            niche,
            visual_type,
        )

        start_time = time.time()

        try:
            image = self._route_generation(
                visual_type=visual_type,
                niche=niche,
                hook=hook,
                body_text=body_text,
                visual_notes=visual_notes,
            )

            if image is None:
                logger.error(
                    "Echec generation image pour tache %s", task_id
                )
                return None

            # Post-processing (gestion str -> fichier deja sur disque)
            final_path = self.postprocessor.process(
                image=image,
                task_id=task_id,
                add_gradient=(
                    visual_type != VISUAL_TYPE_TEXT
                ),
            )

            elapsed = time.time() - start_time
            logger.info(
                "Pipeline image termine en %.1fs - %s",
                elapsed,
                final_path,
            )
            return final_path

        except (ValueError, RuntimeError, IOError) as exc:
            logger.error(
                "Erreur pipeline image tache %s: %s",
                task_id,
                exc,
            )
            return None

    def _route_generation(
        self,
        visual_type: str,
        niche: str,
        hook: str,
        body_text: str,
        visual_notes: str,
    ) -> Optional[object]:
        """Route la generation vers le module approprie.

        Args:
            visual_type: Type de visuel.
            niche: Niche de contenu.
            hook: Accroche du script.
            body_text: Texte du corps.
            visual_notes: Notes visuelles.

        Returns:
            Image PIL ou chemin de fichier selon le module.
        """
        if visual_type == VISUAL_TYPE_TEXT:
            if not self.text_visual:
                raise RuntimeError("TextVisualGenerator non initialise")
            script_data: Dict[str, Any] = {
                "niche": niche,
                "hook": hook,
                "body_points": [body_text] if body_text else [],
            }
            return self.text_visual.generate(script_data)

        elif visual_type == VISUAL_TYPE_THUMBNAIL:
            if not self.thumbnail:
                raise RuntimeError(
                    "ThumbnailGenerator non disponible (HF_TOKEN ?)"
                )
            prompt = f"{visual_notes} {hook}".strip()[:500]
            image, _elapsed = self.thumbnail.generate(prompt)
            return image

        elif visual_type == VISUAL_TYPE_BACKGROUND:
            if not self.background:
                raise RuntimeError(
                    "BackgroundGenerator non disponible (HF_TOKEN ?)"
                )
            prompt = f"{visual_notes} {niche}".strip()[:500]
            image, _elapsed = self.background.generate(prompt)
            return image

        elif visual_type == VISUAL_TYPE_ILLUSTRATION:
            if not self.illustration:
                raise RuntimeError(
                    "IllustrationGenerator non disponible (HF_TOKEN ?)"
                )
            prompt = f"{visual_notes} {hook}".strip()[:500]
            image, _elapsed = self.illustration.generate(prompt)
            return image

        else:
            raise ValueError(f"Type de visuel inconnu: {visual_type}")

    def get_available_types(self) -> List[str]:
        """Retourne la liste des types de visuels disponibles.

        Returns:
            Liste des noms de types.
        """
        return list(VISUAL_TYPES)

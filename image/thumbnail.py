"""Generateur de miniatures TikTok via SDXL Turbo.

Utilise le modele stabilityai/sdxl-turbo en mode turbo
(num_inference_steps=1, guidance_scale=0.0) pour des generations
ultra-rapides via l'API serverless Hugging Face.
"""

import io
import time
from typing import Optional, Tuple

from huggingface_hub import InferenceClient
from huggingface_hub.utils import HfHubHTTPError

from utils.logger import logger

MODEL_ID = "stabilityai/sdxl-turbo"
DEFAULT_WIDTH = 512
DEFAULT_HEIGHT = 512
HF_TIMEOUT = 60


class ThumbnailGenerator:
    """Generateur de miniatures TikTok via SDXL Turbo.

    Attributes:
        client: Client Hugging Face Inference.
        model_id: Identifiant du modele.
    """

    def __init__(self, hf_token: str, model_id: str = MODEL_ID):
        """Initialise le generateur de miniatures.

        Args:
            hf_token: Token Hugging Face pour l'API Inference.
            model_id: Identifiant du modele (defaut: sdxl-turbo).
        """
        if not hf_token:
            raise ValueError("HF_TOKEN requis pour ThumbnailGenerator")
        self.client = InferenceClient(token=hf_token, timeout=HF_TIMEOUT)
        self.model_id = model_id

    def generate(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ) -> Tuple[str, float]:
        """Genere une miniature a partir d'un prompt texte.

        Utilise le mode turbo (1 step, guidance=0.0) pour une
        generation quasi-instantanee.

        Args:
            prompt: Description de l'image a generer.
            negative_prompt: Prompt negatif (optionnel).
            width: Largeur en pixels.
            height: Hauteur en pixels.

        Returns:
            Tuple (chemin_fichier, temps_generation_en_secondes).

        Raises:
            RuntimeError: Si la generation echoue apres retries.
        """
        start_time = time.time()
        logger.info(
            "Generation thumbnail - modele: %s, prompt: %s...",
            self.model_id,
            prompt[:80],
        )

        full_prompt = (
            f"{prompt}, portrait 9:16 vertical, TikTok format, "
            f"high quality, vibrant colors, social media thumbnail"
        )
        neg = (
            negative_prompt
            or "blurry, low quality, watermark, text, "
            "distorted, ugly, bad anatomy, cropped"
        )

        max_retries = 2
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                image = self.client.text_to_image(
                    prompt=full_prompt,
                    model=self.model_id,
                    negative_prompt=neg,
                    num_inference_steps=1,
                    guidance_scale=0.0,
                    width=width,
                    height=height,
                )

                elapsed = time.time() - start_time
                logger.info(
                    "Thumbnail generee en %.1fs (tentative %d/%d)",
                    elapsed,
                    attempt,
                    max_retries,
                )
                return image, elapsed

            except HfHubHTTPError as exc:
                last_error = exc
                logger.warning(
                    "Erreur API HF thumbnail (tentative %d/%d): %s",
                    attempt,
                    max_retries,
                    exc,
                )
                if attempt < max_retries:
                    wait = attempt * 3
                    logger.info("Nouvelle tentative dans %ds...", wait)
                    time.sleep(wait)

            except Exception as exc:
                last_error = exc
                logger.error(
                    "Erreur generation thumbnail: %s", exc
                )
                raise RuntimeError(
                    f"Echec generation thumbnail: {exc}"
                ) from exc

        raise RuntimeError(
            f"Echec generation thumbnail apres {max_retries} "
            f"tentatives: {last_error}"
        )

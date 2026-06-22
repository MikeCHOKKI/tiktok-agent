"""Generateur de fonds TikTok via Stable Diffusion 2.1.

Utilise le modele stabilityai/stable-diffusion-2-1 avec scheduler
DPM solver pour generer des fonds en ratio 9:16 (768x1366).
"""

import time
from typing import Optional, Tuple

from huggingface_hub import InferenceClient
from huggingface_hub.utils import HfHubHTTPError

from utils.logger import logger

MODEL_ID = "stabilityai/stable-diffusion-2-1"
DEFAULT_WIDTH = 768
DEFAULT_HEIGHT = 1366
HF_TIMEOUT = 60


class BackgroundGenerator:
    """Generateur de fonds TikTok via Stable Diffusion 2.1.

    Attributes:
        client: Client Hugging Face Inference.
        model_id: Identifiant du modele.
    """

    def __init__(self, hf_token: str, model_id: str = MODEL_ID):
        """Initialise le generateur de fonds.

        Args:
            hf_token: Token Hugging Face pour l'API Inference.
            model_id: Identifiant du modele (defaut: SD 2.1).
        """
        if not hf_token:
            raise ValueError("HF_TOKEN requis pour BackgroundGenerator")
        self.client = InferenceClient(token=hf_token, timeout=HF_TIMEOUT)
        self.model_id = model_id

    def generate(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ) -> Tuple[object, float]:
        """Genere un fond d'ecran a partir d'un prompt texte.

        Args:
            prompt: Description du fond a generer.
            negative_prompt: Prompt negatif (optionnel).
            width: Largeur en pixels (defaut: 768).
            height: Hauteur en pixels (defaut: 1366, ratio 9:16).

        Returns:
            Tuple (image_PIL, temps_generation_en_secondes).

        Raises:
            RuntimeError: Si la generation echoue apres retries.
        """
        start_time = time.time()
        logger.info(
            "Generation fond - modele: %s, prompt: %s...",
            self.model_id,
            prompt[:80],
        )

        full_prompt = (
            f"{prompt}, TikTok video background, vertical 9:16 format, "
            f"smooth gradients, soft lighting, professional photography"
        )
        neg = (
            negative_prompt
            or "blurry, low quality, watermark, text, "
            "distorted, ugly, bad anatomy, cropped, frame"
        )

        max_retries = 2
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                image = self.client.text_to_image(
                    prompt=full_prompt,
                    model=self.model_id,
                    negative_prompt=neg,
                    num_inference_steps=20,
                    guidance_scale=7.5,
                    width=width,
                    height=height,
                    scheduler="DPMSolverMultistepScheduler",
                )

                elapsed = time.time() - start_time
                logger.info(
                    "Fond genere en %.1fs (tentative %d/%d)",
                    elapsed,
                    attempt,
                    max_retries,
                )
                return image, elapsed

            except HfHubHTTPError as exc:
                last_error = exc
                logger.warning(
                    "Erreur API HF fond (tentative %d/%d): %s",
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
                    "Erreur generation fond: %s", exc
                )
                raise RuntimeError(
                    f"Echec generation fond: {exc}"
                ) from exc

        raise RuntimeError(
            f"Echec generation fond apres {max_retries} "
            f"tentatives: {last_error}"
        )

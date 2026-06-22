"""Generateur d'illustrations via Kandinsky 2.2.

Utilise le modele kandinsky-community/kandinsky-2-2-decoder
pour generer des illustrations abstraites et conceptuelles
a partir de prompts textes.
"""

import time
from typing import Optional, Tuple

from huggingface_hub import InferenceClient
from huggingface_hub.utils import HfHubHTTPError

from utils.logger import logger

MODEL_ID = "kandinsky-community/kandinsky-2-2-decoder"
DEFAULT_WIDTH = 512
DEFAULT_HEIGHT = 512
HF_TIMEOUT = 60


class IllustrationGenerator:
    """Generateur d'illustrations via Kandinsky 2.2.

    Attributes:
        client: Client Hugging Face Inference.
        model_id: Identifiant du modele.
    """

    def __init__(self, hf_token: str, model_id: str = MODEL_ID):
        """Initialise le generateur d'illustrations.

        Args:
            hf_token: Token Hugging Face pour l'API Inference.
            model_id: Identifiant du modele (defaut: Kandinsky 2.2).
        """
        if not hf_token:
            raise ValueError("HF_TOKEN requis pour IllustrationGenerator")
        self.client = InferenceClient(token=hf_token, timeout=HF_TIMEOUT)
        self.model_id = model_id

    def generate(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ) -> Tuple[object, float]:
        """Genere une illustration a partir d'un prompt texte.

        Args:
            prompt: Description de l'illustration.
            negative_prompt: Prompt negatif (optionnel).
            width: Largeur en pixels (defaut: 512).
            height: Hauteur en pixels (defaut: 512).

        Returns:
            Tuple (image_PIL, temps_generation_en_secondes).

        Raises:
            RuntimeError: Si la generation echoue apres retries.
        """
        start_time = time.time()
        logger.info(
            "Generation illustration - modele: %s, prompt: %s...",
            self.model_id,
            prompt[:80],
        )

        full_prompt = (
            f"{prompt}, digital art, high quality, "
            f"artistic illustration, concept art, vibrant"
        )
        neg = (
            negative_prompt
            or "blurry, low quality, watermark, text, "
            "distorted, ugly, bad anatomy, photograph, realistic"
        )

        max_retries = 2
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                image = self.client.text_to_image(
                    prompt=full_prompt,
                    model=self.model_id,
                    negative_prompt=neg,
                    num_inference_steps=25,
                    guidance_scale=4.0,
                    width=width,
                    height=height,
                )

                elapsed = time.time() - start_time
                logger.info(
                    "Illustration generee en %.1fs (tentative %d/%d)",
                    elapsed,
                    attempt,
                    max_retries,
                )
                return image, elapsed

            except HfHubHTTPError as exc:
                last_error = exc
                logger.warning(
                    "Erreur API HF illustration (tentative %d/%d): %s",
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
                    "Erreur generation illustration: %s", exc
                )
                raise RuntimeError(
                    f"Echec generation illustration: {exc}"
                ) from exc

        raise RuntimeError(
            f"Echec generation illustration apres {max_retries} "
            f"tentatives: {last_error}"
        )

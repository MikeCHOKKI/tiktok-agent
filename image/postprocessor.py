"""Pipeline de post-processing pour les images generees.

Etapes obligatoires :
1. Recadrage 9:16 (1080x1920)
2. Watermark (texte parametrable, bas droite)
3. Optimisation JPEG (< 8MB pour Discord)
4. Gradient sombre optionnel (lisibilite texte)
5. Sauvegarde avec nettoyage automatique
"""

import datetime
import io
import os
import time
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from utils.logger import logger

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
RATIO = TARGET_WIDTH / TARGET_HEIGHT  # 9:16

MAX_FILE_SIZE = 8 * 1024 * 1024  # 8 MB (limite Discord)
INITIAL_JPEG_QUALITY = 90
OUTPUT_DIR = "/tmp/tiktok-agent"
CLEANUP_AGE_HOURS = 2


class PostProcessor:
    """Pipeline de post-processing pour les images generees.

    Applique 5 etapes obligatoires dans l'ordre :
    1. Recadrage au format 9:16
    2. Watermark personnalise
    3. Optimisation JPEG (< 8MB)
    4. Gradient sombre optionnel (bas de l'image)
    5. Sauvegarde et nettoyage
    """

    def __init__(self, watermark_text: str = "@tiktok_agent"):
        """Initialise le post-processeur.

        Args:
            watermark_text: Texte du filigrane.
        """
        self.watermark_text = watermark_text
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        logger.info(
            "PostProcessor initialise (watermark: '%s', max_size: %d MB)",
            watermark_text,
            MAX_FILE_SIZE // (1024 * 1024),
        )

    def process(
        self,
        image: object,
        task_id: str,
        add_gradient: bool = True,
    ) -> str:
        """Execute le pipeline complet de post-processing.

        Args:
            image: Image PIL a traiter (ou chemin de fichier).
            task_id: Identifiant de la tache (pour le nom de fichier).
            add_gradient: Ajouter le gradient sombre en bas (defaut: True).

        Returns:
            Chemin absolu du fichier final.
        """
        start_time = time.time()

        # Chargement si chemin
        if isinstance(image, str):
            img = Image.open(image)
            logger.debug("Image chargee depuis: %s", image)
        else:
            img = image

        logger.info(
            "Post-processing - taille initiale: %dx%d",
            img.width,
            img.height,
        )

        # Etape 1 : Recadrage 9:16
        img = self._crop_to_ratio(img)
        logger.debug("Apres recadrage: %dx%d", img.width, img.height)

        # Verification format final
        if img.width != TARGET_WIDTH or img.height != TARGET_HEIGHT:
            img = img.resize(
                (TARGET_WIDTH, TARGET_HEIGHT), Image.LANCZOS
            )
            logger.debug(
                "Redimensionnement force: %dx%d", TARGET_WIDTH, TARGET_HEIGHT
            )

        # Etape 2 : Watermark
        img = self._add_watermark(img)
        logger.debug("Watermark ajoute")

        # Etape 3 : Gradient sombre optionnel
        if add_gradient:
            img = self._add_dark_gradient(img)
            logger.debug("Gradient sombre ajoute")

        # Etape 4 : Optimisation JPEG
        img_rgb = img.convert("RGB")
        filepath = self._save_optimized(img_rgb, task_id)

        elapsed = time.time() - start_time
        file_size = os.path.getsize(filepath)
        logger.info(
            "Post-processing termine en %.1fs - %s (%d x %d, %.1f MB)",
            elapsed,
            filepath,
            TARGET_WIDTH,
            TARGET_HEIGHT,
            file_size / (1024 * 1024),
        )

        return filepath

    def _crop_to_ratio(self, img: Image.Image) -> Image.Image:
        """Recadre l'image au ratio 9:16 (1080x1920).

        3 cas possibles :
        - Image trop large : recadre les cotes
        - Image trop haute : recadre le haut/bas
        - Image plus petite : rembourrage intelligent (copie du bord)

        Args:
            img: Image PIL a recadrer.

        Returns:
            Image recadree au ratio 9:16.
        """
        target_ratio = RATIO
        current_ratio = img.width / img.height

        if abs(current_ratio - target_ratio) < 0.01:
            return img.resize(
                (TARGET_WIDTH, TARGET_HEIGHT), Image.LANCZOS
            )

        if current_ratio > target_ratio:
            # Trop large : recadrer les cotes
            new_width = int(img.height * target_ratio)
            offset = (img.width - new_width) // 2
            img = img.crop((offset, 0, offset + new_width, img.height))
        else:
            # Trop haute : recadrer le haut/bas
            new_height = int(img.width / target_ratio)
            offset = (img.height - new_height) // 2
            img = img.crop((0, offset, img.width, offset + new_height))

        return img.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.LANCZOS)

    def _add_watermark(self, img: Image.Image) -> Image.Image:
        """Ajoute un filigrane semi-transparent en bas a droite.

        Args:
            img: Image PIL.

        Returns:
            Image avec filigrane.
        """
        overlay = img.copy()
        draw = ImageDraw.Draw(overlay)

        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                24,
            )
        except (OSError, IOError):
            font = ImageFont.load_default()

        # Position : bas droite avec marge de 20px
        bbox = font.getbbox(self.watermark_text)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = TARGET_WIDTH - text_w - 20
        y = TARGET_HEIGHT - text_h - 20

        # Texte blanc semi-transparent
        draw.text((x, y), self.watermark_text, fill=(255, 255, 255, 77), font=font)

        # Fusion avec transparence
        img = Image.blend(img, overlay, 0.3)
        return img

    def _add_dark_gradient(self, img: Image.Image) -> Image.Image:
        """Ajoute une bande sombre degradee en bas de l'image.

        Bande sur 20% de la hauteur, opacite 0 -> 0.6,
        pour ameliorer la lisibilite du texte superpose.

        Args:
            img: Image PIL.

        Returns:
            Image avec gradient sombre.
        """
        gradient_height = int(TARGET_HEIGHT * 0.2)
        overlay = Image.new("RGBA", (TARGET_WIDTH, TARGET_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for i in range(gradient_height):
            y = TARGET_HEIGHT - gradient_height + i
            opacity = int(255 * 0.6 * (i / gradient_height))
            draw.line([(0, y), (TARGET_WIDTH, y)], fill=(0, 0, 0, opacity))

        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay)
        return img.convert("RGB")

    def _save_optimized(
        self,
        img: Image.Image,
        task_id: str,
    ) -> str:
        """Sauvegarde l'image en JPEG avec qualite optimisee.

        Qualite initiale 90%, reduite progressivement jusqu'a
        ce que le fichier soit sous la limite de 8 MB.

        Args:
            img: Image PIL en RGB.
            task_id: Identifiant de la tache.

        Returns:
            Chemin absolu du fichier sauvegarde.
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"img_{task_id}_{timestamp}.jpg"
        filepath = os.path.join(OUTPUT_DIR, filename)

        quality = INITIAL_JPEG_QUALITY
        buffer = io.BytesIO()

        while quality >= 10:
            buffer.seek(0)
            buffer.truncate()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            size = buffer.tell()

            if size <= MAX_FILE_SIZE:
                break
            quality -= 5
            logger.debug(
                "Taille %d MB > 8 MB, baisse qualite a %d%%",
                size // (1024 * 1024),
                quality,
            )

        with open(filepath, "wb") as f:
            f.write(buffer.getvalue())

        final_size = os.path.getsize(filepath)
        if final_size > MAX_FILE_SIZE:
            logger.warning(
                "Image %s depasse 8 MB (%d MB), "
                "qualite minimale atteinte",
                filepath,
                final_size // (1024 * 1024),
            )

        self._cleanup_old_files()
        return filepath

    def _cleanup_old_files(self) -> None:
        """Nettoie les fichiers images de plus de 2 heures.

        Parcourt le repertoire de sortie et supprime les fichiers
        dont l'age depasse CLEANUP_AGE_HOURS.
        """
        now = time.time()
        cutoff = now - (CLEANUP_AGE_HOURS * 3600)
        cleaned = 0

        try:
            for fname in os.listdir(OUTPUT_DIR):
                fpath = os.path.join(OUTPUT_DIR, fname)
                if not fname.startswith("img_") or not os.path.isfile(fpath):
                    continue
                if os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
                    cleaned += 1

            if cleaned:
                logger.info(
                    "Nettoyage: %d fichier(s) supprime(s) de %s",
                    cleaned,
                    OUTPUT_DIR,
                )
        except OSError as exc:
            logger.warning(
                "Erreur nettoyage %s: %s", OUTPUT_DIR, exc
            )

"""Generateur de visuels texte 100% Pillow (sans appel API).

Cree des images de type "texte sur fond" avec gradient, ombres,
et mise en page professionnelle. Utilise les palettes de couleurs
definies par niche dans palettes.py.
"""

import math
import os
from typing import Any, Dict, Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from image.palettes import get_palette
from utils.logger import logger

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_FALLBACK_SIZE = 60


class TextVisualGenerator:
    """Generateur de visuels texte 100% Pillow.

    Cree des images verticales 9:16 (1080x1920) avec :
    - Fond degrade (2 couleurs selon la palette de la niche)
    - Texte principal centre avec ombre portee
    - Sous-titre optionnel
    - Ligne decorative
    - Logo/icone optionnel en haut a gauche
    """

    def __init__(self):
        """Initialise le generateur de visuels texte."""
        self._font_bold = None
        self._font_regular = None
        self._load_fonts()

    def _load_fonts(self) -> None:
        """Charge les polices systeme avec fallback.

        Tente de charger DejaVu Sans (disponible sur la plupart
        des systemes Linux). Fallback sur Police par defaut Pillow.
        """
        try:
            self._font_bold = ImageFont.truetype(
                FONT_BOLD_PATH, FONT_FALLBACK_SIZE
            )
            self._font_regular = ImageFont.truetype(
                FONT_REGULAR_PATH, 50
            )
        except (OSError, IOError):
            logger.warning(
                "Polices DejaVu introuvables, utilisation du defaut"
            )
            self._font_bold = ImageFont.load_default()

    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """Convertit une couleur hexadcimale en tuple RGB.

        Args:
            hex_color: Chaine hexadecimale (ex: "#FF4500").

        Returns:
            Tuple (R, G, B).
        """
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    def _draw_gradient_background(
        self,
        draw: ImageDraw.ImageDraw,
        color_start: str,
        color_end: str,
    ) -> None:
        """Dessine un fond degrade vertical.

        Args:
            draw: Contexte de dessin Pillow.
            color_start: Couleur haute (hex).
            color_end: Couleur basse (hex).
        """
        rgb_start = self._hex_to_rgb(color_start)
        rgb_end = self._hex_to_rgb(color_end)

        for y in range(CANVAS_HEIGHT):
            ratio = y / CANVAS_HEIGHT
            r = int(rgb_start[0] + (rgb_end[0] - rgb_start[0]) * ratio)
            g = int(rgb_start[1] + (rgb_end[1] - rgb_start[1]) * ratio)
            b = int(rgb_start[2] + (rgb_end[2] - rgb_start[2]) * ratio)
            draw.line([(0, y), (CANVAS_WIDTH, y)], fill=(r, g, b))

    def _calculate_font_size(
        self,
        text: str,
        max_width: int,
        max_height: int,
        font_path: str,
    ) -> int:
        """Calcule la taille de police optimale pour que le texte tienne.

        Args:
            text: Texte a mesurer.
            max_width: Largeur maximale en pixels.
            max_height: Hauteur maximale en pixels.
            font_path: Chemin de la police.

        Returns:
            Taille de police en pixels.
        """
        for size in range(120, 39, -2):
            try:
                font = ImageFont.truetype(font_path, size)
                bbox = font.getbbox(text)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                if text_width <= max_width and text_height <= max_height:
                    return size
            except (OSError, IOError):
                return FONT_FALLBACK_SIZE
        return 40

    def _draw_text_with_shadow(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        position: tuple,
        font: ImageFont.FreeTypeFont,
        text_color: str,
        shadow_offset: int = 4,
    ) -> None:
        """Dessine du texte avec une ombre portee.

        Args:
            draw: Contexte de dessin.
            text: Texte a afficher.
            position: Position (x, y) du texte.
            font: Police a utiliser.
            text_color: Couleur du texte (hex).
            shadow_offset: Decalage de l'ombre en pixels.
        """
        rgb_color = self._hex_to_rgb(text_color)
        shadow_color = (0, 0, 0, 80)

        # Ombre portee
        shadow_pos = (position[0] + shadow_offset, position[1] + shadow_offset)
        draw.text(shadow_pos, text, fill=shadow_color, font=font)

        # Texte principal
        draw.text(position, text, fill=rgb_color, font=font)

    def generate(
        self,
        script_data: Dict[str, Any],
        output_dir: str = "/tmp/tiktok-agent",
    ) -> str:
        """Genere un visuel texte a partir des donnees du script.

        Args:
            script_data: Donnees du script (hook, body_points, niche...).
            output_dir: Repertoire de sortie.

        Returns:
            Chemin absolu du fichier image genere.

        Raises:
            ValueError: Si les donnees du script sont invalides.
            IOError: Si l'ecriture du fichier echoue.
        """
        niche = script_data.get("niche", "tech")
        palette = get_palette(niche)

        hook = script_data.get("hook", "Accroche")
        body_points = script_data.get("body_points", [])

        logger.info(
            "Generation visuel texte - niche: %s, hook: %s",
            niche,
            hook[:60],
        )

        # Creation du canvas
        canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT))
        draw = ImageDraw.Draw(canvas)

        # 1. Fond degrade
        colors = palette["colors"]
        self._draw_gradient_background(
            draw, colors[0], colors[1]
        )
        logger.debug("Fond degrade applique: %s -> %s", colors[0], colors[1])

        # 2. Texte principal (hook)
        text_color = palette["text"]
        accent_color = palette["accent"]
        font_bold_path = FONT_BOLD_PATH

        hook_font_size = self._calculate_font_size(
            hook,
            int(CANVAS_WIDTH * 0.85),
            400,
            font_bold_path,
        )
        try:
            hook_font = ImageFont.truetype(font_bold_path, hook_font_size)
        except (OSError, IOError):
            hook_font = ImageFont.load_default()

        # Centrage du hook
        hook_bbox = hook_font.getbbox(hook)
        hook_w = hook_bbox[2] - hook_bbox[0]
        hook_x = (CANVAS_WIDTH - hook_w) // 2
        hook_y = CANVAS_HEIGHT // 2 - 200

        self._draw_text_with_shadow(
            draw, hook, (hook_x, hook_y), hook_font, text_color
        )
        logger.debug(
            "Hook place: taille=%d, pos=(%d, %d)",
            hook_font_size,
            hook_x,
            hook_y,
        )

        # 3. Ligne decorative
        line_y = hook_y + 320
        line_width = 200
        line_x = (CANVAS_WIDTH - line_width) // 2
        accent_rgb = self._hex_to_rgb(accent_color)
        draw.rectangle(
            [line_x, line_y, line_x + line_width, line_y + 4],
            fill=accent_rgb,
        )

        # 4. Sous-titre (body_points resume)
        if body_points:
            subtitle = " | ".join(body_points[:3])
            subtitle = subtitle[:120]

            try:
                subtitle_font = ImageFont.truetype(
                    FONT_REGULAR_PATH, 45
                )
            except (OSError, IOError):
                subtitle_font = ImageFont.load_default()

            subtitle_color = palette.get("text_secondary", "#AAAAAA")
            sub_rgb = self._hex_to_rgb(subtitle_color)
            sub_bbox = subtitle_font.getbbox(subtitle)
            sub_w = sub_bbox[2] - sub_bbox[0]
            sub_x = max(20, (CANVAS_WIDTH - sub_w) // 2)
            sub_y = line_y + 60

            # Ombre legere pour le sous-titre
            draw.text(
                (sub_x + 2, sub_y + 2),
                subtitle,
                fill=(0, 0, 0, 60),
                font=subtitle_font,
            )
            draw.text(
                (sub_x, sub_y),
                subtitle,
                fill=sub_rgb,
                font=subtitle_font,
            )

        # 5. Sauvegarde
        os.makedirs(output_dir, exist_ok=True)

        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        niche_slug = niche.lower().replace(" & ", "_").replace(" ", "_")[:30]
        filename = f"text_visual_{niche_slug}_{timestamp}.jpg"
        filepath = os.path.join(output_dir, filename)

        canvas.save(filepath, "JPEG", quality=95)
        logger.info("Visuel texte sauvegarde: %s", filepath)

        return filepath

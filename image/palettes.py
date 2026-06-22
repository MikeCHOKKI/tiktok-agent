"""Palettes de couleurs predfinies pour la generation de visuels texte.

Chaque palette suit la structure :
{
    "colors": (couleur_debut, couleur_fin),  # Gradient background
    "text": couleur_texte_principal,
    "accent": couleur_accent (ligne, sous-titre, etc.),
    "text_secondary": couleur_secondaire_texte (optionnel)
}
"""

from typing import Any, Dict, Tuple

# Type structure : palette est un dict avec des champs bien definis
Palette = Dict[str, Any]

PALETTES: Dict[str, Palette] = {
    "tech": {
        "colors": ("#0D0D0D", "#1A1A2E"),
        "text": "#FFFFFF",
        "accent": "#4A90D9",
        "text_secondary": "#8899AA",
    },
    "motivation": {
        "colors": ("#FF4500", "#FF8C00"),
        "text": "#FFFFFF",
        "accent": "#FFD700",
        "text_secondary": "#FFD700",
    },
    "sante": {
        "colors": ("#FFFFFF", "#F0F0F0"),
        "text": "#1A1A1A",
        "accent": "#2ECC71",
        "text_secondary": "#555555",
    },
    "mode": {
        "colors": ("#2D1B69", "#534AB7"),
        "text": "#FFFFFF",
        "accent": "#D4C5F9",
        "text_secondary": "#D4C5F9",
    },
    "nature": {
        "colors": ("#064E3B", "#065F46"),
        "text": "#FFFFFF",
        "accent": "#6EE7B7",
        "text_secondary": "#6EE7B7",
    },
    "cuisine": {
        "colors": ("#8B0000", "#CD5C5C"),
        "text": "#FFFFFF",
        "accent": "#FFD700",
        "text_secondary": "#FFE4B5",
    },
    "sport": {
        "colors": ("#1A1A2E", "#16213E"),
        "text": "#FFFFFF",
        "accent": "#E94560",
        "text_secondary": "#BBBBBB",
    },
}

DEFAULT_PALETTE_KEY = "tech"


def get_palette(niche: str) -> Palette:
    """Retourne la palette correspondant a une niche.

    Normalise la cle de niche (lowercase, strip) et cherche une
    correspondance. Si aucune correspondance, retourne la palette par defaut.

    Args:
        niche: Nom de la niche (ex: "Tech & IA", "mode", "cuisine").

    Returns:
        Dictionnaire de palette avec couleurs et styles.
    """
    normalized = niche.lower().strip()
    # Extrait le premier mot significatif
    for sep in [" &", " ", "-"]:
        parts = normalized.split(sep)
        if parts and parts[0]:
            normalized = parts[0]
            break

    for key in PALETTES:
        if key == normalized or key in normalized or normalized in key:
            return PALETTES[key]

    return PALETTES.get(DEFAULT_PALETTE_KEY, PALETTES["tech"])

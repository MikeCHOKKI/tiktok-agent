"""Fonctions utilitaires pour le projet tiktok-agent."""

import datetime
import os
import re
from typing import Optional


def generate_task_id() -> str:
    """Genere un identifiant unique pour une tache.

    Format: task_YYYYMMDD_NNN avec un compteur incrementiel.

    Returns:
        Identifiant de tache au format task_YYYYMMDD_001.
    """
    now = datetime.datetime.now()
    date_part = now.strftime("%Y%m%d")
    return f"task_{date_part}_001"


def format_timestamp(dt: Optional[datetime.datetime] = None) -> str:
    """Formate un timestamp au format ISO 8601.

    Args:
        dt: Datetime a formater. Si None, utilise datetime.now().

    Returns:
        Chaine ISO 8601.
    """
    if dt is None:
        dt = datetime.datetime.now()
    return dt.isoformat()


def format_duration(seconds: float) -> str:
    """Formate une duree en secondes en chaine lisible.

    Args:
        seconds: Duree en secondes.

    Returns:
        Chaine au format 'Xm Ys'.
    """
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def sanitize_filename(name: str) -> str:
    """Supprime les caracteres speciaux d'un nom de fichier.

    Args:
        name: Nom a nettoyer.

    Returns:
        Nom nettoye, sans caracteres speciaux.
    """
    cleaned = re.sub(r'[<>:"/\\|?*]', "", name)
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    cleaned = cleaned[:200]
    return cleaned


def truncate_text(text: str, max_length: int = 100) -> str:
    """Tronque un texte avec '...' si necessaire.

    Args:
        text: Texte a tronquer.
        max_length: Longueur maximale (defaut: 100).

    Returns:
        Texte tronque avec '...' si trop long.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."

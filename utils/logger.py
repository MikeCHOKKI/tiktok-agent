"""Logger structure pour le projet tiktok-agent.

Fournit un logger pre-configure avec format horodate, niveau et module.
Output stdout uniquement (logs Hugging Face Spaces).
"""

import logging
import sys
from typing import Optional


def setup_logger(
    name: str = "tiktok-agent",
    level: Optional[str] = None,
) -> logging.Logger:
    """Cree et configure un logger structure.

    Args:
        name: Nom du logger (par defaut 'tiktok-agent').
        level: Niveau de log (DEBUG, INFO, WARNING, ERROR).
               Si None, lit LOG_LEVEL env ou utilise INFO.

    Returns:
        Logger configure.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    log_level = level or "INFO"
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logger.level)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    return logger


logger = setup_logger()

"""Configuration centralisee du projet tiktok-agent.

Charge les variables d'environnement et fournit une classe Settings
accessible depuis tous les modules.
"""

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Configuration centralisee du bot TikTok Agent.

    Tous les parametres sont charges depuis les variables d'environnement
    avec des valeurs par defaut quand c'est pertinent.
    """

    # --- Tokens obligatoires ---
    HF_TOKEN: str = field(default_factory=lambda: os.getenv("HF_TOKEN", ""))
    DISCORD_BOT_TOKEN: str = field(
        default_factory=lambda: os.getenv("DISCORD_BOT_TOKEN", "")
    )

    # --- Discord IDs obligatoires ---
    DISCORD_GUILD_ID: int = field(
        default_factory=lambda: int(os.getenv("DISCORD_GUILD_ID", "0"))
    )

    # --- IDs des channels Discord ---
    CHANNEL_COMMANDES: int = field(
        default_factory=lambda: int(os.getenv("CHANNEL_COMMANDES", "0"))
    )
    CHANNEL_VALIDATION: int = field(
        default_factory=lambda: int(os.getenv("CHANNEL_VALIDATION", "0"))
    )
    CHANNEL_SCRIPTS: int = field(
        default_factory=lambda: int(os.getenv("CHANNEL_SCRIPTS", "0"))
    )
    CHANNEL_TENDANCES: int = field(
        default_factory=lambda: int(os.getenv("CHANNEL_TENDANCES", "0"))
    )
    CHANNEL_RAPPORTS: int = field(
        default_factory=lambda: int(os.getenv("CHANNEL_RAPPORTS", "0"))
    )
    CHANNEL_CHAT_AGENT: int = field(
        default_factory=lambda: int(os.getenv("CHANNEL_CHAT_AGENT", "0"))
    )

    # --- Parametres de contenu ---
    DEFAULT_NICHE: str = os.getenv("DEFAULT_NICHE", "Tech & IA")
    WATERMARK_TEXT: str = os.getenv("WATERMARK_TEXT", "@tiktok_agent")

    # --- URLs RSS & tendances ---
    GOOGLE_TRENDS_RSS_URL: str = os.getenv(
        "GOOGLE_TRENDS_RSS_URL",
        "https://trends.google.com/trends/trendingsearches/daily/rss?geo=FR",
    )
    FEED_NICHE_URLS: List[str] = field(default_factory=list)
    YOUTUBE_API_KEY: str = field(
        default_factory=lambda: os.getenv("YOUTUBE_API_KEY", "")
    )

    # --- Planification ---
    SCHEDULE_HOURS: List[int] = field(
        default_factory=lambda: [6, 18]
    )
    REMINDER_HOURS: int = int(os.getenv("REMINDER_HOURS", "24"))

    # --- Comportement ---
    AUTO_GENERATE: bool = os.getenv("AUTO_GENERATE", "true").lower() == "true"

    def validate(self) -> None:
        """Valide que tous les parametres obligatoires sont presents.

        Raises:
            ValueError: Si un parametre obligatoire est manquant.
        """
        missing = []
        if not self.HF_TOKEN:
            missing.append("HF_TOKEN")
        if not self.DISCORD_BOT_TOKEN:
            missing.append("DISCORD_BOT_TOKEN")
        if not self.DISCORD_GUILD_ID:
            missing.append("DISCORD_GUILD_ID")

        channel_ids = {
            "CHANNEL_COMMANDES": self.CHANNEL_COMMANDES,
            "CHANNEL_VALIDATION": self.CHANNEL_VALIDATION,
            "CHANNEL_SCRIPTS": self.CHANNEL_SCRIPTS,
            "CHANNEL_TENDANCES": self.CHANNEL_TENDANCES,
            "CHANNEL_RAPPORTS": self.CHANNEL_RAPPORTS,
            "CHANNEL_CHAT_AGENT": self.CHANNEL_CHAT_AGENT,
        }
        for name, value in channel_ids.items():
            if not value:
                missing.append(name)

        if missing:
            raise ValueError(
                "Variables d'environnement manquantes obligatoires : "
                + ", ".join(missing)
                + "\nCreez un fichier .env avec ces valeurs."
            )

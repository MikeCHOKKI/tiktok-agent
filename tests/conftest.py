"""Fixtures partagées pour les tests du tiktok-agent.

Fournit des mocks et données de test réutilisables
par tous les modules de test.
"""

from unittest.mock import MagicMock, patch
from typing import Any, Dict, List

import pytest


@pytest.fixture
def mock_state_store():
    """Fixture pour un StateStore mocké.

    Returns:
        MagicMock simulant StateStore avec état par défaut.
    """
    store = MagicMock()
    store.get_config.return_value = {
        "niche": "Tech & IA",
        "style": "educatif",
        "langue": "fr",
        "schedule_hours": [6, 18],
        "auto_generate": True,
        "watermark_text": "@tiktok_agent",
    }
    store.get_tasks.return_value = []
    store.get_task.return_value = None
    store.get_weekly_stats.return_value = {}
    store.get_cached_trends.return_value = ["Tendance 1", "Tendance 2"]
    return store


@pytest.fixture
def mock_hf_client():
    """Fixture pour un InferenceClient mocké.

    Returns:
        MagicMock simulant InferenceClient avec réponse par défaut.
    """
    with patch("agent.script_generator.InferenceClient") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def sample_script_data() -> Dict[str, Any]:
    """Données de script exemple pour les tests.

    Returns:
        Dict structuré comme un script TikTok généré.
    """
    return {
        "hook": "Cette astuce IA va vous surprendre",
        "transition": "Voici comment ca marche",
        "body_points": [
            "Point principal numero un",
            "Deuxieme point a retenir",
            "Troisieme astuce imparable",
        ],
        "cta": "Like pour plus d astuces",
        "hashtags": ["#IA", "#tech", "#astuce", "#viral", "#TikTok"],
        "description": "Decouvrez cette astuce incroyable",
        "music_suggestion": "Son tendance du moment",
        "visual_notes": "Montage dynamique avec transitions",
    }


@pytest.fixture
def sample_task() -> Dict[str, Any]:
    """Tâche exemple pour les tests.

    Returns:
        Dict structuré comme une tâche de génération.
    """
    return {
        "task_id": "task_20260622_001",
        "subject": "Test sujet",
        "niche": "Tech & IA",
        "style": "educatif",
        "status": "pending",
        "created_at": "2026-06-22T10:00:00",
        "updated_at": "2026-06-22T10:00:00",
        "script_data": None,
        "image_path": None,
        "rejection_reason": None,
        "notes": "",
    }


@pytest.fixture
def mock_settings():
    """Fixture pour un Settings mocké.

    Returns:
        MagicMock simulant Settings avec valeurs par défaut.
    """
    settings = MagicMock()
    settings.HF_TOKEN = "fake_token_for_tests"
    settings.WATERMARK_TEXT = "@test_watermark"
    settings.DISCORD_BOT_TOKEN = "fake_discord_token"
    settings.DISCORD_GUILD_ID = 123456789
    settings.CHANNEL_COMMANDES = 111111
    settings.CHANNEL_VALIDATION = 222222
    settings.CHANNEL_SCRIPTS = 333333
    settings.CHANNEL_TENDANCES = 444444
    settings.CHANNEL_RAPPORTS = 555555
    settings.CHANNEL_CHAT_AGENT = 666666
    settings.DEFAULT_NICHE = "Tech & IA"
    settings.YOUTUBE_API_KEY = ""
    settings.AUTO_GENERATE = True
    settings.GOOGLE_TRENDS_RSS_URL = (
        "https://trends.google.com/trends/trendingsearches/daily/rss?geo=FR"
    )
    settings.FEED_NICHE_URLS = []
    return settings
